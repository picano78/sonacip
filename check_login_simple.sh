#!/bin/bash
# CONTROLLO LOGIN SUPERADMIN - VERSIONE SEMPLIFICATA

echo "=== CONTROLLO LOGIN SUPERADMIN ==="

cd /root/sonacip
source venv/bin/activate

# Setup .env
cat > .env << 'EOF'
SUPERADMIN_EMAIL=picano78@gmail.com
SUPERADMIN_PASSWORD=Simone78
DATABASE_URL=sqlite:////root/sonacip/uploads/sonacip.db
SQLALCHEMY_DATABASE_URI=sqlite:////root/sonacip/uploads/sonacip.db
SECRET_KEY=4f8a2b9c1d3e5f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2
FLASK_ENV=production
PORT=8000
WTF_CSRF_ENABLED=True
WTF_CSRF_TIME_LIMIT=None
EOF

python3 << 'PY'
from app import create_app, db
from app.models import User, Role

app = create_app()
with app.app_context():
    print("1. Verifica utente superadmin...")
    
    admin = User.query.filter_by(email='picano78@gmail.com').first()
    
    if not admin:
        print("❌ Utente non trovato - Creazione in corso...")
        
        # Crea ruolo
        super_role = Role.query.filter_by(name='super_admin').first()
        if not super_role:
            super_role = Role(name='super_admin', description='Super Administrator', is_system=True)
            db.session.add(super_role)
            db.session.commit()
        
        # Crea utente
        admin = User(
            email='picano78@gmail.com',
            username='picano78@gmail.com',
            first_name='Simone',
            last_name='Admin',
            is_active=True,
            is_verified=True,
            email_confirmed=True,
            role_id=super_role.id
        )
        admin.set_password('Simone78')
        db.session.add(admin)
        db.session.commit()
        print("✅ Utente creato")
    else:
        print(f"✅ Utente trovato: {admin.email}")
    
    print("2. Verifica password...")
    password_check = admin.check_password('Simone78')
    print(f"Password valida: {password_check}")
    
    if not password_check:
        print("❌ Password non valida - Reset...")
        admin.set_password('Simone78')
        db.session.commit()
        print("✅ Password resettata")
    
    print("3. Verifica stato account...")
    admin.is_active = True
    admin.is_verified = True
    admin.email_confirmed = True
    admin.is_banned = False
    
    # Assicura ruolo
    super_role = Role.query.filter_by(name='super_admin').first()
    if super_role:
        admin.role_id = super_role.id
    
    db.session.commit()
    
    print(f"✅ Stato: Active={admin.is_active}, Verified={admin.is_verified}, EmailConfirmed={admin.email_confirmed}")
    
    print("4. Test login...")
    from flask import Flask
    with app.test_client() as client:
        response = client.post('/auth/login', data={
            'identifier': 'picano78@gmail.com',
            'password': 'Simone78'
        }, follow_redirects=False)
        
        print(f"Login POST: HTTP {response.status_code}")
        
        if response.status_code == 302:
            print(f"✅ Login SUCCESSO - Redirect a: {response.location}")
        elif response.status_code == 200:
            content = response.data.decode('utf-8', errors='ignore')
            if 'Credenziali non valide' in content:
                print("❌ Login FALLITO - Credenziali non valide")
            else:
                print("✅ Login possibile - pagina ritornata")
        else:
            print(f"❌ Errore login: HTTP {response.status_code}")
    
    print("5. Test pagine con sessione...")
    with app.test_client() as client:
        # Login
        client.post('/auth/login', data={
            'identifier': 'picano78@gmail.com',
            'password': 'Simone78'
        })
        
        # Test pagine
        pages = [
            ('/', 'Homepage'),
            ('/dashboard', 'Dashboard'),
            ('/admin', 'Admin'),
            ('/field_planner/', 'Field Planner')
        ]
        
        for route, name in pages:
            response = client.get(route)
            status = "✅" if response.status_code == 200 else f"❌ {response.status_code}"
            print(f"  {name}: {status}")

print ""
echo "6. Riavvio servizio..."
systemctl restart sonacip
sleep 3

echo "7. Test finale..."
echo -n "Login page: "
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/auth/login

echo ""
echo "=== CONTROLLO COMPLETATO ==="
echo "Credenziali: picano78@gmail.com / Simone78"
PY
