"""
Application Factory
Creates and configures the Flask application instance
"""
import os
from datetime import datetime
import time
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

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
    app = Flask(__name__)
    
    # Load configuration
    if config_name is None:
        config_name = os.environ.get('APP_ENV') or os.environ.get('FLASK_ENV') or 'production'
    
    from config import config
    if config_name not in config:
        config_name = 'production'
    app.config.from_object(config[config_name])
    
    # Validate configuration in production
    if config_name in ['production', 'ProductionConfig']:
        config[config_name].validate_config()

    # Configure rate limit storage (Redis recommended in production)
    storage_uri = app.config.get('RATELIMIT_STORAGE_URI') or app.config.get('REDIS_URL')
    if storage_uri:
        app.config['RATELIMIT_STORAGE_URI'] = storage_uri
    else:
        app.config['RATELIMIT_STORAGE_URI'] = 'memory://'
    
    # Ensure required directories exist
    ensure_directories(app)
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    csrf.init_app(app)
    write_limit = app.config.get('WRITE_RATE_LIMIT', '100 per minute')
    limiter.default_limits = [write_limit]
    limiter.init_app(app)
    
    # Configure Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Effettua il login per accedere a questa pagina.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register template filters and context processors
    register_template_utilities(app)
    
    # Configure logging
    import logging
    from logging.handlers import RotatingFileHandler
    
    if not app.debug and not app.testing:
        # Create logs directory if it doesn't exist
        logs_dir = app.config['LOGS_FOLDER']
        os.makedirs(logs_dir, exist_ok=True)
        
        # Set up file handler
        file_handler = RotatingFileHandler(
            os.path.join(logs_dir, 'sonacip.log'),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=10
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        
        # Add handler to app logger
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('SONACIP startup')

    if app.config.get('RATELIMIT_STORAGE_URI', '').startswith('memory://'):
        app.logger.warning('Rate limiting is using in-memory storage; configure REDIS_URL/RATELIMIT_STORAGE_URI for production.')

    # Create database tables if they don't exist and run bootstrap (idempotent)
    with app.app_context():
        db.create_all()
        ensure_schema_columns()
        bootstrap_system(app)

    # Lightweight auto-backup check on each request (once per hour max)
    from app.backup.utils import run_scheduled_backup_if_due
    @app.before_request
    def auto_backup_middleware():
        now = datetime.utcnow()
        last_check = app.config.get('_AUTO_BACKUP_LAST_CHECK')
        if last_check and (now - last_check).total_seconds() < 3600:
            return None
        run_scheduled_backup_if_due(now)
        app.config['_AUTO_BACKUP_LAST_CHECK'] = now

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


def ensure_directories(app):
    """Ensure all required directories exist"""
    storage_root = app.config.get('STORAGE_LOCAL_PATH', app.config['UPLOAD_FOLDER'])
    directories = [
        storage_root,
        app.config['BACKUP_FOLDER'],
        app.config['LOGS_FOLDER'],
        os.path.join(storage_root, 'avatars'),
        os.path.join(storage_root, 'covers'),
        os.path.join(storage_root, 'posts'),
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def ensure_schema_columns():
    """Ensure legacy databases have required columns (lightweight patch)."""
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)

    def add_column_if_missing(table: str, column: str, ddl: str):
        cols = [c['name'] for c in inspector.get_columns(table)]
        if column not in cols:
            db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))

    # User: role_id was added in newer schema
    try:
        add_column_if_missing('user', 'role_id', 'INTEGER')
        add_column_if_missing('user', 'role', "VARCHAR(50) DEFAULT 'appassionato'")
    except Exception:
        db.session.rollback()

    # StorageSetting new governance fields
    try:
        add_column_if_missing('storage_setting', 'video_bitrate', 'INTEGER DEFAULT 1200000')
        add_column_if_missing('storage_setting', 'video_max_width', 'INTEGER DEFAULT 1280')
        add_column_if_missing('storage_setting', 'max_image_mb', 'INTEGER DEFAULT 8')
        add_column_if_missing('storage_setting', 'max_video_mb', 'INTEGER DEFAULT 64')
    except Exception:
        db.session.rollback()

    # AutomationRule retry controls
    try:
        add_column_if_missing('automation_rule', 'max_retries', 'INTEGER DEFAULT 3')
        add_column_if_missing('automation_rule', 'retry_delay', 'INTEGER DEFAULT 60')
    except Exception:
        db.session.rollback()

    # AutomationRun retry tracking
    try:
        add_column_if_missing('automation_run', 'retry_count', 'INTEGER DEFAULT 0')
        add_column_if_missing('automation_run', 'next_retry_at', 'DATETIME')
        add_column_if_missing('automation_run', 'completed_at', 'DATETIME')
    except Exception:
        db.session.rollback()

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


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
    from app.calendar import bp as calendar_bp
    app.register_blueprint(calendar_bp)

    # Optional external modules (safe discovery)
    from app import module_loader
    module_loader.discover_and_register_modules(app)


