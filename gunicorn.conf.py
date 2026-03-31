#!/usr/bin/env python
"""
Gunicorn configuration for SONACIP production.

Usage:
    gunicorn -c gunicorn.conf.py wsgi:app
"""

import os
import multiprocessing

# Server socket
bind = os.environ.get('BIND', '0.0.0.0:8000')

# Worker processes
workers = int(os.environ.get('WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'sync'
worker_connections = 1000

# Timeout settings
timeout = 120
keepalive = 5
graceful_timeout = 30

# Logging
accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('LOG_LEVEL', 'info')
capture_output = True
enable_stdio_inheritance = True

# Process naming
proc_name = 'sonacip'

# Server mechanics
daemon = False
pidfile = 'sonacip.pid'

# SSL (set via environment variables)
keyfile = os.environ.get('SSL_KEYFILE')
certfile = os.environ.get('SSL_CERTFILE')

# Preload app for faster worker startup
preload_app = True

def on_starting(server):
    """Called just before the master process is initialized."""
    pass

def on_reload(server):
    """Called when receiving SIGHUP signal."""
    pass

def when_ready(server):
    """Called just after the server is started."""
    print(f"[OK] Gunicorn ready with {server.num_workers} workers on {bind}")

def worker_int(worker):
    """Called when a worker receives SIGINT or SIGQUIT."""
    pass

def worker_abort(worker):
    """Called when a worker receives SIGABRT."""
    pass
