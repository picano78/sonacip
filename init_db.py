"""Initialize PostgreSQL database using Alembic as source of truth."""

from __future__ import annotations

from sqlalchemy import text, inspect

from app import create_app, db


def init_db() -> None:
    """
    Production-grade init:
    - verify connection
    - run Alembic migrations
    - seed defaults only if DB is empty
    """
    app = create_app()
    with app.app_context():
        # Verify connection
        db.session.execute(text("SELECT 1"))

        # Run migrations (fail-fast)
        from flask_migrate import upgrade

        migrations_dir = app.config.get("MIGRATIONS_DIR", "migrations")
        upgrade(directory=migrations_dir, revision="heads")

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
            from app.core.seed import seed_defaults

            seed_defaults(app)
            print("✓ Seed completed")
        else:
            print("Seed skipped (DB not empty)")

        print("✓ Database initialized")


if __name__ == "__main__":
    init_db()
