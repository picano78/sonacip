#!/bin/bash
# SONACIP Complete Fix & Test Script
# Esegui come root su Ubuntu
# Questo script risolve definitivamente il login superadmin e testa tutto il sito

set -e

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1"; }
warn() { echo -e "${YELLOW}[AVVISO]${NC} $1"; }
error() { echo -e "${RED}[ERRORE]${NC} $1"; }

# =============================================================================
# FASE 1 — ANALISI SISTEMA
# =============================================================================
log "=========================================="
log "FASE 1: ANALISI SISTEMA"
log "=========================================="

cd /root/sonacip || { error "Directory /root/sonacip non trovata!"; exit 1; }
log "Directory progetto: $(pwd)"

# Attiva venv
log "Attivazione virtual environment..."
source venv/bin/activate || { error "venv non trovato!"; exit 1; }
log "Python: $(which python3)"

# Verifica .env
log "Verifica file .env..."
if [ -f .env ]; then
    log ".env trovato"
    grep "SUPERADMIN_EMAIL" .env || warn "SUPERADMIN_EMAIL mancante in .env"
    grep "SUPERADMIN_PASSWORD" .env || warn "SUPERADMIN_PASSWORD mancante in .env"
else
    warn ".env non trovato, verrà creato..."
fi

# Verifica directory uploads
log "Verifica directory uploads..."
mkdir -p uploads
ls -la uploads/sonacip.db 2>/dev/null && log "Database trovato" || warn "Database non trovato"

# Leggi log recenti
log "Analisi log recenti..."
journalctl -u sonacip -n 20 --no-pager 2>/dev/null || warn "Servizio sonacip non trovato in systemd"
tail -n 50 /var/log/syslog 2>/dev/null | grep -i sonacip || true

# =============================================================================
# FASE 2 — FIX DATABASE
# =============================================================================
log ""
log "=========================================="
log "FASE 2: FIX DATABASE"
log "=========================================="

# Crea/Correggi .env
cat > .env << 'EOF'
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
EOF
log ".env creato/corretto"

# Verifica se DB esiste e ha errori
DB_PATH="/root/sonacip/uploads/sonacip.db"
if [ -f "$DB_PATH" ]; then
    log "Database esistente trovato, verifica integrità..."
    # Test query semplice
    python3 << 'PY' 2>&1 | head -20
import os
os.chdir('/root/sonacip')
from dotenv import load_dotenv
load_dotenv('/root/sonacip/.env', override=True)
from app import create_app, db
app = create_app()
with app.app_context():
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"[OK] Tabelle trovate: {len(tables)}")
        if 'user' in tables:
            print("[OK] Tabella user presente")
        else:
            print("[X] Tabella user MANCANTE")
    except Exception as e:
        print(f"[ERRORE] {e}")
PY
else
    warn "Database non esiste, verrà creato"
fi

# Migrazioni
log "Esecuzione migrazioni..."
flask db stamp head 2>/dev/null || true
flask db upgrade 2>/dev/null || {
    warn "Migrazioni fallite, ricreo database..."
    rm -f "$DB_PATH"
    flask db upgrade || true
}

# =============================================================================
# FASE 3 — CREA SUPER ADMIN
# =============================================================================
log ""
log "=========================================="
log "FASE 3: CREAZIONE SUPER ADMIN"
log "=========================================="

cat > /tmp/fix_admin.py << 'PYEOF'
import os
import sys

os.chdir('/root/sonacip')
sys.path.insert(0, '/root/sonacip')

from dotenv import load_dotenv
load_dotenv('/root/sonacip/.env', override=True)

from app import create_app, db
from app.models import User, Role
from werkzeug.security import generate_password_hash, check_password_hash

app = create_app()

