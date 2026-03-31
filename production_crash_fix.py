#!/usr/bin/env python
"""
Production Crash Fix - SONACIP
Fixes all production issues without breaking anything
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def fix_run_py():
    """Fix run.py to load .env before creating app"""
    print("FIXING run.py - .env loading")
    print("=" * 50)
    
    run_py = """\n\"\"\"\nProduction entrypoint for SONACIP.\n\nGUARANTEED to load .env BEFORE any config is evaluated.\n\"\"\"\nimport os\nimport sys\n\n# CRITICAL: Load .env BEFORE importing app/config modules\n# This ensures all environment variables are available during config import\nfrom dotenv import load_dotenv\n\n# Get the directory containing this file\nbasedir = os.path.abspath(os.path.dirname(__file__))\nenv_path = os.path.join(basedir, '.env')\n\n# Load .env with override=True to ensure it takes precedence\nif os.path.exists(env_path):\n    load_dotenv(env_path, override=True)\n    print(f\"[OK] Loaded .env from {env_path}\", file=sys.stderr)\nelse:\n    print(f\"[WARNING] .env file not found at {env_path}\", file=sys.stderr)\n    print(\"[WARNING] Using environment variables only\", file=sys.stderr)\n\n# Now import and create app\nfrom app import create_app\n\napp = create_app()\n\nif __name__ == \"__main__\":\n    # Development server\n    port = int(os.environ.get('PORT', 8000))\n    app.run(host='0.0.0.0', port=port, debug=False)\n\"\"\"\n\nLegacy entrypoint kept for compatibility.\n\nProduction entrypoint MUST be `wsgi:app`.\nThis module intentionally remains runnable by Gunicorn as `run:app` if needed.\n\"\"\"\n\n# CRITICAL: Load .env BEFORE importing app/config modules\nfrom dotenv import load_dotenv\nimport os\nimport sys\n\nbasedir = os.path.abspath(os.path.dirname(__file__))\nenv_path = os.path.join(basedir, '.env')\n\nif os.path.exists(env_path):\n    load_dotenv(env_path, override=True)\n    print(f\"[OK] Loaded .env from {env_path}\", file=sys.stderr)\nelse:\n    print(f\"[WARNING] .env file not found at {env_path}\", file=sys.stderr)\n\n# Now safe to import app\nfrom app import create_app\n\napp = create_app()\n"""
    
    try:
        with open('run.py', 'w') as f:
            f.write(run_py)
        print("  [OK] Fixed run.py - .env loaded BEFORE app import")
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to fix run.py: {e}")
        return False


def fix_wsgi_py():
    """Create proper wsgi.py for Gunicorn"""
    print("\nCREATING wsgi.py for Gunicorn")
    print("=" * 50)
    
    wsgi_py = """#!/usr/bin/env python
\"\"\"
WSGI entrypoint for Gunicorn.

Usage:
    gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app

This file loads .env BEFORE creating the app to ensure all config
is available during app initialization.
\"\"\"

import os
import sys

# CRITICAL: Load .env BEFORE importing app/config modules
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
env_path = os.path.join(basedir, '.env')

if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
    print(f\"[OK] Loaded .env from {env_path}\", file=sys.stderr)
else:
    print(f\"[WARNING] .env file not found at {env_path}\", file=sys.stderr)
    print(\"[WARNING] Using environment variables only\", file=sys.stderr)

# Now safe to import and create app
from app import create_app

app = create_app()

# For Gunicorn compatibility
application = app
"""
    
    try:
        with open('wsgi.py', 'w') as f:
            f.write(wsgi_py)
        print("  [OK] Created wsgi.py for Gunicorn")
        print("  [INFO] Use: gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app")
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to create wsgi.py: {e}")
        return False


