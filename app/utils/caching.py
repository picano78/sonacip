"""Advanced Caching Utilities"""
from flask import current_app, g
from functools import wraps
from app.cache import get_cache
import hashlib
import json


def cache_key(*args, **kwargs):
    """Generate cache key from arguments"""
    key_data = {'args': args, 'kwargs': kwargs}
    key_str = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.md5(key_str.encode()).hexdigest()


def cached_query(timeout=300, key_prefix='query'):
    """Decorator for caching database query results"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            cache = get_cache()
            cache_key_str = f"{key_prefix}:{cache_key(*args, **kwargs)}"
            cached_value = cache.get(cache_key_str)
            if cached_value is not None:
                return cached_value
            result = f(*args, **kwargs)
            cache.set(cache_key_str, result, ttl=timeout)
            return result
        return decorated_function
    return decorator


def memoize_request(f):
    """Cache function results for the duration of the request"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, '_memoize_cache'):
            g._memoize_cache = {}
        key = (f.__name__, args, tuple(sorted(kwargs.items())))
        if key in g._memoize_cache:
            return g._memoize_cache[key]
        result = f(*args, **kwargs)
        g._memoize_cache[key] = result
        return result
    return decorated_function
