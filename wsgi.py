#!/usr/bin/env python3
"""
WSGI entrypoint for Gunicorn production deployment.

Command:
    gunicorn -w 3 -b 0.0.0.0:8000 run:app
"""

from run import app
application = app