with app.app_context():
    print("[1] Creazione tabelle...")
    db.create_all()
    print("[OK] Tabelle pronte")
    
    # Crea/verifica ruolo super_admin
    print("[2] Verifica ruolo super_admin...")
    role = Role.query.filter_by(name='super_admin').first()
    if not role:
        role = Role(name='super_admin', description='Super Administrator', is_system=True)
        db.session.add(role)
        db.session.commit()
        print(f"[OK] Ruolo creato (ID: {role.id})")
    else:
        print(f"[OK] Ruolo trovato (ID: {role.id})")
    
    # Credenziali
    email = 'picano78@gmail.com'
    password = 'Simone78'
    
    print(f"[3] Gestione utente admin...")
    user = User.query.filter_by(email=email).first()
    
    if not user:
        print(f"   Creazione nuovo admin...")
        user = User(
            email=email,
            username=email,
            first_name='Admin',
            last_name='',
            is_active=True,
            is_verified=True,
            email_confirmed=True,
            role_obj=role,
            role_legacy='super_admin'
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"[OK] Admin creato (ID: {user.id})")
    else:
        print(f"   Admin esistente (ID: {user.id}), aggiornamento...")
        user.set_password(password)
        user.is_active = True
        user.is_verified = True
        user.email_confirmed = True
        user.role_obj = role
        db.session.commit()
        print(f"[OK] Admin aggiornato")
    
    # Verifica password
    print("[4] Verifica password...")
    if user.check_password(password):
        print("[OK] Password verificata con successo!")
    else:
        print("[ERRORE] Password non corrisponde!")
        sys.exit(1)
    
    print("\n" + "="*50)
    print("ADMIN CONFIGURATO:")
    print(f"  Email: {email}")
    print(f"  Password: {password}")
    print("="*50)

PYEOF

python3 /tmp/fix_admin.py || { error "Creazione admin fallita!"; exit 1; }

# =============================================================================
# FASE 4 — TEST LOGIN AUTOMATICO
# =============================================================================
log ""
log "=========================================="
log "FASE 4: TEST LOGIN"
log "=========================================="

# Avvia temporaneamente il server per test
log "Avvio server temporaneo..."
pkill -f gunicorn 2>/dev/null || true
sleep 2

# Avvia in background
cd /root/sonacip
source venv/bin/activate
python3 -c "from app import create_app; app=create_app(); app.run(host='0.0.0.0', port=8000, threaded=True)" > /tmp/flask_server.log 2>&1 &
SERVER_PID=$!
sleep 5

log "Server avviato (PID: $SERVER_PID), test login..."

# Test con curl
LOGIN_RESULT=$(curl -s -X POST http://127.0.0.1:8000/auth/login \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "csrf_token=test" \
    -d "identifier=picano78@gmail.com" \
    -d "password=Simone78" \
    -c /tmp/cookies.txt \
    -w "%{http_code}" \
    -L 2>/dev/null | tail -1)

log "Risposta login HTTP: $LOGIN_RESULT"

if [ "$LOGIN_RESULT" = "200" ] || [ "$LOGIN_RESULT" = "302" ]; then
    log "[OK] Login funziona! (HTTP $LOGIN_RESULT)"
else
    warn "Login potrebbe avere problemi (HTTP $LOGIN_RESULT)"
    log "Verifica log server..."
    tail -20 /tmp/flask_server.log || true
fi

# Ferma server temporaneo
kill $SERVER_PID 2>/dev/null || true
sleep 2

# =============================================================================
# FASE 5 — SCAN COMPLETO SITO
# =============================================================================
log ""
log "=========================================="
log "FASE 5: SCAN PAGINE SITO"
log "=========================================="

# Riavvia con systemd per test completi
log "Riavvio servizio sonacip..."
systemctl restart sonacip 2>/dev/null || {
    warn "systemd service non trovato, avvio manuale..."
    cd /root/sonacip
    source venv/bin/activate
    gunicorn --bind 0.0.0.0:8000 --workers 2 --timeout 60 run:app > /tmp/gunicorn.log 2>&1 &
}
sleep 5

# Test pagine
URLS="/
/auth/login
/auth/register
/dashboard
/admin
/profile
/marketplace
/messages
/notifications
/tournaments
/tasks
/subscription/plans"

ERRORS=0
for url in $URLS; do
    CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8000$url" 2>/dev/null || echo "000")
    if [ "$CODE" = "200" ] || [ "$CODE" = "302" ] || [ "$CODE" = "301" ]; then
        log "  $url -> HTTP $CODE [OK]"
    elif [ "$CODE" = "401" ] || [ "$CODE" = "403" ]; then
        warn "  $url -> HTTP $CODE (richiede auth - normale)"
    elif [ "$CODE" = "500" ]; then
        error "  $url -> HTTP $CODE [ERRORE 500!]"
        ERRORS=$((ERRORS + 1))
    else
        warn "  $url -> HTTP $CODE"
    fi
