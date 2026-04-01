#!/usr/bin/env python3
"""
SENIOR FLASK ENGINEER - SUPERADMIN PASSWORD FIX
Analisi e riparazione definitiva del problema password
"""

import os
import sys
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).parent
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / '.env', override=True)

print("="*70)
print("SENIOR FLASK ENGINEER - SUPERADMIN PASSWORD FIX")
print("="*70)
print()

# 1. ANALISI MODELLO USER
print("[1] ANALISI MODELLO USER")
print("-"*50)

try:
    from app import create_app, db
    from app.models import User, Role
    from werkzeug.security import generate_password_hash, check_password_hash
    
    print("✅ Import completati")
    print(f"   Algoritmo: werkzeug.security")
    print(f"   Funzioni: generate_password_hash, check_password_hash")
    
    # Test algoritmo
    test_hash = generate_password_hash("test123")
    test_check = check_password_hash(test_hash, "test123")
    print(f"   Test algoritmo: {test_check}")
    
except Exception as e:
    print(f"❌ Errore import: {e}")
    sys.exit(1)

print()

# 2. TROVA E ANALIZZA SUPERADMIN ESISTENTE
print("[2] ANALISI SUPERADMIN ESISTENTE")
print("-"*50)

app = create_app()

with app.app_context():
    # Trova utente specifico
    user = User.query.filter_by(email="picano78@gmail.com").first()
    
    if not user:
        # Prova con maiuscole diverse
        user = User.query.filter(User.email.like('%picano78%')).first()
        if user:
            print(f"⚠️  Utente trovato con email diversa: {user.email}")
        else:
            print("❌ Nessun utente picano78 trovato!")
            sys.exit(1)
    
    print(f"✅ Utente trovato:")
    print(f"   ID: {user.id}")
    print(f"   Email: {user.email}")
    print(f"   Username: {user.username}")
    print(f"   Role ID: {user.role_id}")
    print(f"   Role Name: {user.role_obj.name if user.role_obj else 'NONE'}")
    print(f"   Is Active: {user.is_active}")
    print(f"   Is Verified: {user.is_verified}")
    print(f"   Email Confirmed: {getattr(user, 'email_confirmed', 'N/A')}")
    
    # 3. ANALISI PASSWORD HASH
    print()
    print("[3] ANALISI PASSWORD HASH")
    print("-"*50)
    
    print(f"   Hash salvato: {user.password_hash[:50]}..." if user.password_hash else "   Hash: NONE")
    
    # Test password corrente
    test_passwords = ["Simone78", "Picano78", "simone78", "picano78"]
    
    for pwd in test_passwords:
        try:
            result = user.check_password(pwd)
            print(f"   Test '{pwd}': {result}")
            if result:
                print(f"   ✅ Password funzionante: {pwd}")
                working_password = pwd
                break
        except Exception as e:
            print(f"   Test '{pwd}': ERRORE - {e}")
    else:
        working_password = None
        print("   ❌ Nessuna password funziona!")
    
    # 4. RESET SICURO PASSWORD
    print()
    print("[4] RESET SICURO PASSWORD")
    print("-"*50)
    
    try:
        # Genera nuovo hash
        new_hash = generate_password_hash("Simone78")
        print(f"   Nuovo hash generato: {new_hash[:50]}...")
        
        # Imposta password usando il metodo corretto
        user.set_password("Simone78")
        
        # Verifica hash
        print(f"   Hash dopo set_password: {user.password_hash[:50]}...")
        
        # Commit
        db.session.commit()
        print("✅ Password resettata e salvata")
        
    except Exception as e:
        print(f"❌ Errore reset password: {e}")
        traceback.print_exc()
        sys.exit(1)
    
    # 5. VERIFICA PASSWORD
    print()
    print("[5] VERIFICA PASSWORD")
    print("-"*50)
    
    try:
        # Test diretto
        direct_check = check_password_hash(user.password_hash, "Simone78")
        print(f"   Check diretto: {direct_check}")
        
        # Test metodo user
        method_check = user.check_password("Simone78")
        print(f"   Check metodo: {method_check}")
        
        if method_check:
            print("✅ Password verificata con successo!")
        else:
            print("❌ Password NON verificata!")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Errore verifica: {e}")
        sys.exit(1)
    
    # 6. TEST LOGIN COMPLETO
    print()
    print("[6] TEST LOGIN COMPLETO")
    print("-"*50)
    
    try:
        from app import create_app
        client = app.test_client()
        
        # Test login
        response = client.post('/auth/login', 
                              data={'identifier': user.email, 
                                    'password': 'Simone78'}, 
                              follow_redirects=True)
        
        print(f"   Status HTTP: {response.status_code}")
        
        if response.status_code == 200:
            content = response.data.decode('utf-8', errors='ignore').lower()
            
            # Verifica indicatori di successo
            success_indicators = ['dashboard', 'admin', 'feed', 'logout', 'benvenuto']
            found = [ind for ind in success_indicators if ind in content]
            
            if found:
                print(f"   ✅ Login SUCCESSO! Indicatori: {found[:3]}")
                login_success = True
            else:
                print(f"   ⚠️  Login HTTP 200 ma contenuto anomalo")
                print(f"   Contenuto: {content[:200]}...")
                login_success = False
                
        elif response.status_code == 302:
            print("   ✅ Login SUCCESSO (redirect)")
            login_success = True
            
        else:
            print(f"   ❌ Login FALLITO: HTTP {response.status_code}")
            print(f"   Contenuto: {response.data.decode()[:200]}...")
            login_success = False
            
    except Exception as e:
        print(f"❌ Errore test login: {e}")
        traceback.print_exc()
        login_success = False
    
    # 7. CONTROLLI EXTRA
    print()
    print("[7] CONTROLLI EXTRA")
    print("-"*50)
    
    # Verifica email case sensitivity
    email_variants = [
        "picano78@gmail.com",
        "Picano78@gmail.com", 
        "PICANO78@GMAIL.COM"
    ]
    
    for email in email_variants:
        test_user = User.query.filter_by(email=email).first()
        if test_user and test_user.id == user.id:
            print(f"   ✅ Email '{email}' trovata (ID: {test_user.id})")
        else:
            print(f"   ❌ Email '{email}' NON trovata")
    
    # Verifica Flask-Login
    try:
        with app.test_request_context():
            from flask_login import login_user, current_user
            
            # Simula login_user
            login_success_flask = login_user(user)
            print(f"   Flask-Login login_user: {login_success_flask}")
            
            # Verifica current_user
            print(f"   Current user after login: {current_user.email if current_user.is_authenticated else 'None'}")
            
    except Exception as e:
        print(f"   Errore Flask-Login: {e}")
    
    # 8. OUTPUT FINALE
    print()
    print("="*70)
    print("OUTPUT FINALE")
    print("="*70)
    
    if login_success and method_check:
        print("🎉 SUPER ADMIN FIXED")
        print()
        print("✅ Checklist completata:")
        print("   ✔ Password verificata")
        print("   ✔ Login funzionante")
        print("   ✔ Accesso riuscito")
        print()
        print("Credenziali finali:")
        print(f"   Email: {user.email}")
        print(f"   Password: Simone78")
        print(f"   User ID: {user.id}")
        print(f"   Role: {user.role_obj.name}")
        print()
        print("URL login:")
        print("   http://87.106.1.221:8000/auth/login")
        print("="*70)
    else:
        print("❌ SUPERADMIN NON RIPARATO")
        print()
        if not method_check:
            print("   ❌ Password non verifica")
        if not login_success:
            print("   ❌ Login non funziona")
        print("="*70)
        sys.exit(1)
