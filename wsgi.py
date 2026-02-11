"""
Gunicorn entrypoint.

Expose `application` for WSGI servers.
"""

from run import app

application = app
