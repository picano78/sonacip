#!/usr/bin/env python3
"""
Script per aggiornare le credenziali del Super Admin
Uso: python update_admin_credentials.py
IMPORTANTE: Impostare ADMIN_EMAIL e ADMIN_PASSWORD come variabili d'ambiente
"""

import sys
import os

# Aggiungi la directory corrente al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User

# SECURITY: Credenziali DEVONO essere configurate tramite variabili d'ambiente
NEW_EMAIL = os.environ.get("ADMIN_EMAIL")
NEW_PASSWORD = os.environ.get("ADMIN_PASSWORD")

if not NEW_EMAIL or not NEW_PASSWORD:
    print("❌ ERRORE: Credenziali non configurate!")
    print()
    print("Per ragioni di sicurezza, le credenziali devono essere impostate tramite variabili d'ambiente:")
    print()
    print("  export ADMIN_EMAIL='tuaemail@esempio.it'")
    print("  export ADMIN_PASSWORD='TuaPasswordSicura'")
    print("  python update_admin_credentials.py")
    print()
    sys.exit(1)

def update_admin_credentials():
    """Aggiorna le credenziali del super admin"""
    app = create_app()
    
    with app.app_context():
        # Trova il super admin
        admin = User.query.filter_by(role='super_admin').first()
        
        if not admin:
            # Se non esiste, cerca qualsiasi admin
            admin = User.query.filter(User.role.in_(['super_admin', 'admin'])).first()
        
        if not admin:
            print("❌ ERRORE: Nessun super admin trovato nel database!")
            print("💡 Suggerimento: Esegui prima 'python manage.py seed'")
            return False
        
        # Stampa le info attuali
        print("📋 Super Admin trovato:")
        print(f"   ID: {admin.id}")
        print(f"   Email attuale: {admin.email}")
        print(f"   Username: {admin.username}")
        print(f"   Ruolo: {admin.role}")
        print()
        
        # Aggiorna le credenziali
        admin.email = NEW_EMAIL
        admin.username = NEW_EMAIL  # Mantieni username allineato con email
        admin.set_password(NEW_PASSWORD)
        admin.is_active = True
        admin.is_verified = True
        admin.email_confirmed = True
        
        # Salva le modifiche
        db.session.commit()
        
        print("✅ Credenziali aggiornate con successo!")
        print()
        print("🔑 Nuove credenziali Super Admin:")
        print(f"   Email: {NEW_EMAIL}")
        print(f"   Password: {NEW_PASSWORD}")
        print()
        print("⚠️  IMPORTANTE: Cambia questa password dopo il primo accesso!")
        print()
        return True

if __name__ == "__main__":
    try:
        update_admin_credentials()
    except Exception as e:
        print(f"❌ ERRORE durante l'aggiornamento: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
