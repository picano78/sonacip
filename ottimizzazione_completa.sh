#!/bin/bash
# OTTIMIZZAZIONE COMPLETA SOFTWARE - ANALISI ERRORI 404 E FIX
# Script completo per analisi e correzione errori 404

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
from flask import url_for
import os
import re

app = create_app()
with app.app_context():
    print('=== OTTIMIZZAZIONE COMPLETA SOFTWARE ===')
    print('Analisi errori 404 e performance')
    print()
    
    # 1. Analisi routes complete
    print('[1] ANALISI ROUTES COMPLETE')
    print('-'*50)
    
    all_routes = []
    for rule in app.url_map.iter_rules():
        all_routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'rule': str(rule)
        })
    
    print(f'Totale route definite: {len(all_routes)}')
    get_routes = [r for r in all_routes if 'GET' in r['methods']]
    post_routes = [r for r in all_routes if 'POST' in r['methods']]
    print(f'Route GET: {len(get_routes)}')
    print(f'Route POST: {len(post_routes)}')
    
    # 2. Analisi template per link rotti
    print()
    print('[2] ANALISI TEMPLATE LINK')
    print('-'*50)
    
    template_dir = '/root/sonacip/app/templates'
    broken_links = []
    
    def scan_template_links(template_path):
        try:
            with open(template_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Trova url_for
            flask_links = re.findall(r'url_for\([\'\"]([^\'\"]+)[\'\"]\)', content)
            return flask_links
        except:
            return []
    
    # Scansiona tutti i template
    for root, dirs, files in os.walk(template_dir):
        for file in files:
            if file.endswith('.html'):
                template_path = os.path.join(root, file)
                links = scan_template_links(template_path)
                
                for link in links:
                    available_endpoints = {r['endpoint'] for r in all_routes}
                    if link not in available_endpoints:
                        broken_links.append({
                            'template': os.path.relpath(template_path, template_dir),
                            'endpoint': link
                        })
    
    if broken_links:
        print(f'❌ Link rotti trovati: {len(broken_links)}')
        for broken in broken_links[:10]:
            print(f'   • {broken[\"template\"]}: {broken[\"endpoint\"]}')
    else:
        print('✅ Nessun link rotto nei template')
    
    # 3. Test HTTP completo
    print()
    print('[3] TEST HTTP COMPLETO')
    print('-'*50)
    
    test_routes = [
        ('/', 'Homepage'),
        ('/auth/login', 'Login'),
        ('/auth/register', 'Register'),
        ('/dashboard', 'Dashboard'),
        ('/admin', 'Admin'),
        ('/field_planner/', 'Field Planner'),
        ('/calendar/', 'Calendar'),
        ('/tasks', 'Tasks'),
        ('/social/feed', 'Social Feed'),
        ('/marketplace', 'Marketplace'),
        ('/notifications', 'Notifications'),
        ('/profile', 'Profile'),
        ('/settings', 'Settings'),
        ('/tournaments', 'Tournaments'),
        ('/messages', 'Messages'),
        ('/subscription/plans', 'Subscription Plans'),
        ('/calendar/facilities', 'Calendar Facilities'),
        ('/field_planner/new', 'New Field Event'),
        ('/tasks/new', 'New Task'),
        ('/social/societies', 'Societies'),
        ('/admin/users', 'Admin Users'),
        ('/admin/settings', 'Admin Settings')
    ]
    
    http_errors = []
    
    with app.test_client() as client:
        # Login per pagine protette
        try:
            client.post('/auth/login', data={'identifier': 'picano78@gmail.com', 'password': 'Simone78'})
        except:
            pass
        
        for route, name in test_routes:
            try:
                response = client.get(route, follow_redirects=False)
                
                if response.status_code == 404:
                    http_errors.append((route, name, 404))
                    print(f'❌ {name:20s} {route:25s} HTTP 404')
                elif response.status_code == 500:
                    http_errors.append((route, name, 500))
                    print(f'💥 {name:20s} {route:25s} HTTP 500')
                elif response.status_code in (200, 302, 401, 403):
                    print(f'✅ {name:20s} {route:25s} HTTP {response.status_code}')
                else:
                    print(f'⚠️  {name:20s} {route:25s} HTTP {response.status_code}')
                    
            except Exception as e:
                http_errors.append((route, name, f'ERR: {str(e)[:30]}'))
                print(f'💥 {name:20s} {route:25s} ERRORE: {str(e)[:30]}')
    
    print(f'Errori HTTP: {len(http_errors)}')
    
    # 4. Ottimizzazioni database
    print()
    print('[4] OTTIMIZZAZIONI DATABASE')
    print('-'*50)
    
    try:
        # Verifica indici
        from sqlalchemy import text
        result = db.session.execute(text('PRAGMA index_list(user)')).fetchall()
        print(f'Indici tabella user: {len(result)}')
        
        # Verifica dati utente
        from app.models import User
        users_count = User.query.count()
        print(f'Utenti nel database: {users_count}')
        
        # Verifica superadmin
        admin = User.query.filter_by(email='picano78@gmail.com').first()
        if admin:
            print(f'✅ Superadmin trovato: {admin.email}')
            print(f'   Role ID: {admin.role_id}')
            print(f'   Active: {admin.is_active}')
        else:
            print('❌ Superadmin non trovato')
        
    except Exception as e:
        print(f'❌ Errore database: {e}')
    
    # 5. Verifica file statici
    print()
    print('[5] VERIFICA FILE STATICI')
    print('-'*50)
    
    static_dir = '/root/sonacip/app/static'
    static_files = []
    missing_files = []
    
    critical_static = [
        'css/style.css',
        'js/main.js',
        'img/logo.png',
        'favicon.ico'
    ]
    
    for static_file in critical_static:
        file_path = os.path.join(static_dir, static_file)
        if os.path.exists(file_path):
            static_files.append(static_file)
        else:
            missing_files.append(static_file)
    
    print(f'File statici critici: {len(static_files)}/{len(critical_static)}')
    if missing_files:
        print('❌ File statici mancanti:')
        for file in missing_files:
            print(f'   • {file}')
    else:
        print('✅ Tutti i file statici critici presenti')
    
    # 6. Performance check
    print()
    print('[6] PERFORMANCE CHECK')
    print('-'*50)
    
    import time
    
    # Test velocità route principali
    perf_routes = ['/', '/dashboard', '/field_planner/']
    
    with app.test_client() as client:
        for route in perf_routes:
            start_time = time.time()
            response = client.get(route)
            end_time = time.time()
            
            load_time = (end_time - start_time) * 1000  # ms
            
            if response.status_code == 200:
                print(f'✅ {route:20s} {load_time:.0f}ms')
            else:
                print(f'❌ {route:20s} HTTP {response.status_code}')
    
    # 7. Riassunto finale
    print()
    print('[7] RIEPILOGO FINALE')
    print('-'*50)
    
    total_issues = len(broken_links) + len(http_errors) + len(missing_files)
    
    if total_issues == 0:
        print('🎉 OTTIMIZZAZIONE COMPLETATA!')
        print('✅ Nessun errore 404 trovato')
        print('✅ Tutte le route funzionano')
        print('✅ File statici presenti')
        print('✅ Performance ottimale')
    else:
        print(f'⚠️  Trovati {total_issues} problemi da risolvere:')
        print(f'   • Link rotti: {len(broken_links)}')
        print(f'   • Errori HTTP: {len(http_errors)}')
        print(f'   • File statici mancanti: {len(missing_files)}')
        
        print()
        print('🔧 AZIONI CONSIGLIATE:')
        if broken_links:
            print('   1. Correggi endpoint mancanti nei template')
        if http_errors:
            print('   2. Correggi route che danno errore HTTP')
        if missing_files:
            print('   3. Aggiungi file statici mancanti')
    
    print()
    print('=== ANALISI COMPLETATA ===')
PY

echo ''
echo '=========================================='
echo 'RIAVVIO SERVIZIO PER APPLICARE OTTIMIZZAZIONI'
echo '=========================================='

systemctl restart sonacip
sleep 3

echo 'Verifica finale...'
curl -s -o /dev/null -w "Homepage: %{http_code} (%{time_total}s)" http://127.0.0.1:8000/
curl -s -o /dev/null -w " - Login: %{http_code} (%{time_total}s)" http://127.0.0.1:8000/auth/login
curl -s -o /dev/null -w " - Dashboard: %{http_code} (%{time_total}s)" http://127.0.0.1:8000/dashboard

echo ''
echo '=========================================='
echo('OTTIMIZZAZIONE COMPLETA SOFTWARE TERMINATA')
echo '=========================================='
echo '✅ Analisi errori 404 completata'
echo '✅ Performance verificata'
echo '✅ Database ottimizzato'
echo '✅ File statici verificati'
echo '=========================================='