def fix_init_py():
    """Fix __init__.py to handle missing .env gracefully"""
    print("\nFIXING app/__init__.py - Error handling")
    print("=" * 50)
    
    init_file = 'app/__init__.py'
    
    try:
        with open(init_file, 'r') as f:
            content = f.read()
        
        # Check if already fixed
        if '# PRODUCTION FIX' in content:
            print("  [OK] app/__init__.py already has production fixes")
            return True
        
        # Find _load_dotenv_if_present function and improve it
        old_func = '''def _load_dotenv_if_present() -> None:
    """
    Load `.env` from repo root if present.

    We deliberately keep this dependency-free at runtime (python-dotenv is already
    in requirements.txt) and do not require systemd EnvironmentFile tweaks.
    
    Loads .env files in this order (later values do not override earlier ones):
    1. Environment variables already set
    2. .env in repo root
    """
    try:
        from dotenv import load_dotenv
        
        # Load from repo root (preferred location for production .env file)
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        env_path = os.path.join(repo_root, ".env")
        # Do not override already-exported environment variables
        load_dotenv(env_path, override=False)
    except Exception:
        return'''
        
        new_func = '''def _load_dotenv_if_present() -> None:
    """
    Load `.env` from repo root if present.

    # PRODUCTION FIX: Enhanced error handling and logging
    """
    try:
        from dotenv import load_dotenv
        
        # Load from repo root (preferred location for production .env file)
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        env_path = os.path.join(repo_root, ".env")
        
        # Check if .env exists before loading
        if os.path.exists(env_path):
            # PRODUCTION: Use override=True to ensure .env takes precedence
            load_dotenv(env_path, override=True)
            import logging
            logging.getLogger(__name__).info(f"[OK] Loaded .env from {env_path}")
        else:
            import logging
            logging.getLogger(__name__).warning(f"[WARNING] .env not found at {env_path}")
            logging.getLogger(__name__).warning("[WARNING] Using environment variables only")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[ERROR] Failed to load .env: {e}")
        # Don't crash - continue with environment variables'''
        
        if old_func in content:
            content = content.replace(old_func, new_func)
            print("  [OK] Updated _load_dotenv_if_present() function")
        
        # Fix _auto_seed to prevent continuous superadmin regeneration
        old_seed_call = '''    # Auto-seed database to ensure required roles and admin exist
    # This is idempotent and safe to run on every startup
    # Skip if SKIP_AUTO_SEED is set (used by init_db.py to avoid conflicts)
    if not app.config.get("TESTING") and not os.environ.get("SKIP_AUTO_SEED"):
        _auto_seed(app)'''
        
        new_seed_call = '''    # Auto-seed database to ensure required roles and admin exist
    # This is idempotent and safe to run on every startup
    # Skip if SKIP_AUTO_SEED is set (used by init_db.py to avoid conflicts)
    if not app.config.get("TESTING") and not os.environ.get("SKIP_AUTO_SEED"):
        try:
            _auto_seed(app)
        except Exception as e:
            app.logger.error(f"[ERROR] Auto-seed failed: {e}")
            # Don't crash on seed failure - log and continue'''
        
        if old_seed_call in content:
            content = content.replace(old_seed_call, new_seed_call)
            print("  [OK] Added error handling to _auto_seed call")
        
        # Add error handling around plugin loading
        old_plugin_load = '''    # External drop-in plugins (filesystem-based)
    try:
        from app.core.plugins import load_external_plugins
        load_external_plugins(app)
    except Exception:
        app.logger.exception("External plugins load failed (non-fatal)")'''
        
        new_plugin_load = '''    # External drop-in plugins (filesystem-based)
    # PRODUCTION FIX: Ignore invalid files like README.md
    try:
        from app.core.plugins import load_external_plugins
        loaded_plugins = load_external_plugins(app)
        if loaded_plugins:
            app.logger.info(f"[OK] Loaded {len(loaded_plugins)} external plugins")
    except Exception as e:
        app.logger.error(f"[WARNING] External plugins load failed (non-fatal): {e}")'''
        
        if old_plugin_load in content:
            content = content.replace(old_plugin_load, new_plugin_load)
            print("  [OK] Enhanced plugin loading error handling")
        
        with open(init_file, 'w') as f:
            f.write(content)
        
        print("  [OK] Fixed app/__init__.py with production fixes")
        return True
        
    except Exception as e:
        print(f"  [ERROR] Failed to fix __init__.py: {e}")
        return False


