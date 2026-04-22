#!/usr/bin/env python3
"""
SONACIP Flask application - Single Source of Truth.

This module creates and exports the Flask application instance.
Used by:
  - run.py: Development server (python run.py)
  - wsgi.py: Production Gunicorn (gunicorn wsgi:app)
"""

import os
import sys

# CRITICAL: Load .env BEFORE importing app/config modules
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
env_path = os.path.join(basedir, '.env')

# Load .env with override=True to ensure it takes precedence
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
else:
    # Create .env with production values if missing
    print(f"[WARNING] .env not found, creating with defaults", file=sys.stderr)
    with open(env_path, 'w') as f:
        f.write("SUPERADMIN_EMAIL=picano78@gmail.com\n")
        f.write("SUPERADMIN_PASSWORD=Simone78\n")
        f.write("SECRET_KEY=4f8a2b9c1d3e5f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2\n")
        f.write("DATABASE_URL=sqlite:////root/sonacip/uploads/sonacip.db\n")
        f.write("FLASK_ENV=production\n")
        f.write("FLASK_DEBUG=False\n")
        f.write("PORT=8000\n")
        f.write("WTF_CSRF_ENABLED=True\n")
        f.write("WTF_CSRF_TIME_LIMIT=None\n")
    load_dotenv(env_path, override=True)

# Now safe to import and create app
from app import create_app

app = create_app()

# Development server entrypoint
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    print(f"[INFO] Starting SONACIP on 0.0.0.0:{port}", file=sys.stderr)
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
