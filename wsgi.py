"""
Gunicorn entrypoint.

Expose `application` for WSGI servers.
"""

from run import app

# Gunicorn common: `wsgi:application`
application = app

# Backward compatibility: some configs use `wsgi:app`
__all__ = ["app", "application"]
