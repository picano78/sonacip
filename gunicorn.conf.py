"""
Gunicorn configuration for SONACIP (production-grade).

Single source of truth: systemd should run gunicorn with `--config gunicorn.conf.py`.
All values are env-configurable.
"""

from __future__ import annotations

import multiprocessing
import os


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return default


# Server socket
bind = os.environ.get("GUNICORN_BIND", "127.0.0.1:8000")
backlog = _env_int("GUNICORN_BACKLOG", 2048)

# Workers/threads
cpu = multiprocessing.cpu_count()
workers = _env_int("GUNICORN_WORKERS", max(2, cpu * 2 + 1))
threads = _env_int("GUNICORN_THREADS", 4)
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "gthread" if threads > 1 else "sync")

# Robustness
preload_app = os.environ.get("GUNICORN_PRELOAD_APP", "true").lower() in ("1", "true", "on", "yes")
timeout = _env_int("GUNICORN_TIMEOUT", 60)
graceful_timeout = _env_int("GUNICORN_GRACEFUL_TIMEOUT", 30)
keepalive = _env_int("GUNICORN_KEEPALIVE", 5)

max_requests = _env_int("GUNICORN_MAX_REQUESTS", 2000)
max_requests_jitter = _env_int("GUNICORN_MAX_REQUESTS_JITTER", 200)

# Logging
logs_folder = os.environ.get("LOGS_FOLDER", "logs")
os.makedirs(logs_folder, exist_ok=True)
accesslog = os.path.join(logs_folder, "gunicorn_access.log")
errorlog = os.path.join(logs_folder, "gunicorn_error.log")
loglevel = os.environ.get("LOG_LEVEL", "info").lower()
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Security: do not daemonize under systemd
daemon = False
