"""
Application Factory
Creates and configures the Flask application instance
"""
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail

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
    
    # Backup
    from app.backup import bp as backup_bp
    app.register_blueprint(backup_bp, url_prefix='/backup')
    
    # CRM
    from app.crm import bp as crm_bp
    app.register_blueprint(crm_bp, url_prefix='/crm')


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
        
        def get_unread_notifications_count():
            """Get count of unread notifications for current user"""
            if current_user.is_authenticated:
                from app.models import Notification
                return Notification.query.filter_by(
                    user_id=current_user.id, 
                    is_read=False
                ).count()
            return 0
        
        return dict(
            get_unread_notifications_count=get_unread_notifications_count,
            now=datetime.utcnow
        )


def create_super_admin():
    """Create default super admin if not exists"""
    from app.models import User
    
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
        print('Super Admin created: admin@sonacip.it / admin123')
