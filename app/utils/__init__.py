"""
Common utilities and decorators for the application
"""
from functools import wraps
from flask import flash, redirect, url_for, abort, current_app, request, session, g
from flask_login import current_user
from datetime import datetime, timezone


def check_feature_enabled(feature_key):
    if current_user and current_user.is_authenticated and current_user.is_admin():
        return True
    try:
        from app.models import PlatformFeature
        pf = PlatformFeature.query.filter_by(key=feature_key).first()
        if pf and not pf.is_enabled:
            return False
    except (ImportError, AttributeError) as e:
        current_app.logger.debug(f"Feature check failed: {e}")
        pass
    return True


def feature_required(feature_key):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not check_feature_enabled(feature_key):
                flash('Questa funzionalità non è attualmente disponibile.', 'warning')
                return redirect(url_for('main.dashboard'))
            return f(*args, **kwargs)
        return wrapped
    return decorator


def rate_limit(key: str, limit: int = 10, window_seconds: int = 60):
    """
    Lightweight rate limiter using the app cache (memory/redis).
    Designed to avoid adding new dependencies.

    Args:
        key: logical bucket key (e.g. 'social:post', 'auth:login')
        limit: max requests in the window
        window_seconds: rolling window size in seconds (bucketed by time slice)
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            try:
                from app.cache import get_cache
                cache = get_cache()
                now = int(datetime.now(timezone.utc).timestamp())
                bucket = now // max(1, int(window_seconds))
                actor = current_user.id if getattr(current_user, "is_authenticated", False) else "anon"
                ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "unknown").split(",")[0].strip()
                cache_key = f"rl:{key}:{actor}:{ip}:{bucket}"
                val = cache.get(cache_key) or {"count": 0}
                val["count"] = int(val.get("count", 0)) + 1
                cache.set(cache_key, val, ttl=window_seconds + 5)
                if val["count"] > int(limit):
                    if current_app:
                        current_app.logger.warning(f"Rate limit exceeded key={key} actor={actor} ip={ip}")
                    abort(429)
            except Exception as e:
                # FALLBACK: if cache unavailable, use strict in-memory rate limiting
                if current_app:
                    current_app.logger.error(f"Rate limit cache failed: {e}")
                if not hasattr(g, '_rate_limit_fallback'):
                    g._rate_limit_fallback = {}
                now = int(datetime.now(timezone.utc).timestamp())
                bucket = now // max(1, int(window_seconds))
                actor = current_user.id if getattr(current_user, "is_authenticated", False) else "anon"
                ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "unknown").split(",")[0].strip()
                fallback_key = f"{key}:{actor}:{ip}:{bucket}"
                count = g._rate_limit_fallback.get(fallback_key, 0) + 1
                g._rate_limit_fallback[fallback_key] = count
                if count > limit:
                    if current_app:
                        current_app.logger.warning(f"Rate limit exceeded (fallback) key={key}")
                    abort(429)
            return f(*args, **kwargs)
        return wrapped
    return decorator


def check_permission(user, resource, action, society_id=None):
    """Centralized permission resolver with optional society scoping."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False

    if user.is_admin():
        return True

    # Global safe defaults for authenticated users (non society-scoped).
    # Social interactions should work for "generic" users too.
    if resource == 'social' and action in {'comment', 'post'}:
        return True

    # For society-scoped resources, require a resolvable society scope.
    SOCIETY_REQUIRED = {"crm", "calendar", "tournaments", "tasks", "society"}
    if society_id is None and resource in SOCIETY_REQUIRED:
        try:
            s = user.get_primary_society()
            society_id = s.id if s else None
        except Exception:
            society_id = None
        if society_id is None:
            return False

    # When scope is provided, resolve society membership + per-society overrides.
    if society_id:
        # Must be in scope
        if not user.can_access_society(society_id):
            return False
        try:
            from app.models import Permission, SocietyRolePermission
        except (ImportError, AttributeError) as e:
            current_app.logger.warning(f"Permission check failed: {e}")
            return False

        perm = Permission.query.filter_by(resource=resource, action=action).first()
        if not perm:
            return False

        role_name = None
        try:
            role_name = user.get_society_role(society_id)
        except (AttributeError, ValueError) as e:
            current_app.logger.warning(f"Failed to get society role: {e}")
            role_name = None

        def _default_allows(rn: str | None) -> bool:
            # Minimal, safe defaults. Società can override via SocietyRolePermission.
            if rn in ('societa', 'society_admin'):
                return True
            if rn in ('dirigente', 'coach', 'staff'):
                # operational roles
                if (resource, action) in {
                    ('social', 'comment'),
                    ('social', 'post'),
                    ('events', 'view'),
                    ('events', 'create'),
                    ('events', 'manage'),
                    ('calendar', 'view'),
                    ('calendar', 'manage'),
                    ('crm', 'access'),
                    ('crm', 'manage'),
                    ('tasks', 'manage'),
                    ('tournaments', 'view'),
                    ('tournaments', 'manage'),
                    ('society', 'manage_staff'),
                }:
                    return True
            if rn in ('atleta', 'athlete'):
                if (resource, action) in {
                    ('social', 'comment'),
                    ('events', 'view'),
                    ('calendar', 'view'),
                    ('tournaments', 'view'),
                }:
                    return True
            return False

        # Explicit overrides for this society-role-permission
        if role_name:
            ov = SocietyRolePermission.query.filter_by(
                society_id=society_id, role_name=role_name, permission_id=perm.id
            ).first()
            if ov:
                return True if ov.effect == 'allow' else False

        # Fallback to defaults or global role permission surface
        return _default_allows(role_name) or user.has_permission(resource, action)

    try:
        allowed = user.has_permission(resource, action)
    except Exception:
        return False

    if not allowed:
        return False

    return True


