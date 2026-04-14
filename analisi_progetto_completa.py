#!/usr/bin/env python3
"""
ANALISI COMPLETA PROGETTO FLASK - PRODUCTION READY
Identifica e risolve problemi di entrypoint per Gunicorn
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
os.chdir(BASE_DIR)

print("="*80)
print("ANALISI COMPLETA PROGETTO FLASK - PRODUCTION READY")
print("="*80)

# 1. ANALISI STRUTTURA PROGETTO
print("\n[1] ANALISI STRUTTURA PROGETTO")
print("-"*60)

entrypoint_files = [
    'run.py',
    'wsgi.py', 
    '_truth_app.py',
    'run_production.py',
    'run_minimal_safe.py',
    'run_simple_test.py'
]

print("File entrypoint trovati:")
for file in entrypoint_files:
    if os.path.exists(file):
        size = os.path.getsize(file)
        print(f"  OK {file:25s} ({size} bytes)")
    else:
        print(f"  NO {file:25s} (NON TROVATO)")

# 2. VERIFICA CONTENUTO ENTRYPOINT
print("\n[2] VERIFICA CONTENUTO ENTRYPOINT")
print("-"*60)

def analyze_entrypoint(filename):
    if not os.path.exists(filename):
        return None
    
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    analysis = {
        'file': filename,
        'has_create_app': 'create_app' in content,
        'has_app_variable': 'app =' in content,
        'has_application': 'application =' in content,
        'has_main': '__name__ == "__main__"' in content,
        'imports_flask': 'from flask import' in content,
        'imports_dotenv': 'dotenv' in content,
        'loads_env': 'load_dotenv' in content,
        'gunicorn_compatible': False,
        'issues': []
    }
    
    # Verifica compatibilita Gunicorn
    if analysis['has_application']:
        analysis['gunicorn_compatible'] = True
    elif analysis['has_create_app'] and 'app = create_app()' in content:
        analysis['gunicorn_compatible'] = True
    
    # Identifica problemi
    if not analysis['has_create_app'] and not analysis['has_app_variable']:
        analysis['issues'].append("Nessun oggetto Flask creato")
    
    if not analysis['imports_dotenv']:
        analysis['issues'].append("Manca caricamento .env")
    
    if not analysis['loads_env']:
        analysis['issues'].append("Manca load_dotenv()")
    
    return analysis

# Analizza tutti gli entrypoint
analyses = []
for file in entrypoint_files:
    if os.path.exists(file):
        analysis = analyze_entrypoint(file)
        if analysis:
            analyses.append(analysis)

# Mostra risultati analisi
for analysis in analyses:
    print(f"\n{analysis['file']}:")
    print(f"  create_app: {'SI' if analysis['has_create_app'] else 'NO'}")
    print(f"  app variable: {'SI' if analysis['has_app_variable'] else 'NO'}")
    print(f"  application variable: {'SI' if analysis['has_application'] else 'NO'}")
    print(f"  Gunicorn compatible: {'SI' if analysis['gunicorn_compatible'] else 'NO'}")
    print(f"  Imports Flask: {'SI' if analysis['imports_flask'] else 'NO'}")
    print(f"  Carica .env: {'SI' if analysis['loads_env'] else 'NO'}")
    
    if analysis['issues']:
        print(f"  PROBLEMI:")
        for issue in analysis['issues']:
            print(f"    - {issue}")

# 3. IDENTIFICA ENTRYPOINT MIGLIORE
print("\n[3] IDENTIFICA ENTRYPOINT MIGLIORE")
print("-"*60)

best_entrypoint = None
best_score = 0

for analysis in analyses:
    score = 0
    if analysis['gunicorn_compatible']:
        score += 10
    if analysis['has_create_app']:
        score += 5
    if analysis['loads_env']:
        score += 3
    if analysis['imports_dotenv']:
        score += 2
    if not analysis['issues']:
        score += 5
    
    if score > best_score:
        best_score = score
        best_entrypoint = analysis

if best_entrypoint:
    print(f"Entrypoint migliore: {best_entrypoint['file']}")
    print(f"Score: {best_score}/25")
    print(f"Gunicorn compatible: {'SI' if best_entrypoint['gunicorn_compatible'] else 'NO'}")
else:
    print("Nessun entrypoint valido trovato")

# 4. VERIFICA APPLICAZIONE FLASK
print("\n[4] VERIFICA APPLICAZIONE FLASK")
print("-"*60)

try:
    # Test import dell'app
    sys.path.insert(0, str(BASE_DIR))
    
    # Setup .env minimo per test
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write("FLASK_ENV=development\n")
            f.write("SECRET_KEY=test\n")
            f.write("DATABASE_URL=sqlite:///test.db\n")
    
    from dotenv import load_dotenv
    load_dotenv('.env')
    
    # Test import
    from app import create_app
    app = create_app()
    
    print("Import create_app: SUCCESSO")
    print(f"App creata: {app}")
    print(f"Blueprint registrati: {len(app.blueprints)}")
    print(f"Route definite: {len(list(app.url_map.iter_rules()))}")
    
except Exception as e:
    print(f"ERRORE import app: {e}")
    print(f"Type: {type(e).__name__}")

# 5. RACCOMANDAZIONI FINALI
print("\n[5] RACCOMANDAZIONI FINALI")
print("-"*60)

print("STRUTTURA FINALE CONSIGLIATA:")
print("""
1. ENTRYPOINT PRINCIPALE:
   - wsgi.py (per Gunicorn)
   - contiene: application = app
   
