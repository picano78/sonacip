"""Initialize PostgreSQL database using Alembic as source of truth."""

from __future__ import annotations

from sqlalchemy import text, inspect

from app import create_app, db


def init_db() -> None:
    """
    Production-grade init:
    - verify connection
    - run Alembic migrations (with fallback to create_all if migrations fail)
    - seed defaults only if DB is empty
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

        # Run migrations (with create_all fallback)
        from flask_migrate import upgrade
        
        migrations_dir = app.config.get("MIGRATIONS_DIR", "migrations")
        try:
            upgrade(directory=migrations_dir, revision="heads")
            print("✓ Migrations applied successfully")
        except Exception as e:
            print(f"Warning: Migration upgrade failed: {e}")
            print("Attempting create_all() fallback...")
            try:
                # Import all models to ensure they're registered
                from app import models as _models  # noqa: F401
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