def can(resource, action, society_id=None, user=None):
    """Lightweight helper used by routes and templates to resolve permissions."""
    actor = user or current_user
    # If no explicit scope is provided, try to infer it for society-scoped resources.
    inferred_scope = society_id
    if inferred_scope is None and actor and getattr(actor, "is_authenticated", False):
        SOCIETY_SCOPED_RESOURCES = {"crm", "calendar", "tournaments", "tasks", "events", "society"}
        if resource in SOCIETY_SCOPED_RESOURCES:
            try:
                inferred_scope = get_active_society_id(actor)
            except Exception:
                inferred_scope = None
    return check_permission(actor, resource, action, inferred_scope)


def get_active_society_id(user=None) -> int | None:
    """
    Return the currently selected society scope id for the session, if valid.
    Falls back to user's primary society.
    """
    actor = user or current_user
    if not actor or not getattr(actor, "is_authenticated", False):
        return None

    # Per-request cache
    try:
        cached = getattr(g, "_active_society_id", None)
        if cached is not None:
            return cached
    except Exception:
        pass

    raw = session.get("active_society_id")
    try:
        sid = int(raw) if raw is not None else None
    except Exception:
        sid = None

    # Admin can scope to any society id.
    try:
        if sid and actor.is_admin():
            g._active_society_id = sid
            return sid
    except Exception:
        pass

    if sid and actor.can_access_society(sid):
        g._active_society_id = sid
        return sid

    try:
        scope = actor.get_primary_society()
        resolved = scope.id if scope else None
        g._active_society_id = resolved
        return resolved
    except Exception:
        return None


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
    Returns Society object or None
    """
    try:
        return user.get_primary_society()
    except Exception:
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
            else:
                # Auto-infer scope for society-required resources to keep routes and UI consistent.
                if resource in {"crm", "calendar", "tournaments", "tasks", "society"}:
                    try:
                        scope_id = get_active_society_id(current_user)
                    except Exception:
                        scope_id = None

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


def plan_feature_required(feature_name):
    """
    Decorator to require a specific plan feature (subscription-based)
    Usage: @plan_feature_required('crm')
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


def timeago(date):
    """
    Jinja2 filter to return a 'time ago' string.
    """
    if not date:
        return ""

    # Normalize naive/aware datetimes to avoid TypeError on subtraction.
    # - If `date` is naive, assume it's UTC naive.
    # - If `date` is aware, convert to UTC.
    try:
        is_aware = date.tzinfo is not None and date.tzinfo.utcoffset(date) is not None
    except Exception:
        is_aware = False

    if is_aware:
        now = datetime.now(timezone.utc)
        try:
            date_norm = date.astimezone(timezone.utc)
        except Exception:
            date_norm = date
    else:
        # Use recommended datetime.now(timezone.utc) instead of deprecated datetime.utcnow()
        now = datetime.now(timezone.utc)
        # Treat naive datetime as UTC naive for consistency
        date_norm = date

    diff = now - date_norm
    
    seconds = diff.total_seconds()
    if seconds < 0:
        return "proprio ora"
    
    if seconds < 60:
        return f"{int(seconds)} secondi fa"
    if seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} {'minuto' if minutes == 1 else 'minuti'} fa"
    if seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} {'ora' if hours == 1 else 'ore'} fa"
    if seconds < 2592000:
        days = int(seconds // 86400)
        return f"{days} {'giorno' if days == 1 else 'giorni'} fa"
    if seconds < 31536000:
        months = int(seconds // 2592000)
        return f"{months} {'mese' if months == 1 else 'mesi'} fa"
    
    years = int(seconds // 31536000)
    return f"{years} {'anno' if years == 1 else 'anni'} fa"


def escape_like(value: str) -> str:
    """Escape special characters for SQL LIKE queries to prevent injection."""
    if not value:
        return value
    # Escape backslash first, then SQL LIKE wildcards
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def datetime_format(value, format='%d/%m/%Y %H:%M'):
    """Format a date/time object to string."""
    if value is None:
        return ""
    return value.strftime(format)


def log_action(action, entity_type=None, entity_id=None, details=None, society_id=None):
    """
    Log an action to the audit log
    """
    from app.models import AuditLog
    from app import db
    from flask import request
    
    if current_user.is_authenticated:
        log = AuditLog()
        log.user_id = current_user.id
        log.society_id = society_id
        log.action = action
        log.entity_type = entity_type
        log.entity_id = entity_id
        log.details = details
        log.ip_address = request.remote_addr if request else None
        db.session.add(log)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # Log to console but don't fail the main operation
            print(f"Warning: Failed to log action: {e}")


# Make submodules available for import
# These are lazily loaded to avoid circular imports

__all__ = [
    'check_feature_enabled',
    'feature_required',
    'rate_limit',
    'check_permission',
    'can',
    'get_active_society_id',
    'enforce_permission',
    'admin_required',
    'society_required',
    'staff_or_society_required',
    'role_required',
    'can_manage_user',
    'can_view_user',
    'get_user_society',
    'permission_required',
    'plan_feature_required',  # Subscription-based features (distinct from feature_required which checks platform feature flags)
    'safe_get_or_404',
    'timeago',
    'escape_like',
    'datetime_format',
    'log_action',
    # Submodules
    'caching',
    'search',
    'exports',
    'error_handling',
]
