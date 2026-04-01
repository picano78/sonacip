#!/usr/bin/env python3
"""
SONACIP Error 500 Diagnostic & Fix Tool
Diagnostica e corregge errori 500 sul sito
"""

import os
import sys
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).parent
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))

print("=" * 80)
print("SONACIP ERROR 500 DIAGNOSTIC & FIX")
print("=" * 80)
print()

# Carica .env
from dotenv import load_dotenv
load_dotenv(BASE_DIR / '.env', override=True)

# Importa app
from app import create_app, db
from app.models import User, Role

app = create_app()
client = app.test_client()

errors_found = []
fixes_applied = []

print("[1] INIZIALIZZAZIONE DATABASE")
print("-" * 80)
try:
    with app.app_context():
        db.create_all()
        
        # Crea/verifica superadmin
        role = Role.query.filter_by(name='super_admin').first()
        if not role:
            role = Role(name='super_admin', description='Super Administrator', is_system=True)
            db.session.add(role)
            db.session.commit()
        
        user = User.query.filter_by(email='picano78@gmail.com').first()
        if not user:
            user = User(
                email='picano78@gmail.com',
                username='picano78@gmail.com',
                first_name='Admin',
                is_active=True,
                is_verified=True,
                email_confirmed=True,
                role_obj=role
            )
            db.session.add(user)
        user.set_password('Simone78')
        user.is_active = True
        db.session.commit()
        print("  [OK] Database e admin pronti")
except Exception as e:
    print(f"  [ERRORE] {e}")
    errors_found.append(("Database Init", str(e)))
print()

print("[2] TEST LOGIN SUPERADMIN")
print("-" * 80)
try:
    response = client.post('/auth/login', 
                          data={'identifier': 'picano78@gmail.com', 
                                'password': 'Simone78'},
                          follow_redirects=True)
    if response.status_code in (200, 302):
        print(f"  [OK] Login riuscito (HTTP {response.status_code})")
        logged_in = True
    else:
        print(f"  [ERRORE] Login fallito (HTTP {response.status_code})")
        print(f"  Risposta: {response.data.decode()[:200]}")
        errors_found.append(("Login", f"HTTP {response.status_code}"))
        logged_in = False
except Exception as e:
    print(f"  [ERRORE] Eccezione login: {e}")
    traceback.print_exc()
    errors_found.append(("Login Exception", str(e)))
    logged_in = False
print()

print("[3] SCAN PAGINE - RICERCA ERRORI 500")
print("-" * 80)

pages_to_test = [
    ("GET", "/", "Homepage"),
    ("GET", "/auth/login", "Login Page"),
    ("GET", "/auth/register", "Register"),
    ("GET", "/dashboard", "Dashboard"),
    ("GET", "/admin", "Admin Panel"),
    ("GET", "/admin/users", "User Management"),
    ("GET", "/admin/roles", "Role Management"),
    ("GET", "/profile", "Profile"),
    ("GET", "/social/feed", "Feed"),
    ("GET", "/tournaments", "Tournaments"),
    ("GET", "/tasks", "Tasks"),
    ("GET", "/marketplace", "Marketplace"),
    ("GET", "/notifications", "Notifications"),
    ("GET", "/messages", "Messages"),
    ("GET", "/subscription/plans", "Subscription"),
    ("GET", "/settings", "Settings"),
]

error_500_pages = []

for method, url, name in pages_to_test:
    try:
        if method == "GET":
            response = client.get(url, follow_redirects=True)
        else:
            response = client.post(url, follow_redirects=True)
        
        status = response.status_code
        
        if status == 500:
            error_500_pages.append((name, url, "HTTP 500"))
            print(f"  [ERRORE 500] {name:25s} {url}")
        elif status in (200, 302, 301):
            print(f"  [OK {status:3d}]    {name:25s} {url}")
        elif status in (401, 403, 404):
            print(f"  [{status}]      {name:25s} {url} (atteso/ok)")
        else:
            print(f"  [? {status:3d}]     {name:25s} {url}")
            
    except Exception as e:
        error_500_pages.append((name, url, str(e)))
        print(f"  [ECCEZIONE] {name:25s} {url}")
        print(f"             -> {str(e)[:80]}")

print()

print("[4] ANALISI ERRORI 500")
print("-" * 80)

if error_500_pages:
    print(f"  Trovati {len(error_500_pages)} errori 500:")
    for name, url, error in error_500_pages:
        print(f"    - {name} ({url}): {error}")
else:
    print("  Nessun errore 500 trovato!")
print()

print("[5] TENTATIVO FIX AUTOMATICO")
print("-" * 80)

