"""
Application Configuration
Environment-based configuration for development and production
"""
import os
from datetime import timedelta

class Config:
    """Base configuration"""
    # Base directory
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # Secret key for session management and CSRF protection
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production-2026'
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'sqlite:///{os.path.join(BASE_DIR, "sonacip.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
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
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}

    # Caching / Redis
    REDIS_URL = os.environ.get('REDIS_URL') or os.environ.get('CACHE_REDIS_URL')
    CACHE_DEFAULT_TTL = int(os.environ.get('CACHE_DEFAULT_TTL', '300'))

    # Plug-in modules folder (safe discovery)
    MODULES_FOLDER = os.environ.get('MODULES_FOLDER') or os.path.join(BASE_DIR, 'app', 'modules')
    
    # Backup configuration
    BACKUP_FOLDER = os.path.join(BASE_DIR, 'backups')
    
    # Logs configuration
    LOGS_FOLDER = os.path.join(BASE_DIR, 'logs')
    
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


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True  # Require HTTPS
    
    # Override with stronger settings in production
    # Warn if SECRET_KEY not set but don't crash during module import
    @classmethod
    def validate_config(cls):
        if not os.environ.get('SECRET_KEY'):
            import warnings
            warnings.warn("SECRET_KEY not set! Using default - CHANGE THIS IN PRODUCTION!")


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
