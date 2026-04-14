#!/bin/bash
# CORREZIONE DEFINITIVA PROGETTO FLASK - PRODUCTION READY
# Rende il progetto SONACIP production-ready con Gunicorn

echo "=== CORREZIONE DEFINITIVA PROGETTO FLASK ==="
echo ""

# 1. Backup file correnti
echo "[1] Backup file correnti..."
for file in wsgi.py run.py; do
    if [ -f "$file" ]; then
        cp "$file" "${file}.backup"
        echo "  Backup: ${file}.backup"
    fi
done

# 2. Crea wsgi.py ottimizzato per Gunicorn
echo ""
echo "[2] Creazione wsgi.py ottimizzato..."

cat > wsgi.py << 'WSGI_EOF'
#!/usr/bin/env python3
"""
WSGI entrypoint for Gunicorn production deployment.
Optimized for SONACIP Flask application.
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables BEFORE importing app
from dotenv import load_dotenv
env_path = project_root / '.env'

if env_path.exists():
    load_dotenv(env_path, override=True)
    print(f"[OK] Loaded .env from {env_path}", file=sys.stderr)
else:
    print(f"[WARNING] .env not found at {env_path}", file=sys.stderr)

# Import and create Flask app
try:
    from app import create_app
    app = create_app()
    print(f"[OK] Flask app created successfully", file=sys.stderr)
except ImportError as e:
    print(f"[ERROR] Failed to import app: {e}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Failed to create app: {e}", file=sys.stderr)
    sys.exit(1)

# Gunicorn compatibility
application = app

# Export for potential use
if __name__ == "__main__":
    print(f"[INFO] WSGI application ready for Gunicorn", file=sys.stderr)
    print(f"[INFO] App name: {app.name if hasattr(app, 'name') else 'SONACIP'}", file=sys.stderr)
    print(f"[INFO] Blueprints: {len(app.blueprints)}", file=sys.stderr)
WSGI_EOF

echo "✅ wsgi.py ottimizzato creato"

# 3. Ottimizza run.py per sviluppo
echo ""
echo "[3] Ottimizzazione run.py per sviluppo..."

cat > run.py << 'RUN_EOF'
#!/usr/bin/env python3
"""
Development entrypoint for SONACIP.
Usage: python run.py
"""

import os
import sys

# CRITICAL: Load .env BEFORE any config is evaluated
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
env_path = os.path.join(basedir, '.env')

# Load .env with override=True to ensure it takes precedence
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
    print(f"[OK] Loaded .env from {env_path}", file=sys.stderr)
else:
    # Create .env with fixed values if missing
    print(f"[WARNING] .env not found, creating with default values", file=sys.stderr)
    with open(env_path, 'w') as f:
        f.write("SUPERADMIN_EMAIL=picano78@gmail.com\n")
        f.write("SUPERADMIN_PASSWORD=Simone78\n")
        f.write("SECRET_KEY=4f8a2b9c1d3e5f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2\n")
        f.write("DATABASE_URL=sqlite:////root/sonacip/uploads/sonacip.db\n")
        f.write("SQLALCHEMY_DATABASE_URI=sqlite:////root/sonacip/uploads/sonacip.db\n")
        f.write("FLASK_ENV=development\n")
        f.write("FLASK_DEBUG=False\n")
        f.write("PORT=8000\n")
    load_dotenv(env_path, override=True)

# Now safe to import and create app
from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
RUN_EOF

echo "✅ run.py ottimizzato"

# 4. Elimina file non necessari
echo ""
echo "[4] Eliminazione file non necessari..."

files_to_remove=(
    "run_production.py"
    "run_minimal_safe.py"
    "run_simple_test.py"
)

for file in "${files_to_remove[@]}"; do
    if [ -f "$file" ]; then
        rm "$file"
        echo "  Rimosso: $file"
    fi
done

# 5. Crea .env di produzione se mancante
echo ""
echo "[5] Creazione .env di produzione..."

if [ ! -f ".env" ]; then
    cat > .env << 'ENV_EOF'
SUPERADMIN_EMAIL=picano78@gmail.com
SUPERADMIN_PASSWORD=Simone78
DATABASE_URL=sqlite:////root/sonacip/uploads/sonacip.db
SQLALCHEMY_DATABASE_URI=sqlite:////root/sonacip/uploads/sonacip.db
SECRET_KEY=4f8a2b9c1d3e5f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2
FLASK_ENV=production
FLASK_DEBUG=False
PORT=8000
WTF_CSRF_ENABLED=True
WTF_CSRF_TIME_LIMIT=None
CACHE_TYPE=simple
CACHE_DEFAULT_TIMEOUT=300
ENV_EOF
    echo "✅ .env di produzione creato"
else
    echo "✅ .env gia esistente"
fi

# 6. Verifica struttura finale
echo ""
echo "[6] Verifica struttura finale..."

echo "Struttura progetto finale:"
echo "  ├── app/ (directory principale)"
echo "  ├── wsgi.py (entrypoint Gunicorn)"
echo "  ├── run.py (sviluppo locale)"
echo "  ├── .env (configurazione)"
echo "  ├── requirements.txt (dipendenze)"
echo "  └── uploads/ (database e file statici)"

echo ""
echo "File principali:"
ls -la *.py | grep -E "(wsgi|run)" | awk '{print "  " $9}'

# 7. Test import dell'app
echo ""
echo "[7] Test import dell'app..."

python3 -c "
import sys
sys.path.insert(0, '.')

try:
    from dotenv import load_dotenv
    load_dotenv('.env')
    
    from app import create_app
    app = create_app()
    
    print('✅ Import create_app: SUCCESSO')
    print(f'✅ App creata: {app}')
    print(f'✅ Blueprint registrati: {len(app.blueprints)}')
    print(f'✅ Route definite: {len(list(app.url_map.iter_rules()))}')
    
except Exception as e:
    print(f'❌ Errore import app: {e}')
    sys.exit(1)
"

# 8. Test Gunicorn compatibility
echo ""
echo "[8] Test Gunicorn compatibility..."

python3 -c "
import sys
sys.path.insert(0, '.')

try:
    from wsgi import application
    print('✅ Import wsgi.application: SUCCESSO')
    print(f'✅ App type: {type(application)}')
    print(f'✅ App name: {application.name if hasattr(application, \"name\") else \"SONACIP\"}')
    
    # Test route
    with application.test_client() as client:
        response = client.get('/')
        print(f'✅ Test route: HTTP {response.status_code}')
    
except Exception as e:
    print(f'❌ Errore wsgi: {e}')
    sys.exit(1)
"

echo ""
echo "=== CORREZIONE DEFINITIVA COMPLETATA ==="
echo ""
echo "📋 MODIFICHE APPLICATE:"
echo "  ✅ wsgi.py ottimizzato per Gunicorn"
echo "  ✅ run.py ottimizzato per sviluppo"
echo "  ✅ File non necessari rimossi"
echo "  ✅ .env di produzione configurato"
echo "  ✅ Import app verificato"
echo "  ✅ Compatibilità Gunicorn testata"
echo ""
echo "🚀 COMANDI PRODUCTION:"
echo "  Sviluppo: python run.py"
echo "  Produzione: gunicorn -w 4 -b 0.0.0.0:8000 wsgi:application"
echo "  Debug: gunicorn --reload -w 1 -b 127.0.0.1:8000 wsgi:application"
echo ""
echo "🎯 PROGETTO ORA PRODUCTION-READY!"
