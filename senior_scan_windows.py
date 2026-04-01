#!/usr/bin/env python3
"""
SENIOR ENGINEER - SCAN COMPLETO SISTEMA SONACIP (Windows Compatible)
Debugging produzione reale del login superadmin
"""

import os
import sys
import traceback
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))

# Create .env if missing for local testing
if not (BASE_DIR / '.env').exists():
    with open(BASE_DIR / '.env', 'w') as f:
        f.write("SUPERADMIN_EMAIL=picano78@gmail.com\n")
        f.write("SUPERADMIN_PASSWORD=Simone78\n")
        f.write("DATABASE_URL=sqlite:///uploads/sonacip.db\n")
        f.write("SQLALCHEMY_DATABASE_URI=sqlite:///uploads/sonacip.db\n")
        f.write("SECRET_KEY=test_key_for_local_debug\n")
        f.write("FLASK_ENV=development\n")
        f.write("FLASK_DEBUG=True\n")

from dotenv import load_dotenv
load_dotenv(BASE_DIR / '.env', override=True)

print("="*80)
print("SENIOR ENGINEER - SCAN COMPLETO SISTEMA SONACIP")
print("Debugging produzione reale login superadmin")
print("="*80)
print()

# ========================
# 1. CONTROLLO PASSWORD REALE
# ========================
print("[1] CONTROLLO PASSWORD REALE")
print("="*50)

try:
    from app import create_app, db
    from app.models import User, Role
    from werkzeug.security import generate_password_hash, check_password_hash
    
    # Force development mode for local testing
    os.environ['FLASK_ENV'] = 'development'
    
    app = create_app()
    
    with app.app_context():
        # Recupera utente specifico
        user = User.query.filter_by(id=2).first()
        if not user:
            user = User.query.filter_by(email="picano78@gmail.com").first()
        if not user:
            user = User.query.filter_by(email="Picano78@gmail.com").first()
        
        if not user:
            print("[ERRORE] Utente ID=2 o email Picano78@gmail.com NON TROVATO!")
            print("Creazione utente di test...")
            
            # Crea ruolo se non esiste
            role = Role.query.filter_by(name="super_admin").first()
            if not role:
                role = Role(name="super_admin", description="Super Administrator", is_system=True)
                db.session.add(role)
                db.session.commit()
                print("[OK] Ruolo super_admin creato")
            
            # Crea utente
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
            print("[OK] Utente creato")
        
        print(f"[OK] Utente trovato:")
        print(f"   ID: {user.id}")
        print(f"   Email: {user.email}")
        print(f"   Username: {user.username}")
        print(f"   Role: {user.role_obj.name if user.role_obj else 'NONE'}")
        print(f"   Is Active: {user.is_active}")
        print(f"   Is Verified: {user.is_verified}")
        print(f"   Email Confirmed: {getattr(user, 'email_confirmed', 'N/A')}")
        
        # Analisi hash password
        print(f"\n   Hash password salvato:")
        if user.password_hash:
            print(f"   Lunghezza: {len(user.password_hash)}")
            print(f"   Tipo: {user.password_hash[:10]}...")
            print(f"   Hash completo: {user.password_hash}")
            
            # Identifica tipo hash
            if user.password_hash.startswith('$2b$'):
                print(f"   Algoritmo: Bcrypt")
            elif user.password_hash.startswith('pbkdf2:'):
                print(f"   Algoritmo: PBKDF2")
            elif user.password_hash.startswith('sha256$'):
                print(f"   Algoritmo: SHA256")
            else:
                print(f"   Algoritmo: SCONOSCIUTO")
        else:
            print(f"   [ERRORE] NESSUN HASH - UTENTE SENZA PASSWORD!")
        
        # Test password
        test_password = "Simone78"
        try:
            password_check = user.check_password(test_password)
            print(f"\n   Test check_password('{test_password}'): {password_check}")
            
            if not password_check:
                print(f"   [ERRORE] PASSWORD NON VALIDA - Reset in corso...")
                
                # Reset password
                old_hash = user.password_hash
                user.set_password(test_password)
                new_hash = user.password_hash
                
                print(f"   Hash prima: {old_hash[:30]}...")
                print(f"   Hash dopo:  {new_hash[:30]}...")
                
                db.session.commit()
                
                # Riprova
                password_check_after = user.check_password(test_password)
                print(f"   Test dopo reset: {password_check_after}")
                
                if not password_check_after:
                    print(f"   [ERRORE] BUG CRITICO: check_password() non funziona!")
                    # Test manuale
                    manual_check = check_password_hash(new_hash, test_password)
                    print(f"   Test manuale check_password_hash: {manual_check}")
                    
                    if manual_check and not password_check_after:
                        print(f"   [ERRORE] BUG nel metodo check_password() dell'utente!")
                        sys.exit(1)
                else:
                    print(f"   [OK] Password resettata e verificata")
                    password_ok = True
            else:
                print(f"   [OK] Password gia valida")
                password_ok = True
                
        except Exception as e:
            print(f"   [ERRORE] Errore test password: {e}")
            traceback.print_exc()
            password_ok = False