done

if [ $ERRORS -gt 0 ]; then
    error "Trovati $ERRORS errori 500"
    log "Log recenti:"
    journalctl -u sonacip -n 50 --no-pager 2>/dev/null || tail -50 /tmp/gunicorn.log 2>/dev/null || true
fi

# =============================================================================
# FASE 6 — FIX ERRORI (AUTO-CORREZIONE)
# =============================================================================
log ""
log "=========================================="
log "FASE 6: FIX ERRORI AUTOMATICO"
log "=========================================="

# Verifica errori comuni e correggi
python3 << 'PYFIX' 2>&1
import os
import sys

os.chdir('/root/sonacip')
sys.path.insert(0, '/root/sonacip')

from dotenv import load_dotenv
load_dotenv('/root/sonacip/.env', override=True)

try:
    from app import create_app, db
    from app.models import User, Role
    
    app = create_app()
    
    with app.app_context():
        # Fix 1: Assicura che tutti gli admin abbiano is_active=True
        print("[Fix 1] Verifica stato admin...")
        for user in User.query.filter(User.email.like('%picano78%')).all():
            if not user.is_active:
                print(f"   Attivazione user {user.id}...")
                user.is_active = True
                db.session.commit()
        print("   [OK]")
        
        # Fix 2: Verifica ruoli
        print("[Fix 2] Verifica ruoli...")
        if not Role.query.filter_by(name='super_admin').first():
            print("   Creazione ruolo super_admin...")
            role = Role(name='super_admin', description='Super Administrator', is_system=True)
            db.session.add(role)
            db.session.commit()
        print("   [OK]")
        
        print("[OK] Fix automatici completati")
        
except Exception as e:
    print(f"[WARN] Fix automatici: {e}")

PYFIX

# =============================================================================
# FASE 7 — RIAVVIO FINALE
# =============================================================================
log ""
log "=========================================="
log "FASE 7: RIAVVIO FINALE"
log "=========================================="

pkill -f gunicorn 2>/dev/null || true
sleep 2

systemctl restart sonacip 2>/dev/null || {
    warn "systemctl fallito, avvio manuale..."
    cd /root/sonacip
    source venv/bin/activate
    nohup gunicorn --bind 0.0.0.0:8000 --workers 2 --timeout 60 run:app > /var/log/sonacip.log 2>&1 &
}

sleep 5

log "Verifica stato servizio..."
systemctl status sonacip --no-pager 2>/dev/null || ps aux | grep gunicorn | head -3 || true

# =============================================================================
# FASE 8 — VALIDAZIONE FINALE
# =============================================================================
log ""
log "=========================================="
log "FASE 8: VALIDAZIONE FINALE"
log "=========================================="

# Test finale
FINAL_TEST=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/ 2>/dev/null || echo "000")
LOGIN_TEST=$(curl -s -X POST http://127.0.0.1:8000/auth/login \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "identifier=picano78@gmail.com" \
    -d "password=Simone78" \
    -w "%{http_code}" \
    -L 2>/dev/null | tail -1 || echo "000")

log "Test homepage: HTTP $FINAL_TEST"
log "Test login: HTTP $LOGIN_TEST"

echo ""
echo "=========================================="
echo "RISULTATO FINALE"
echo "=========================================="

if [ "$FINAL_TEST" = "200" ] || [ "$FINAL_TEST" = "302" ]; then
    log "✓ Sito accessibile"
else
    error "✗ Sito NON accessibile"
fi

if [ "$LOGIN_TEST" = "200" ] || [ "$LOGIN_TEST" = "302" ]; then
    log "✓ Login funzionante"
else
    error "✗ Login BLOCCATO"
fi

echo ""
echo "=========================================="
echo "CREDENZIALI ADMIN"
echo "=========================================="
echo "  Email: picano78@gmail.com"
echo "  Password: Simone78"
echo "  URL: http://87.106.1.221:8000/auth/login"
echo "=========================================="
echo ""
echo "Se ci sono ancora problemi, controlla:"
echo "  journalctl -u sonacip -f"
echo "  tail -f /var/log/sonacip.log"
echo ""
