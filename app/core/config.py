"""
Application Configuration
Environment-based configuration for development and production
"""
import os
import secrets
from datetime import timedelta
from sqlalchemy.pool import StaticPool


class Config:
    """Base configuration"""
    # Base directory
    BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    DEBUG = False

    # Secret key for session management and CSRF protection
    # Development: auto-generate if missing
    # Production: must be explicitly set via environment variable
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY and os.environ.get('FLASK_ENV') != 'production':
        SECRET_KEY = secrets.token_hex(32)

    # Database configuration (production-grade)
    #
    # PostgreSQL is the only supported database for production scale.
    # Provide DATABASE_URL (e.g. postgresql://user:pass@host:5432/dbname).
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "").strip()
    # Backward compatibility: some platforms still use the old `postgres://` scheme.
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # SQLAlchemy engine tuning (PostgreSQL)
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "300"))
    DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_size": DB_POOL_SIZE,
        "max_overflow": DB_MAX_OVERFLOW,
        "pool_recycle": DB_POOL_RECYCLE,
        "pool_timeout": DB_POOL_TIMEOUT,
        "connect_args": {"connect_timeout": DB_CONNECT_TIMEOUT},
    }

    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in ['true', 'on', '1']

    # File upload configuration
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    STORAGE_BACKEND = os.environ.get('STORAGE_BACKEND', 'local')
    STORAGE_LOCAL_PATH = os.environ.get('STORAGE_LOCAL_PATH') or UPLOAD_FOLDER
    MEDIA_PREFERRED_IMAGE_FORMAT = os.environ.get('MEDIA_PREFERRED_IMAGE_FORMAT', 'webp')
    MEDIA_PREFERRED_VIDEO_FORMAT = os.environ.get('MEDIA_PREFERRED_VIDEO_FORMAT', 'mp4')
    MEDIA_IMAGE_QUALITY = int(os.environ.get('MEDIA_IMAGE_QUALITY', '75'))
    MEDIA_MAX_IMAGE_MB = int(os.environ.get('MEDIA_MAX_IMAGE_MB', '8'))
    MEDIA_MAX_VIDEO_MB = int(os.environ.get('MEDIA_MAX_VIDEO_MB', '64'))
    MEDIA_VIDEO_MAX_BITRATE = int(os.environ.get('MEDIA_VIDEO_MAX_BITRATE', '1200000'))  # bps
    MEDIA_VIDEO_MAX_WIDTH = int(os.environ.get('MEDIA_VIDEO_MAX_WIDTH', '1280'))
    RATE_LIMIT_REQUESTS = int(os.environ.get('RATE_LIMIT_REQUESTS', '300'))
    RATE_LIMIT_WINDOW = int(os.environ.get('RATE_LIMIT_WINDOW', '300'))  # seconds
    WRITE_RATE_LIMIT = os.environ.get('WRITE_RATE_LIMIT', '100 per minute')
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}

    # Caching / Redis
    REDIS_URL = os.environ.get('REDIS_URL') or os.environ.get('CACHE_REDIS_URL')
    CACHE_DEFAULT_TTL = int(os.environ.get('CACHE_DEFAULT_TTL', '300'))
    # Sessions (optional, via Flask-Session)
    SESSION_TYPE = os.environ.get("SESSION_TYPE")  # e.g. "redis"

    # Plug-in modules folder (safe discovery)
    MODULES_FOLDER = os.environ.get('MODULES_FOLDER') or os.path.join(BASE_DIR, 'app', 'modules')

    # External plugins folder (drop-in plugins, not part of core package)
    # Each plugin lives in: PLUGINS_FOLDER/<plugin_id>/
    # and must provide a plugin.py with `register(app)` function.
    PLUGINS_FOLDER = os.environ.get('PLUGINS_FOLDER') or os.path.join(BASE_DIR, 'plugins')
    # Allow/deny lists (comma-separated plugin IDs)
    PLUGINS_ALLOWLIST = os.environ.get('PLUGINS_ALLOWLIST')  # e.g. "hello_world,calendar_ext"
    PLUGINS_BLOCKLIST = os.environ.get('PLUGINS_BLOCKLIST')  # e.g. "broken_plugin"

    # Backup configuration (production: use env var for custom path)
    BACKUP_FOLDER = os.environ.get('BACKUP_FOLDER') or os.path.join(BASE_DIR, 'backups')

    # Logs configuration (production: use env var for custom path)
    LOGS_FOLDER = os.environ.get('LOGS_FOLDER') or os.path.join(BASE_DIR, 'logs')

    # Migrations
    MIGRATIONS_DIR = os.environ.get('MIGRATIONS_DIR') or os.path.join(BASE_DIR, 'migrations')

    # ProxyFix (reverse proxy support)
    USE_PROXYFIX = os.environ.get('USE_PROXYFIX', 'false').lower() in ['true', 'on', '1']
    PROXYFIX_X_FOR = int(os.environ.get('PROXYFIX_X_FOR', '1'))
    PROXYFIX_X_PROTO = int(os.environ.get('PROXYFIX_X_PROTO', '1'))
    PROXYFIX_X_HOST = int(os.environ.get('PROXYFIX_X_HOST', '1'))
    PROXYFIX_X_PORT = int(os.environ.get('PROXYFIX_X_PORT', '1'))
    PROXYFIX_X_PREFIX = int(os.environ.get('PROXYFIX_X_PREFIX', '0'))

    # Email configuration (SMTP)
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'noreply@sonacip.it'

    # SMS configuration (ready for integration)
    SMS_PROVIDER = os.environ.get('SMS_PROVIDER')  # e.g., 'twilio'
    SMS_API_KEY = os.environ.get('SMS_API_KEY')
    SMS_API_SECRET = os.environ.get('SMS_API_SECRET')
    SMS_FROM_NUMBER = os.environ.get('SMS_FROM_NUMBER')

    # Pagination
    POSTS_PER_PAGE = 20
    USERS_PER_PAGE = 30
    EVENTS_PER_PAGE = 15

    # Application name
    APP_NAME = 'SONACIP'

    # Bootstrap admin (used by manage.py seed)
    SUPERADMIN_EMAIL = os.environ.get('SUPERADMIN_EMAIL')
    SUPERADMIN_PASSWORD = os.environ.get('SUPERADMIN_PASSWORD')

    # Stripe (payments)
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    STRIPE_PORTAL_RETURN_URL = os.environ.get('STRIPE_PORTAL_RETURN_URL')

    # Security headers (safe defaults; CSP is off by default because of CDNs)
    SECURITY_HEADERS_ENABLED = os.environ.get('SECURITY_HEADERS_ENABLED', 'true').lower() in ['true', 'on', '1']
    HSTS_ENABLED = os.environ.get('HSTS_ENABLED', 'true').lower() in ['true', 'on', '1']
    HSTS_MAX_AGE = int(os.environ.get('HSTS_MAX_AGE', '31536000'))  # 1 year
    CSP_ENABLED = os.environ.get('CSP_ENABLED', 'false').lower() in ['true', 'on', '1']
    CSP_REPORT_ONLY = os.environ.get('CSP_REPORT_ONLY', 'false').lower() in ['true', 'on', '1']


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = False
    USE_PROXYFIX = False


