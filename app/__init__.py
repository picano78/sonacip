"""
Application Factory
Creates and configures the Flask application instance
"""
import os
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask import request

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()


def create_app(config_name=None):
    """
    Application factory pattern
    Creates and configures the Flask application
    """
    app = Flask(__name__)
    
    # Load configuration
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    from config import config
    app.config.from_object(config[config_name])
    
    # Ensure required directories exist
    ensure_directories(app)
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    
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
    
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()
        create_super_admin()

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
    directories = [
        app.config['UPLOAD_FOLDER'],
        app.config['BACKUP_FOLDER'],
        app.config['LOGS_FOLDER'],
        os.path.join(app.config['UPLOAD_FOLDER'], 'avatars'),
        os.path.join(app.config['UPLOAD_FOLDER'], 'covers'),
        os.path.join(app.config['UPLOAD_FOLDER'], 'posts'),
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


def register_error_handlers(app):
    """Register error handlers"""
    from flask import render_template
    
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(e):
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
        
        return dict(
            get_unread_notifications_count=get_unread_notifications_count,
            get_privacy_settings=get_privacy_settings,
            now=datetime.utcnow
        )


def create_super_admin():
    """Create default super admin and initialize base data if not exists"""
    from app.models import User, Role, Permission, Plan
    
    # Initialize base roles
    init_roles()
    
    # Initialize base permissions
    init_permissions()
    
    # Initialize default plans
    init_plans()
    
    # Create super admin user
    admin = User.query.filter_by(role='super_admin').first()
    if not admin:
        admin = User(
            email='admin@sonacip.it',
            username='admin',
            first_name='Super',
            last_name='Admin',
            role='super_admin',
            is_active=True,
            is_verified=True
        )
        admin.set_password('admin123')  # Change this in production!
        db.session.add(admin)
        db.session.commit()
        print('✓ Super Admin created: admin@sonacip.it / admin123')


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
            'name': 'atleta',
            'display_name': 'Atleta',
            'description': 'Atleta affiliato a una società',
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
