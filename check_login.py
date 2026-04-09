from app import create_app, db
from app.models import User, Role

app = create_app()
with app.app_context():
    print('=== CONTROLLO LOGIN SUPERADMIN ===')
    
    print('1. Verifica utente superadmin...')
    
    admin = User.query.filter_by(email='picano78@gmail.com').first()
    
    if not admin:
        print('❌ Utente non trovato - Creazione in corso...')
        
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
        print('✅ Utente creato')
    else:
        print(f'✅ Utente trovato: {admin.email}')
    
    print('2. Reset password per sicurezza...')
    admin.set_password('Simone78')
    admin.is_active = True
    admin.is_verified = True
    admin.email_confirmed = True
    admin.is_banned = False
    
    # Assicura ruolo
    super_role = Role.query.filter_by(name='super_admin').first()
    if super_role:
        admin.role_id = super_role.id
    
    db.session.commit()
    
    print('3. Verifica password...')
    password_check = admin.check_password('Simone78')
    print(f'Password valida: {password_check}')
    
    print('4. Test login...')
    with app.test_client() as client:
        response = client.post('/auth/login', data={
            'identifier': 'picano78@gmail.com',
            'password': 'Simone78'
        }, follow_redirects=False)
        
        print(f'Login POST: HTTP {response.status_code}')
        
        if response.status_code == 302:
            print(f'✅ Login SUCCESSO - Redirect a: {response.location}')
        elif response.status_code == 200:
            content = response.data.decode('utf-8', errors='ignore')
            if 'Credenziali non valide' in content:
                print('❌ Login FALLITO - Credenziali non valide')
            else:
                print('✅ Login possibile - pagina ritornata')
        else:
            print(f'❌ Errore login: HTTP {response.status_code}')
    
    print('5. Test pagine con sessione...')
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
            print(f'  {name}: {status}')

print('')
print('=== CONTROLLO COMPLETATO ===')
print('Credenziali: picano78@gmail.com / Simone78')
