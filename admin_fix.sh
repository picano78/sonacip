#!/bin/bash
# SONACIP Admin Fix Script
# Esegui come root su Ubuntu

set -e

echo "=========================================="
echo "SONACIP Admin Fix - $(date)"
echo "=========================================="

# 1. Vai nella directory progetto
echo "[1] Entrando in /root/sonacip..."
cd /root/sonacip || { echo "ERRORE: Directory non trovata"; exit 1; }

# 2. Verifica se esiste database
echo "[2] Verifica database..."
if [ -f /root/sonacip/uploads/sonacip.db ]; then
    echo "    Database trovato: $(ls -lh /root/sonacip/uploads/sonacip.db | awk '{print $5}')"
else
    echo "    Database NON trovato"
fi
ls -la /root/sonacip/uploads/ 2>/dev/null || mkdir -p /root/sonacip/uploads

# 3. Attiva venv
echo "[3] Attivazione venv..."
source venv/bin/activate || { echo "ERRORE: venv non trovato"; exit 1; }

# Verifica/crea .env
echo "[3b] Verifica .env..."
if [ ! -f .env ]; then
    echo "    Creando .env..."
    cat > .env << 'ENVFILE'
SUPERADMIN_EMAIL=picano78@gmail.com
SUPERADMIN_PASSWORD=Simone78
DATABASE_URL=sqlite:////root/sonacip/uploads/sonacip.db
SQLALCHEMY_DATABASE_URI=sqlite:////root/sonacip/uploads/sonacip.db
SECRET_KEY=4f8a2b9c1d3e5f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2
FLASK_ENV=production
FLASK_DEBUG=False
PORT=8000
ENVFILE
fi

# 3. Inizializza DB se necessario
echo "[4] Inizializzazione database..."
flask db upgrade 2>/dev/null || echo "    Skip: migrazioni già fatte o errore (continuo...)"

# 4. Crea script Python admin
echo "[5] Creando script create_admin.py..."
cat > /tmp/create_admin.py << 'PYEOF'
import os
import sys

# Setup path
os.chdir('/root/sonacip')
sys.path.insert(0, '/root/sonacip')

# Carica .env
from dotenv import load_dotenv
load_dotenv('/root/sonacip/.env', override=True)

# Importa app
from app import create_app, db
from app.models import User, Role
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    print("[DB] Connessione al database...")
    
    # Crea tutte le tabelle
    db.create_all()
    print("[DB] Tabelle verificate/creare")
    
    # Cerca o crea ruolo super_admin
    role = Role.query.filter_by(name='super_admin').first()
    if not role:
        print("[ROLE] Creando ruolo super_admin...")
        role = Role(
            name='super_admin',
            description='Super Administrator',
            is_system=True
        )
        db.session.add(role)
        db.session.commit()
        print("[ROLE] Creato (ID: %d)" % role.id)
    else:
        print("[ROLE] Trovato (ID: %d)" % role.id)
    
    # Credenziali admin
    email = "picano78@gmail.com"
    password = "Simone78"
    
    # Cerca utente esistente
    user = User.query.filter_by(email=email).first()
    
    if not user:
        print("[ADMIN] Creando nuovo superadmin...")
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
        print("[ADMIN] Creato nuovo admin con ID: %d" % user.id)
    else:
        print("[ADMIN] Trovato esistente (ID: %d)" % user.id)
        print("        Aggiornando password...")
        user.set_password(password)
        user.is_active = True
        user.email_confirmed = True
        user.role_obj = role
        db.session.commit()
        print("[ADMIN] Password aggiornata")
    
    # Verifica password
    if user.check_password(password):
        print("[OK] Verifica password: SUCCESSO!")
    else:
        print("[ERRORE] Verifica password FALLITA!")
        sys.exit(1)
    
    print("\n" + "="*50)
    print("ADMIN PRONTO:")
    print("  Email: %s" % email)
    print("  Password: %s" % password)
    print("="*50)

PYEOF

# 5. Esegui script
echo "[6] Eseguendo script admin..."
python3 /tmp/create_admin.py || { echo "ERRORE: Script fallito"; exit 1; }

# 6. Riavvia servizio
echo "[7] Riavvio servizio sonacip..."
systemctl restart sonacip
sleep 3

# 7. Test finale
echo "[8] Test finale..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000 || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
    echo "[OK] Server risponde HTTP %s" "$HTTP_CODE"
else
    echo "[WARN] Server risponde HTTP %s (controllare logs)" "$HTTP_CODE"
fi

# Status servizio
echo ""
echo "[9] Status servizio:"
systemctl status sonacip --no-pager 2>/dev/null | head -5 || true

echo ""
echo "=========================================="
echo "FIX COMPLETATO!"
echo "=========================================="
echo ""
echo "Prova login:"
echo "  URL: http://87.106.1.221:8000/auth/login"
echo "  Email: picano78@gmail.com"
echo "  Password: Simone78"
echo ""
echo "Se errore, controlla logs:"
echo "  journalctl -u sonacip -f"
