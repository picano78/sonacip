
"""
Production entrypoint for SONACIP.

GUARANTEED to load .env BEFORE any config is evaluated.
"""
import os
import sys

# CRITICAL: Load .env BEFORE importing app/config modules
# This ensures all environment variables are available during config import
from dotenv import load_dotenv

# Get the directory containing this file
basedir = os.path.abspath(os.path.dirname(__file__))
env_path = os.path.join(basedir, '.env')

# Load .env with override=True to ensure it takes precedence
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
    print(f"[OK] Loaded .env from {env_path}", file=sys.stderr)
else:
    print(f"[WARNING] .env file not found at {env_path}", file=sys.stderr)
    print("[WARNING] Using environment variables only", file=sys.stderr)

# Now import and create app
from app import create_app

app = create_app()

if __name__ == "__main__":
    # Development server
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
"""

Legacy entrypoint kept for compatibility.

Production entrypoint MUST be `wsgi:app`.
This module intentionally remains runnable by Gunicorn as `run:app` if needed.
"""

# CRITICAL: Load .env BEFORE importing app/config modules
from dotenv import load_dotenv
import os
import sys

basedir = os.path.abspath(os.path.dirname(__file__))
env_path = os.path.join(basedir, '.env')

if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
    print(f"[OK] Loaded .env from {env_path}", file=sys.stderr)
else:
    print(f"[WARNING] .env file not found at {env_path}", file=sys.stderr)

# Now safe to import app
from app import create_app

app = create_app()