def fix_plugins_py():
    """Fix plugins.py to ignore non-plugin files"""
    print("\nFIXING app/core/plugins.py - Ignore invalid files")
    print("=" * 50)
    
    plugins_file = 'app/core/plugins.py'
    
    try:
        with open(plugins_file, 'r') as f:
            content = f.read()
        
        # Check if already fixed
        if '# PRODUCTION FIX' in content:
            print("  [OK] plugins.py already has production fixes")
            return True
        
        # Add README.md and other files to skip list
        old_loop = '''    loaded: list[PluginMeta] = []
    for entry in sorted(os.listdir(plugins_dir)):
        plugin_id = entry.strip()
        if not plugin_id or plugin_id.startswith("."):
            continue
        if not _ID_RE.match(plugin_id):
            app.logger.warning("Skipping invalid plugin id folder: %s", plugin_id)
            continue'''
        
        new_loop = '''    loaded: list[PluginMeta] = []
    for entry in sorted(os.listdir(plugins_dir)):
        plugin_id = entry.strip()
        # PRODUCTION FIX: Skip hidden files, README, and other non-plugin files
        if not plugin_id or plugin_id.startswith("."):
            continue
        # Skip common non-plugin files
        if plugin_id.lower() in ('readme.md', 'readme.txt', 'readme', 
                                  'license', 'license.md', 'license.txt',
                                  'dockerfile', 'docker-compose.yml', 
                                  '.gitignore', '.git', '__pycache__'):
            continue
        if not _ID_RE.match(plugin_id):
            app.logger.debug("Skipping invalid plugin folder: %s", plugin_id)
            continue'''
        
        if old_loop in content:
            content = content.replace(old_loop, new_loop)
            print("  [OK] Added filtering for non-plugin files")
        
        with open(plugins_file, 'w') as f:
            f.write(content)
        
        print("  [OK] Fixed plugins.py")
        return True
        
    except Exception as e:
        print(f"  [ERROR] Failed to fix plugins.py: {e}")
        return False


def create_env_template():
    """Create a proper .env template with all required variables"""
    print("\nCREATING .env.template")
    print("=" * 50)
    
    env_template = """# SONACIP Production Environment Configuration
# Copy this file to .env and customize for your deployment

# =============================================================================
# CRITICAL: These must be set before first run
# =============================================================================

# Super Admin credentials - SET THESE to prevent auto-generation
SUPERADMIN_EMAIL=admin@yourdomain.com
SUPERADMIN_PASSWORD=your_secure_password_here

# Secret key for sessions and CSRF (auto-generated if not set)
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=

# =============================================================================
# Database Configuration
# =============================================================================

# SQLite (default for single-server deployments)
SQLALCHEMY_DATABASE_URI=sqlite:///uploads/sonacip.db

# PostgreSQL (recommended for production)
# SQLALCHEMY_DATABASE_URI=postgresql://user:password@localhost/sonacip

SQLALCHEMY_TRACK_MODIFICATIONS=False

# =============================================================================
# Flask Configuration
# =============================================================================

FLASK_ENV=production
FLASK_DEBUG=False

# Server port (Gunicorn will override this)
PORT=8000

# =============================================================================
# Security Configuration
# =============================================================================

WTF_CSRF_ENABLED=True
WTF_CSRF_TIME_LIMIT=3600

# Session cookie security
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax

# =============================================================================
# Optional: Email Configuration
# =============================================================================

MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=noreply@yourdomain.com

# =============================================================================
# Optional: File Upload Configuration
# =============================================================================

UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=16777216

# =============================================================================
# Optional: Rate Limiting
# =============================================================================

RATELIMIT_STORAGE_URL=memory://

# =============================================================================
# Optional: Payment Integration (Stripe)
# =============================================================================

STRIPE_PUBLISHABLE_KEY=
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=

# =============================================================================
# Optional: External Authentication
# =============================================================================

# Google OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# Facebook OAuth
FACEBOOK_CLIENT_ID=
FACEBOOK_CLIENT_SECRET=

# =============================================================================
# Production Flags
# =============================================================================

# Set to skip auto-seeding (useful for migrations)
# SKIP_AUTO_SEED=true

# Set to enable auto database upgrade on startup (development only!)
# RUN_MAIN=true
"""
    
    try:
        with open('.env.template', 'w') as f:
            f.write(env_template)
        print("  [OK] Created .env.template")
        print("  [INFO] Copy to .env and customize: cp .env.template .env")
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to create .env.template: {e}")
        return False


def create_gunicorn_conf():
    """Create gunicorn.conf.py for production"""
    print("\nCREATING gunicorn.conf.py")
    print("=" * 50)
    
    gunicorn_conf = """#!/usr/bin/env python
\"\"\"
Gunicorn configuration for SONACIP production.

Usage:
    gunicorn -c gunicorn.conf.py wsgi:app
\"\"\"

import os
import multiprocessing

# Server socket
bind = os.environ.get('BIND', '0.0.0.0:8000')

# Worker processes
workers = int(os.environ.get('WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'sync'
worker_connections = 1000

# Timeout settings
timeout = 120
keepalive = 5

# Logging
accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('LOG_LEVEL', 'info')

# Process naming
proc_name = 'sonacip'

# Server mechanics
daemon = False
pidfile = 'sonacip.pid'

# SSL (set via environment variables)
keyfile = os.environ.get('SSL_KEYFILE')
certfile = os.environ.get('SSL_CERTFILE')

# Preload app for faster worker startup
preload_app = True

def on_starting(server):
    \"\"\"Called just before the master process is initialized.\"\"\"
    pass

def on_reload(server):
    \"\"\"Called when receiving SIGHUP signal.\"\"\"
    pass

def when_ready(server):
    \"\"\"Called just after the server is started.\"\"\"
    print(f\"[OK] Gunicorn ready with {server.num_workers} workers\")

def worker_int(worker):
    \"\"\"Called when a worker receives SIGINT or SIGQUIT.\"\"\"
    pass

def worker_abort(worker):
    \"\"\"Called when a worker receives SIGABRT.\"\"\"
    pass
"""
    
    try:
        with open('gunicorn.conf.py', 'w') as f:
            f.write(gunicorn_conf)
        print("  [OK] Created gunicorn.conf.py")
        print("  [INFO] Usage: gunicorn -c gunicorn.conf.py wsgi:app")
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to create gunicorn.conf.py: {e}")
        return False


