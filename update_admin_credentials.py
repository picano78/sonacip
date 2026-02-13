#!/usr/bin/env python3
"""
Script per aggiornare le credenziali del Super Admin
Uso: python update_admin_credentials.py
"""

import sys
import os

# Aggiungi la directory corrente al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User

# Nuove credenziali - Da configurare tramite variabili d'ambiente in produzione
# SECURITY NOTE: Queste sono credenziali di default. 
# In produzione, usa variabili d'ambiente: ADMIN_EMAIL e ADMIN_PASSWORD
NEW_EMAIL = os.environ.get("ADMIN_EMAIL", "picano78@gmail.com")
NEW_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Simone78")

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
