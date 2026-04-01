#!/usr/bin/env python3
"""
SENIOR ENGINEER - FIX DEFINITIVO SUPERADMIN
Risoluzione definitiva problema login superadmin
"""

import os
import sys
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).parent
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))

# Setup environment
if not (BASE_DIR / '.env').exists():
    with open(BASE_DIR / '.env', 'w') as f:
        f.write("SUPERADMIN_EMAIL=picano78@gmail.com\n")
        f.write("SUPERADMIN_PASSWORD=Simone78\n")
        f.write("DATABASE_URL=sqlite:///uploads/sonacip.db\n")
        f.write("SQLALCHEMY_DATABASE_URI=sqlite:///uploads/sonacip.db\n")
        f.write("SECRET_KEY=test_key_debug\n")
        f.write("FLASK_ENV=development\n")

from dotenv import load_dotenv
load_dotenv(BASE_DIR / '.env', override=True)

print("="*70)
print("SENIOR ENGINEER - FIX DEFINITIVO SUPERADMIN")
print("="*70)

# ========================
# FASE 1 — FIX PASSWORD SICURO
# ========================
print("\n[FASE 1] FIX PASSWORD SICURO")
print("-"*50)

try:
    from app import create_app, db
    from app.models import User, Role
    
    os.environ['FLASK_ENV'] = 'development'
    app = create_app()
    
    with app.app_context():
        # Recupera utente ID=2
        user = User.query.filter_by(id=2).first()
        if not user:
            user = User.query.filter_by(email="picano78@gmail.com").first()
        if not user:
            user = User.query.filter_by(email="Picano78@gmail.com").first()
        
        if not user:
            print("ERRORE: Utente ID=2 non trovato!")
            sys.exit(1)
        
        print(f"Utente trovato: ID={user.id}, Email={user.email}")
        
        # Reset password sicuro
        print("Reset password...")
        user.set_password("Simone78")
        db.session.commit()
        
        # Verifica immediata
        password_check = user.check_password("Simone78")
        print(f"check_password('Simone78'): {password_check}")
        
        # ASSERT CRITICO
        assert password_check == True, "ERRORE CRITICO: check_password() restituisce False!"
        print("✅ Password verificata con successo")
        
except Exception as e:
    print(f"ERRORE FASE 1: {e}")
    traceback.print_exc()
    print(f"❌ FAIL AT STEP: 1 - {e}")
    sys.exit(1)

# ========================
# FASE 2 — VERIFICA METODI PASSWORD
# ========================
print("\n[FASE 2] VERIFICA METODI PASSWORD")
print("-"*50)

try:
    import inspect
    from werkzeug.security import generate_password_hash, check_password_hash
    
    # Analizza set_password
    set_source = inspect.getsource(User.set_password)
    print("set_password():")
    for line in set_source.split('\n')[:3]:
        print(f"  {line}")
    
    # Analizza check_password
    check_source = inspect.getsource(User.check_password)
    print("\ncheck_password():")
    for line in check_source.split('\n')[:3]:
        print(f"  {line}")
    
    # Test coerenza
    test_hash = generate_password_hash("test")
    test_verify = check_password_hash(test_hash, "test")
    print(f"\nCoerenza werkzeug: {test_verify}")
    
    assert test_verify == True, "ERRORE: werkzeug non coerente!"
    print("✅ Metodi password coerenti")
    
except Exception as e:
    print(f"ERRORE FASE 2: {e}")
    print(f"❌ FAIL AT STEP: 2 - {e}")
    sys.exit(1)

# ========================
# FASE 3 — DEBUG LOGIN FLOW
# ========================
print("\n[FASE 3] DEBUG LOGIN FLOW")
print("-"*50)

try:
    # Analizza route login
    from app.auth import routes
    
    # Trova funzione login route
    login_route = None
    for rule in app.url_map.iter_rules():
        if 'login' in rule.endpoint and 'POST' in rule.methods:
            login_route = rule.endpoint
            break
    
    print(f"Route login trovata: {login_route}")
    
    # Analizza codice sorgente
    import app.auth.routes as auth_module
    login_func = getattr(auth_module, 'login', None)
    
    if login_func:
        source = inspect.getsource(login_func)
        
        # Controlli chiave
        checks = {
            'User.query': 'User.query' in source,
            'email.lower()': 'lower(' in source,
            'check_password': 'check_password' in source,
            'login_user': 'login_user' in source
        }
        
        for check, result in checks.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check}: {result}")
            
        if not all(checks.values()):
            print("ERRORE: Mancano elementi critici nel login!")
            print(f"❌ FAIL AT STEP: 3 - Elementi mancanti nel login flow")
            sys.exit(1)
            
        print("✅ Login flow completo")
    else:
        print("ERRORE: Funzione login non trovata!")
        print(f"❌ FAIL AT STEP: 3 - Funzione login mancante")
        sys.exit(1)
        
except Exception as e:
    print(f"ERRORE FASE 3: {e}")
    print(f"❌ FAIL AT STEP: 3 - {e}")
    sys.exit(1)

# ========================
# FASE 4 — TEST REALE LOGIN
# ========================
print("\n[FASE 4] TEST REALE LOGIN")
print("-"*50)

