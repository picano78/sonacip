#!/usr/bin/env python
"""
WSGI entrypoint for Gunicorn.

Usage:
    gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app

This file loads .env BEFORE creating the app to ensure all config
is available during app initialization.
"""

import os
import sys

# CRITICAL: Load .env BEFORE importing app/config modules
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
env_path = os.path.join(basedir, '.env')

if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
    print(f"[OK] Loaded .env from {env_path}", file=sys.stderr)
else:
    print(f"[WARNING] .env file not found at {env_path}", file=sys.stderr)
    print("[WARNING] Using environment variables only", file=sys.stderr)

# Now safe to import and create app
from app import create_app

app = create_app()

# For Gunicorn compatibility
application = app
