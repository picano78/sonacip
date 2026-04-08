#!/usr/bin/env python3
"""
DIAGNOSI ERRORI 500 FIELD PLANNER
Script per identificare le cause degli errori 500 nel planner
"""

import os
import sys
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).parent
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))

print("="*70)
print("DIAGNOSI ERRORI 500 FIELD PLANNER")
print("="*70)

# Setup environment
if not (BASE_DIR / '.env').exists():
    with open(BASE_DIR / '.env', 'w') as f:
        f.write("FLASK_ENV=development\n")
        f.write("DATABASE_URL=sqlite:///uploads/sonacip.db\n")
        f.write("SECRET_KEY=test_debug\n")

from dotenv import load_dotenv
load_dotenv(BASE_DIR / '.env', override=True)

try:
    from app import create_app, db
    from app.models import FieldPlannerEvent, Facility, User, Society
    from app.field_planner.forms import FieldPlannerEventForm
    
    os.environ['FLASK_ENV'] = 'development'
    app = create_app()
    
    with app.app_context():
        print("\n[1] VERIFICA MODELLI")
        print("-"*50)
        
        # Verifica tabelle esistenti
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        print(f"Tabelle nel database: {len(tables)}")
        for table in sorted(tables):
            if 'field' in table.lower() or 'facility' in table.lower() or 'event' in table.lower():
                print(f"  - {table}")
        
        # Verifica modello FieldPlannerEvent
        try:
            print(f"\nFieldPlannerEvent colonne:")
            columns = inspector.get_columns('field_planner_event')
            for col in columns:
                print(f"  - {col['name']}: {col['type']}")
        except Exception as e:
            print(f"ERRORE: Tabella field_planner_event non trovata: {e}")
        
        # Verifica modello Facility
        try:
            print(f"\nFacility colonne:")
            columns = inspector.get_columns('facility')
            for col in columns:
                print(f"  - {col['name']}: {col['type']}")
        except Exception as e:
            print(f"ERRORE: Tabella facility non trovata: {e}")
        
        print("\n[2] VERIFICA DATI")
        print("-"*50)
        
        # Conta eventi
        try:
            events_count = FieldPlannerEvent.query.count()
            print(f"Eventi nel planner: {events_count}")
            
            if events_count > 0:
                sample_event = FieldPlannerEvent.query.first()
                print(f"Esempio evento: {sample_event.title if sample_event else 'None'}")
                print(f"  ID: {sample_event.id}")
                print(f"  Facility ID: {sample_event.facility_id}")
                print(f"  Society ID: {sample_event.society_id}")
        except Exception as e:
            print(f"ERRORE query eventi: {e}")
            traceback.print_exc()
        
        # Conta facilities
        try:
            facilities_count = Facility.query.count()
            print(f"Facilities totali: {facilities_count}")
            
            if facilities_count > 0:
                sample_facility = Facility.query.first()
                print(f"Esempio facility: {sample_facility.name}")
                print(f"  ID: {sample_facility.id}")
                print(f"  Society ID: {sample_facility.society_id}")
        except Exception as e:
            print(f"ERRORE query facilities: {e}")
            traceback.print_exc()
        
        print("\n[3] VERIFICA UTENTE E SOCIETY")
        print("-"*50)
        
        # Verifica utente corrente (simulato)
        try:
            users_count = User.query.count()
            print(f"Utenti nel sistema: {users_count}")
            
            if users_count > 0:
                sample_user = User.query.first()
                print(f"Utente esempio: {sample_user.email}")
                print(f"  ID: {sample_user.id}")
                print(f"  Society ID primario: {getattr(sample_user, 'society_id', 'N/A')}")
        except Exception as e:
            print(f"ERRORE query utenti: {e}")
        
        # Verifica societies
        try:
            societies_count = Society.query.count()
            print(f"Societies nel sistema: {societies_count}")
            
            if societies_count > 0:
                sample_society = Society.query.first()
                print(f"Society esempio: {sample_society.name}")
                print(f"  ID: {sample_society.id}")
        except Exception as e:
            print(f"ERRORE query societies: {e}")
        
        print("\n[4] TEST FORM VALIDATION")
        print("-"*50)
        
        try:
            # Test form senza dati
            form = FieldPlannerEventForm()
            print("Form creato correttamente")
            
            # Test form validation vuoto
            is_valid = form.validate()
            print(f"Form validation (vuoto): {is_valid}")
            
            if not is_valid:
                print("Errori di validation:")
                for field, errors in form.errors.items():
                    print(f"  {field}: {errors}")
            
        except Exception as e:
            print(f"ERRORE form validation: {e}")
            traceback.print_exc()
        
        print("\n[5] TEST CREAZIONE EVENTO")
        print("-"*50)
        
        try:
            # Simula creazione evento
            if facilities_count > 0 and users_count > 0:
                facility = Facility.query.first()
                user = User.query.first()
                
                from datetime import datetime, date, time as dt_time
                
                test_event = FieldPlannerEvent(
                    society_id=getattr(user, 'society_id', 1),
                    facility_id=facility.id,
                    created_by=user.id,
                    event_type='training',
                    title='Test Event',
                    start_datetime=datetime.combine(date.today(), dt_time(18, 0)),
                    end_datetime=datetime.combine(date.today(), dt_time(19, 0))
                )
                
                db.session.add(test_event)
                db.session.flush()  # Non commit
                
                print("✅ Creazione evento test: SUCCESSO")
                
                # Rollback per non salvare
                db.session.rollback()
                
            else:
                print("⚠️  Impossibile testare: mancano facility o utenti")
                
        except Exception as e:
            print(f"❌ ERRORE creazione evento: {e}")
            traceback.print_exc()
        
        print("\n[6] VERIFICA PERMESSI")
        print("-"*50)
        
        try:
            from app.utils import check_permission
            
            # Test permessi utente esempio
            if users_count > 0:
                user = User.query.first()
                
                # Test permessi base
                can_admin = check_permission(user, 'admin', 'access')
                can_field_planner = check_permission(user, 'field_planner', 'view')
                
                print(f"Utente {user.email}:")
                print(f"  Admin access: {can_admin}")
                print(f"  Field planner view: {can_field_planner}")
                
        except Exception as e:
            print(f"ERRORE verifica permessi: {e}")
            traceback.print_exc()
        
        print("\n[7] TEST ROUTES")
        print("-"*50)
        
        try:
            with app.test_client() as client:
                # Test GET index
                response = client.get('/field_planner/')
                print(f"GET /field_planner/: HTTP {response.status_code}")
                
                if response.status_code == 500:
                    print("❌ ERRORE 500 sulla pagina index!")
                    print("Contenuto errore:")
                    print(response.data.decode()[:500])
                elif response.status_code == 302:
                    print("Redirect a login (normale)")
                else:
                    print("✅ Pagina accessibile")
                
        except Exception as e:
            print(f"ERRORE test route: {e}")
            traceback.print_exc()

except Exception as e:
    print(f"ERRORE GENERALE: {e}")
    traceback.print_exc()

print("\n" + "="*70)
print("DIAGNOSI COMPLETATA")
print("="*70)
