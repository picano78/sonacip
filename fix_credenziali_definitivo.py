#!/usr/bin/env python3
"""
Fix immediato credenziali superadmin
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / '.env', override=True)

from app import create_app, db
from app.models import User, Role

app = create_app()

print("=== FIX CREDENZIALI SUPERADMIN ===")
print()

with app.app_context():
    # 1. Verifica ruolo
    role = Role.query.filter_by(name="super_admin").first()
    if not role:
        role = Role(name="super_admin", description="Super Administrator", is_system=True)
        db.session.add(role)
        db.session.commit()
        print("✅ Creato ruolo super_admin")
    else:
        print(f"✅ Ruolo super_admin esistente (ID: {role.id})")
    
    # 2. Cerca UTENTE con diverse varianti email
    emails_to_check = [
        "picano78@gmail.com",
        "Picano78@gmail.com", 
        "PICANO78@GMAIL.COM"
    ]
    
    user_found = None
    for email in emails_to_check:
        user = User.query.filter_by(email=email).first()
        if user:
            print(f"✅ Utente trovato: {email}")
            user_found = user
            break
    
    if not user_found:
        print("❌ Nessun utente trovato - CREAZIONE...")
        user_found = User(
            email="picano78@gmail.com",
            username="picano78@gmail.com",
            first_name="Simone",
            last_name="Admin",
            is_active=True,
            is_verified=True,
            email_confirmed=True,
            role_id=role.id,
            role_obj=role,
            role_legacy="super_admin"
        )
        user_found.set_password("Simone78")
        db.session.add(user_found)
        db.session.commit()
        print("✅ Utente creato")
    else:
        print(f"✅ Utente esistente (ID: {user_found.id})")
        
        # 3. FIX COMPLETO
        user_found.role_id = role.id
        user_found.role_obj = role
        user_found.is_active = True
        user_found.is_verified = True
        user_found.email_confirmed = True
        user_found.set_password("Simone78")
        
        db.session.commit()
        print("✅ Utente aggiornato")
    
    # 4. VERIFICHE CRITICHE
    print()
    print("=== VERIFICHE ===")
    print(f"Email: {user_found.email}")
    print(f"Username: {user_found.username}")
    print(f"Role ID: {user_found.role_id}")
    print(f"Role Name: {user_found.role_obj.name if user_found.role_obj else 'NONE'}")
    print(f"Is Active: {user_found.is_active}")
    print(f"Email Confirmed: {user_found.email_confirmed}")
    
    # Test password
    if user_found.check_password("Simone78"):
        print("✅ Password: Simone78 (corretta)")
    else:
        print("❌ Password non corrisponde!")
    
    # Test ruolo
    if user_found.role_obj and user_found.role_obj.name == "super_admin":
        print("✅ Ruolo: super_admin (corretto)")
    else:
        print("❌ Ruolo non corretto!")
    
    print()
    print("=== CREDENZIALI FINALI ===")
    print("Email: picano78@gmail.com")
    print("Password: Simone78")
    print("URL: http://87.106.1.221:8000/auth/login")
    print("="*40)
