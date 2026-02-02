"""Application bootstrap utilities and dynamic module loader."""
import importlib
import pkgutil
from typing import Optional

import os
from sqlalchemy import text


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


def verify_database_connectivity(app) -> None:
    """Fail fast if the database is unreachable."""
    from app import db

    try:
        with app.app_context():
            db.session.execute(text('SELECT 1'))
    except Exception as exc:
        app.logger.critical('Database connectivity check failed.', exc_info=True)
        raise RuntimeError('Database is unreachable; aborting startup.') from exc


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
