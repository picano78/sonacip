"""Application Factory
Creates and configures the Flask application instance
"""
import os
from datetime import datetime

import jinja2
from dotenv import load_dotenv
from flask import Flask, request, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from app.core.config import config
from app.core.extensions import db, migrate, login_manager, mail, csrf, limiter
from app.core.bootstrap import (
    ensure_directories,
    bootstrap_database_if_missing,
    register_blueprints,
    verify_database_connectivity,
    apply_migrations_or_fail,
    ensure_default_roles,
    ensure_admin_user,
)


def create_app(config_name=None):
    """
    Application factory pattern
    Creates and configures the Flask application
    """
    load_dotenv()
    app = Flask(__name__)
    app.jinja_env.undefined = getattr(jinja2, 'ChainableUndefined', jinja2.Undefined)

    if config_name is None:
        config_name = os.environ.get('APP_ENV') or os.environ.get('FLASK_ENV') or 'development'

    if config_name not in config:
        config_name = 'development'
    app.config.from_object(config[config_name])

    if config_name == 'production':
        app.config['ENV'] = 'production'
        app.config['FLASK_ENV'] = 'production'
        app.config['DEBUG'] = False
        app.config['TESTING'] = False
        app.config['PROPAGATE_EXCEPTIONS'] = False
        app.debug = False

    if config_name == 'production' and hasattr(config[config_name], 'validate_config'):
        config[config_name].validate_config()

    if not app.config.get('SECRET_KEY'):
        if config_name == 'production':
            raise RuntimeError('SECRET_KEY environment variable must be set in production.')
        app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or os.urandom(32)

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

    ensure_directories(app)

    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    csrf.init_app(app)
    write_limit = app.config.get('WRITE_RATE_LIMIT', '100 per minute')
    app.config['RATELIMIT_DEFAULT'] = [write_limit]
    limiter.init_app(app)

    bootstrap_database_if_missing(app)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Effettua il login per accedere a questa pagina.'
    login_manager.login_message_category = 'info'
    login_manager.session_protection = 'strong'

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))

    register_blueprints(app)

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

    import logging
    from logging.handlers import RotatingFileHandler
    from logging import StreamHandler

    if not app.debug and not app.testing:
        app.logger.handlers.clear()

        logs_dir = app.config.get('LOGS_FOLDER', 'logs')
        os.makedirs(logs_dir, exist_ok=True)

        log_formatter = logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        )

        stream_handler = StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(log_formatter)
        app.logger.addHandler(stream_handler)

        try:
            file_handler = RotatingFileHandler(
                os.path.join(logs_dir, 'sonacip.log'),
                maxBytes=10 * 1024 * 1024,
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

    if config_name == 'production' and not app.testing:
        verify_database_connectivity(app)
        if app.config.get('AUTO_MIGRATE_ON_STARTUP', True):
            apply_migrations_or_fail(app)

    if not app.testing:
        ensure_default_roles(app)
        ensure_admin_user(app)

    @app.after_request
    def apply_security_headers(response):
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'geolocation=(), microphone=(), camera=()')
        response.headers.setdefault(
            'Content-Security-Policy',
            "default-src 'self' https://cdn.jsdelivr.net; img-src 'self' data: https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; script-src 'self' https://cdn.jsdelivr.net"
        )
        if request.is_secure:
            response.headers.setdefault('Strict-Transport-Security', 'max-age=63072000; includeSubDomains')
        return response

    return app
