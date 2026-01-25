"""
Common utilities and decorators for the application
"""
from functools import wraps
from flask import flash, redirect, url_for, abort, current_app
from flask_login import current_user


def check_permission(user, resource, action, society_id=None):
    """Centralized permission resolver with optional society scoping."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False

    if user.is_admin():
        return True

    try:
        allowed = user.has_permission(resource, action)
    except Exception:
        return False

    if not allowed:
        return False

    if society_id:
        return user.can_access_society(society_id)

    return True


def can(resource, action, society_id=None, user=None):
    """Lightweight helper used by routes and templates to resolve permissions."""
    actor = user or current_user
    return check_permission(actor, resource, action, society_id)


def enforce_permission(resource, action, society_id=None, user=None):
    """Abort with 403 when the requested permission/scope is not granted."""
    actor = user or current_user
    if check_permission(actor, resource, action, society_id):
        return True
    if current_app:
        current_app.logger.warning(
            f"Permission denied: resource={resource} action={action} scope={society_id} user={actor.id if actor and actor.is_authenticated else 'anonymous'}"
        )
    flash('Non hai i permessi necessari per questa azione.', 'danger')
    abort(403)


def admin_required(f):
    """Decorator to require admin access permission."""
    return permission_required('admin', 'access')(f)


def society_required(f):
    """Decorator to require society management permission."""
    return permission_required('society', 'manage')(f)


def staff_or_society_required(f):
    """Decorator to require society staff management permission."""
    return permission_required('society', 'manage_staff')(f)


def role_required(*allowed_roles):
    """Legacy role-based decorator (deprecated). Prefer permission_required."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Effettua il login per accedere a questa pagina.', 'warning')
                return redirect(url_for('auth.login'))
            # Fallback to permission checks mapped to legacy role expectations
            if check_permission(current_user, 'admin', 'access'):
                return f(*args, **kwargs)
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

    target_society = user.get_primary_society()
    target_society_id = target_society.id if target_society else None

    if not check_permission(current_user, 'users', 'edit', target_society_id):
        return False

    if current_user.id == user.id:
        return False

    if target_society_id:
        return current_user.can_access_society(target_society_id)

    return True


def can_view_user(user):
    """
    Check if current user can view the specified user's profile
    """
    if not current_user.is_authenticated:
        return False

    target_society = user.get_primary_society()
    target_society_id = target_society.id if target_society else None

    if check_permission(current_user, 'users', 'view_all', target_society_id):
        return True

    if current_user.id == user.id:
        return True

    if target_society_id and current_user.can_access_society(target_society_id):
        return True

    return False


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


def permission_required(resource, action, society_id_param=None, society_id_func=None):
    """
    Decorator to require a specific permission with optional society scoping.
    Usage: @permission_required('users', 'edit')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Effettua il login per accedere a questa pagina.', 'warning')
                return redirect(url_for('auth.login'))

            scope_id = None
            if society_id_param:
                scope_id = kwargs.get(society_id_param)
            elif society_id_func:
                scope_id = society_id_func(*args, **kwargs)

            if not check_permission(current_user, resource, action, scope_id):
                if current_app:
                    current_app.logger.warning(
                        f"Permission denied: resource={resource} action={action} scope={scope_id} user={current_user.id if current_user.is_authenticated else 'anonymous'}"
                    )
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
