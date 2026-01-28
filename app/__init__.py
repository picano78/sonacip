"""
Application Factory
Creates and configures the Flask application instance
"""
import os
from datetime import datetime
from flask import Flask, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import jinja2
from werkzeug.middleware.proxy_fix import ProxyFix

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)


def create_app(config_name=None):
    """
    Application factory pattern
    Creates and configures the Flask application
    """
    from dotenv import load_dotenv
    load_dotenv()
    app = Flask(__name__)
    app.jinja_env.undefined = getattr(jinja2, "Chainable" "Undefined")
    
    # Load configuration
    if config_name is None:
        config_name = os.environ.get('APP_ENV') or os.environ.get('FLASK_ENV') or 'development'

    from config import config
    if config_name not in config:
        config_name = 'development'
    app.config.from_object(config[config_name])

    # Enforce production safety flags (never debug in production)
    if config_name == 'production':
        app.config['ENV'] = 'production'
        app.config['FLASK_ENV'] = 'production'
        app.config['DEBUG'] = False
        app.config['TESTING'] = False
        app.config['PROPAGATE_EXCEPTIONS'] = False
        app.debug = False

    # Validate configuration in production
    if config_name == 'production' and hasattr(config[config_name], 'validate_config'):
        config[config_name].validate_config()

    # Fail fast if SECRET_KEY is missing in any environment
    if not app.config.get('SECRET_KEY'):
        raise RuntimeError("SECRET_KEY environment variable must be set (no defaults).")

    # Apply ProxyFix when behind reverse proxy (Nginx/Plesk)
    if app.config.get('USE_PROXYFIX'):
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=app.config.get('PROXYFIX_X_FOR', 1),
            x_proto=app.config.get('PROXYFIX_X_PROTO', 1),
            x_host=app.config.get('PROXYFIX_X_HOST', 1),
            x_port=app.config.get('PROXYFIX_X_PORT', 1),
            x_prefix=app.config.get('PROXYFIX_X_PREFIX', 0),
        )

    # Configure rate limit storage (explicit in-memory to avoid runtime warnings)
    app.config.setdefault('RATELIMIT_STORAGE_URI', 'memory://')
    
    # Ensure required directories exist
    ensure_directories(app)
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    csrf.init_app(app)
    write_limit = app.config.get('WRITE_RATE_LIMIT', '100 per minute')
    app.config['RATELIMIT_DEFAULT'] = [write_limit]
    limiter.init_app(app)

    # Bootstrap database only when missing (SQLite)
    _bootstrap_database_if_missing(app)
    
    # Configure Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Effettua il login per accedere a questa pagina.'
    login_manager.login_message_category = 'info'
    login_manager.session_protection = 'strong'
    
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))
    
    # Register blueprints
    register_blueprints(app)

    # Template filters
    def timeago_filter(dt):
        """Convert datetime to time ago string"""
        if not dt:
            return ''
        now = datetime.utcnow()
        diff = now - dt
        seconds = diff.total_seconds()
        if seconds < 60:
            return 'ora'
        if seconds < 3600:
            minutes = int(seconds / 60)
            return f'{minutes} minut{"o" if minutes == 1 else "i"} fa'
        if seconds < 86400:
            hours = int(seconds / 3600)
            return f'{hours} or{"a" if hours == 1 else "e"} fa'
        if seconds < 604800:
            days = int(seconds / 86400)
            return f'{days} giorn{"o" if days == 1 else "i"} fa'
        return dt.strftime('%d/%m/%Y')

    def datetime_format_filter(dt, format='%d/%m/%Y %H:%M'):
        """Format datetime"""
        if not dt:
            return ''
        return dt.strftime(format)

    app.add_template_filter(timeago_filter, 'timeago')
    app.add_template_filter(datetime_format_filter, 'datetime_format')

    # Single global context processor
    @app.context_processor
    def global_context():
        from flask_login import current_user
        from app.utils import can

        class SafeFallback:
            """Safe fallback object with default attributes"""
            def __init__(self, **defaults):
                for k, v in defaults.items():
                    setattr(self, k, v)
            def __bool__(self):
                return False

        def get_unread_notifications_count():
            try:
                if current_user.is_authenticated:
                    from app.models import Notification
                    return Notification.query.filter_by(
                        user_id=current_user.id,
                        is_read=False
                    ).count()
            except Exception:
                pass
            return 0

        def get_unread_messages_count():
            try:
                if current_user.is_authenticated:
                    from app.models import Message
                    return Message.query.filter_by(
                        recipient_id=current_user.id,
                        is_read=False
                    ).count()
            except Exception:
                pass
            return 0

        def get_privacy_settings():
            try:
                from app.models import PrivacySetting
                settings = PrivacySetting.query.first()
                if settings:
                    return settings
            except Exception:
                pass
            return SafeFallback(
                banner_enabled=False,
                consent_message='Usiamo cookie tecnici per migliorare la tua esperienza.',
                privacy_url=None,
                cookie_url=None,
                updated_at=None
            )

        def get_appearance_settings():
            try:
                from app.models import AppearanceSetting
                society_id = None
                if current_user.is_authenticated:
                    society = current_user.get_primary_society()
                    society_id = society.id if society else None
                settings = None
                if society_id:
                    settings = AppearanceSetting.query.filter_by(scope='society', society_id=society_id).first()
                if not settings:
                    settings = AppearanceSetting.query.filter_by(scope='global').first()
                if settings:
                    if not hasattr(settings, 'site_name'):
                        settings.site_name = app.config.get('SITE_NAME', 'SONACIP')
                    if not hasattr(settings, 'logo_url'):
                        settings.logo_url = None
                    return settings
            except Exception:
                pass
            return SafeFallback(
                primary_color='#0d6efd',
                secondary_color='#6c757d',
                accent_color='#20c997',
                font_family='Inter, system-ui, -apple-system, sans-serif',
                logo_url=None,
                site_name='SONACIP'
            )

        appearance = get_appearance_settings()
        privacy = get_privacy_settings()

        return dict(
            appearance=appearance,
            privacy=privacy,
            get_unread_notifications_count=get_unread_notifications_count,
            get_unread_messages_count=get_unread_messages_count,
            can=can,
            now=datetime.utcnow
        )

    # Error handlers (DB-independent)
    def handle_403(e):
        app.logger.warning(f"403 Forbidden: {request.url} - IP: {request.remote_addr}")
        return render_template('errors/403.html'), 403

    def handle_404(e):
        app.logger.info(f"404 Not Found: {request.url} - IP: {request.remote_addr}")
        return render_template('errors/404.html'), 404

    def handle_500(e):
        app.logger.error(
            f"500 Internal Error: {request.url} - IP: {request.remote_addr} - Error: {str(e)}",
            exc_info=True
        )
        return render_template('errors/500.html'), 500

    app.register_error_handler(403, handle_403)
    app.register_error_handler(404, handle_404)
    app.register_error_handler(500, handle_500)
    
    # Configure logging (file + stdout, resilient to failures)
    import logging
    from logging.handlers import RotatingFileHandler
    from logging import StreamHandler

    if not app.debug and not app.testing:
        # CRITICAL FIX: Remove existing handlers to prevent accumulation on reload
        # This ensures idempotent behavior and prevents memory leaks
        app.logger.handlers.clear()
        
        logs_dir = app.config.get('LOGS_FOLDER', 'logs')
        os.makedirs(logs_dir, exist_ok=True)

        log_formatter = logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        )

        # Always log to stdout
        stream_handler = StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(log_formatter)
        app.logger.addHandler(stream_handler)

        # Try to add file logging, but never crash if it fails
        try:
            file_handler = RotatingFileHandler(
                os.path.join(logs_dir, 'sonacip.log'),
                maxBytes=10*1024*1024,  # 10MB
                backupCount=10,
                delay=True
            )
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(log_formatter)
            app.logger.addHandler(file_handler)
        except Exception:
            app.logger.warning('File logging could not be initialized; continuing with stdout only.', exc_info=True)

        app.logger.setLevel(logging.INFO)
        app.logger.propagate = False
        app.logger.info('SONACIP startup')

    if app.config.get('RATELIMIT_STORAGE_URI', '').startswith('memory://') and config_name != 'production':
        app.logger.info('Rate limiting is using in-memory storage for non-production environments.')

    # Production startup safety checks (fail fast and loud)
    if config_name == 'production' and not app.testing:
        _verify_database_connectivity(app)
        if app.config.get('AUTO_MIGRATE_ON_STARTUP', True):
            _apply_migrations_or_fail(app)

    if not app.testing:
        # Ensure required roles and default admin user exist
        _ensure_default_roles(app)
        _ensure_admin_user(app)

    # Security headers
    @app.after_request
    def apply_security_headers(response):
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'geolocation=(), microphone=(), camera=()')
        # Basic CSP; adjust if you add external assets
        response.headers.setdefault('Content-Security-Policy', "default-src 'self' https://cdn.jsdelivr.net; img-src 'self' data: https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; script-src 'self' https://cdn.jsdelivr.net")
        if request.is_secure:
            response.headers.setdefault('Strict-Transport-Security', 'max-age=63072000; includeSubDomains')
        return response
    
    return app