class ProductionConfig(Config):
    """Production configuration"""
    # PRODUCTION SAFETY: DEBUG must NEVER be True
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'true').lower() in ['true', 'on', '1']
    USE_PROXYFIX = True
    PROPAGATE_EXCEPTIONS = False
    TRAP_HTTP_EXCEPTIONS = False
    TRAP_BAD_REQUEST_ERRORS = False

    @classmethod
    def validate_config(cls):
        """Validate production configuration after app factory has run."""
        if not os.environ.get('SECRET_KEY'):
            raise RuntimeError("SECRET_KEY must be set in production environment")
        uri = (os.environ.get("DATABASE_URL") or "").strip()
        if not uri:
            raise RuntimeError("DATABASE_URL must be set in production")
        if uri.startswith("postgres://"):
            uri = uri.replace("postgres://", "postgresql://", 1)
        if not uri.startswith("postgresql://"):
            raise RuntimeError("DATABASE_URL must be PostgreSQL (postgresql://...)")


class TestingConfig(Config):
    """Testing configuration (used under pytest)."""
    TESTING = True
    DEBUG = False

    # Use in-memory SQLite for isolated tests
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }

    # Avoid CSRF in unit tests
    WTF_CSRF_ENABLED = False

    # Use in-memory rate limit storage
    RATELIMIT_STORAGE_URI = 'memory://'
    SESSION_TYPE = None


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': ProductionConfig
}
