"""Initialize PostgreSQL database using Alembic as source of truth."""

from __future__ import annotations

import os
from sqlalchemy import text, inspect

# Prevent auto-seed during init_db to avoid conflicts with migrations
os.environ['SKIP_AUTO_SEED'] = '1'

from app import create_app, db


def init_db() -> None:
    """
    Production-grade init:
    - verify connection
    - run Alembic migrations (with fallback to create_all if migrations fail)
    - seed defaults only if DB is empty
    
    Note: Sets SKIP_AUTO_SEED=1 to prevent duplicate seeding during app creation.
    """
    app = create_app()
    with app.app_context():
        # Verify connection
        try:
            db.session.execute(text("SELECT 1"))
            print("✓ Database connection verified")
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            raise

        # Check if tables already exist
        insp = inspect(db.engine)
        tables = set(insp.get_table_names())
        tables_exist = 'role' in tables and 'user' in tables and 'permission' in tables
        
        # Determine if we're using SQLite
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        is_sqlite = 'sqlite:' in db_uri
        
        # Run migrations only if tables don't exist or if we're in a state where migrations make sense
        from flask_migrate import upgrade
        
        migrations_dir = app.config.get("MIGRATIONS_DIR", "migrations")
        
        if tables_exist:
            # Tables already exist - they were likely created by app startup or previous init
            # Skip migration to avoid DuplicateTable errors
            print("ℹ Tables already exist - skipping migration (database already initialized)")
        elif is_sqlite:
            # SQLite doesn't support all ALTER TABLE operations needed by migrations
            # Use create_all instead for SQLite databases
            print("ℹ SQLite detected - using create_all() instead of migrations")
            try:
                from app import models  # noqa: F401
                db.create_all()
                print("✓ Database schema created via create_all()")
            except Exception as create_err:
                print(f"✗ create_all() failed: {create_err}")
                raise
        else:
            # PostgreSQL - use proper migrations
            try:
                upgrade(directory=migrations_dir, revision="heads")
                print("✓ Migrations applied successfully")
            except Exception as e:
                print(f"Warning: Migration upgrade failed: {e}")
                print("Attempting create_all() fallback...")
                try:
                    from app import models  # noqa: F401
                    db.create_all()
                    print("✓ Database schema created via create_all()")
                except Exception as create_err:
                    print(f"✗ create_all() also failed: {create_err}")
                    raise

        # Seed only if empty (no users table rows)
        insp = inspect(db.engine)
        tables = set(insp.get_table_names())
        should_seed = False
        if "user" not in tables:
            should_seed = True
        else:
            try:
                count = db.session.execute(text('SELECT COUNT(*) FROM "user"')).scalar()
                should_seed = int(count or 0) == 0
            except Exception:
                should_seed = True

        if should_seed:
            try:
                from app.core.seed import seed_defaults
                seed_defaults(app)
                print("✓ Seed completed")
            except Exception as e:
                print(f"Warning: Seeding failed (non-fatal): {e}")
        else:
            print("Seed skipped (DB not empty)")

        print("✓ Database initialized")


if __name__ == "__main__":
    init_db()