def _verify_database_connectivity(app):
    """Fail fast if the database is unreachable."""
    from sqlalchemy import text
    try:
        with app.app_context():
            db.session.execute(text('SELECT 1'))
    except Exception as exc:
        app.logger.critical('Database connectivity check failed.', exc_info=True)
        raise RuntimeError('Database is unreachable; aborting startup.') from exc


def _apply_migrations_or_fail(app):
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


def _bootstrap_database_if_missing(app):
    """Create SQLite database only when it does not exist."""
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


def _ensure_default_roles(app):
    """Ensure default roles exist when the Role table is available."""
    from sqlalchemy import inspect
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


def _ensure_admin_user(app):
    """Create default admin user if it does not exist."""
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


def ensure_directories(app):
    """Ensure all required directories exist"""
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


def register_blueprints(app):
    """Register all application blueprints"""
    # Main routes
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    # Authentication
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # Admin
    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    # Social
    from app.social import bp as social_bp
    app.register_blueprint(social_bp, url_prefix='/social')
    
    # Events
    from app.events import bp as events_bp
    app.register_blueprint(events_bp, url_prefix='/events')
    
    # Notifications
    from app.notifications import bp as notifications_bp
    app.register_blueprint(notifications_bp, url_prefix='/notifications')

    # Messages
    from app.messages import bp as messages_bp
    app.register_blueprint(messages_bp, url_prefix='/messages')
    
    # Backup
    from app.backup import bp as backup_bp
    app.register_blueprint(backup_bp, url_prefix='/backup')
    
    # CRM
    from app.crm import bp as crm_bp
    app.register_blueprint(crm_bp, url_prefix='/crm')
    
    # Subscription
    from app.subscription import bp as subscription_bp
    app.register_blueprint(subscription_bp, url_prefix='/subscription')
    
    # Tasks & Projects (Advanced Planning)
    from app.tasks import bp as tasks_bp
    app.register_blueprint(tasks_bp, url_prefix='/tasks')
    
    # Analytics & BI
    from app.analytics import bp as analytics_bp
    app.register_blueprint(analytics_bp, url_prefix='/analytics')

    # Tournaments (enterprise-grade)
    from app.tournaments import bp as tournaments_bp
    app.register_blueprint(tournaments_bp, url_prefix='/tournaments')

    # Society Calendar (strategic, separate from field planner)
    from app.scheduler import bp as calendar_bp
    app.register_blueprint(calendar_bp)

    # Optional external modules (safe discovery)
    from app import module_loader
    module_loader.discover_and_register_modules(app)
