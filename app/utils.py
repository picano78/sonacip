"""
Common utilities and decorators for the application
"""
from functools import wraps
from flask import flash, redirect, url_for, abort
from flask_login import current_user


def admin_required(f):
    """
    Decorator to require super_admin role
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Effettua il login per accedere a questa pagina.', 'warning')
            return redirect(url_for('auth.login'))
        
        if not current_user.is_admin():
            flash('Accesso negato. Area riservata agli amministratori.', 'danger')
            return redirect(url_for('main.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function


def society_required(f):
    """
    Decorator to require societa role
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Effettua il login per accedere a questa pagina.', 'warning')
            return redirect(url_for('auth.login'))
        
        if not current_user.is_society():
            flash('Accesso negato. Area riservata alle società sportive.', 'danger')
            return redirect(url_for('main.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function


def staff_or_society_required(f):
    """
    Decorator to require staff or societa role
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Effettua il login per accedere a questa pagina.', 'warning')
            return redirect(url_for('auth.login'))
        
        if not (current_user.is_staff() or current_user.is_society()):
            flash('Accesso negato. Area riservata a staff e società.', 'danger')
            return redirect(url_for('main.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function


def role_required(*allowed_roles):
    """
    Decorator to require specific roles
    Usage: @role_required('super_admin', 'societa', 'staff')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Effettua il login per accedere a questa pagina.', 'warning')
                return redirect(url_for('auth.login'))
            
            if current_user.role not in allowed_roles:
                flash('Accesso negato. Non hai i permessi necessari.', 'danger')
                return redirect(url_for('main.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def can_manage_user(user):
    """
    Check if current user can manage the specified user
    Super admin can manage everyone
    Society can manage their own staff and athletes
    """
    if not current_user.is_authenticated:
        return False
    
    # Super admin can manage everyone
    if current_user.is_admin():
        return True
    
    # Can't manage yourself through admin interface
    if current_user.id == user.id:
        return False
    
    # Society can manage their staff and athletes
    if current_user.is_society():
        if user.is_staff() and user.society_id == current_user.id:
            return True
        if user.is_athlete() and user.athlete_society_id == current_user.id:
            return True
    
    return False


def can_view_user(user):
    """
    Check if current user can view the specified user's profile
    """
    if not current_user.is_authenticated:
        return False
    
    # Super admin can view everyone
    if current_user.is_admin():
        return True
    
    # Everyone can view their own profile
    if current_user.id == user.id:
        return True
    
    # Society can view their staff and athletes
    if current_user.is_society():
        if user.is_staff() and user.society_id == current_user.id:
            return True
        if user.is_athlete() and user.athlete_society_id == current_user.id:
            return True
    
    # Staff can view athletes of their society
    if current_user.is_staff() and current_user.society_id:
        if user.is_athlete() and user.athlete_society_id == current_user.society_id:
            return True
    
    # Public profiles (for social features)
    return True


def get_user_society(user):
    """
    Get the society associated with a user
    Returns User object or None
    """
    from app.models import User
    
    if user.is_society():
        return user
    
    if user.is_staff() and user.society_id:
        return User.query.get(user.society_id)
    
    if user.is_athlete() and user.athlete_society_id:
        return User.query.get(user.athlete_society_id)
    
    return None


def permission_required(resource, action):
    """
    Decorator to require a specific permission
    Usage: @permission_required('users', 'edit')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Effettua il login per accedere a questa pagina.', 'warning')
                return redirect(url_for('auth.login'))
            
            if not current_user.has_permission(resource, action):
                flash('Non hai i permessi necessari per questa azione.', 'danger')
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def feature_required(feature_name):
    """
    Decorator to require a specific plan feature
    Usage: @feature_required('crm')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Effettua il login per accedere a questa pagina.', 'warning')
                return redirect(url_for('auth.login'))
            
            if not current_user.has_feature(feature_name):
                flash(f'Questa funzionalità richiede un piano superiore.', 'warning')
                return redirect(url_for('main.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def safe_get_or_404(model, entity_id, error_message=None):
    """
    Safely get an entity or return 404
    """
    entity = model.query.get(entity_id)
    if not entity:
        if error_message:
            flash(error_message, 'warning')
        abort(404)
    return entity


def log_action(action, entity_type=None, entity_id=None, details=None):
    """
    Log an action to the audit log
    """
    from app.models import AuditLog
    from app import db
    from flask import request
    
    if current_user.is_authenticated:
        log = AuditLog(
            user_id=current_user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=request.remote_addr if request else None
        )
        db.session.add(log)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # Log to console but don't fail the main operation
            print(f"Warning: Failed to log action: {e}")