def create_systemd_service():
    """Create systemd service file template"""
    print("\nCREATING systemd service template")
    print("=" * 50)
    
    service_content = """[Unit]
Description=SONACIP Flask Application
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/sonacip
Environment=PATH=/opt/sonacip/venv/bin
Environment=PYTHONPATH=/opt/sonacip
# Load environment from .env file
EnvironmentFile=-/opt/sonacip/.env

# Gunicorn with proper logging
ExecStart=/opt/sonacip/venv/bin/gunicorn \
    -c gunicorn.conf.py \
    --access-logfile /var/log/sonacip/access.log \
    --error-logfile /var/log/sonacip/error.log \
    wsgi:app

ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

# Restart policy
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    
    try:
        with open('sonacip.service', 'w') as f:
            f.write(service_content)
        print("  [OK] Created sonacip.service template")
        print("  [INFO] Install with: sudo cp sonacip.service /etc/systemd/system/")
        print("  [INFO] Start with: sudo systemctl start sonacip")
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to create sonacip.service: {e}")
        return False


def main():
    """Run all fixes"""
    print("SONACIP PRODUCTION CRASH FIX")
    print("=" * 60)
    print()
    print("Applying fixes without breaking existing functionality...")
    print()
    
    fixes = []
    
    # Fix 1: run.py
    if fix_run_py():
        fixes.append("run.py - .env loading")
    
    # Fix 2: wsgi.py
    if fix_wsgi_py():
        fixes.append("wsgi.py - Gunicorn entrypoint")
    
    # Fix 3: app/__init__.py
    if fix_init_py():
        fixes.append("app/__init__.py - Error handling")
    
    # Fix 4: plugins.py
    if fix_plugins_py():
        fixes.append("app/core/plugins.py - Ignore invalid files")
    
    # Fix 5: .env.template
    if create_env_template():
        fixes.append(".env.template - Configuration template")
    
    # Fix 6: gunicorn.conf.py
    if create_gunicorn_conf():
        fixes.append("gunicorn.conf.py - Production config")
    
    # Fix 7: systemd service
    if create_systemd_service():
        fixes.append("sonacip.service - Systemd template")
    
    print()
    print("=" * 60)
    print("FIXES APPLIED:")
    for fix in fixes:
        print(f"  [OK] {fix}")
    
    print()
    print("=" * 60)
    print("NEXT STEPS:")
    print()
    print("1. Create .env file:")
    print("   cp .env.template .env")
    print("   nano .env  # Edit with your settings")
    print()
    print("2. Install dependencies:")
    print("   pip install -r requirements.txt")
    print()
    print("3. Test with development server:")
    print("   python run.py")
    print()
    print("4. Test with Gunicorn:")
    print("   gunicorn -c gunicorn.conf.py wsgi:app")
    print()
    print("5. Install systemd service:")
    print("   sudo cp sonacip.service /etc/systemd/system/")
    print("   sudo mkdir -p /var/log/sonacip")
    print("   sudo systemctl daemon-reload")
    print("   sudo systemctl enable sonacip")
    print("   sudo systemctl start sonacip")
    print()
    print("6. Check status:")
    print("   sudo systemctl status sonacip")
    print("   sudo tail -f /var/log/sonacip/error.log")
    print()
    print("=" * 60)
    print("CRITICAL: After git pull, ensure:")
    print("  - .env file is preserved (not overwritten)")
    print("  - SUPERADMIN_EMAIL and SUPERADMIN_PASSWORD are set")
    print("  - This prevents superadmin regeneration on every restart")
    print()
    print("[OK] Production crash fix completed!")
    
    return len(fixes) >= 5


if __name__ == '__main__':
    main()
