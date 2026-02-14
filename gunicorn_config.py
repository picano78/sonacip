"""
Deprecated Gunicorn config.

Use `gunicorn.conf.py` as the single source of truth.
Kept for backwards compatibility with older deploy scripts.

This file imports from the canonical gunicorn.conf.py configuration.
"""

# Import all settings from the canonical configuration file
import sys
import os

# Add the current directory to the Python path to import gunicorn.conf
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import configuration from the canonical file
try:
    from gunicorn.conf import (
        bind, backlog, workers, threads, worker_class,
        preload_app, timeout, graceful_timeout, keepalive,
        max_requests, max_requests_jitter,
        accesslog, errorlog, loglevel, access_log_format,
        daemon, pidfile, user, group, umask, tmp_upload_dir,
        proc_name
    )
    
    __all__ = [
        'bind', 'backlog', 'workers', 'threads', 'worker_class',
        'preload_app', 'timeout', 'graceful_timeout', 'keepalive',
        'max_requests', 'max_requests_jitter',
        'accesslog', 'errorlog', 'loglevel', 'access_log_format',
        'daemon', 'pidfile', 'user', 'group', 'umask', 'tmp_upload_dir',
        'proc_name'
    ]
except ImportError:
    # If imports fail, provide minimal fallback configuration
    bind = "127.0.0.1:8000"
    workers = 4
    timeout = 90