def register_error_handlers(app):
    """Register error handlers"""
    from flask import render_template
    from flask_login import current_user
    
    @app.errorhandler(403)
    def forbidden(e):
        app.logger.warning(f"403 Forbidden: {request.url} - User: {current_user.id if current_user.is_authenticated else 'Anonymous'} - IP: {request.remote_addr}")
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def not_found(e):
        app.logger.info(f"404 Not Found: {request.url} - User: {current_user.id if current_user.is_authenticated else 'Anonymous'} - IP: {request.remote_addr}")
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(e):
        app.logger.error(f"500 Internal Error: {request.url} - User: {current_user.id if current_user.is_authenticated else 'Anonymous'} - IP: {request.remote_addr} - Error: {str(e)}", exc_info=True)
        db.session.rollback()
        return render_template('errors/500.html'), 500


def register_template_utilities(app):
    """Register template filters and context processors"""
    from datetime import datetime
    
    @app.template_filter('timeago')
    def timeago_filter(dt):
        """Convert datetime to time ago string"""
        if not dt:
            return ''
        
        now = datetime.utcnow()
        diff = now - dt
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return 'ora'
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f'{minutes} minut{"o" if minutes == 1 else "i"} fa'
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f'{hours} or{"a" if hours == 1 else "e"} fa'
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f'{days} giorn{"o" if days == 1 else "i"} fa'
        else:
            return dt.strftime('%d/%m/%Y')
    
    @app.template_filter('datetime_format')
    def datetime_format_filter(dt, format='%d/%m/%Y %H:%M'):
        """Format datetime"""
        if not dt:
            return ''
        return dt.strftime(format)
    
    @app.context_processor
    def utility_processor():
        """Add utility functions to template context"""
        from flask_login import current_user
        from app.models import PrivacySetting
        from app.utils import can
        
        def get_unread_notifications_count():
            """Get count of unread notifications for current user"""
            if current_user.is_authenticated:
                from app.models import Notification
                return Notification.query.filter_by(
                    user_id=current_user.id, 
                    is_read=False
                ).count()
            return 0

        def get_privacy_settings():
            """Return privacy banner settings with safe defaults"""
            settings = PrivacySetting.query.first()
            if not settings:
                settings = PrivacySetting()
            return settings

        def get_unread_messages_count():
            """Get count of unread direct messages for current user"""
            if current_user.is_authenticated:
                from app.models import Message
                return Message.query.filter_by(recipient_id=current_user.id, is_read=False).count()
            return 0

        def get_social_settings():
            from app.models import SocialSetting
            settings = SocialSetting.query.first()
            if not settings:
                settings = SocialSetting(feed_enabled=True)
                db.session.add(settings)
                db.session.commit()
            return settings

        def get_appearance_settings():
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
            if not settings:
                settings = AppearanceSetting()
                db.session.add(settings)
                db.session.commit()
            return settings
        
        return dict(
            get_unread_notifications_count=get_unread_notifications_count,
            get_unread_messages_count=get_unread_messages_count,
            get_privacy_settings=get_privacy_settings,
            get_social_settings=get_social_settings,
            get_appearance_settings=get_appearance_settings,
            can=can,
            now=datetime.utcnow
        )


