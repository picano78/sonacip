#!/usr/bin/env python3
"""
WSGI entrypoint for Gunicorn production deployment.
SINGLE SOURCE OF TRUTH: imports app from run.py

Usage: gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
"""

# Import app from run.py - the single source of truth
from run import app

# Gunicorn requires 'application' variable
application = app
