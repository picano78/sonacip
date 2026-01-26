# Gunicorn Configuration for SONACIP

import multiprocessing
import os

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Process naming
proc_name = "sonacip"

# Logging (respect LOGS_FOLDER env var, fallback to relative path)
logs_folder = os.environ.get('LOGS_FOLDER', 'logs')
accesslog = os.path.join(logs_folder, "gunicorn_access.log")
errorlog = os.path.join(logs_folder, "gunicorn_error.log")
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Server mechanics
daemon = False
pidfile = "gunicorn.pid"
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (uncomment and configure for HTTPS)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# Environment variables
raw_env = [
    "FLASK_ENV=production",
    "APP_ENV=production",
]
