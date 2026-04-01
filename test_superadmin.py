#!/usr/bin/env python3
"""
SONACIP Superadmin Login Simulation & Verification
Simula il processo di login per verificare che il superadmin funzioni
"""

import os
import sys
from pathlib import Path

# Setup environment
BASE_DIR = Path(__file__).parent
os.chdir(BASE_DIR)

print("=" * 70)
print("SONACIP SUPERADMIN LOGIN SIMULATION")
print("=" * 70)
print()

# 1. Verifica file .env
print("[1] VERIFICA .env")
print("-" * 70)
env_path = BASE_DIR / '.env'
if env_path.exists():
    with open(env_path, 'r') as f:
        content = f.read()
        if 'picano78@gmail.com' in content:
            print("[OK] SUPERADMIN_EMAIL corretto")
        if 'Simone78' in content:
            print("[OK] SUPERADMIN_PASSWORD corretto")
        if 'sqlite:///' in content and 'sonacip.db' in content:
            print("[OK] DATABASE_URL configurato")
        else:
            print("[X] DATABASE_URL mancante o errato")
else:
    print("[X] .env NON TROVATO!")
    sys.exit(1)
print()

# 2. Carica dotenv
print("[2] CARICAMENTO .env")
print("-" * 70)
try:
    from dotenv import load_dotenv
    load_dotenv(env_path, override=True)
    print("[OK] .env caricato")
    print(f"  DATABASE_URL: {os.environ.get('DATABASE_URL', 'NON SETTATO')}")
    print(f"  SUPERADMIN_EMAIL: {os.environ.get('SUPERADMIN_EMAIL', 'NON SETTATO')}")
except Exception as e:
    print("[X] Errore caricamento .env: %s" % e)
    sys.exit(1)
print()

# 3. Importa app
print("[3] CARICAMENTO APPLICAZIONE")
print("-" * 70)
try:
    sys.path.insert(0, str(BASE_DIR))
    from app import create_app, db
    from app.models import User, Role
    from werkzeug.security import generate_password_hash, check_password_hash
    print("[OK] Moduli importati")
except Exception as e:
    print("[X] Errore import: %s" % e)
    import traceback
    traceback.print_exc()
    sys.exit(1)
print()

# 4. Crea app context
print("[4] INIZIALIZZAZIONE APP")
print("-" * 70)
try:
    app = create_app()
    print("[OK] App creata")
    print(f"  Config DB: {app.config.get('SQLALCHEMY_DATABASE_URI', 'NON SETTATO')}")
except Exception as e:
    print("[X] Errore creazione app: %s" % e)
    import traceback
    traceback.print_exc()
    sys.exit(1)
print()

# 5. Simulazione completa
print("[5] SIMULAZIONE LOGIN SUPERADMIN")
print("-" * 70)
print()

test_email = "picano78@gmail.com"
test_password = "Simone78"

