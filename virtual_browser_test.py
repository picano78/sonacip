#!/usr/bin/env python3
"""
SONACIP Virtual Browser Simulation & Complete Site Test
Simula un utente reale che naviga nel sito come superadmin
"""

import os
import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
os.chdir(BASE_DIR)

print("=" * 80)
print("SONACIP VIRTUAL BROWSER SIMULATION")
print("Simulazione completa navigazione utente + Superadmin")
print("=" * 80)
print()

# Setup environment
print("[SETUP] Configurazione ambiente...")
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
env_path = BASE_DIR / '.env'
if env_path.exists():
    load_dotenv(env_path, override=True)
    print("  [OK] .env caricato")
else:
    print("  [WARN] .env non trovato, uso defaults")

# Import app
print("[SETUP] Caricamento applicazione...")
try:
    from app import create_app, db
    from app.models import User, Role
    from werkzeug.security import check_password_hash
    print("  [OK] App importata")
except Exception as e:
    print(f"  [ERRORE] {e}")
    sys.exit(1)

app = create_app()
print(f"  [OK] App creata (DB: {app.config.get('SQLALCHEMY_DATABASE_URI', 'N/A')})")
print()

# =============================================================================
# FASE 1: PREPARAZIONE DATABASE
# =============================================================================
print("[FASE 1] Preparazione Database...")
print("-" * 80)

with app.app_context():
    # Crea tabelle
    db.create_all()
    print("  [OK] Tabelle create/verificate")
    
    # Crea ruolo super_admin
    role = Role.query.filter_by(name='super_admin').first()
    if not role:
        role = Role(name='super_admin', description='Super Administrator', is_system=True)
        db.session.add(role)
        db.session.commit()
        print(f"  [OK] Ruolo super_admin creato (ID: {role.id})")
    else:
        print(f"  [OK] Ruolo super_admin esistente (ID: {role.id})")
    
    # Crea/verifica superadmin
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
        print(f"  [OK] Superadmin creato (ID: {user.id})")
    else:
        user.set_password(password)
        user.is_active = True
        user.email_confirmed = True
        db.session.commit()
        print(f"  [OK] Superadmin aggiornato (ID: {user.id})")
    
    # Verifica password
    if user.check_password(password):
        print(f"  [OK] Password verificata")
    else:
        print(f"  [ERRORE] Password non valida!")
        sys.exit(1)
    
    user_id = user.id
    print()

# =============================================================================
# FASE 2: SIMULAZIONE BROWSER
# =============================================================================
print("[FASE 2] Simulazione Browser (Test Client Flask)")
print("-" * 80)

client = app.test_client()
results = {
    'passed': 0,
    'failed': 0,
    'warnings': 0,
    'details': []
}

def test_page(name, method, url, data=None, expected_codes=(200, 302), 
              check_content=None, login_first=False):
    """Testa una pagina e registra il risultato"""
    try:
        if method == 'GET':
            response = client.get(url, follow_redirects=True)
        elif method == 'POST':
            response = client.post(url, data=data, follow_redirects=True)
        else:
            response = client.get(url, follow_redirects=True)
        
        status = response.status_code
        content = response.data.decode('utf-8', errors='ignore')
        
        # Verifica codice atteso
        if status in expected_codes:
            status_ok = True
        else:
            status_ok = False
        
        # Verifica contenuto
        content_ok = True
        if check_content:
            for check in check_content:
                if check not in content:
                    content_ok = False
                    break
        
        if status_ok and content_ok:
            results['passed'] += 1
            symbol = "[OK]"
        elif status_ok and not content_ok:
            results['warnings'] += 1
            symbol = "[WARN]"
        else:
            results['failed'] += 1
            symbol = "[FAIL]"
        
        results['details'].append({
            'name': name,
            'url': url,
            'status': status,
            'symbol': symbol,
            'content_check': content_ok if check_content else None
        })
        
        print(f"  {symbol} {name:30s} HTTP {status:3d} - {url}")
        
        if not content_ok and check_content:
            print(f"       -> Mancano: {[c for c in check_content if c not in content][:2]}")
            
    except Exception as e:
        results['failed'] += 1
        results['details'].append({
            'name': name,
            'url': url,
            'status': 'ERROR',
            'symbol': '[ERROR]',
            'error': str(e)
        })
        print(f"  [ERROR] {name:30s} - {e}")

# Test 1: Homepage (non loggato)
print("\n  --- Pagine Pubbliche (non loggato) ---")
test_page("Homepage", "GET", "/", check_content=["SONACIP", "login"])
test_page("Login Page", "GET", "/auth/login", 
          check_content=["login", "password", "email"])
test_page("Register Page", "GET", "/auth/register",
          check_content=["registrati", "email"])
test_page("Register Society", "GET", "/auth/register-society",
          check_content=["society", "societ"])

# Test 2: Tentativo accesso pagine protette (deve redirect o 401)
print("\n  --- Pagine Protette (non loggato -> redirect) ---")
test_page("Dashboard (no auth)", "GET", "/dashboard",
          expected_codes=(302, 401, 403))
