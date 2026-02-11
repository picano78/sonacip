"""Script to initialize database schema safely (SQLite default)."""

from app import create_app, db


def init_db() -> None:
    """
    Create all tables for the configured database.
    This should never crash a fresh install.
    """
    app = create_app()
    with app.app_context():
        try:
            db.create_all()
            print("✓ Database initialized")
        except Exception as exc:
            # Never crash installs; print the reason for troubleshooting.
            print("Database init skipped:", exc)


if __name__ == "__main__":
    init_db()
