#!/bin/bash
# FIX ERRORI 500 FIELD PLANNER - CONFIGURAZIONE COMPLETA

ssh root@87.106.1.221 "cd /root/sonacip && source venv/bin/activate && cat > .env << 'EOF'
SUPERADMIN_EMAIL=picano78@gmail.com
SUPERADMIN_PASSWORD=Simone78
DATABASE_URL=sqlite:////root/sonacip/uploads/sonacip.db
SQLALCHEMY_DATABASE_URI=sqlite:////root/sonacip/uploads/sonacip.db
SECRET_KEY=4f8a2b9c1d3e5f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2
FLASK_ENV=production
PORT=8000
WTF_CSRF_ENABLED=True
WTF_CSRF_TIME_LIMIT=None
EOF

python3 << 'PY'
from app import create_app, db
from app.models import FieldPlannerEvent, Facility, User, Society
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    print('=== DIAGNOSI FIELD PLANNER ===')
    
    # 1. Verifica tabelle
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    print(f'Tabelle totali: {len(tables)}')
    
    critical_tables = ['field_planner_event', 'facility', 'user', 'society']
    for table in critical_tables:
        if table in tables:
            print(f'✅ {table}: PRESENTE')
            
            # Verifica colonne critiche
            if table == 'field_planner_event':
                cols = inspector.get_columns(table)
                col_names = [c['name'] for c in cols]
                required_cols = ['id', 'facility_id', 'society_id', 'created_by', 'title', 'start_datetime', 'end_datetime']
                missing = [c for c in required_cols if c not in col_names]
                if missing:
                    print(f'   ❌ Colonne mancanti: {missing}')
                else:
                    print(f'   ✅ Tutte le colonne richieste presenti')
                    
        else:
            print(f'❌ {table}: MANCANTE')
    
    # 2. Verifica dati
    print()
    print('=== DATI ===')
    
    try:
        events_count = FieldPlannerEvent.query.count()
        print(f'Eventi planner: {events_count}')
    except Exception as e:
        print(f'❌ Errore query eventi: {e}')
    
    try:
        facilities_count = Facility.query.count()
        print(f'Facilities: {facilities_count}')
        
        if facilities_count > 0:
            facility = Facility.query.first()
            print(f'   Prima facility: {facility.name} (ID: {facility.id})')
    except Exception as e:
        print(f'❌ Errore query facilities: {e}')
    
    try:
        users_count = User.query.count()
        print(f'Utenti: {users_count}')
        
        if users_count > 0:
            user = User.query.first()
            print(f'   Primo utente: {user.email} (ID: {user.id})')
    except Exception as e:
        print(f'❌ Errore query utenti: {e}')
    
    # 3. Test creazione evento
    print()
    print('=== TEST CREAZIONE EVENTO ===')
    
    try:
        if facilities_count > 0 and users_count > 0:
            from datetime import datetime, date, time as dt_time
            
            facility = Facility.query.first()
            user = User.query.first()
            society_id = getattr(user, 'society_id', 1)
            
            test_event = FieldPlannerEvent(
                society_id=society_id,
                facility_id=facility.id,
                created_by=user.id,
                event_type='training',
                title='Test Diagnosi',
                start_datetime=datetime.combine(date.today(), dt_time(18, 0)),
                end_datetime=datetime.combine(date.today(), dt_time(19, 0))
            )
            
            db.session.add(test_event)
            db.session.flush()  # Test senza commit
            
            print('✅ Creazione evento: SUCCESSO')
            print(f'   Evento ID: {test_event.id}')
            print(f'   Facility: {facility.name}')
            print(f'   Society ID: {society_id}')
            
            db.session.rollback()  # Annulla test
            
        else:
            print('❌ Impossibile testare: mancano dati')
            
    except Exception as e:
        print(f'❌ Errore creazione evento: {e}')
        import traceback
        traceback.print_exc()
    
    # 4. Test route
    print()
    print('=== TEST ROUTE ===')
    
    try:
        with app.test_client() as client:
            response = client.get('/field_planner/')
            print(f'GET /field_planner/: HTTP {response.status_code}')
            
            if response.status_code == 500:
                print('❌ ERRORE 500 DETECTATO!')
                content = response.data.decode()
                print(f'Errore: {content[:300]}...')
            elif response.status_code == 302:
                print('✅ Redirect a login (normale)')
            else:
                print('✅ Pagina accessibile')
                
    except Exception as e:
        print(f'❌ Errore test route: {e}')
    
    print()
    print('=== DIAGNOSI COMPLETATA ===')
PY

echo ''
echo '=========================================='
echo 'FIX ERRORI 500 FIELD PLANNER'
echo '=========================================='
echo 'Configurazione completata e diagnosi eseguita.'
echo 'Controlla output sopra per identificare il problema.'
echo '=========================================='
