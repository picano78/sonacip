#!/usr/bin/env python3
"""
Create Test Users
Populates the database with sample users for testing
"""
from app import create_app, db
from app.models import User, Subscription, Plan
from datetime import datetime, timedelta

app = create_app()

with app.app_context():
    print("Creating test users...")
    
    # Create a società (sports society)
    society = User.query.filter_by(email='societa@test.it').first()
    if not society:
        society = User(
            email='societa@test.it',
            username='asd_calcio',
            first_name='ASD',
            last_name='Calcio Roma',
            company_name='ASD Calcio Roma',
            company_type='ASD',
            vat_number='IT12345678901',
            fiscal_code='RSSMRA80A01H501Z',
            role='societa',
            is_active=True,
            is_verified=True,
            address='Via dello Sport 10',
            city='Roma',
            province='RM',
            postal_code='00100',
            phone='+39 06 12345678',
            website='www.asdcalcioroma.it'
        )
        society.set_password('test123')
        db.session.add(society)
        db.session.commit()
        print(f"✅ Created società: {society.email}")
        
        # Give society a Basic plan subscription
        basic_plan = Plan.query.filter_by(slug='basic').first()
        if basic_plan:
            subscription = Subscription(
                user_id=society.id,
                plan_id=basic_plan.id,
                status='active',
                billing_cycle='monthly',
                start_date=datetime.utcnow(),
                next_billing_date=datetime.utcnow() + timedelta(days=30),
                amount=basic_plan.price_monthly,
                auto_renew=True
            )
            db.session.add(subscription)
            db.session.commit()
            print(f"  ✅ Subscribed to {basic_plan.name} plan")
    
    # Create staff member
    staff = User.query.filter_by(email='staff@test.it').first()
    if not staff:
        staff = User(
            email='staff@test.it',
            username='coach_mario',
            first_name='Mario',
            last_name='Rossi',
            role='staff',
            staff_role='coach',
            society_id=society.id,
            is_active=True,
            is_verified=True,
            phone='+39 333 1234567'
        )
        staff.set_password('test123')
        db.session.add(staff)
        db.session.commit()
        print(f"✅ Created staff: {staff.email}")
    
    # Create athletes
    athlete_names = [
        ('Giuseppe', 'Verdi', 'giuseppe@test.it'),
        ('Luca', 'Bianchi', 'luca@test.it'),
        ('Marco', 'Neri', 'marco@test.it')
    ]
    
    for first, last, email in athlete_names:
        athlete = User.query.filter_by(email=email).first()
        if not athlete:
            athlete = User(
                email=email,
                username=f"{first.lower()}_{last.lower()}",
                first_name=first,
                last_name=last,
                role='atleta',
                athlete_society_id=society.id,
                birth_date=datetime(2005, 1, 15),
                sport='Calcio',
                is_active=True,
                is_verified=True
            )
            athlete.set_password('test123')
            db.session.add(athlete)
            print(f"✅ Created athlete: {email}")
    
    # Create a fan/appassionato
    fan = User.query.filter_by(email='fan@test.it').first()
    if not fan:
        fan = User(
            email='fan@test.it',
            username='tifoso_roma',
            first_name='Giovanni',
            last_name='Ferrari',
            role='appassionato',
            is_active=True,
            is_verified=True
        )
        fan.set_password('test123')
        db.session.add(fan)
        db.session.commit()
        print(f"✅ Created fan: {fan.email}")
    
    db.session.commit()
    
    print("\n" + "="*60)
    print("TEST USERS CREATED SUCCESSFULLY")
    print("="*60)
    print("\nLogin credentials (password: test123 for all):")
    print(f"  Admin:   admin@sonacip.it")
    print(f"  Società: societa@test.it")
    print(f"  Staff:   staff@test.it")
    print(f"  Atleta:  giuseppe@test.it")
    print(f"  Fan:     fan@test.it")
    print("\n" + "="*60)
