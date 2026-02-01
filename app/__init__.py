"""SONACIP application factory and shared extensions."""
from __future__ import annotations

import importlib
import os

from flask import Flask, request, session
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from authlib.integrations.flask_client import OAuth

from app.core.config import config

# Single source of truth for extensions
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)
oauth = OAuth()

# Explicit core module list (ordered, stable)
CORE_MODULES = [
    'main',
    'auth',
    'admin',
    'ads',
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
    'marketplace',
]


def _register_blueprints(app: Flask, modules: list[str] | None = None) -> None:
    if modules is None:
        modules = CORE_MODULES

    for module_name in modules:
        try:
            routes_module = importlib.import_module(f'app.{module_name}.routes')
        except ModuleNotFoundError as exc:
            if exc.name != f'app.{module_name}.routes':
                raise
            routes_module = importlib.import_module(f'app.{module_name}')

        blueprint = getattr(routes_module, 'bp', None)
        if blueprint is None:
            raise RuntimeError(
                f"Blueprint 'bp' non trovato in app.{module_name}.routes"
            )

        app.register_blueprint(blueprint)


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)

    if config_name is None:
        config_name = os.environ.get('APP_ENV') or os.environ.get('FLASK_ENV') or 'development'

    if config_name not in config:
        config_name = 'development'

    config_class = config[config_name]
    app.config.from_object(config_class)

    if hasattr(config_class, 'validate_config'):
        config_class.validate_config()

    if not app.config.get('SECRET_KEY'):
        raise RuntimeError(
            "Missing SECRET_KEY. Set SECRET_KEY in the environment (see .env.example)."
        )

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
    oauth.init_app(app)

    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        try:
            from app.models import User
            return User.query.get(int(user_id))
        except Exception:
            return None

    from app.core.bootstrap import discover_and_register_modules

    _register_blueprints(app)
    discover_and_register_modules(app, strict=False)

    @app.context_processor
    def inject_platform_context():
        """Globals used by base templates (theme, privacy, counts, per-page content)."""
        from flask_login import current_user

        from app.utils import can as can_fn, get_active_society_id

        appearance = None
        privacy = None
        site = None
        page = None
        nav_links = None
        society_scopes = []
        active_society = None
        active_society_id = None

        try:
            from app.models import (
                AppearanceSetting,
                CustomizationKV,
                Message,
                Notification,
                PageCustomization,
                PrivacySetting,
                SiteCustomization,
            )

            appearance = AppearanceSetting.query.filter_by(scope='global').order_by(AppearanceSetting.id.desc()).first()
            privacy = PrivacySetting.query.order_by(PrivacySetting.id.desc()).first()
            site = SiteCustomization.query.order_by(SiteCustomization.id.desc()).first()

            endpoint = request.endpoint or ''
            if endpoint:
                page = PageCustomization.query.filter_by(slug=endpoint).first()

            # Admin-configurable navigation links (site scope)
            nav_row = CustomizationKV.query.filter_by(scope='site', scope_key=None, key='navbar.links').first()
            nav_links = nav_row.get_value(default=None) if nav_row else None

            def get_unread_notifications_count():
                if not current_user.is_authenticated:
                    return 0
                return Notification.query.filter_by(user_id=current_user.id, is_read=False).count()

            def get_unread_messages_count():
                if not current_user.is_authenticated:
                    return 0
                return Message.query.filter_by(recipient_id=current_user.id, is_read=False).count()

            # Society scope switcher (when user has multiple memberships)
            try:
                from app.models import SocietyMembership, Society

                if current_user.is_authenticated:
                    scopes = []
                    # Society users own their society profile
                    if current_user.is_society() and getattr(current_user, "society_profile", None):
                        scopes.append(current_user.society_profile)
                    # Membership-based scopes
                    ms = SocietyMembership.query.filter_by(user_id=current_user.id, status='active').all()
                    for m in ms:
                        if m.society:
                            scopes.append(m.society)
                    # Deduplicate by id
                    uniq = {}
                    for s in scopes:
                        try:
                            uniq[int(s.id)] = s
                        except Exception:
                            continue
                    society_scopes = list(uniq.values())
                    active_society_id = get_active_society_id(current_user)
                    if active_society_id:
                        active_society = uniq.get(int(active_society_id)) or Society.query.get(int(active_society_id))
            except Exception:
                society_scopes = []
                active_society = None
                active_society_id = None

        except Exception:
            # DB not initialized yet or models unavailable: keep templates functional.
            def get_unread_notifications_count():
                return 0

            def get_unread_messages_count():
                return 0

        return {
            'can': can_fn,
            'appearance': appearance,
            'privacy': privacy,
            'site': site,
            'page': page,
            'nav_links': nav_links,
            'society_scopes': society_scopes,
            'active_society': active_society,
            'active_society_id': active_society_id,
            'get_unread_notifications_count': get_unread_notifications_count,
            'get_unread_messages_count': get_unread_messages_count,
        }

    return app
