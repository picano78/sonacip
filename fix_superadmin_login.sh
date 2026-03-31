#!/bin/bash
# SONACIP Superadmin Login Fix
# Esegui sul server: bash fix_superadmin_login.sh

set -e

echo "=========================================="
echo "SONACIP Superadmin Login Fix"
echo "=========================================="

cd /root/sonacip || { echo "ERRORE: Directory /root/sonacip non trovata"; exit 1; }

# 1. Ferma il servizio
echo "[1] Fermando servizio sonacip..."
systemctl stop sonacip 2>/dev/null || true
pkill -f gunicorn 2>/dev/null || true
sleep 2

# 2. Correggi .env con path assoluto database
echo "[2] Correggendo .env..."
cat > .env << 'EOF'
SUPERADMIN_EMAIL=picano78@gmail.com
SUPERADMIN_PASSWORD=Picano78
DATABASE_URL=sqlite:////root/sonacip/uploads/sonacip.db
SQLALCHEMY_DATABASE_URI=sqlite:////root/sonacip/uploads/sonacip.db
SECRET_KEY=4f8a2b9c1d3e5f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2
FLASK_ENV=production
FLASK_DEBUG=False
PORT=8000
EOF

echo "[OK] .env aggiornato:"
cat .env

# 3. Crea directory uploads se manca
echo "[3] Verifica directory uploads..."
mkdir -p /root/sonacip/uploads

# 4. Verifica se il database esiste
echo "[4] Verifica database..."
DB_PATH="/root/sonacip/uploads/sonacip.db"

if [ -f "$DB_PATH" ]; then
    echo "[OK] Database trovato: $DB_PATH"
    echo "    Dimensione: $(du -h $DB_PATH | cut -f1)"
else
    echo "[INFO] Database non trovato, verrà creato al primo avvio"
fi

# 5. Crea script Python per fix superadmin
echo "[5] Creando script di fix superadmin..."
cat > /tmp/fix_admin.py << 'PYEOF'
import os
import sys

os.chdir('/root/sonacip')

# Carica .env
from dotenv import load_dotenv
load_dotenv('/root/sonacip/.env', override=True)

# Ora importa l'app
sys.path.insert(0, '/root/sonacip')
from app import create_app, db
from app.models import User, Role
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    print("[DB] Connessione database...")
    
    # Crea tabelle se non esistono
    db.create_all()
    print("[DB] Tabelle verificate/create")
    
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
        print("[ROLE] Ruolo super_admin creato")
    else:
        print(f"[ROLE] Ruolo super_admin trovato (ID: {role.id})")
    
    # Cerca superadmin
    email = 'picano78@gmail.com'
    password = 'Picano78'
    
    user = User.query.filter_by(email=email).first()
    
    if not user:
        print(f"[USER] Superadmin non trovato, creazione in corso...")
        user = User(
            email=email,
            username=email,
            first_name='Simone',
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
        print(f"[USER] Superadmin creato: {email}")
    else:
        print(f"[USER] Superadmin trovato (ID: {user.id})")
        print(f"       Email: {user.email}")
        print(f"       Username: {user.username}")
        print(f"       Is Active: {user.is_active}")
        
        # Aggiorna password
        print("[USER] Aggiornamento password...")
        user.set_password(password)
        user.is_active = True
        user.email_confirmed = True
        user.role_obj = role
        user.role_legacy = 'super_admin'
        db.session.commit()
        print("[USER] Password aggiornata")
    
    # Verifica password
    if user.check_password(password):
        print("[OK] Verifica password: SUCCESSO!")
    else:
        print("[ERRORE] Verifica password: FALLITA!")
        sys.exit(1)
    
    print("\n[OK] Superadmin pronto per il login:")
    print(f"  Email: {email}")
    print(f"  Password: {password}")

PYEOF

# 6. Esegui lo script Python
echo "[6] Eseguendo fix superadmin..."
cd /root/sonacip
source venv/bin/activate
python /tmp/fix_admin.py

# 7. Verifica database
echo "[7] Verifica finale database..."
ls -la /root/sonacip/uploads/sonacip.db

# 8. Avvia servizio
echo "[8] Avviando servizio..."
systemctl start sonacip
sleep 5

# 9. Verifica stato
echo "[9] Verifica stato servizio..."
systemctl status sonacip --no-pager || true

echo ""
echo "=========================================="
echo "FIX COMPLETATO!"
echo "=========================================="
echo ""
echo "Prova a fare login con:"
echo "  Email: picano78@gmail.com"
echo "  Password: Picano78"
echo ""
echo "URL: http://87.106.1.221:8000/auth/login"
echo ""
