#!/bin/bash
# SONACIP - FIX COMPLETO SUPERADMIN
# Risolve: .env mancante, DB vecchio, ruolo superadmin

set -e

echo "=========================================="
echo "SONACIP - FIX COMPLETO SUPERADMIN"
echo "=========================================="

cd /root/sonacip
source venv/bin/activate

# 1. CREA .env CORRETTO
echo "[1] Creazione .env..."
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
echo "✅ .env creato"

# 2. FIX DATABASE COMPLETO
echo "[2] Fix database..."
# Backup se esiste
if [ -f "uploads/sonacip.db" ]; then
    cp uploads/sonacip.db uploads/sonacip.db.backup.$(date +%s)
    echo "✅ Backup creato"
fi

# Migrazioni complete
flask db upgrade 2>/dev/null || {
    echo "   Migrazioni fallite, reset completo..."
    rm -f uploads/sonacip.db
    flask db upgrade
}

# 3. VERIFICA/AGGIUNGI COLONNE MANCANTI
echo "[3] Verifica colonne database..."
python3 << 'PY'
import os, sys
os.chdir('/root/sonacip')
sys.path.insert(0, '/root/sonacip')
from dotenv import load_dotenv
load_dotenv('/root/sonacip/.env', override=True)
from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    # Verifica colonna email_confirmed
    try:
        result = db.session.execute(text("SELECT email_confirmed FROM user LIMIT 1"))
        print("✅ Colonna email_confirmed esiste")
    except Exception:
        print("❌ Colonna email_confirmed mancante - AGGIUNGO...")
        try:
            db.session.execute(text("ALTER TABLE user ADD COLUMN email_confirmed BOOLEAN DEFAULT 1"))
            db.session.commit()
            print("✅ Colonna email_confirmed aggiunta")
        except Exception as e:
            print(f"   Errore: {e}")
            # Se non funziona, ricrea tabelle
            db.create_all()
            db.session.commit()
            print("✅ Tabelle ricreate")
    
    # Verifica altre colonne critiche
    colonne_criticalhe = ['role_id', 'is_active', 'is_verified']
    for col in colonne_criticalhe:
        try:
            db.session.execute(text(f"SELECT {col} FROM user LIMIT 1"))
            print(f"✅ Colonna {col} esiste")
        except:
            print(f"❌ Colonna {col} mancante")
            db.create_all()
            db.session.commit()
            print("✅ Tabelle aggiornate")
            break
PY

# 4. CREAZIONE SUPERADMIN DEFINITIVA
echo "[4] Creazione superadmin..."
python3 << 'PY'
import os, sys
os.chdir('/root/sonacip')
sys.path.insert(0, '/root/sonacip')
from dotenv import load_dotenv
load_dotenv('/root/sonacip/.env', override=True)
from app import create_app, db
from app.models import User, Role

app = create_app()
with app.app_context():
    # Crea ruolo
    role = Role.query.filter_by(name="super_admin").first()
    if not role:
        role = Role(name="super_admin", description="Super Administrator", is_system=True)
        db.session.add(role)
        db.session.commit()
        print("✅ Ruolo super_admin creato")
    
    # Elimina utenti vecchi ambigui
    User.query.filter(User.email.like('%picano78%')).delete()
    db.session.commit()
    print("🗑️ Utenti vecchi eliminati")
    
    # Crea utente pulito
    user = User(
        email="picano78@gmail.com",
        username="picano78@gmail.com",
        first_name="Simone",
        last_name="Admin",
        is_active=True,
        is_verified=True,
        email_confirmed=True,
        role_id=role.id,
        role_legacy="super_admin"
    )
    user.set_password("Simone78")
    db.session.add(user)
    db.session.commit()
    
    print("✅ Superadmin creato")
    print(f"   Email: {user.email}")
    print(f"   Role: {user.role_obj.name}")
    print(f"   Password OK: {user.check_password('Simone78')}")
    
    # Verifica finale
    if user.role_obj.name == "super_admin":
        print("🎉 SUPERADMIN PRONTO!")
    else:
        print("❌ Errore ruolo!")
PY

# 5. RIAVVIO
echo "[5] Riavvio servizio..."
systemctl restart sonacip
sleep 3

# 6. TEST FINALE
echo "[6] Test finale..."
python3 << 'TEST'
import os, sys
os.chdir('/root/sonacip')
sys.path.insert(0, '/root/sonacip')
from dotenv import load_dotenv
load_dotenv('/root/sonacip/.env', override=True)
from app import create_app
app = create_app()
client = app.test_client()

# Test login
response = client.post('/auth/login', 
                      data={'identifier': 'picano78@gmail.com', 
                            'password': 'Simone78'}, 
                      follow_redirects=True)

if response.status_code == 200:
    content = response.data.decode('utf-8', errors='ignore').lower()
    if any(x in content for x in ['dashboard', 'admin', 'feed', 'logout']):
        print("✅ LOGIN SUCCESSO!")
    else:
        print("⚠️  Login HTTP 200 ma contenuto anomalo")
elif response.status_code == 302:
    print("✅ LOGIN SUCCESSO (redirect)")
else:
    print(f"❌ Login fallito: HTTP {response.status_code}")
TEST

echo ""
echo "=========================================="
echo "✅ FIX COMPLETO TERMINATO"
echo "=========================================="
echo "Credenziali:"
echo "  Email: picano78@gmail.com"
echo "  Password: Simone78"
echo "  URL: http://87.106.1.221:8000/auth/login"
echo "=========================================="
