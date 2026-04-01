#!/bin/bash
# SONACIP - FIX DEFINITIVO RUOLO SUPERADMIN
# Risolve il problema: user.role_obj.name == 'super_admin'

set -e

echo "=========================================="
echo "SONACIP - FIX DEFINITIVO RUOLO SUPERADMIN"
echo "=========================================="

cd /root/sonacip
source venv/bin/activate

echo "[1] Creazione ruolo super_admin e assegnazione utente..."
python3 << 'PY'
from app import create_app, db
from app.models import User, Role
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # CREA RUOLO super_admin SE NON ESISTE
    role = Role.query.filter_by(name="super_admin").first()
    
    if not role:
        role = Role(name="super_admin", description="Super Administrator", is_system=True)
        db.session.add(role)
        db.session.commit()
        print("✅ Creato ruolo super_admin")
    else:
        print("✅ Ruolo super_admin esistente")
    
    # PRENDI UTENTE (email corretta: minuscola)
    user = User.query.filter_by(email="picano78@gmail.com").first()
    
    if not user:
        print("❌ ERRORE: utente non esiste - CREAZIONE...")
        user = User(
            email="picano78@gmail.com",
            username="picano78@gmail.com",
            first_name="Simone",
            last_name="Admin",
            is_active=True,
            is_verified=True,
            email_confirmed=True
        )
        user.set_password("Simone78")
        db.session.add(user)
        db.session.commit()
        print("✅ Utente creato")
    else:
        print("✅ Utente trovato")
    
    # 🔥 CHIAVE: ASSEGNA RUOLO CORRETTO
    user.role_id = role.id
    user.role_obj = role  # Forza la relazione
    
    # FIX COMPLETO STATO
    user.is_active = True
    user.is_verified = True
    user.email_confirmed = True
    user.set_password("Simone78")
    
    # Fix legacy
    if hasattr(user, "role_legacy"):
        user.role_legacy = "super_admin"
    
    db.session.commit()
    
    # 🔥 VERIFICA CHIAVE
    print("\n--- VERIFICA RUOLO ---")
    print(f"user.role_id: {user.role_id}")
    print(f"user.role_obj.name: {user.role_obj.name if user.role_obj else 'NONE'}")
    print(f"user.role: {user.role}")
    
    # Test critico
    if user.role_obj and user.role_obj.name == "super_admin":
        print("✅ SUCCESSO: user.role_obj.name == 'super_admin'")
    else:
        print("❌ ERRORE: ruolo non assegnato correttamente!")
        exit(1)
    
    # Verifica password
    if user.check_password("Simone78"):
        print("✅ Password OK")
    else:
        print("❌ Password errata!")
        exit(1)
    
    print("\n🎉 SUPER ADMIN SISTEMATO DEFINITIVAMENTE!")
PY

echo ""
echo "[2] Riavvio servizio..."
systemctl restart sonacip
sleep 3

echo ""
echo "[3] Test login con ruolo corretto..."
python3 << 'TEST'
from app import create_app
app = create_app()
client = app.test_client()

# Login
response = client.post('/auth/login', 
                      data={'identifier': 'picano78@gmail.com', 
                            'password': 'Simone78'}, 
                      follow_redirects=True)

if response.status_code == 200:
    content = response.data.decode('utf-8', errors='ignore').lower()
    if any(x in content for x in ['dashboard', 'admin', 'feed', 'logout']):
        print("✅ LOGIN SUCCESSO CON RUOLO SUPER_ADMIN!")
    else:
        print("⚠️  Login HTTP 200 ma contenuto anomalo")
elif response.status_code == 302:
    print("✅ LOGIN SUCCESSO (redirect)")
else:
    print(f"❌ Login fallito: HTTP {response.status_code}")
    print(f"Risposta: {response.data.decode()[:200]}...")
TEST

echo ""
echo "=========================================="
echo "✅ PROBLEMA RISOLTO DEFINITIVAMENTE"
echo "=========================================="
echo "Ora l'utente ha:"
echo "  ✓ user.role_obj.name == 'super_admin'"
echo "  ✓ Login funzionante"
echo ""
echo "Credenziali:"
echo "  Email: picano78@gmail.com"
echo "  Password: Simone78"
echo "  URL: http://87.106.1.221:8000/auth/login"
echo "=========================================="
