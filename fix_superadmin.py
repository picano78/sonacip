#!/usr/bin/env python3
"""
SONACIP Superadmin Fix & Diagnostics
Script per diagnosticare e correggere problemi di login superadmin
"""

import os
import sys
from pathlib import Path

# Setup
BASE_DIR = Path(__file__).parent
os.chdir(BASE_DIR)

# Carica .env prima di tutto
from dotenv import load_dotenv
env_path = BASE_DIR / '.env'
if env_path.exists():
    load_dotenv(env_path, override=True)

print("=" * 70)
print("SONACIP SUPERADMIN DIAGNOSTICS & FIX")
print("=" * 70)
print()

# 1. Verifica .env
print("1. VERIFICA FILE .env")
print("-" * 70)
if env_path.exists():
    with open(env_path, 'r') as f:
        content = f.read()
        if 'SUPERADMIN_EMAIL=picano78@gmail.com' in content:
            print("✓ SUPERADMIN_EMAIL corretto")
        else:
            print("✗ SUPERADMIN_EMAIL mancante o errato")
        
        if 'SUPERADMIN_PASSWORD=Picano78' in content:
            print("✓ SUPERADMIN_PASSWORD corretto")
        else:
            print("✗ SUPERADMIN_PASSWORD mancante o errato")
        
        if 'DATABASE_URL' in content:
            print("✓ DATABASE_URL presente")
            for line in content.split('\n'):
                if 'DATABASE_URL' in line:
                    print(f"  → {line}")
        else:
            print("✗ DATABASE_URL mancante")
else:
    print("✗ .env non trovato!")
print()

# 2. Verifica database
print("2. VERIFICA DATABASE")
print("-" * 70)

# Cerca il database
possible_db_paths = [
    BASE_DIR / "uploads" / "sonacip.db",
    BASE_DIR / "sonacip.db",
    Path("/root/sonacip/uploads/sonacip.db"),
    Path("/uploads/sonacip.db"),
]

db_found = None
for db_path in possible_db_paths:
    if db_path.exists():
        size = db_path.stat().st_size
        print(f"✓ Database trovato: {db_path} ({size} bytes)")
        db_found = db_path
        break

if not db_found:
    print("✗ Database NON trovato!")
    print("  Cercato in:")
    for p in possible_db_paths:
        print(f"    - {p}")
print()

# 3. Verifica struttura database
if db_found:
    print("3. VERIFICA TABELLE DATABASE")
    print("-" * 70)
    
    import sqlite3
    try:
        conn = sqlite3.connect(str(db_found))
        cursor = conn.cursor()
        
        # Lista tabelle
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        if 'user' in tables:
            print("✓ Tabella 'user' trovata")
            
            # Cerca superadmin
            cursor.execute("SELECT id, email, username, password_hash, role_id, is_active FROM user WHERE email='picano78@gmail.com';")
            user = cursor.fetchone()
            
            if user:
                user_id, email, username, pw_hash, role_id, is_active = user
                print(f"✓ Superadmin trovato:")
                print(f"  ID: {user_id}")
                print(f"  Email: {email}")
                print(f"  Username: {username}")
                print(f"  Role ID: {role_id}")
                print(f"  Is Active: {is_active}")
                print(f"  Password hash length: {len(pw_hash) if pw_hash else 0}")
                
                if not pw_hash:
                    print("⚠ ATTENZIONE: Password hash vuoto!")
                    print("  → Reset password a 'Picano78'")
                    from werkzeug.security import generate_password_hash
                    new_hash = generate_password_hash("Picano78")
                    cursor.execute("UPDATE user SET password_hash=? WHERE id=?", (new_hash, user_id))
                    conn.commit()
                    print("  ✓ Password aggiornata!")
                    
                if not is_active:
                    print("⚠ ATTENZIONE: Utente non attivo!")
                    cursor.execute("UPDATE user SET is_active=1 WHERE id=?", (user_id,))
                    conn.commit()
                    print("  ✓ Utente attivato!")
            else:
                print("✗ Superadmin NON trovato nel database!")
                print("  → Creazione superadmin...")
                
                # Cerca ruolo super_admin
                cursor.execute("SELECT id FROM role WHERE name='super_admin';")
                role = cursor.fetchone()
                
                if role:
                    role_id = role[0]
                    print(f"  ✓ Role super_admin trovato (ID: {role_id})")
                else:
                    print("  ✗ Role super_admin non trovato!")
                    print("    Creazione ruolo...")
                    cursor.execute("INSERT INTO role (name, description, is_system) VALUES (?, ?, ?)",
                                 ("super_admin", "Super Administrator", 1))
                    role_id = cursor.lastrowid
                    conn.commit()
                    print(f"    ✓ Role creato (ID: {role_id})")
                
                # Crea superadmin
                from werkzeug.security import generate_password_hash
                password_hash = generate_password_hash("Picano78")
                
                cursor.execute("""
                    INSERT INTO user (email, username, password_hash, first_name, is_active, is_verified, email_confirmed, role_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, ("picano78@gmail.com", "picano78@gmail.com", password_hash, "Simone", 1, 1, 1, role_id))
                conn.commit()
                print("  ✓ Superadmin creato con successo!")
        else:
            print("✗ Tabella 'user' non trovata!")
            print("  Il database potrebbe non essere inizializzato.")
            
        conn.close()
        
    except Exception as e:
        print(f"✗ Errore accesso database: {e}")
print()

# 4. Test login
print("4. TEST LOGIN SUPERADMIN")
print("-" * 70)

try:
    from app import create_app, db
    from app.models import User
    from werkzeug.security import check_password_hash
    
    app = create_app()
    
    with app.app_context():
        # Cerca utente
        user = User.query.filter_by(email="picano78@gmail.com").first()
        
        if user:
            print(f"✓ Utente trovato via SQLAlchemy: {user.email}")
            print(f"  Username: {user.username}")
            print(f"  Is Active: {user.is_active}")
            
            # Test password
            test_pw = "Picano78"
            if user.check_password(test_pw):
                print(f"  ✓ Password '{test_pw}' corretta!")
            else:
                print(f"  ✗ Password '{test_pw}' NON corrisponde!")
                print("  → Aggiornamento password...")
                user.set_password(test_pw)
                db.session.commit()
                print("  ✓ Password aggiornata!")
                
                # Verifica di nuovo
                if user.check_password(test_pw):
                    print("  ✓ Verifica: password ora corretta!")
        else:
            print("✗ Utente non trovato via SQLAlchemy")
            
except Exception as e:
    print(f"✗ Errore test login: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 70)
print("DIAGNOSTICA COMPLETATA")
print("=" * 70)
print()
print("Se hai visto errori sopra, esegui questo script sul server:")
print("  python3 fix_superadmin.py")
print()
print("Poi riavvia il servizio:")
print("  systemctl restart sonacip")
