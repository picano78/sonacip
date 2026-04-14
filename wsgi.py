#!/usr/bin/env python3
"""
WSGI entrypoint for Gunicorn production deployment.
Usage: gunicorn -w 4 -b 0.0.0.0:8000 wsgi:application
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
    print(f"[OK] Loaded .env from {env_path}", file=sys.stderr)
else:
    # Create .env with production values if missing
    print(f"[WARNING] .env not found, creating with production values", file=sys.stderr)
    with open(env_path, 'w') as f:
        f.write("SUPERADMIN_EMAIL=picano78@gmail.com\n")
        f.write("SUPERADMIN_PASSWORD=Simone78\n")
        f.write("SECRET_KEY=4f8a2b9c1d3e5f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2\n")
        f.write("DATABASE_URL=sqlite:////root/sonacip/uploads/sonacip.db\n")
        f.write("SQLALCHEMY_DATABASE_URI=sqlite:////root/sonacip/uploads/sonacip.db\n")
        f.write("FLASK_ENV=production\n")
        f.write("FLASK_DEBUG=False\n")
        f.write("PORT=8000\n")
        f.write("WTF_CSRF_ENABLED=True\n")
        f.write("WTF_CSRF_TIME_LIMIT=None\n")
    load_dotenv(env_path, override=True)

# Now safe to import and create app
from app import create_app

app = create_app()

# Gunicorn compatibility - CRITICAL: application = app
application = app

# Export for potential use
if __name__ == "__main__":
    print(f"[INFO] WSGI application ready for Gunicorn", file=sys.stderr)
    print(f"[INFO] App name: {app.name if hasattr(app, 'name') else 'SONACIP'}", file=sys.stderr)
    print(f"[INFO] Blueprints: {len(app.blueprints)}", file=sys.stderr)
