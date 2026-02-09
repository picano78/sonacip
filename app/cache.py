"""Simple caching utilities with optional Redis backend."""
from functools import wraps
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional
import json
from flask import current_app

try:  # Optional redis support
    import redis  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    redis = None


class SimpleCache:
    """In-memory cache with TTL support."""
    
    def __init__(self):
        self._cache = {}
        self._timestamps = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        if key not in self._cache:
            return None
        
        if key in self._timestamps:
            if datetime.now(timezone.utc) > self._timestamps[key]:
                # Expired
                del self._cache[key]
                del self._timestamps[key]
                return None
        
        return self._cache[key]
    
    def set(self, key: str, value: Any, ttl: int = 300):
        """Set cached value with TTL in seconds."""
        self._cache[key] = value
        self._timestamps[key] = datetime.now(timezone.utc) + timedelta(seconds=ttl)
    
    def delete(self, key: str):
        """Delete cached value."""
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)
    
    def clear(self):
        """Clear all cache."""
        self._cache.clear()
        self._timestamps.clear()
    
    def cleanup(self):
        """Remove expired entries."""
        now = datetime.now(timezone.utc)
        expired_keys = [k for k, v in self._timestamps.items() if now > v]
        for key in expired_keys:
            self.delete(key)


class RedisBackedCache(SimpleCache):
    """Redis-backed cache that falls back to memory for non-JSON values."""

    def __init__(self, redis_url: str, prefix: str = 'appcache:'):
        super().__init__()
        self._redis_url = redis_url
        self._prefix = prefix
        self._client = redis.from_url(redis_url) if redis else None

    def _prefixed(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def get(self, key: str) -> Optional[Any]:
        if self._client:
            cached_bytes = self._client.get(self._prefixed(key))
            if cached_bytes:
                try:
                    return json.loads(cached_bytes)
                except (json.JSONDecodeError, TypeError) as e:
                    current_app.logger.debug(f"Cache JSON decode failed: {e}")
                    pass  # Fallback to in-memory payloads
        return super().get(key)

    def set(self, key: str, value: Any, ttl: int = 300):
        if self._client:
            try:
                payload = json.dumps(value, default=str)
                self._client.setex(self._prefixed(key), ttl, payload)
            except TypeError:
                # If not JSON serializable, store only in memory
                super().set(key, value, ttl)
        else:
            super().set(key, value, ttl)

    def delete(self, key: str):
        if self._client:
            self._client.delete(self._prefixed(key))
        super().delete(key)

    def clear(self):
        if self._client:
            cursor = 0
            pattern = f"{self._prefix}*"
            while True:
                cursor, keys = self._client.scan(cursor=cursor, match=pattern, count=200)
                if keys:
                    self._client.delete(*keys)
                if cursor == 0:
                    break
        super().clear()


# Global cache instance (lazy configured)
_cache: SimpleCache = SimpleCache()


def _configure_cache_from_app():
    global _cache
    if isinstance(_cache, RedisBackedCache):
        return
    redis_url = current_app.config.get('REDIS_URL') if current_app else None
    if redis_url and redis:
        _cache = RedisBackedCache(redis_url)


def get_cache() -> SimpleCache:
    """Get cache instance, upgrading to Redis when configured."""
    if current_app:
        _configure_cache_from_app()
    return _cache


def cached(ttl: int = 300, key_prefix: str = ''):
    """
    Decorator to cache function results.
    
    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache key
        
    Usage:
        @cached(ttl=600, key_prefix='user')
        def get_user_data(user_id):
            return expensive_query(user_id)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()

            # Build cache key
            cache_key = f"{key_prefix}:{func.__name__}:"
            if args:
                cache_key += f"args:{':'.join(str(a) for a in args)}"
            if kwargs:
                cache_key += f"kwargs:{':'.join(f'{k}={v}' for k, v in sorted(kwargs.items()))}"
            
            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                current_app.logger.debug(f"Cache hit: {cache_key}")
                return cached_value
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Store in cache
            cache.set(cache_key, result, ttl)
            current_app.logger.debug(f"Cache set: {cache_key} (TTL: {ttl}s)")
            
            return result
        
        # Add cache control methods
        wrapper.cache_clear = lambda: get_cache().clear()
        wrapper.cache_info = lambda: {'ttl': ttl, 'prefix': key_prefix}
        
        return wrapper
    return decorator


def cache_model_query(model_class: Any, query_filter: dict, ttl: int = 300) -> Optional[Any]:
    """
    Cache database query result.
    
    Args:
        model_class: SQLAlchemy model class
        query_filter: Filter kwargs for query
        ttl: Cache TTL in seconds
        
    Returns:
        Query result or None
    """
    cache_key = f"model:{model_class.__tablename__}:{':'.join(f'{k}={v}' for k, v in sorted(query_filter.items()))}"
    
    cached_result = get_cache().get(cache_key)
    if cached_result is not None:
        return cached_result
    
    result = model_class.query.filter_by(**query_filter).first()
    if result:
        get_cache().set(cache_key, result, ttl)
    
    return result


def invalidate_model_cache(model_class: Any, **filters):
    """Invalidate cache for specific model queries."""
    prefix = f"model:{model_class.__tablename__}"
    cache = get_cache()
    keys_to_delete = [k for k in cache._cache.keys() if k.startswith(prefix)]
    
    if filters:
        # Only delete matching filters
        filter_str = ':'.join(f'{k}={v}' for k, v in sorted(filters.items()))
        keys_to_delete = [k for k in keys_to_delete if filter_str in k]
    
    for key in keys_to_delete:
        cache.delete(key)