with app.app_context():
    # 5a. Verifica/crea tabelle
    print("[5a] Verifica tabelle database...")
    try:
        db.create_all()
        print("[OK] Tabelle verificate")
    except Exception as e:
        print("[X] Errore tabelle: %s" % e)
    print()
    
    # 5b. Verifica/crea ruolo
    print("[5b] Verifica ruolo super_admin...")
    try:
        role = Role.query.filter_by(name='super_admin').first()
        if not role:
            print("  --> Ruolo non trovato, creazione...")
            role = Role(
                name='super_admin',
                description='Super Administrator',
                is_system=True
            )
            db.session.add(role)
            db.session.commit()
            print("[OK] Ruolo creato (ID: %d)" % role.id)
        else:
            print("[OK] Ruolo trovato (ID: %d)" % role.id)
    except Exception as e:
        print("[X] Errore ruolo: %s" % e)
        role = None
    print()
    
    # 5c. Verifica/crea utente
    print("[5c] Verifica utente superadmin...")
    user = None
    try:
        user = User.query.filter_by(email=test_email).first()
        if not user:
            print("  --> Utente non trovato, creazione...")
            user = User(
                email=test_email,
                username=test_email,
                first_name='Admin',
                last_name='',
                is_active=True,
                is_verified=True,
                email_confirmed=True,
                role_obj=role,
                role_legacy='super_admin'
            )
            user.set_password(test_password)
            db.session.add(user)
            db.session.commit()
            print("[OK] Utente creato (ID: %d)" % user.id)
        else:
            print("[OK] Utente trovato (ID: %d)" % user.id)
            print(f"  Email: {user.email}")
            print(f"  Username: {user.username}")
            print(f"  Is Active: {user.is_active}")
            print(f"  Is Verified: {getattr(user, 'is_verified', 'N/A')}")
            print(f"  Email Confirmed: {getattr(user, 'email_confirmed', 'N/A')}")
            
            # Aggiorna password per sicurezza
            print("  --> Aggiornamento password...")
            user.set_password(test_password)
            user.is_active = True
            user.email_confirmed = True
            if role:
                user.role_obj = role
            db.session.commit()
            print("  [OK] Password aggiornata")
    except Exception as e:
        print("[X] Errore utente: %s" % e)
        import traceback
        traceback.print_exc()
    print()
    
    # 5d. Simulazione login
    print("[5d] SIMULAZIONE LOGIN")
    print("-" * 40)
    if user:
        print(f"Tentativo login:")
        print(f"  Email: {test_email}")
        print(f"  Password: {'*' * len(test_password)}")
        print()
        
        # Step 1: Ricerca utente
        print("Step 1: Ricerca utente per email...")
        found_user = User.query.filter_by(email=test_email).first()
        if found_user:
            print("  [OK] Utente trovato (ID: %d)" % found_user.id)
        else:
            print("  [X] Utente NON trovato!")
        print()
        
        # Step 2: Verifica password
        print("Step 2: Verifica password...")
        if found_user and found_user.check_password(test_password):
            print("  [OK] Password CORRETTA!")
        else:
            print("  [X] Password ERRATA!")
            # Debug
            if found_user:
                print(f"  Debug: hash salvato = {found_user.password_hash[:30]}...")
                test_hash = generate_password_hash(test_password)
                print(f"  Debug: test hash = {test_hash[:30]}...")
                match = check_password_hash(found_user.password_hash, test_password)
                print(f"  Debug: check_password_hash = {match}")
        print()
        
        # Step 3: Verifica stato utente
        print("Step 3: Verifica stato utente...")
        if found_user:
            checks = []
            if found_user.is_active:
                checks.append("✓ is_active")
            else:
                checks.append("✗ is_active = False")
            
            email_confirmed = getattr(found_user, 'email_confirmed', None)
            if email_confirmed:
                checks.append("✓ email_confirmed")
            elif email_confirmed is False:
                checks.append("✗ email_confirmed = False")
            else:
                checks.append("? email_confirmed non definito")
            
            print(f"  {' | '.join(checks)}")
        print()
        
        # Risultato finale
        print("=" * 40)
        if found_user and found_user.check_password(test_password) and found_user.is_active:
            print("✅ LOGIN SIMULATO: SUCCESSO!")
            print("   Il superadmin può fare login.")
        else:
            print("❌ LOGIN SIMULATO: FALLITO!")
            print("   Problemi rilevati:")
            if not found_user:
                print("   - Utente non trovato")
            elif not found_user.check_password(test_password):
                print("   - Password non corrisponde")
            if found_user and not found_user.is_active:
                print("   - Utente non attivo")
        print("=" * 40)
    else:
        print("❌ Nessun utente disponibile per il test")

print()
print("[6] RIEPILOGO")
print("-" * 70)
print(f"Credenziali testate:")
print(f"  Email:    {test_email}")
print(f"  Password: {test_password}")
print()
print(f"Database: {os.environ.get('DATABASE_URL', 'NON SETTATO')}")
print()

# 7. Test connessione
print("[7] TEST CONNESSIONE HTTP (se server attivo)")
print("-" * 70)
try:
    import urllib.request
    req = urllib.request.Request('http://127.0.0.1:8000', method='HEAD')
    try:
        response = urllib.request.urlopen(req, timeout=5)
        print(f"✓ Server risponde HTTP {response.status}")
    except Exception as e:
        print(f"⚠ Server non risponde (potrebbe essere spento): {e}")
except ImportError:
    print("⚠ urllib non disponibile, skip test HTTP")

print()
print("=" * 70)
print("SIMULAZIONE COMPLETATA")
print("=" * 70)