def bootstrap_system(app=None):
    """Deterministic bootstrap: roles, permissions, plans, super admin."""
    from app.models import User, Role, Permission, Plan, SocialSetting, AppearanceSetting
    from flask import current_app
    import secrets
    
    logger = current_app.logger if current_app else None

    if app and app.config.get('_BOOTSTRAP_DONE'):
        return

    init_roles()
    init_permissions()
    init_plans()

    # Governance defaults
    if not SocialSetting.query.first():
        db.session.add(SocialSetting())
        db.session.commit()
    if not AppearanceSetting.query.filter_by(scope='global').first():
        db.session.add(AppearanceSetting(scope='global'))
        db.session.commit()

    # Sync legacy role column to role_id when missing
    try:
        users_missing_role = User.query.filter(User.role_id.is_(None)).all()
        if users_missing_role:
            for user in users_missing_role:
                legacy_name = getattr(user, 'role_legacy', None) or 'appassionato'
                role_obj = Role.query.filter_by(name=legacy_name).first() or Role.query.filter_by(name='appassionato').first()
                if role_obj:
                    user.role_obj = role_obj
            db.session.commit()
    except Exception:
        db.session.rollback()

    # Create super admin only when missing
    admin = User.query.join(Role, User.role_id == Role.id).filter(Role.name == 'super_admin').first()
    if not admin:
        super_admin_role = Role.query.filter_by(name='super_admin').first()
        admin_password = os.environ.get('SUPERADMIN_PASSWORD') or secrets.token_urlsafe(16)
        admin = User(
            email='admin@sonacip.it',
            username='admin',
            first_name='Super',
            last_name='Admin',
            role='super_admin',
            role_obj=super_admin_role,
            is_active=True,
            is_verified=True
        )
        admin.set_password(admin_password)
        db.session.add(admin)
        db.session.commit()
        if logger:
            logger.warning('Bootstrap: Super Admin created (admin@sonacip.it); set SUPERADMIN_PASSWORD or rotate immediately.')
            logger.warning(f'Bootstrap: Initial super admin password: {admin_password}')

    # Log bootstrap execution on empty DB
    try:
        if User.query.count() == 1 and Role.query.count() > 0 and Permission.query.count() > 0 and Plan.query.count() > 0:
            if logger:
                logger.info('Bootstrap: base roles, permissions, plans initialized')
    except Exception:
        pass

    if app:
        app.config['_BOOTSTRAP_DONE'] = True


def init_roles():
    """Initialize base roles"""
    from app.models import Role
    
    base_roles = [
        {
            'name': 'super_admin',
            'display_name': 'Super Amministratore',
            'description': 'Accesso completo a tutte le funzionalità del sistema',
            'level': 100,
            'is_system': True
        },
        {
            'name': 'society_admin',
            'display_name': 'Admin Società',
            'description': 'Gestione amministrativa della società sportiva',
            'level': 80,
            'is_system': True
        },
        {
            'name': 'societa',
            'display_name': 'Società Sportiva',
            'description': 'Gestione completa della propria società',
            'level': 50,
            'is_system': True
        },
        {
            'name': 'staff',
            'display_name': 'Staff',
            'description': 'Membro dello staff di una società',
            'level': 30,
            'is_system': True
        },
        {
            'name': 'coach',
            'display_name': 'Coach',
            'description': 'Allenatore affiliato a una società',
            'level': 35,
            'is_system': True
        },
        {
            'name': 'atleta',
            'display_name': 'Atleta',
            'description': 'Atleta affiliato a una società',
            'level': 20,
            'is_system': True
        },
        {
            'name': 'athlete',
            'display_name': 'Athlete',
            'description': 'Atleta (alias inglese)',
            'level': 20,
            'is_system': True
        },
        {
            'name': 'appassionato',
            'display_name': 'Appassionato',
            'description': 'Utente base della piattaforma',
            'level': 10,
            'is_system': True
        }
    ]
    
    for role_data in base_roles:
        existing = Role.query.filter_by(name=role_data['name']).first()
        if not existing:
            role = Role(**role_data)
            db.session.add(role)
    
    db.session.commit()


