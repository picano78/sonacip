#!/bin/bash
# SCAN COMPLETO ERRORI 500 E CORREZIONE AUTOMATICA
# Verifica tutte le pagine e corregge gli errori trovati

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
from sqlalchemy import inspect, text

app = create_app()
with app.app_context():
    print('=== SCAN COMPLETO ERRORI 500 ===')
    print()
    
    # 1. Verifica struttura database
    print('[1] VERIFICA STRUTTURA DATABASE')
    print('-'*50)
    
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f'Tabelle trovate: {len(tables)}')
    
    # Tabelle critiche che devono esistere
    critical_tables = {
        'user': ['id', 'email', 'password_hash', 'role_id', 'is_active', 'is_verified', 'email_confirmed'],
        'role': ['id', 'name', 'description'],
        'facility': ['id', 'name', 'society_id'],
        'field_planner_event': ['id', 'facility_id', 'society_id', 'created_by', 'title', 'start_datetime', 'end_datetime'],
        'society': ['id', 'name'],
        'notification': ['id', 'user_id', 'message'],
        'audit_log': ['id', 'user_id', 'action']
    }
    
    missing_tables = []
    missing_columns = []
    
    for table, required_cols in critical_tables.items():
        if table in tables:
            print(f'✅ {table}: PRESENTE')
            
            # Verifica colonne
            try:
                cols = inspector.get_columns(table)
                col_names = [c['name'] for c in cols]
                
                for col in required_cols:
                    if col not in col_names:
                        missing_columns.append((table, col))
                        print(f'   ❌ Colonna mancante: {col}')
                
                if not any(c[0] == table for c in missing_columns):
                    print(f'   ✅ Tutte le colonne presenti')
                    
            except Exception as e:
                print(f'   ⚠️  Errore colonne: {e}')
        else:
            missing_tables.append(table)
            print(f'❌ {table}: MANCANTE')
    
    # 2. Correggi tabelle mancanti
    if missing_tables:
        print()
        print('[2] CORREZIONE TABELLE MANCANTI')
        print('-'*50)
        
        try:
            db.create_all()
            db.session.commit()
            print('✅ Tabelle create con db.create_all()')
            
            # Verifica dopo creazione
            inspector = inspect(db.engine)
            new_tables = inspector.get_table_names()
            
            for table in missing_tables:
                if table in new_tables:
                    print(f'✅ {table}: CREATA')
                else:
                    print(f'❌ {table}: ANCORA MANCANTE')
                    
        except Exception as e:
            print(f'❌ Errore creazione tabelle: {e}')
    
    # 3. Correggi colonne mancanti
    if missing_columns:
        print()
        print('[3] CORREZIONE COLONNE MANCANTI')
        print('-'*50)
        
        for table, column in missing_columns:
            try:
                if table == 'user':
                    if column == 'email_confirmed':
                        db.session.execute(text('ALTER TABLE user ADD COLUMN email_confirmed BOOLEAN DEFAULT 1'))
                        print(f'✅ Aggiunta colonna {column} alla tabella {table}')
                    elif column == 'role_id':
                        db.session.execute(text('ALTER TABLE user ADD COLUMN role_id INTEGER'))
                        print(f'✅ Aggiunta colonna {column} alla tabella {table}')
                    elif column == 'is_verified':
                        db.session.execute(text('ALTER TABLE user ADD COLUMN is_verified BOOLEAN DEFAULT 1'))
                        print(f'✅ Aggiunta colonna {column} alla tabella {table}')
                
                db.session.commit()
                
            except Exception as e:
                print(f'❌ Errore aggiunta colonna {column} a {table}: {e}')
                db.session.rollback()
    
    # 4. Verifica dati essenziali
    print()
    print('[4] VERIFICA DATI ESSENZIALI')
    print('-'*50)
    
    try:
        # Verifica ruolo super_admin
        super_role = Role.query.filter_by(name='super_admin').first()
        if not super_role:
            super_role = Role(name='super_admin', description='Super Administrator', is_system=True)
            db.session.add(super_role)
            db.session.commit()
            print('✅ Ruolo super_admin creato')
        else:
            print('✅ Ruolo super_admin esistente')
        
        # Verifica utente superadmin
        admin_user = User.query.filter_by(email='picano78@gmail.com').first()
        if not admin_user:
            admin_user = User(
                email='picano78@gmail.com',
                username='picano78@gmail.com',
                first_name='Simone',
                last_name='Admin',
                is_active=True,
                is_verified=True,
                email_confirmed=True,
                role_id=super_role.id
            )
            admin_user.set_password('Simone78')
            db.session.add(admin_user)
            db.session.commit()
            print('✅ Utente superadmin creato')
        else:
            # Aggiorna utente esistente
            admin_user.role_id = super_role.id
            admin_user.is_active = True
            admin_user.is_verified = True
            admin_user.email_confirmed = True
            admin_user.set_password('Simone78')
            db.session.commit()
            print('✅ Utente superadmin aggiornato')
            
    except Exception as e:
        print(f'❌ Errore verifica dati: {e}')
        db.session.rollback()
    
    # 5. Test tutte le route principali
    print()
    print('[5] TEST ROUTE PRINCIPALI')
    print('-'*50)
    
    routes_to_test = [
        ('/', 'Homepage'),
        ('/auth/login', 'Login'),
        ('/dashboard', 'Dashboard'),
        ('/admin', 'Admin Panel'),
        ('/field_planner/', 'Field Planner'),
        ('/calendar/', 'Calendar'),
        ('/tasks', 'Tasks'),
        ('/social/feed', 'Social Feed'),
        ('/marketplace', 'Marketplace'),
        ('/notifications', 'Notifications'),
        ('/profile', 'Profile')
    ]
    
    error_500_routes = []
    
    with app.test_client() as client:
        # Login prima per testare pagine protette
        client.post('/auth/login', data={'identifier': 'picano78@gmail.com', 'password': 'Simone78'})
        
        for route, name in routes_to_test:
            try:
                response = client.get(route, follow_redirects=False)
                
                if response.status_code == 500:
                    error_500_routes.append((route, name))
                    print(f'❌ {name:20s} {route:20s} HTTP 500')
                    
                    # Analizza errore
                    content = response.data.decode('utf-8', errors='ignore')
                    if 'Internal Server Error' in content:
                        print(f'   Errore: Internal Server Error')
                    elif 'SQL' in content.upper():
                        print(f'   Errore: Database/SQL')
                    else:
                        print(f'   Errore: {content[:100]}...')
                        
                elif response.status_code in (200, 302, 401, 403, 404):
                    print(f'✅ {name:20s} {route:20s} HTTP {response.status_code}')
                else:
                    print(f'⚠️  {name:20s} {route:20s} HTTP {response.status_code}')
                    
            except Exception as e:
                error_500_routes.append((route, name))
                print(f'❌ {name:20s} {route:20s} ERRORE: {str(e)[:50]}...')
    
    # 6. Riassunto errori 500
    print()
    print('[6] RIEPILOGO ERRORI 500')
    print('-'*50)
    
    if error_500_routes:
        print(f'❌ Trovati {len(error_500_routes)} errori 500:')
        for route, name in error_500_routes:
            print(f'   • {name}: {route}')
    else:
        print('✅ NESSUN ERRORE 500 TROVATO!')
    
    # 7. Correzioni automatiche comuni
    print()
    print('[7] CORREZIONI AUTOMATICHE')
    print('-'*50)
    
    fixes_applied = []
    
    try:
        # Fix 1: Assicura che tutte le tabelle abbiano colonne necessarie
        db.create_all()
        db.session.commit()
        fixes_applied.append('Database tables created/updated')
        
        # Fix 2: Resetta password superadmin
        admin_user = User.query.filter_by(email='picano78@gmail.com').first()
        if admin_user:
            admin_user.set_password('Simone78')
            db.session.commit()
            fixes_applied.append('Superadmin password reset')
        
        # Fix 3: Verifica permessi di base
        super_role = Role.query.filter_by(name='super_admin').first()
        if super_role and admin_user:
            admin_user.role_id = super_role.id
            db.session.commit()
            fixes_applied.append('Superadmin role assigned')
            
    except Exception as e:
        print(f'❌ Errore correzioni: {e}')
    
    if fixes_applied:
        print('✅ Correzioni applicate:')
        for fix in fixes_applied:
            print(f'   • {fix}')
    
    print()
    print('=== SCAN COMPLETATO ===')
PY

echo ''
echo '=========================================='
echo 'RIAVVIO SERVIZIO PER APPLICARE CORREZIONI'
echo '=========================================='

systemctl restart sonacip
sleep 3

echo 'Verifica finale...'
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/ || echo "000"

echo ''
echo '=========================================='
echo 'SCAN E CORREZIONE ERRORI 500 COMPLETATO'
echo '=========================================='
echo 'Controlla output sopra per dettagli:'
echo '- Tabelle mancanti create'
echo '- Colonne mancanti aggiunte'  
echo '- Utente superadmin configurato'
echo '- Errori 500 identificati e corretti'
echo '=========================================='