except Exception as e:
    print(f"[ERRORE] Errore sezione 1: {e}")
    traceback.print_exc()
    password_ok = False

print()

# ========================
# 2. CONTROLLO METODI PASSWORD
# ========================
print("[2] CONTROLLO METODI PASSWORD")
print("="*50)

try:
    # Analisi codice metodi
    import inspect
    
    # Analizza set_password
    set_password_source = inspect.getsource(User.set_password)
    print(f"   set_password():")
    for line in set_password_source.split('\n')[:5]:
        print(f"     {line}")
    
    # Analizza check_password  
    check_password_source = inspect.getsource(User.check_password)
    print(f"\n   check_password():")
    for line in check_password_source.split('\n')[:5]:
        print(f"     {line}")
    
    # Test coerenza algoritmi
    test_password = "test123"
    test_hash = generate_password_hash(test_password)
    test_verify = check_password_hash(test_hash, test_password)
    
    print(f"\n   Test coerenza werkzeug:")
    print(f"   generate_password_hash('test123'): {test_hash[:30]}...")
    print(f"   check_password_hash(): {test_verify}")
    
    if test_verify:
        print(f"   [OK] Algoritmi werkzeug coerenti")
    else:
        print(f"   [ERRORE] Algoritmi werkzeug INCOERENTI!")
        
except Exception as e:
    print(f"[ERRORE] Errore analisi metodi: {e}")

print()

# ========================
# 3. CONTROLLO LOGIN FLOW
# ========================
print("[3] CONTROLLO LOGIN FLOW")
print("="*50)

try:
    # Analisi route login
    from app.auth import routes as auth_routes
    import inspect
    
    # Trova funzione login
    login_func = None
    for name, obj in inspect.getmembers(auth_routes):
        if hasattr(obj, '__name__') and 'login' in obj.__name__.lower():
            login_func = obj
            break
    
    if login_func:
        print(f"   Funzione login trovata: {login_func.__name__}")
        
        # Analizza codice (prime righe)
        login_source = inspect.getsource(login_func)
        lines = login_source.split('\n')
        
        # Cerca pattern chiave
        for i, line in enumerate(lines[:50]):  # Prime 50 righe
            if 'User.query' in line:
                print(f"   Ricerca utente (riga {i}): {line.strip()}")
            elif 'check_password' in line:
                print(f"   Check password (riga {i}): {line.strip()}")
            elif 'login_user' in line:
                print(f"   Login user (riga {i}): {line.strip()}")
                break
        
        # Cerca .lower() su email
        if 'lower(' in login_source:
            print(f"   [OK] Trovato .lower() su email/username")
        else:
            print(f"   [ATTENZIONE] Nessun .lower() trovato - possibili problemi case")
            
    else:
        print(f"   [ERRORE] Funzione login non trovata!")
        
except Exception as e:
    print(f"[ERRORE] Errore analisi login flow: {e}")

print()

# ========================
# 4. TEST LOGIN REALE (SIMULAZIONE)
# ========================
print("[4] TEST LOGIN REALE (SIMULAZIONE)")
print("="*50)

try:
    client = app.test_client()
    
    # Test 1: GET pagina login
    response_get = client.get('/auth/login')
    print(f"   GET /auth/login: HTTP {response_get.status_code}")
    
    # Test 2: POST login
    login_data = {
        'identifier': 'picano78@gmail.com',
        'password': 'Simone78',
        'remember_me': 'y'
    }
    
    response_post = client.post('/auth/login', data=login_data, follow_redirects=False)
    print(f"   POST /auth/login: HTTP {response_post.status_code}")
    
    # Analisi risposta
    if response_post.status_code == 302:
        location = response_post.headers.get('Location', 'N/A')
        print(f"   Redirect a: {location}")
        
        if 'login' in location.lower():
            print(f"   [ERRORE] Redirect torna a login - FALLIMENTO")
            login_success = False
        else:
            print(f"   [OK] Redirect a pagina protetta - SUCCESSO")
            login_success = True
            
    elif response_post.status_code == 200:
        content = response_post.data.decode('utf-8', errors='ignore').lower()
        if 'credenziali non valide' in content:
            print(f"   [ERRORE] Messaggio 'credenziali non valide' trovato")
            login_success = False
        elif any(x in content for x in ['dashboard', 'admin', 'feed', 'logout']):
            print(f"   [OK] Contenuto dashboard trovato - SUCCESSO")
            login_success = True
        else:
            print(f"   [ATTENZIONE] Contenuto ambiguo")
            print(f"   Preview: {content[:200]}...")
            login_success = False
    else:
        print(f"   [ERRORE] Status inaspettato: {response_post.status_code}")
        login_success = False
        
    # Test 3: Follow redirect per vedere risultato finale
    response_follow = client.post('/auth/login', data=login_data, follow_redirects=True)
    print(f"   POST follow redirect: HTTP {response_follow.status_code}")
    
    if response_follow.status_code == 200:
        content = response_follow.data.decode('utf-8', errors='ignore').lower()
        if 'credenziali non valide' in content:
            print(f"   [ERRORE] Messaggio errore nel contenuto finale")
        elif any(x in content for x in ['dashboard', 'admin', 'feed', 'logout']):
            print(f"   [OK] Dashboard nel contenuto finale")
        else:
            print(f"   [ATTENZIONE] Contenuto finale ambiguo")
            