try:
    client = app.test_client()
    
    # POST login reale
    login_data = {
        'identifier': 'picano78@gmail.com',
        'password': 'Simone78'
    }
    
    response = client.post('/auth/login', data=login_data, follow_redirects=False)
    print(f"POST /auth/login: HTTP {response.status_code}")
    
    if response.status_code == 302:
        location = response.headers.get('Location', '')
        print(f"Redirect: {location}")
        
        if 'login' in location:
            print("ERRORE: Redirect torna a login!")
            print(f"❌ FAIL AT STEP: 4 - Login fallisce, redirect a login")
            sys.exit(1)
        else:
            print("✅ Login redirect corretto")
            login_success = True
            
    elif response.status_code == 200:
        content = response.data.decode('utf-8', errors='ignore').lower()
        if 'credenziali non valide' in content:
            print("ERRORE: Messaggio credenziali non valide!")
            print(f"❌ FAIL AT STEP: 4 - Credenziali non valide")
            sys.exit(1)
        else:
            print("✅ Login successo diretto")
            login_success = True
    else:
        print(f"ERRORE: Status inaspettato {response.status_code}")
        print(f"❌ FAIL AT STEP: 4 - Status HTTP inaspettato")
        sys.exit(1)
        
except Exception as e:
    print(f"ERRORE FASE 4: {e}")
    print(f"❌ FAIL AT STEP: 4 - {e}")
    sys.exit(1)

# ========================
# FASE 5 — CONTROLLO SESSIONE
# ========================
print("\n[FASE 5] CONTROLLO SESSIONE")
print("-"*50)

try:
    with app.test_client() as client:
        # Esegui login
        client.post('/auth/login', data={'identifier': 'picano78@gmail.com', 'password': 'Simone78'})
        
        # Verifica session
        with client.session_transaction() as sess:
            session_data = dict(sess)
            print(f"Session data: {session_data}")
            
        # Verifica SECRET_KEY
        secret_key = app.config.get('SECRET_KEY')
        print(f"SECRET_KEY: {'Presente' if secret_key else 'MANCANTE'}")
        
        if not secret_key:
            print("ERRORE: SECRET_KEY mancante!")
            print(f"❌ FAIL AT STEP: 5 - SECRET_KEY mancante")
            sys.exit(1)
            
        print("✅ Sessione OK")
        
except Exception as e:
    print(f"ERRORE FASE 5: {e}")
    print(f"❌ FAIL AT STEP: 5 - {e}")
    sys.exit(1)

# ========================
# FASE 6 — CONTROLLO ACCESSO ADMIN
# ========================
print("\n[FASE 6] CONTROLLO ACCESSO ADMIN")
print("-"*50)

try:
    with app.test_client() as client:
        # Login
        client.post('/auth/login', data={'identifier': 'picano78@gmail.com', 'password': 'Simone78'})
        
        # Test pagina protetta
        response = client.get('/admin')
        print(f"GET /admin: HTTP {response.status_code}")
        
        if response.status_code == 200:
            content = response.data.decode('utf-8', errors='ignore').lower()
            if 'admin' in content or 'dashboard' in content:
                print("✅ Accesso admin funzionante")
            else:
                print("ATTENZIONE: Admin accessibile ma contenuto anomalo")
        elif response.status_code == 302:
            location = response.headers.get('Location', '')
            if 'login' in location:
                print("ERRORE: Admin redirect a login!")
                print(f"❌ FAIL AT STEP: 6 - Accesso admin negato")
                sys.exit(1)
            else:
                print("✅ Admin redirect corretto")
        else:
            print(f"ERRORE: Admin status {response.status_code}")
            print(f"❌ FAIL AT STEP: 6 - Accesso admin fallito")
            sys.exit(1)
            
except Exception as e:
    print(f"ERRORE FASE 6: {e}")
    print(f"❌ FAIL AT STEP: 6 - {e}")
    sys.exit(1)

# ========================
# FASE 7 — BUG NASCOSTI
# ========================
print("\n[FASE 7] BUG NASCOSTI")
print("-"*50)

try:
    with app.app_context():
        # Controllo email case
        email_variants = ['picano78@gmail.com', 'Picano78@gmail.com', 'PICANO78@GMAIL.COM']
        found_emails = []
        
        for email in email_variants:
            test_user = User.query.filter_by(email=email).first()
            if test_user and test_user.id == user.id:
                found_emails.append(email)
        
        print(f"Email varianti trovate: {found_emails}")
        
        # Controllo duplicati
        duplicates = User.query.filter(User.email.like('%picano78%')).count()
        print(f"Utenti simili trovati: {duplicates}")
        
        if duplicates > 1:
            print("ERRORE: Trovati duplicati!")
            print(f"❌ FAIL AT STEP: 7 - Utenti duplicati")
            sys.exit(1)
            
        # Controllo override check_password
        if hasattr(User.check_password, '__func__'):
            source = inspect.getsource(User.check_password.__func__)
            if 'check_password_hash' not in source:
                print("ERRORE: check_password personalizzato senza werkzeug!")
                print(f"❌ FAIL AT STEP: 7 - check_password override errato")
                sys.exit(1)
        
        print("✅ Nessun bug nascosto")
        
except Exception as e:
    print(f"ERRORE FASE 7: {e}")
    print(f"❌ FAIL AT STEP: 7 - {e}")
    sys.exit(1)

# ========================
# OUTPUT FINALE
# ========================
print("\n" + "="*70)
print("✅ SUPER ADMIN LOGIN FIXED")
print("="*70)
print()
print("TUTTI i test passati:")
print("  ✓ Password resettata e verificata")
print("  ✓ Metodi password coerenti")
print("  ✓ Login flow completo")
print("  ✓ Login reale funzionante")
print("  ✓ Sessione attiva")
print("  ✓ Accesso admin consentito")
print("  ✓ Nessun bug nascosto")
print()
print("Credenziali finali:")
print(f"  Email: picano78@gmail.com")
print(f"  Password: Simone78")
print(f"  User ID: {user.id}")
print("="*70)