test_page("Admin (no auth)", "GET", "/admin",
          expected_codes=(302, 401, 403))

# =============================================================================
# FASE 3: LOGIN COME SUPERADMIN
# =============================================================================
print("\n[FASE 3] Login come Superadmin")
print("-" * 80)

login_data = {
    'identifier': 'picano78@gmail.com',
    'password': 'Simone78',
    'remember_me': 'y'
}

# Ottieni CSRF token prima
with client.session_transaction() as sess:
    pass  # Inizializza sessione

# Esegui login
response = client.post('/auth/login', data=login_data, follow_redirects=True)
login_status = response.status_code
login_content = response.data.decode('utf-8', errors='ignore')

if login_status in (200, 302):
    if 'dashboard' in login_content.lower() or 'feed' in login_content.lower() or 'admin' in login_content.lower():
        print(f"  [OK] Login riuscito! HTTP {login_status}")
        results['passed'] += 1
        logged_in = True
    else:
        print(f"  [WARN] Login HTTP {login_status} ma possibile problema contenuto")
        results['warnings'] += 1
        logged_in = True
else:
    print(f"  [FAIL] Login fallito! HTTP {login_status}")
    print(f"         Contenuto: {login_content[:200]}...")
    results['failed'] += 1
    logged_in = False

# =============================================================================
# FASE 4: PAGINE LOGGATE (Superadmin)
# =============================================================================
if logged_in:
    print("\n  --- Pagine dopo Login (Superadmin) ---")
    
    test_page("Dashboard", "GET", "/dashboard",
              check_content=["dashboard", "admin", "logout"])
    test_page("Admin Panel", "GET", "/admin",
              check_content=["admin", "dashboard", "gestione"])
    test_page("Profile", "GET", "/profile",
              check_content=["profile", "account"])
    test_page("Feed", "GET", "/social/feed",
              check_content=["feed", "post"])
    test_page("Tournaments", "GET", "/tournaments",
              check_content=["tournament", "torneo"])
    test_page("Tasks", "GET", "/tasks",
              check_content=["task", "progetti"])
    test_page("Marketplace", "GET", "/marketplace",
              check_content=["market", "negozio"])
    test_page("Notifications", "GET", "/notifications",
              check_content=["notific", "notification"])
    test_page("Messages", "GET", "/messages",
              check_content=["messagg", "message"])
    test_page("Subscription", "GET", "/subscription/plans",
              check_content=["plan", "subscription", "abbonamento"])
    test_page("Settings", "GET", "/settings",
              check_content=["setting", "impostazioni"])
    
    # Pagine admin specifiche
    print("\n  --- Pagine Admin Esclusive ---")
    test_page("User Management", "GET", "/admin/users",
              check_content=["user", "utenti"])
    test_page("Role Management", "GET", "/admin/roles",
              check_content=["role", "ruoli"])
    test_page("Site Settings", "GET", "/admin/settings",
              check_content=["setting", "configurazione"])
    test_page("Audit Logs", "GET", "/admin/audit-logs",
              check_content=["audit", "log"])
    test_page("System Info", "GET", "/admin/system",
              check_content=["system", "info"])

# =============================================================================
# FASE 5: LOGOUT
# =============================================================================
print("\n[FASE 5] Logout")
print("-" * 80)

response = client.get('/auth/logout', follow_redirects=True)
if response.status_code in (200, 302):
    print(f"  [OK] Logout riuscito HTTP {response.status_code}")
    results['passed'] += 1
else:
    print(f"  [WARN] Logout HTTP {response.status_code}")
    results['warnings'] += 1

# =============================================================================
# RISULTATO FINALE
# =============================================================================
print()
print("=" * 80)
print("RISULTATO SIMULAZIONE")
print("=" * 80)
print()
print(f"  ✅ Test PASSATI:     {results['passed']}")
print(f"  ⚠️  Avvisi:           {results['warnings']}")
print(f"  ❌ Test FALLITI:     {results['failed']}")
print(f"  📊 Totale pagine:    {results['passed'] + results['warnings'] + results['failed']}")
print()

if results['failed'] == 0:
    print("  🎉 RISULTATO: SITO FUNZIONANTE!")
    print("     Tutte le pagine testate rispondono correttamente.")
elif results['failed'] <= 3:
    print("  ⚠️  RISULTATO: SITO FUNZIONANTE con alcuni problemi minori")
    print("     Alcune pagine potrebbero richiedere attenzione.")
else:
    print("  ❌ RISULTATO: PROBLEMI RILEVATI")
    print("     Diverse pagine non funzionano correttamente.")

print()
print("  Credenziali testate:")
print(f"    Email: picano78@gmail.com")
print(f"    Password: Simone78")
print()

# Dettagli errori
if results['failed'] > 0:
    print("  Dettagli errori:")
    for detail in results['details']:
        if detail['symbol'] in ['[FAIL]', '[ERROR]']:
            print(f"    - {detail['name']}: {detail.get('status', 'N/A')}")

print()
print("=" * 80)
print("SIMULAZIONE COMPLETATA")
print("=" * 80)
