"""
Enhanced Error Handling and Logging Utilities
"""
import functools
import traceback
from flask import current_app, request
from datetime import datetime, timezone
from app import db
from app.models import AuditLog
import json


class ApplicationError(Exception):
    """Base class for application errors"""
    status_code = 500
    
    def __init__(self, message, status_code=None, payload=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload
    
    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        rv['error'] = self.__class__.__name__
        return rv


class ValidationError(ApplicationError):
    """Validation error"""
    status_code = 400


class AuthenticationError(ApplicationError):
    """Authentication error"""
    status_code = 401


class AuthorizationError(ApplicationError):
    """Authorization error"""
    status_code = 403


class NotFoundError(ApplicationError):
    """Resource not found"""
    status_code = 404


class ConflictError(ApplicationError):
    """Resource conflict"""
    status_code = 409


class RateLimitError(ApplicationError):
    """Rate limit exceeded"""
    status_code = 429


def log_error(error, context=None):
    """
    Log error with context information
    
    Args:
        error: Exception object
        context: Additional context dictionary
    """
    error_data = {
        'type': type(error).__name__,
        'message': str(error),
        'traceback': traceback.format_exc(),
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    # Add request context if available
    if request:
        error_data['request'] = {
            'method': request.method,
            'url': request.url,
            'remote_addr': request.remote_addr,
            'user_agent': str(request.user_agent)
        }
    
    # Add custom context
    if context:
        error_data['context'] = context
    
    current_app.logger.error(json.dumps(error_data))


def handle_error_gracefully(default_return=None, log_context=None):
    """
    Decorator to handle errors gracefully
    
    Usage:
        @handle_error_gracefully(default_return=[], log_context={'operation': 'fetch_users'})
        def risky_operation():
            return potentially_failing_code()
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_error(e, context=log_context)
                return default_return
        return wrapper
    return decorator


def audit_action(action, resource_type=None):
    """
    Decorator to audit user actions
    
    Usage:
        @audit_action('user.delete', resource_type='user')
        def delete_user(user_id):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from flask_login import current_user
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Log audit trail
            try:
                if current_user.is_authenticated:
                    audit_log = AuditLog(
                        user_id=current_user.id,
                        action=action,
                        resource_type=resource_type,
                        details=json.dumps({
                            'args': str(args),
                            'kwargs': str(kwargs)
                        }),
                        ip_address=request.remote_addr if request else None,
                        user_agent=str(request.user_agent) if request else None
                    )
                    db.session.add(audit_log)
                    db.session.commit()
            except Exception as e:
                current_app.logger.warning(f"Failed to log audit trail: {e}")
            
            return result
        return wrapper
    return decorator


def retry_on_exception(max_retries=3, delay=1, backoff=2, exceptions=(Exception,)):
    """
    Retry decorator with exponential backoff
    
    Args:
        max_retries: Maximum number of retries
        delay: Initial delay in seconds
        backoff: Backoff multiplier
        exceptions: Tuple of exceptions to catch
        
    Usage:
        @retry_on_exception(max_retries=3, delay=1, backoff=2)
        def unstable_api_call():
            return requests.get('https://api.example.com/data')
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import time
            
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        current_app.logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {current_delay}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        current_app.logger.error(
                            f"{func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )
            
            # Re-raise the last exception
            raise last_exception
        
        return wrapper
    return decorator


def measure_time(operation_name=None):
    """
    Decorator to measure function execution time
    
    Usage:
        @measure_time('database_query')
        def slow_query():
            return User.query.all()
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import time
            
            name = operation_name or func.__name__
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed = time.time() - start_time
                current_app.logger.info(
                    f"Performance: {name} took {elapsed:.3f}s"
                )
        
        return wrapper
    return decorator


class ErrorHandler:
    """Centralized error handler for Flask app"""
    
    @staticmethod
    def register(app):
        """Register error handlers with Flask app"""
        
        @app.errorhandler(ValidationError)
        def handle_validation_error(error):
            from flask import jsonify
            response = jsonify(error.to_dict())
            response.status_code = error.status_code
            return response
        
        @app.errorhandler(AuthenticationError)
        def handle_authentication_error(error):
            from flask import jsonify
            response = jsonify(error.to_dict())
            response.status_code = error.status_code
            return response
        
        @app.errorhandler(AuthorizationError)
        def handle_authorization_error(error):
            from flask import jsonify
            response = jsonify(error.to_dict())
            response.status_code = error.status_code
            return response
        
        @app.errorhandler(NotFoundError)
        def handle_not_found_error(error):
            from flask import jsonify
            response = jsonify(error.to_dict())
            response.status_code = error.status_code
            return response
        
        @app.errorhandler(ConflictError)
        def handle_conflict_error(error):
            from flask import jsonify
            response = jsonify(error.to_dict())
            response.status_code = error.status_code
            return response
        
        @app.errorhandler(RateLimitError)
        def handle_rate_limit_error(error):
            from flask import jsonify
            response = jsonify(error.to_dict())
            response.status_code = error.status_code
            return response
        
        @app.errorhandler(500)
        def handle_internal_error(error):
            from flask import jsonify
            log_error(error)
            db.session.rollback()
            return jsonify({
                'error': 'InternalServerError',
                'message': 'An internal error occurred'
            }), 500