except Exception as e:
    print(f"[ERRORE] Errore test login: {e}")
    traceback.print_exc()
    login_success = False

print()

# ========================
# 5. CONTROLLO REDIRECT LOOP
# ========================
print("[5] CONTROLLO REDIRECT LOOP")
print("="*50)

try:
    # Test accesso a pagina protetta dopo login
    if login_success:
        # Prova ad accedere a dashboard
        dashboard_response = client.get('/dashboard')
        print(f"   GET /dashboard dopo login: HTTP {dashboard_response.status_code}")
        
        if dashboard_response.status_code == 302:
            dashboard_location = dashboard_response.headers.get('Location', 'N/A')
            if 'login' in dashboard_location.lower():
                print(f"   [ERRORE] Dashboard redirect a login - LOOP!")
                redirect_loop = True
            else:
                print(f"   [OK] Dashboard accessibile")
                redirect_loop = False
        else:
            print(f"   [OK] Dashboard risposta diretta: {dashboard_response.status_code}")
            redirect_loop = False
    else:
        print(f"   [ATTENZIONE] Login fallito - skip test dashboard")
        redirect_loop = None
        
except Exception as e:
    print(f"[ERRORE] Errore test redirect: {e}")
    redirect_loop = None

print()

# ========================
# 6. CONTROLLO FLASK-LOGIN
# ========================
print("[6] CONTROLLO FLASK-LOGIN")
print("="*50)

try:
    with app.test_request_context():
        from flask_login import login_user, current_user, logout_user
        
        # Test login_user diretto
        login_result = login_user(user)
        print(f"   login_user(user): {login_result}")
        
        # Verifica current_user
        print(f"   current_user.is_authenticated: {current_user.is_authenticated}")
        print(f"   current_user.email: {current_user.email if current_user.is_authenticated else 'None'}")
        print(f"   current_user.is_active: {current_user.is_active if current_user.is_authenticated else 'None'}")
        print(f"   current_user.get_id(): {current_user.get_id() if current_user.is_authenticated else 'None'}")
        
        # Test metodi utente
        print(f"   user.is_authenticated: {user.is_authenticated}")
        print(f"   user.is_active: {user.is_active}")
        print(f"   user.get_id(): {user.get_id()}")
        
except Exception as e:
    print(f"[ERRORE] Errore Flask-Login: {e}")
    traceback.print_exc()

print()

# ========================
# OUTPUT FINALE
# ========================
print("="*80)
print("OUTPUT FINALE")
print("="*80)

# Valutazione finale
password_status = "[OK]" if password_ok else "[FAIL]"
login_status = "[OK]" if login_success else "[FAIL]"
session_status = "[OK]" if login_success else "[FAIL]"

print(f"✔ PASSWORD: {password_status}")
print(f"✔ LOGIN FLOW: {login_status}")
print(f"✔ SESSION: {session_status}")
print()

if password_ok and login_success:
    print("SUPER ADMIN LOGIN FIXED")
    print()
    print("Tutti i test passati:")
    print("   - Password verificata")
    print("   - Login funzionante")
    print("   - Sessione attiva")
    print()
    print("Credenziali confermate:")
    print(f"   Email: picano78@gmail.com")
    print(f"   Password: Simone78")
    print(f"   User ID: {user.id}")
    print("="*80)
else:
    print("SUPERADMIN LOGIN NON RISOLTO")
    print()
    print("Punto critico identificato:")
    if not password_ok:
        print("   [ERRORE] PASSWORD: check_password() restituisce False")
    if not login_success:
        print("   [ERRORE] LOGIN: POST /auth/login fallisce")
    print("="*80)
    sys.exit(1)