def init_permissions():
    """Initialize base permissions"""
    from app.models import Permission, Role
    
    base_permissions = [
        # User management
        {'name': 'users_view_all', 'resource': 'users', 'action': 'view_all', 'description': 'Visualizzare tutti gli utenti'},
        {'name': 'users_create', 'resource': 'users', 'action': 'create', 'description': 'Creare nuovi utenti'},
        {'name': 'users_edit', 'resource': 'users', 'action': 'edit', 'description': 'Modificare utenti'},
        {'name': 'users_delete', 'resource': 'users', 'action': 'delete', 'description': 'Eliminare utenti'},
        
        # Society management
        {'name': 'society_manage', 'resource': 'society', 'action': 'manage', 'description': 'Gestire la propria società'},
        {'name': 'society_manage_staff', 'resource': 'society', 'action': 'manage_staff', 'description': 'Gestire lo staff'},
        {'name': 'society_manage_athletes', 'resource': 'society', 'action': 'manage_athletes', 'description': 'Gestire gli atleti'},
        
        # Events
        {'name': 'events_create', 'resource': 'events', 'action': 'create', 'description': 'Creare eventi'},
        {'name': 'events_manage', 'resource': 'events', 'action': 'manage', 'description': 'Gestire eventi'},
        {'name': 'events_view', 'resource': 'events', 'action': 'view', 'description': 'Visualizzare eventi'},
        
        # CRM
        {'name': 'crm_access', 'resource': 'crm', 'action': 'access', 'description': 'Accedere al CRM'},
        {'name': 'crm_manage', 'resource': 'crm', 'action': 'manage', 'description': 'Gestire contatti e opportunità'},
        
        # Social
        {'name': 'social_post', 'resource': 'social', 'action': 'post', 'description': 'Pubblicare post'},
        {'name': 'social_comment', 'resource': 'social', 'action': 'comment', 'description': 'Commentare'},
        
        # Admin
        {'name': 'admin_access', 'resource': 'admin', 'action': 'access', 'description': 'Accedere al pannello admin'},
        {'name': 'admin_logs', 'resource': 'admin', 'action': 'logs', 'description': 'Visualizzare i log'},
        {'name': 'admin_backup', 'resource': 'admin', 'action': 'backup', 'description': 'Gestire i backup'},

        # Analytics
        {'name': 'analytics_access', 'resource': 'analytics', 'action': 'access', 'description': 'Accedere alle analytics'},

        # Tasks/Projects
        {'name': 'tasks_manage', 'resource': 'tasks', 'action': 'manage', 'description': 'Gestire task e progetti'},

        # Tournaments
        {'name': 'tournaments_view', 'resource': 'tournaments', 'action': 'view', 'description': 'Visualizzare tornei'},
        {'name': 'tournaments_manage', 'resource': 'tournaments', 'action': 'manage', 'description': 'Gestire tornei'},

        # Society Calendar
        {'name': 'calendar_view', 'resource': 'calendar', 'action': 'view', 'description': 'Visualizzare calendario società'},
        {'name': 'calendar_manage', 'resource': 'calendar', 'action': 'manage', 'description': 'Gestire calendario società'},
    ]
    
    for perm_data in base_permissions:
        existing = Permission.query.filter_by(name=perm_data['name']).first()
        if not existing:
            perm = Permission(**perm_data)
            db.session.add(perm)
    
    db.session.commit()
    
    # Assign permissions to super_admin role
    super_admin_role = Role.query.filter_by(name='super_admin').first()
    if super_admin_role:
        all_perms = Permission.query.all()
        for perm in all_perms:
            if perm not in super_admin_role.permissions:
                super_admin_role.permissions.append(perm)
        db.session.commit()

    # Give society administrators ownership permissions
    society_admin_role = Role.query.filter_by(name='society_admin').first()
    if society_admin_role:
        default_perm_names = [
            'society_manage',
            'society_manage_staff',
            'society_manage_athletes',
            'events_create',
            'events_manage',
            'events_view',
            'crm_access',
            'crm_manage',
            'social_post',
            'social_comment',
            'analytics_access',
            'tasks_manage',
            'tournaments_view',
            'tournaments_manage',
            'calendar_view',
            'calendar_manage'
        ]
        perms = Permission.query.filter(Permission.name.in_(default_perm_names)).all()
        for perm in perms:
            if perm not in society_admin_role.permissions:
                society_admin_role.permissions.append(perm)
        db.session.commit()

    # Give staff/coaches limited permissions
    staff_role = Role.query.filter_by(name='staff').first()
    if staff_role:
        staff_perm_names = [
            'events_view',
            'events_create',
            'crm_access',
            'crm_manage',
            'social_post',
            'social_comment',
            'tasks_manage',
            'tournaments_view',
            'calendar_view'
        ]
        perms = Permission.query.filter(Permission.name.in_(staff_perm_names)).all()
        for perm in perms:
            if perm not in staff_role.permissions:
                staff_role.permissions.append(perm)
        db.session.commit()

    coach_role = Role.query.filter_by(name='coach').first()
    if coach_role:
        coach_perm_names = [
            'events_view',
            'events_create',
            'social_post',
            'social_comment',
            'tournaments_view',
            'calendar_view'
        ]
        perms = Permission.query.filter(Permission.name.in_(coach_perm_names)).all()
        for perm in perms:
            if perm not in coach_role.permissions:
                coach_role.permissions.append(perm)
        db.session.commit()

    athlete_role = Role.query.filter_by(name='atleta').first()
    if athlete_role:
        athlete_perm_names = [
            'events_view',
            'social_post',
            'social_comment',
            'calendar_view'
        ]
        perms = Permission.query.filter(Permission.name.in_(athlete_perm_names)).all()
        for perm in perms:
            if perm not in athlete_role.permissions:
                athlete_role.permissions.append(perm)
        db.session.commit()

    athlete_en_role = Role.query.filter_by(name='athlete').first()
    if athlete_en_role:
        athlete_perm_names = [
            'events_view',
            'social_post',
            'social_comment',
            'calendar_view'
        ]
        perms = Permission.query.filter(Permission.name.in_(athlete_perm_names)).all()
        for perm in perms:
            if perm not in athlete_en_role.permissions:
                athlete_en_role.permissions.append(perm)
        db.session.commit()


