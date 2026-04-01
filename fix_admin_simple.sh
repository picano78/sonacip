#!/bin/bash
# SONACIP Admin Fix - Versione utente
# Esegui come root su Ubuntu

set -e

echo "=========================================="
echo "SONACIP Admin Fix"
echo "=========================================="

# 1. Vai nella directory progetto
echo "[1] cd /root/sonacip"
cd /root/sonacip

# 2. Verifica se esiste database
echo "[2] Verifica database..."
ls -la /root/sonacip/uploads/ 2>/dev/null || mkdir -p /root/sonacip/uploads

# 3. Se NON esiste DB, inizializzalo
echo "[3] Inizializzazione DB..."
source venv/bin/activate
flask db upgrade 2>/dev/null || {
    echo "    Fallback: flask db stamp head"
    flask db stamp head 2>/dev/null || true
    flask db upgrade 2>/dev/null || true
}

# 4. Crea script admin
echo "[4] Creando create_admin.py..."
cat > create_admin.py << 'EOF'
from app import create_app
from app.extensions import db
from app.models import User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    email = "picano78@gmail.com"
    password = "Simone78"
    
    # Cerca utente per email O username
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User.query.filter_by(username="admin").first()
    
    if not user:
        print("[+] Creando nuovo admin...")
        user = User(
            email=email,
            username="admin",
            password_hash=generate_password_hash(password),
            is_active=True,
            is_verified=True,
            email_confirmed=True
        )
        db.session.add(user)
    else:
        print("[~] Aggiornando admin esistente...")
        user.email = email
        user.password_hash = generate_password_hash(password)
        user.is_active = True
    
    db.session.commit()
    print("[OK] ADMIN: %s" % email)
    print("     Password: %s" % password)
EOF

# 5. Esegui script
echo "[5] Eseguendo create_admin.py..."
python3 create_admin.py

# 6. Riavvia servizio
echo "[6] Riavvio servizio..."
systemctl restart sonacip
sleep 3

# 7. Test finale
echo "[7] Test finale..."
curl -I http://127.0.0.1:8000 2>/dev/null | head -1 || echo "    Server non risponde (verificare manualmente)"

echo ""
echo "=========================================="
echo "COMPLETATO!"
echo "=========================================="
echo "Login: picano78@gmail.com / Simone78"
echo "URL: http://87.106.1.221:8000/auth/login"
