"""SONACIP application factory and shared extensions."""
from __future__ import annotations

import importlib
import os
import traceback

from flask import Flask
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from app.core.config import config

# Single source of truth for extensions
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)

# Explicit core module list (ordered, stable)
CORE_MODULES = [
    'main',
    'auth',
    'admin',
    'crm',
    'events',
    'social',
    'backup',
    'notifications',
    'analytics',
    'messages',
    'tournaments',
    'tasks',
    'scheduler',
    'subscription',
]


def _safe_register_blueprints(app: Flask, modules: list[str] | None = None) -> None:
    if modules is None:
        modules = CORE_MODULES

    for module_name in modules:
        try:
            try:
                routes_module = importlib.import_module(f'app.{module_name}.routes')
            except Exception:
                routes_module = importlib.import_module(f'app.{module_name}')

            blueprint = getattr(routes_module, 'bp', None)
            if blueprint is None:
                app.logger.warning(
                    "[SONACIP] Blueprint 'bp' non trovato in app.%s", module_name
                )
                continue

            app.register_blueprint(blueprint)
        except Exception:
            app.logger.warning(
                "[SONACIP] Caricamento modulo app.%s fallito; modulo ignorato.\n%s",
                module_name,
                traceback.format_exc(),
            )


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)

    if config_name is None:
        config_name = os.environ.get('APP_ENV') or os.environ.get('FLASK_ENV') or 'development'

    if config_name not in config:
        config_name = 'development'

    app.config.from_object(config[config_name])

    if not app.config.get('SECRET_KEY'):
        print('[SONACIP] WARNING: SECRET_KEY missing, using a random key for this process.')
        app.config['SECRET_KEY'] = os.urandom(32)

    if app.config.get('USE_PROXYFIX'):
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=app.config.get('PROXYFIX_X_FOR', 1),
            x_proto=app.config.get('PROXYFIX_X_PROTO', 1),
            x_host=app.config.get('PROXYFIX_X_HOST', 1),
            x_port=app.config.get('PROXYFIX_X_PORT', 1),
            x_prefix=app.config.get('PROXYFIX_X_PREFIX', 0),
        )

    app.config.setdefault('RATELIMIT_STORAGE_URI', 'memory://')

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        try:
            from app.models import User
            return User.query.get(int(user_id))
        except Exception:
            return None

    @app.route('/')
    def base_health():
        return 'SONACIP ONLINE'

    try:
        _safe_register_blueprints(app)
    except Exception:
        app.logger.warning(
            "[SONACIP] Registrazione blueprint fallita; avvio in modalità safe.\n%s",
            traceback.format_exc(),
        )

    # Optional modules loader (plugins in app/modules)
    try:
        from app.core.bootstrap import discover_and_register_modules
        discover_and_register_modules(app)
    except Exception:
        app.logger.warning(
            "[SONACIP] Moduli opzionali non caricati; avvio in modalità safe.\n%s",
            traceback.format_exc(),
        )

    return app