def init_plans():
    """Initialize default subscription plans"""
    from app.models import Plan
    
    base_plans = [
        {
            'name': 'Free',
            'slug': 'free',
            'description': 'Piano base gratuito',
            'price_monthly': 0,
            'price_yearly': 0,
            'max_users': 5,
            'max_athletes': 20,
            'max_events': 10,
            'max_storage_mb': 100,
            'has_crm': False,
            'has_advanced_stats': False,
            'has_api_access': False,
            'has_white_label': False,
            'has_priority_support': False,
            'is_active': True,
            'display_order': 1
        },
        {
            'name': 'Basic',
            'slug': 'basic',
            'description': 'Piano per piccole società sportive',
            'price_monthly': 29.99,
            'price_yearly': 299.99,
            'max_users': 20,
            'max_athletes': 100,
            'max_events': 50,
            'max_storage_mb': 1000,
            'has_crm': True,
            'has_advanced_stats': False,
            'has_api_access': False,
            'has_white_label': False,
            'has_priority_support': False,
            'is_active': True,
            'display_order': 2
        },
        {
            'name': 'Professional',
            'slug': 'professional',
            'description': 'Piano completo per società professionali',
            'price_monthly': 79.99,
            'price_yearly': 799.99,
            'max_users': None,  # unlimited
            'max_athletes': None,
            'max_events': None,
            'max_storage_mb': 10000,
            'has_crm': True,
            'has_advanced_stats': True,
            'has_api_access': True,
            'has_white_label': False,
            'has_priority_support': True,
            'is_active': True,
            'is_featured': True,
            'display_order': 3
        },
        {
            'name': 'Enterprise',
            'slug': 'enterprise',
            'description': 'Soluzione personalizzata per grandi organizzazioni',
            'price_monthly': 199.99,
            'price_yearly': 1999.99,
            'max_users': None,
            'max_athletes': None,
            'max_events': None,
            'max_storage_mb': None,
            'has_crm': True,
            'has_advanced_stats': True,
            'has_api_access': True,
            'has_white_label': True,
            'has_priority_support': True,
            'is_active': True,
            'display_order': 4
        }
    ]
    
    for plan_data in base_plans:
        existing = Plan.query.filter_by(slug=plan_data['slug']).first()
        if not existing:
            plan = Plan(**plan_data)
            db.session.add(plan)
    
    db.session.commit()