# Fix 1: Verifica colonne database mancanti
print("  [Fix 1] Verifica struttura database...")
try:
    with app.app_context():
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        required_tables = ['user', 'role', 'post', 'tournament', 'task', 'notification', 'message']
        missing_tables = [t for t in required_tables if t not in tables]
        
        if missing_tables:
            print(f"    Tabelle mancanti: {missing_tables}")
            db.create_all()
            print(f"    [OK] Tabelle create")
            fixes_applied.append("Create missing tables")
        else:
            print(f"    [OK] Tutte le tabelle presenti")
            
        # Verifica colonne in user
        if 'user' in tables:
            columns = [c['name'] for c in inspector.get_columns('user')]
            required_columns = ['email', 'username', 'password_hash', 'is_active', 'role_id']
            missing_columns = [c for c in required_columns if c not in columns]
            if missing_columns:
                print(f"    Colonne mancanti in user: {missing_columns}")
                # Non possiamo aggiungere colonne facilmente con SQLite
                print(f"    [INFO] Ricreare database potrebbe risolvere")
except Exception as e:
    print(f"    [ERRORE] {e}")

# Fix 2: Verifica permessi admin
print("  [Fix 2] Verifica permessi admin...")
try:
    with app.app_context():
        user = User.query.filter_by(email='picano78@gmail.com').first()
        if user:
            if not user.is_active:
                user.is_active = True
                db.session.commit()
                print(f"    [OK] Utente attivato")
                fixes_applied.append("Activate user")
            if not getattr(user, 'email_confirmed', True):
                user.email_confirmed = True
                db.session.commit()
                print(f"    [OK] Email confermata")
                fixes_applied.append("Confirm email")
except Exception as e:
    print(f"    [ERRORE] {e}")

# Fix 3: Verifica CSRF
print("  [Fix 3] Verifica configurazione CSRF...")
if app.config.get('WTF_CSRF_ENABLED') and not app.config.get('WTF_CSRF_TIME_LIMIT'):
    print(f"    [OK] CSRF configurato correttamente")
else:
    print(f"    [INFO] CSRF: enabled={app.config.get('WTF_CSRF_ENABLED')}, time_limit={app.config.get('WTF_CSRF_TIME_LIMIT')}")

print()

print("[6] TEST FINALE LOGIN")
print("-" * 80)
try:
    response = client.post('/auth/login',
                          data={'identifier': 'picano78@gmail.com',
                                'password': 'Simone78'},
                          follow_redirects=True)
    
    if response.status_code == 200:
        content = response.data.decode('utf-8', errors='ignore').lower()
        if any(x in content for x in ['dashboard', 'admin', 'feed', 'logout', 'benvenuto']):
            print(f"  [SUCCESSO] Login funziona! Redirect a dashboard/feed")
            login_works = True
        else:
            print(f"  [WARN] Login HTTP 200 ma contenuto sospetto")
            print(f"  Contenuto: {response.data.decode()[:200]}...")
            login_works = False
    elif response.status_code == 302:
        print(f"  [SUCCESSO] Login riuscito con redirect (HTTP 302)")
        login_works = True
    else:
        print(f"  [FALLITO] Login HTTP {response.status_code}")
        login_works = False
except Exception as e:
    print(f"  [FALLITO] Eccezione: {e}")
    login_works = False
print()

print("=" * 80)
print("RISULTATO FINALE")
print("=" * 80)
print()

if login_works:
    print("  ✅ SUPERADMIN LOGIN: FUNZIONA")
else:
    print("  ❌ SUPERADMIN LOGIN: BLOCCATO")

if error_500_pages:
    print(f"  ❌ ERRORI 500: {len(error_500_pages)} pagine con errori")
    for name, url, _ in error_500_pages[:5]:
        print(f"     - {name}: {url}")
else:
    print("  ✅ ERRORI 500: Nessuno trovato")

if fixes_applied:
    print(f"  🔧 FIX APPLICATI: {len(fixes_applied)}")
    for fix in fixes_applied:
        print(f"     - {fix}")

print()
print("  Credenziali:")
print("    Email: picano78@gmail.com")
print("    Password: Simone78")
print()

if not login_works or error_500_pages:
    print("  ⚠️  PROBLEMI RILEVATI - Azioni consigliate:")
    print("    1. Ricreare database: rm uploads/sonacip.db && flask db upgrade")
    print("    2. Riavviare: systemctl restart sonacip")
    print("    3. Controllare logs: journalctl -u sonacip -f")
else:
    print("  🎉 TUTTO FUNZIONA CORRETTAMENTE!")

print()
print("=" * 80)
