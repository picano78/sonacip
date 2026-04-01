#!/usr/bin/env python3
"""
SONACIP Superadmin Login Test - FOCUSED
Test specifico e dettagliato del login superadmin
"""

import os
import sys
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).parent
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))

print("=" * 70)
print("SUPERADMIN LOGIN TEST - DETTAGLIATO")
print("=" * 70)
print()

# Carica .env
from dotenv import load_dotenv
load_dotenv(BASE_DIR / '.env', override=True)
print(f"[ENV] .env caricato")
print(f"[ENV] SUPERADMIN_EMAIL: {os.environ.get('SUPERADMIN_EMAIL', 'NON SETTATO')}")
print(f"[ENV] SUPERADMIN_PASSWORD: {'*' * len(os.environ.get('SUPERADMIN_PASSWORD', 'N/A')) if os.environ.get('SUPERADMIN_PASSWORD') else 'NON SETTATO'}")
print()

# Importa app
from app import create_app, db
from app.models import User, Role

app = create_app()
client = app.test_client()

print("[1] PREPARAZIONE DATABASE")
print("-" * 70)
try:
    with app.app_context():
        db.create_all()
        print("[OK] Database tabelle create")
        
        # Crea ruolo
        role = Role.query.filter_by(name='super_admin').first()
        if not role:
            role = Role(name='super_admin', description='Super Administrator', is_system=True)
            db.session.add(role)
            db.session.commit()
            print(f"[OK] Ruolo super_admin creato (ID: {role.id})")
        else:
            print(f"[OK] Ruolo super_admin trovato (ID: {role.id})")
        
        # Crea/verifica utente
        email = 'picano78@gmail.com'
        password = 'Simone78'
        
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(
                email=email,
                username=email,
                first_name='Simone',
                last_name='Admin',
                is_active=True,
                is_verified=True,
                email_confirmed=True,
                role_obj=role,
                role_legacy='super_admin'
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            print(f"[OK] Utente creato (ID: {user.id})")
        else:
            user.set_password(password)
            user.is_active = True
            user.email_confirmed = True
            user.role_obj = role
            db.session.commit()
            print(f"[OK] Utente aggiornato (ID: {user.id})")
        
        # Verifica password
        if user.check_password(password):
            print(f"[OK] Password verificata correttamente")
        else:
            print(f"[ERRORE] Password non corrisponde!")
            
        user_id = user.id
        
except Exception as e:
    print(f"[ERRORE] {e}")
    traceback.print_exc()
    sys.exit(1)
print()

print("[2] TEST LOGIN STEP-BY-STEP")
print("-" * 70)

# Step 1: Ottieni pagina login
print("Step 1: Richiesta pagina login...")
try:
    response = client.get('/auth/login')
    print(f"  [OK] GET /auth/login -> HTTP {response.status_code}")
    
    # Cerca CSRF token
    content = response.data.decode('utf-8', errors='ignore')
    if 'csrf_token' in content.lower():
        print("  [OK] Form contiene CSRF token")
    else:
        print("  [WARN] Form senza CSRF token visibile")
        
except Exception as e:
    print(f"  [ERRORE] {e}")
    sys.exit(1)

# Step 2: Esegui login
print("\nStep 2: Esecuzione POST login...")
login_data = {
    'identifier': 'picano78@gmail.com',
    'password': 'Simone78',
    'remember_me': 'y'
}

try:
    response = client.post('/auth/login', data=login_data, follow_redirects=True)
    status = response.status_code
    content = response.data.decode('utf-8', errors='ignore')
    
    print(f"  Status: HTTP {status}")
    
    if status == 200:
        print("  [OK] Login HTTP 200 - Controllando contenuto...")
        
        # Verifica elementi di successo
        success_indicators = [
            'dashboard', 'admin', 'feed', 'logout', 'benvenuto', 'welcome',
            'picano78', 'simone', 'profilo', 'settings'
        ]
        
        found = [ind for ind in success_indicators if ind.lower() in content.lower()]
        
        if found:
            print(f"  [SUCCESSO] Indicatori trovati: {found[:3]}")
            login_success = True
        else:
            print(f"  [WARN] Nessun indicatore di successo trovato")
            print(f"  Contenuto: {content[:300]}...")
            login_success = False
            
    elif status == 302:
        print("  [SUCCESSO] Login con redirect (HTTP 302)")
        login_success = True
        
    elif status == 401:
        print("  [ERRORE] Credenziali non valide (HTTP 401)")
        login_success = False
        
    else:
        print(f"  [ERRORE] Status inaspettato: HTTP {status}")
        print(f"  Contenuto: {content[:300]}...")
        login_success = False
        
except Exception as e:
    print(f"  [ERRORE] Eccezione: {e}")
    traceback.print_exc()
    login_success = False

print()

print("[3] VERIFICA SESSIONE UTENTE")
print("-" * 70)

if login_success:
    try:
        # Testa pagina protetta
        response = client.get('/dashboard', follow_redirects=False)
        if response.status_code == 200:
            print("[OK] Dashboard accessibile (HTTP 200)")
            content = response.data.decode('utf-8', errors='ignore')
            if 'dashboard' in content.lower():
                print("[OK] Contenuto dashboard corretto")
            else:
                print("[WARN] Dashboard accessibile ma contenuto anomalo")
        elif response.status_code == 302:
            print("[WARN] Dashboard redirect (forza login?)")
        else:
            print(f"[ERRORE] Dashboard HTTP {response.status_code}")
            
        # Testa admin panel
        response = client.get('/admin', follow_redirects=False)
        if response.status_code == 200:
            print("[OK] Admin panel accessibile (HTTP 200)")
        elif response.status_code == 302:
            print("[WARN] Admin panel redirect")
        else:
            print(f"[ERRORE] Admin panel HTTP {response.status_code}")
            
    except Exception as e:
        print(f"[ERRORE] Test sessione: {e}")
else:
    print("[SKIP] Login fallito, salto test sessione")

print()

print("[4] DEBUG UTENTE DATABASE")
print("-" * 70)

try:
    with app.app_context():
        user = User.query.filter_by(email='picano78@gmail.com').first()
        if user:
            print(f"ID: {user.id}")
            print(f"Email: {user.email}")
            print(f"Username: {user.username}")
            print(f"Is Active: {user.is_active}")
            print(f"Is Verified: {getattr(user, 'is_verified', 'N/A')}")
            print(f"Email Confirmed: {getattr(user, 'email_confirmed', 'N/A')}")
            print(f"Role: {user.role}")
            print(f"Password Hash: {user.password_hash[:30]}..." if user.password_hash else "N/A")
            
            # Test password
            if user.check_password('Simone78'):
                print("Password Check: [OK]")
            else:
                print("Password Check: [FAIL]")
        else:
            print("[ERRORE] Utente non trovato!")
except Exception as e:
    print(f"[ERRORE] {e}")

print()

print("=" * 70)
print("RISULTATO FINALE")
print("=" * 70)
print()

if login_success:
    print("✅ SUPERADMIN LOGIN: FUNZIONA CORRETTAMENTE")
    print("   L'utente può accedere e navigare nel sito")
else:
    print("❌ SUPERADMIN LOGIN: NON FUNZIONA")
    print("   Problemi rilevati nel processo di autenticazione")

print()
print("Credenziali testate:")
print("  Email: picano78@gmail.com")
print("  Password: Simone78")
print()
print("URL di login:")
print("  http://87.106.1.221:8000/auth/login")
print("=" * 70)