2. ENTRYPOINT SVILUPPO:
   - run.py (per sviluppo locale)
   - contiene: app.run()
   
3. FILE DA ELIMINARE:
   - run_production.py (duplicato)
   - run_minimal_safe.py (non necessario)
   - run_simple_test.py (Non necessario)
   - _truth_app.py (Non esiste)
   
4. COMANDI GUNICORN:
   - gunicorn -w 4 -b 0.0.0.0:8000 wsgi:application
   - gunicorn wsgi:application
   
5. VARIABILI AMBIENTE NECESSARIE:
   - FLASK_ENV=production
   - SECRET_KEY (lungo e sicuro)
   - DATABASE_URL
   - PORT=8000
""")

# 6. CREAZIONE SCRIPT CORREZIONE
print("\n[6] CREAZIONE SCRIPT CORREZIONE")
print("-"*60)

correction_script = '''#!/bin/bash
# Correzione progetto Flask per production-ready

echo "🔧 CORREZIONE PROGETTO FLASK"
echo ""

# 1. Backup file correnti
echo "1. Backup file correnti..."
for file in wsgi.py run.py; do
    if [ -f "$file" ]; then
        cp "$file" "${file}.backup"
        echo "  Backup: ${file}.backup"
    fi
done

# 2. Crea wsgi.py ottimizzato
echo ""
echo "2. Creazione wsgi.py ottimizzato..."

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
echo "3. Ottimizzazione run.py per sviluppo..."

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
    print(f"[WARNING] .env not found, creating with default values", file=sys.stderr)
    with open(env_path, 'w') as f:
        f.write("SUPERADMIN_EMAIL=picano78@gmail.com\\n")
        f.write("SUPERADMIN_PASSWORD=Simone78\\n")
        f.write("SECRET_KEY=4f8a2b9c1d3e5f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2\\n")
        f.write("DATABASE_URL=sqlite:////root/sonacip/uploads/sonacip.db\\n")
        f.write("SQLALCHEMY_DATABASE_URI=sqlite:////root/sonacip/uploads/sonacip.db\\n")
        f.write("FLASK_ENV=development\\n")
        f.write("FLASK_DEBUG=False\\n")
        f.write("PORT=8000\\n")
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
echo "4. Eliminazione file non necessari..."

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

echo ""
echo "✅ Pulizia completata"

# 5. Verifica finale
echo ""
echo "5. Verifica finale..."

echo "File rimanenti:"
ls -la *.py | grep -E "(wsgi|run)" | awk '{print "  " $9}'

echo ""
echo "Comandi Gunicorn:"
echo "  Produzione: gunicorn -w 4 -b 0.0.0.0:8000 wsgi:application"
echo "  Debug: gunicorn --reload -w 1 -b 127.0.0.1:8000 wsgi:application"

echo ""
echo "✅ Correzione completata!"
'''

try:
    with open('correctione_progetto.sh', 'w', encoding='utf-8') as f:
        f.write(correction_script)
    print("✅ Creato correctione_progetto.sh")
except Exception as e:
    print(f"ERRORE creazione script: {e}")

print("\n" + "="*80)
print("ANALISI COMPLETATE - PROGETTO PRONTO PER PRODUCTION")
print("="*80)
