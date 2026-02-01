"""Application bootstrap utilities and dynamic module loader."""
import importlib
import os
import pkgutil
from typing import Optional

from sqlalchemy import inspect, text


PREFIX_OVERRIDES = {
    'main': None,
    'auth': '/auth',
    'admin': '/admin',
    'social': '/social',
    'events': '/events',
    'notifications': '/notifications',
    'messages': '/messages',
    'backup': '/backup',
    'crm': '/crm',
    'subscription': '/subscription',
    'tasks': '/tasks',
    'analytics': '/analytics',
    'tournaments': '/tournaments',
    'scheduler': None,
}


def ensure_directories(app) -> None:
    """Ensure all required directories exist."""
    storage_root = app.config.get('STORAGE_LOCAL_PATH', app.config.get('UPLOAD_FOLDER', 'uploads'))
    directories = [
        storage_root,
        app.config.get('BACKUP_FOLDER', 'backups'),
        app.config.get('LOGS_FOLDER', 'logs'),
        os.path.join(storage_root, 'avatars'),
        os.path.join(storage_root, 'covers'),
        os.path.join(storage_root, 'posts'),
    ]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def bootstrap_database_if_missing(app) -> None:
    """Create SQLite database only when it does not exist."""
    from app import db

    uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if not uri.startswith('sqlite:///'):
        return

    db_path = uri.replace('sqlite:///', '', 1)
    if db_path == ':memory:':
        return

    if os.path.exists(db_path):
        return

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with app.app_context():
        import app.models  # noqa: F401
        db.create_all()
        app.logger.info('SQLite database initialized at %s', db_path)


def verify_database_connectivity(app) -> None:
    """Fail fast if the database is unreachable."""
    from app import db

    try:
        with app.app_context():
            db.session.execute(text('SELECT 1'))
    except Exception as exc:
        app.logger.critical('Database connectivity check failed.', exc_info=True)
        raise RuntimeError('Database is unreachable; aborting startup.') from exc


def apply_migrations_or_fail(app) -> None:
    """Apply Flask-Migrate upgrades safely and idempotently."""
    from flask_migrate import upgrade
    import fcntl

    migrations_dir = app.config.get('MIGRATIONS_DIR', 'migrations')
    if not os.path.isdir(migrations_dir):
        app.logger.info('Migrations directory not found; skipping auto-migration.')
        return

    lock_path = app.config.get('MIGRATIONS_LOCK_PATH', '/tmp/sonacip_migrations.lock')
    try:
        with open(lock_path, 'w') as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            upgrade(directory=migrations_dir)
            fcntl.flock(lock_file, fcntl.LOCK_UN)
    except Exception as exc:
        app.logger.critical('Database migrations failed; aborting startup.', exc_info=True)
        raise RuntimeError('Database migrations failed; aborting startup.') from exc


def ensure_default_roles(app) -> None:
    """Ensure default roles exist when the Role table is available."""
    from app import db
    from app.models import Role

    with app.app_context():
        inspector = inspect(db.engine)
        if 'role' not in inspector.get_table_names():
            import app.models  # noqa: F401
            db.create_all()
            inspector = inspect(db.engine)
            if 'role' not in inspector.get_table_names():
                app.logger.error('Role table missing; database schema is not initialized.')
                return

        if Role.query.count() > 0:
            return

        required_roles = {
            'super_admin': ("Super Admin", 100, 'Amministratore principale con tutti i permessi'),
            'admin': ("Amministratore", 90, 'Amministratore con permessi completi'),
            'moderator': ("Moderatore", 50, 'Moderatore con permessi di gestione contenuti'),
            'society_admin': ("Admin Società", 45, 'Amministratore società sportiva'),
            'societa': ("Società", 40, 'Società sportiva'),
            'staff': ("Staff", 30, 'Staff tecnico o dirigenziale'),
            'coach': ("Coach", 30, 'Allenatore'),
            'atleta': ("Atleta", 20, 'Atleta registrato'),
            'athlete': ("Athlete", 20, 'Atleta (alias inglese)'),
            'appassionato': ("Appassionato", 10, 'Tifoso o appassionato'),
            'user': ("Utente", 10, 'Utente standard'),
            'guest': ("Ospite", 1, 'Utente ospite con permessi limitati'),
        }

        for name, (display, level, description) in required_roles.items():
            db.session.add(Role(
                name=name,
                display_name=display,
                level=level,
                is_system=True,
                description=description
            ))
        db.session.commit()
        app.logger.info('Default roles created to satisfy role_id integrity.')


def ensure_admin_user(app) -> None:
    """Create default admin user if it does not exist."""
    from app import db
    from app.models import User, Role

    with app.app_context():
        existing = User.query.filter_by(email='admin@example.com').first()
        if existing:
            return

        role = Role.query.filter_by(name='super_admin').first()
        if not role:
            role = Role.query.order_by(Role.level.desc()).first()
        if not role:
            raise RuntimeError('No roles available to create admin user.')

        user = User(
            email='admin@example.com',
            username='admin',
            first_name='Admin',
            last_name='SONACIP',
            is_active=True,
            is_verified=True,
            role_obj=role,
            role_legacy=role.name
        )
        user.set_password('Admin123!')
        db.session.add(user)
        db.session.commit()
        app.logger.info('Default admin user created: admin@example.com')


def discover_and_register_modules(app, strict: bool = False) -> None:
    """Load optional modules and register their blueprints."""
    modules_path = app.config.get('MODULES_FOLDER')
    if not modules_path or not os.path.isdir(modules_path):
        return

    package_import = 'app.modules'
    # `app/modules/*` currently contains shims for core blueprints too.
    # Never attempt to re-register core modules here.
    core_module_names = set(PREFIX_OVERRIDES.keys())
    for _, name, _ in pkgutil.iter_modules([modules_path]):
        if name in core_module_names:
            continue
        module_name = f"{package_import}.{name}"
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            if strict:
                raise
            app.logger.warning(f"Modulo opzionale '{module_name}' non caricato: {exc}")
            continue

        bp = getattr(module, 'bp', None)
        if not bp:
            continue

        url_prefix: Optional[str] = getattr(module, 'url_prefix', None)
        if url_prefix is None:
            url_prefix = PREFIX_OVERRIDES.get(name, f'/{name}')
        if not url_prefix:
            url_prefix = None

        try:
            app.register_blueprint(bp, url_prefix=url_prefix)
        except Exception as exc:
            if strict:
                raise
            app.logger.warning(f"Blueprint '{name}' non registrato: {exc}")


def register_blueprints(app) -> None:
    """Register all application blueprints via auto-discovery."""
    discover_and_register_modules(app)
