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
