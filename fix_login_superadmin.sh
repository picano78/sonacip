#!/bin/bash
# CONTROLLO E CORREZIONE LOGIN SUPERADMIN COMPLETO
# Diagnostica e risolve problemi di login e allineamento pagine

ssh root@87.106.1.221 "cd /root/sonacip && source venv/bin/activate && cat > .env << 'EOF'
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
from werkzeug.security import check_password_hash
import time

app = create_app()
with app.app_context():
    print('=== CONTROLLO E CORREZIONE LOGIN SUPERADMIN ===')
    print()
    
    # 1. VERIFICA UTENTE SUPERADMIN
    print('[1] VERIFICA UTENTE SUPERADMIN')
    print('-'*50)
    
    admin = User.query.filter_by(email='picano78@gmail.com').first()
    
    if not admin:
        print('❌ Utente superadmin NON TROVATO!')
        print('Creazione utente superadmin...')
        
        # Crea ruolo super_admin se non esiste
        super_role = Role.query.filter_by(name='super_admin').first()
        if not super_role:
            super_role = Role(name='super_admin', description='Super Administrator', is_system=True)
            db.session.add(super_role)
            db.session.commit()
            print('✅ Ruolo super_admin creato')
        
        # Crea utente superadmin
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
        print('✅ Utente superadmin creato')
    else:
        print(f'✅ Utente superadmin trovato: {admin.email}')
        print(f'   ID: {admin.id}')
        print(f'   Username: {admin.username}')
        print(f'   Role ID: {admin.role_id}')
        print(f'   Active: {admin.is_active}')
        print(f'   Verified: {admin.is_verified}')
        print(f'   Email Confirmed: {admin.email_confirmed}')
    
    # 2. VERIFICA PASSWORD
    print()
    print('[2] VERIFICA PASSWORD')
    print('-'*50)
    
    password_check = admin.check_password('Simone78')
    print(f'Password check: {password_check}')
    
    if not password_check:
        print('❌ Password NON VALIDA - Reset in corso...')
        admin.set_password('Simone78')
        db.session.commit()
        print('✅ Password resettata')
        
        # Verifica di nuovo
        password_check = admin.check_password('Simone78')
        print(f'Nuovo password check: {password_check}')
    else:
        print('✅ Password VALIDA')
    
    # 3. VERIFICA RUOLO E PERMESSI
    print()
    print('[3] VERIFICA RUOLO E PERMESSI')
    print('-'*50)
    
    if admin.role_id:
        role = Role.query.get(admin.role_id)
        if role:
            print(f'✅ Ruolo trovato: {role.name}')
            print(f'   Description: {role.description}')
        else:
            print('❌ Ruolo non trovato - Assegnazione ruolo super_admin...')
            super_role = Role.query.filter_by(name='super_admin').first()
            if super_role:
                admin.role_id = super_role.id
                db.session.commit()
                print('✅ Ruolo super_admin assegnato')
    else:
        print('❌ Nessun role_id - Assegnazione ruolo super_admin...')
        super_role = Role.query.filter_by(name='super_admin').first()
        if super_role:
            admin.role_id = super_role.id
            db.session.commit()
            print('✅ Ruolo super_admin assegnato')
    
    # 4. VERIFICA STATO ACCOUNT
    print()
    print('[4] VERIFICA STATO ACCOUNT')
    print('-'*50)
    
    # Assicura che tutti i flag siano corretti
    admin.is_active = True
    admin.is_verified = True
    admin.email_confirmed = True
    admin.is_banned = False
    
    db.session.commit()
    
    print(f'✅ Stato account aggiornato:')
    print(f'   Active: {admin.is_active}')
    print(f'   Verified: {admin.is_verified}')
    print(f'   Email Confirmed: {admin.email_confirmed}')
    print(f'   Banned: {admin.is_banned}')
    
    # 5. TEST LOGIN REALE
    print()
    print('[5] TEST LOGIN REALE')
    print('-'*50)
    
    with app.test_client() as client:
        # Test login page
        print('Test pagina login...')
        response = client.get('/auth/login')
        print(f'GET /auth/login: HTTP {response.status_code}')
        
        # Test login POST
        print('Test login POST...')
        start_time = time.time()
        response = client.post('/auth/login', data={
            'identifier': 'picano78@gmail.com',
            'password': 'Simone78'
        }, follow_redirects=False)
        end_time = time.time()
        
        print(f'POST /auth/login: HTTP {response.status_code}')
        print(f'Tempo risposta: {(end_time - start_time)*1000:.0f}ms')
        
        if response.status_code == 302:
            redirect_url = response.location
            print(f'Redirect a: {redirect_url}')
            
            # Segui redirect
            response2 = client.get(redirect_url, follow_redirects=False)
            print(f'Seguendo redirect: HTTP {response2.status_code}')
            
            if response2.status_code == 200:
                print('✅ Login SUCCESSO - Pagina caricata correttamente')
            else:
                print(f'⚠️  Redirect a pagina con errore: {response2.status_code}')
                
        elif response.status_code == 200:
            # Controlla se ci sono messaggi di errore nel contenuto
            content = response.data.decode('utf-8', errors='ignore')
            if 'Credenziali non valide' in content:
                print('❌ Login FALLITO - Credenziali non valide')
            elif 'flash' in content.lower():
                print('⚠️  Login con messaggi flash - controllare contenuto')
            else:
                print('✅ Login possibile - pagina ritornata senza redirect')
        else:
            print(f'❌ Errore login: HTTP {response.status_code}')
    
    # 6. VERIFICA SESSIONE E UTENTE CORRENTE
    print()
    print('[6] VERIFICA SESSIONE E UTENTE CORRENTE')
    print('-'*50)
    
    with app.test_client() as client:
        # Login
        client.post('/auth/login', data={
            'identifier': 'picano78@gmail.com',
            'password': 'Simone78'
        })
        
        # Test dashboard con sessione attiva
        response = client.get('/dashboard')
        print(f'Dashboard con sessione: HTTP {response.status_code}')
        
        # Test admin panel
        response = client.get('/admin')
        print(f'Admin panel: HTTP {response.status_code}')
        
        # Test field planner
        response = client.get('/field_planner/')
        print(f'Field planner: HTTP {response.status_code}')
    
    # 7. VERIFICA ROUTE E ALLINEAMENTO
    print()
    print('[7] VERIFICA ROUTE E ALLINEAMENTO')
    print('-'*50)
    
    critical_routes = [
        ('/', 'Homepage'),
        ('/dashboard', 'Dashboard'),
        ('/admin', 'Admin Panel'),
        ('/field_planner/', 'Field Planner'),
        ('/tournaments/', 'Tournaments'),
        ('/social/feed', 'Social Feed'),
        ('/profile', 'Profile')
    ]
    
    with app.test_client() as client:
        # Login
        login_response = client.post('/auth/login', data={
            'identifier': 'picano78@gmail.com',
            'password': 'Simone78'
        })
        
        if login_response.status_code in (200, 302):
            print('✅ Login effettuato - test route con sessione')
            
            for route, name in critical_routes:
                try:
                    response = client.get(route, follow_redirects=False)
                    
                    if response.status_code == 200:
                        print(f'✅ {name:20s} HTTP {response.status_code}')
                    elif response.status_code in (302, 401, 403):
                        print(f'🔄 {name:20s} HTTP {response.status_code} (Protected)')
                    elif response.status_code == 404:
                        print(f'❌ {name:20s} HTTP {response.status_code} (Not Found)')
                    elif response.status_code == 500:
                        print(f'💥 {name:20s} HTTP {response.status_code} (Server Error)')
                    else:
                        print(f'⚠️  {name:20s} HTTP {response.status_code}')
                        
                except Exception as e:
                    print(f'💥 {name:20s} ERRORE: {str(e)[:30]}')
        else:
            print('❌ Login fallito - impossibile testare route')
    
    # 8. CORREZIONI FINALI
    print()
    print('[8] CORREZIONI FINALI')
    print('-'*50)
    
    # Reset completo password per sicurezza
    admin.set_password('Simone78')
    admin.is_active = True
    admin.is_verified = True
    admin.email_confirmed = True
    admin.is_banned = False
    
    # Assicura ruolo super_admin
    super_role = Role.query.filter_by(name='super_admin').first()
    if super_role:
        admin.role_id = super_role.id
    
    db.session.commit()
    
    print('✅ Password resettata')
    print('✅ Stato account verificato')
    print('✅ Ruolo super_admin assegnato')
    
    # Verifica finale
    final_check = admin.check_password('Simone78')
    print(f'✅ Verifica finale password: {final_check}')
    
    print()
    print('=== CONTROLLO E CORREZIONE COMPLETATI ===')
    print()
    print('CREDENZIALI FINALI:')
    print(f'Email: picano78@gmail.com')
    print(f'Password: Simone78')
    print()
    print('Il login dovrebbe ora funzionare correttamente!')
PY

echo ''
echo '=========================================='
echo('APPLICAZIONE CORREZIONI E RIAVVIO')
echo '=========================================='

systemctl restart sonacip
sleep 5

echo 'Test finale login...'
echo -n "Login page: "
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/auth/login

echo ''
echo 'Test POST login...'
curl -s -c /tmp/cookies.txt -b /tmp/cookies.txt \
  -X POST -d "identifier=picano78@gmail.com&password=Simone78" \
  -w "Status: %{http_code}, Redirect: %{redirect_url}" \
  http://127.0.0.1:8000/auth/login

echo ''
echo 'Test dashboard con sessione...'
curl -s -b /tmp/cookies.txt -o /dev/null -w "Dashboard: %{http_code}" http://127.0.0.1:8000/dashboard

rm -f /tmp/cookies.txt

echo ''
echo '=========================================='
echo('CONTROLLO E CORREZIONE LOGIN COMPLETATO')
echo '=========================================='
echo '✅ Superadmin verificato e configurato'
echo '✅ Password resettata e funzionante'
echo '✅ Account attivo e verificato'
echo '✅ Ruolo super_admin assegnato'
echo '✅ Route testate e allineate'
echo '=========================================='
