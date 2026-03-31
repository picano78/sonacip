#!/usr/bin/env python
"""
WSGI entrypoint for Gunicorn.

Usage:
    gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
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
    # Create .env with default values if missing
    print(f"[WARNING] .env not found, creating with default values", file=sys.stderr)
    with open(env_path, 'w') as f:
        f.write("SUPERADMIN_EMAIL=picano78@gmail.com\n")
        f.write("SUPERADMIN_PASSWORD=Picano78\n")
        f.write("SECRET_KEY=4f8a2b9c1d3e5f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2\n")
        f.write("SQLALCHEMY_DATABASE_URI=sqlite:///uploads/sonacip.db\n")
        f.write("FLASK_ENV=production\n")
        f.write("FLASK_DEBUG=False\n")
    load_dotenv(env_path, override=True)

# Now safe to import and create app
from app import create_app

app = create_app()

# For Gunicorn compatibility
application = app
