"""Script to initialize or upgrade database schema."""
import os
import sys
from app import create_app
from app import db
from app.models import (
    User, Post, Comment, Event, Notification, AuditLog, Backup, Message,
    Contact, Opportunity, CRMActivity, Subscription, Payment,
    Society, Template, Task, Project, SocialSetting, AppearanceSetting,
    StorageSetting, PrivacySetting, AdsSetting, Analytics, Automation,
    AutomationRule, AutomationRun, Team, Role, SocietyCalendarEvent,
    Tournament, TournamentTeam, TournamentMatch, TournamentStanding
)


def init_db():
    """Initialize database with all tables."""
    app = create_app()
    
    with app.app_context():
        print("Creating all database tables...")
        db.create_all()
        print("✓ Database tables created successfully")
        
        # Create default records
        print("\nCreating default settings...")
        
        # Storage settings
        storage = StorageSetting.query.first()
        if not storage:
            storage = StorageSetting(
                storage_backend='local',
                base_path=app.config.get('UPLOAD_FOLDER', 'uploads'),
                preferred_image_format='webp',
                preferred_video_format='mp4',
                image_quality=75,
                video_bitrate=1200000,
                video_max_width=1280,
                max_image_mb=8,
                max_video_mb=64
            )
            db.session.add(storage)
            print("  ✓ Storage settings created")
        
        # Privacy settings
        privacy = PrivacySetting.query.first()
        if not privacy:
            privacy = PrivacySetting(banner_enabled=True)
            db.session.add(privacy)
            print("  ✓ Privacy settings created")
        
        # Ads settings
        ads = AdsSetting.query.first()
        if not ads:
            ads = AdsSetting(
                price_per_day=5.0,
                price_per_thousand_views=2.0,
                default_duration_days=7,
                default_views=500
            )
            db.session.add(ads)
            print("  ✓ Ads settings created")
        
        # Social settings
        social = SocialSetting.query.first()
        if not social:
            social = SocialSetting(
                feed_enabled=True,
                allow_likes=True,
                allow_comments=True,
                allow_shares=True,
                boost_official=True,
                mute_user_posts=False,
                max_posts_per_day=20
            )
            db.session.add(social)
            print("  ✓ Social settings created")
        
        # Appearance settings
        appearance = AppearanceSetting.query.first()
        if not appearance:
            appearance = AppearanceSetting(
                scope='global',
                primary_color='#0d6efd',
                secondary_color='#6c757d',
                accent_color='#20c997',
                font_family='Inter, system-ui, -apple-system, sans-serif'
            )
            db.session.add(appearance)
            print("  ✓ Appearance settings created")
        
        # CRITICAL: Create default roles (User model requires role_id NOT NULL)
        print("\nCreating default roles...")
        required_roles = {
            'super_admin': ("Super Admin", 100, 'Amministratore principale con tutti i permessi'),
            'admin': ("Amministratore", 90, 'Amministratore con permessi completi'),
            'moderator': ("Moderatore", 50, 'Moderatore con permessi di gestione contenuti'),
            'society_admin': ("Admin Società", 45, 'Amministratore società sportiva'),
            'societa': ("Società", 40, 'Società sportiva'),
            'staff': ("Staff", 30, 'Staff tecnico o dirigenziale'),
            'coach': ("Coach", 30, 'Allenatore'),
            'atleta': ("Atleta", 20, 'Atleta registrato'),
            'athlete': ("Athlete", 20, 'Atleta (alias inglese)'),
            'appassionato': ("Appassionato", 10, 'Tifoso o appassionato'),
            'user': ("Utente", 10, 'Utente standard'),
            'guest': ("Ospite", 1, 'Utente ospite con permessi limitati'),
        }

        created_count = 0
        for name, (display, level, description) in required_roles.items():
            if not Role.query.filter_by(name=name).first():
                db.session.add(Role(
                    name=name,
                    display_name=display,
                    level=level,
                    is_system=True,
                    description=description
                ))
                created_count += 1

        if created_count:
            print(f"  ✓ Created {created_count} missing roles")
        else:
            print(f"  ✓ Roles already exist ({Role.query.count()} roles)")
        
        db.session.commit()
        # Seed deterministic defaults required for a fully working installation
        # (permissions, plan 'free', dashboard templates, navbar config, etc.).
        try:
            from app.core.seed import seed_defaults
            summary = seed_defaults(app)
            print("\nSeeding defaults summary:")
            for k, v in (summary or {}).items():
                print(f"  - {k}: {v}")
        except Exception as exc:
            print(f"\n! Warning: default seeding failed: {exc}")

        print("\n✓ Database initialization complete!")
        return True


def add_migration_columns():
    """Add new columns for recent updates."""
    app = create_app()
    
    with app.app_context():
        print("Checking for missing columns...")
        
        # Check AutomationRule columns
        from sqlalchemy import inspect, Integer, DateTime
        inspector = inspect(db.engine)
        
        automation_cols = [col['name'] for col in inspector.get_columns('automation_rule')]
        if 'max_retries' not in automation_cols:
            print("Adding max_retries to automation_rule...")
            db.session.execute(db.text('ALTER TABLE automation_rule ADD COLUMN max_retries INTEGER DEFAULT 3'))
        
        if 'retry_delay' not in automation_cols:
            print("Adding retry_delay to automation_rule...")
            db.session.execute(db.text('ALTER TABLE automation_rule ADD COLUMN retry_delay INTEGER DEFAULT 60'))
        
        # Check AutomationRun columns
        run_cols = [col['name'] for col in inspector.get_columns('automation_run')]
        if 'retry_count' not in run_cols:
            print("Adding retry_count to automation_run...")
            db.session.execute(db.text('ALTER TABLE automation_run ADD COLUMN retry_count INTEGER DEFAULT 0'))
        
        if 'next_retry_at' not in run_cols:
            print("Adding next_retry_at to automation_run...")
            db.session.execute(db.text('ALTER TABLE automation_run ADD COLUMN next_retry_at DATETIME'))
        
        if 'completed_at' not in run_cols:
            print("Adding completed_at to automation_run...")
            db.session.execute(db.text('ALTER TABLE automation_run ADD COLUMN completed_at DATETIME'))
        
        # Check StorageSetting columns
        storage_cols = [col['name'] for col in inspector.get_columns('storage_setting')]
        if 'video_bitrate' not in storage_cols:
            print("Adding video_bitrate to storage_setting...")
            db.session.execute(db.text('ALTER TABLE storage_setting ADD COLUMN video_bitrate INTEGER DEFAULT 1200000'))
        
        if 'video_max_width' not in storage_cols:
            print("Adding video_max_width to storage_setting...")
            db.session.execute(db.text('ALTER TABLE storage_setting ADD COLUMN video_max_width INTEGER DEFAULT 1280'))
        
        if 'max_image_mb' not in storage_cols:
            print("Adding max_image_mb to storage_setting...")
            db.session.execute(db.text('ALTER TABLE storage_setting ADD COLUMN max_image_mb INTEGER DEFAULT 8'))
        
        if 'max_video_mb' not in storage_cols:
            print("Adding max_video_mb to storage_setting...")
            db.session.execute(db.text('ALTER TABLE storage_setting ADD COLUMN max_video_mb INTEGER DEFAULT 64'))
        
        db.session.commit()
        print("✓ Migration columns added successfully")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'migrate':
        add_migration_columns()
    else:
        init_db()
