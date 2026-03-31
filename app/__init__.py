"""SONACIP application factory and shared extensions."""
from __future__ import annotations

import importlib
import logging
import os
import secrets
import sqlite3
import time

from flask import Flask, flash, redirect, request, session, url_for
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFError, CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool
from werkzeug.exceptions import BadRequest, Forbidden, InternalServerError, NotFound, TooManyRequests, RequestEntityTooLarge, RequestURITooLarge
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_compress import Compress
from authlib.integrations.flask_client import OAuth

from app.core.config import config
from app.core.logging import configure_logging

# Single source of truth for extensions
# Keep sessions alive after commit to avoid DetachedInstanceError in tests/async flows.
db = SQLAlchemy(session_options={"expire_on_commit": False})
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
csrf = CSRFProtect()
try:
    from flask_session import Session  # type: ignore
except Exception:  # pragma: no cover
    Session = None  # type: ignore
session_ext = Session() if Session else None  # type: ignore

# SocketIO for real-time features (livestreaming, chat, notifications)
try:
    from flask_socketio import SocketIO
    socketio = SocketIO()
except Exception:
    socketio = None
# Production-safe: rate limiting should never crash critical endpoints (e.g. /auth/login)
def _get_real_ip():
    """
    Return the real client IP even behind a reverse proxy (nginx).
    Falls back to REMOTE_ADDR if no forwarded header is present.
    """
    from flask import request
    return (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.headers.get("X-Real-Ip", "")
        or request.remote_addr
        or "127.0.0.1"
    )

limiter = Limiter(key_func=_get_real_ip, swallow_errors=True)
oauth = OAuth()

# Global SQLAlchemy hook: enforce safe pragmas on SQLite connections.
# This must be registered without touching `db.engine` (which requires app context).
@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record):
    try:
        if not isinstance(dbapi_connection, sqlite3.Connection):
            return
        # During pytest runs we need to allow teardown to drop tables with FKs.
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return
        cur = dbapi_connection.cursor()
        # Enable WAL for better concurrent reads/writes under gunicorn.
        cur.execute("PRAGMA journal_mode=WAL;")
        # Reduce fsync overhead while staying safe enough for web workloads.
        cur.execute("PRAGMA synchronous=NORMAL;")
        # Enforce FK constraints.
        cur.execute("PRAGMA foreign_keys=ON;")
        cur.close()
    except Exception:
        return

# Explicit core module list (ordered, stable)
CORE_MODULES = [
    'main',
    'auth',
    'admin',
    'ads',
    'crm',
    'events',
    'social',
    'backup',
    'notifications',
    'analytics',
    'messages',
    'tournaments',
    'tasks',
    'scheduler',
    'field_planner',
    'subscription',
    'marketplace',
    'groups',
    'stories',
    'livestream',
    'polls',
    'stats',
    'payments',
    'accounting',
    'documents',
    'gamification',
    'security',
]


def _register_blueprints(app: Flask, modules: list[str] | None = None) -> None:
    if modules is None:
        modules = CORE_MODULES

    for module_name in modules:
        try:
            routes_module = importlib.import_module(f'app.{module_name}.routes')
        except ModuleNotFoundError as exc:
            if exc.name != f'app.{module_name}.routes':
                raise
            routes_module = importlib.import_module(f'app.{module_name}')

        blueprint = getattr(routes_module, 'bp', None)
        if blueprint is None:
            raise RuntimeError(
                f"Blueprint 'bp' non trovato in app.{module_name}.routes"
            )

        app.register_blueprint(blueprint)

        # Optional legacy/alias blueprint support
        legacy_blueprint = getattr(routes_module, 'legacy_bp', None)
        if legacy_blueprint is not None:
            app.register_blueprint(legacy_blueprint)


def _load_dotenv_if_present() -> None:
    """
    Load `.env` from repo root if present.
    If not present, create with fixed credentials.
    """
    try:
        from dotenv import load_dotenv
        
        # Load from repo root (preferred location for production .env file)
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        env_path = os.path.join(repo_root, ".env")
        
        # If .env doesn't exist, create it with fixed credentials
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                f.write("SUPERADMIN_EMAIL=picano78@gmail.com\n")
                f.write("SUPERADMIN_PASSWORD=Picano78\n")
                f.write("SECRET_KEY=4f8a2b9c1d3e5f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2\n")
                f.write("SQLALCHEMY_DATABASE_URI=sqlite:///uploads/sonacip.db\n")
                f.write("FLASK_ENV=production\n")
                f.write("FLASK_DEBUG=False\n")
                f.write("PORT=8000\n")
            import logging
            logging.getLogger(__name__).info(f"[OK] Created .env at {env_path}")
        
        # Load .env with override=True to ensure it takes precedence
        load_dotenv(env_path, override=True)
        import logging
        logging.getLogger(__name__).info(f"[OK] Loaded .env from {env_path}")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[ERROR] Failed to load/create .env: {e}")
        # Don't crash - continue with environment variables


def _ensure_secret_key(app: Flask) -> None:
    """
    Ensure `SECRET_KEY` is always available for sessions + CSRF.

    Priority:
    1) app.config SECRET_KEY (from config object)
    2) os.environ SECRET_KEY (possibly loaded from .env)
    3) persistent instance secret file (generated once)
    4) ephemeral generated secret (last resort; avoids hard crash)
    """
    # If config already has it, also mirror to env for config validators that read os.environ.
    if app.config.get("SECRET_KEY"):
        os.environ.setdefault("SECRET_KEY", app.config["SECRET_KEY"])
        return

    env_secret = os.environ.get("SECRET_KEY")
    if env_secret:
        app.config["SECRET_KEY"] = env_secret
        return

    def _try_secret_dir(dir_path: str | None, *, create_dir: bool) -> str | None:
        if not dir_path:
            return None
        try:
            if create_dir:
                os.makedirs(dir_path, exist_ok=True)
            else:
                if not os.path.isdir(dir_path):
                    return None
        except Exception:
            return None

        secret_file = os.path.join(dir_path, "secret_key")

        # Read existing
        try:
            if os.path.exists(secret_file):
                with open(secret_file, "r", encoding="utf-8") as f:
                    existing = (f.read() or "").strip()
                if existing:
                    return existing
        except Exception:
            pass

        # Create new
        try:
            val = secrets.token_hex(32)
            with open(secret_file, "w", encoding="utf-8") as f:
                f.write(val)
            try:
                os.chmod(secret_file, 0o600)
            except Exception:
                pass
            return val
        except Exception:
            return None

    # Try multiple persistent locations (ordered).
    # instance_path may be read-only under some systemd deployments.
    candidates = [
        # Best default for Flask apps (may be writable in systemd deployments)
        (app.instance_path, True),
        # Existing persistent dirs (do not auto-create them at runtime)
        (app.config.get("LOGS_FOLDER"), False),
        (app.config.get("BACKUP_FOLDER"), False),
        (os.path.expanduser("~/.sonacip"), True),
    ]

    for d, create_dir in candidates:
        val = _try_secret_dir(d, create_dir=create_dir)
        if val:
            app.config["SECRET_KEY"] = val
            os.environ["SECRET_KEY"] = val
            return

    # Last resort: ephemeral secret (keeps app alive; sessions reset on restart)
    val = secrets.token_hex(32)
    app.config["SECRET_KEY"] = val
    os.environ["SECRET_KEY"] = val
    try:
        app.logger.warning(
            "SECRET_KEY was missing and could not be persisted; using an ephemeral key."
        )
    except Exception:
        pass


def _is_safe_referrer(app: Flask, ref: str | None) -> bool:
    if not ref:
        return False
    try:
        # Allow relative URLs
        if ref.startswith("/"):
            return True
        # Allow same-origin absolute URLs
        return ref.startswith(app.config.get("PREFERRED_URL_SCHEME", "http") + "://") and ref.startswith(request.host_url)
    except Exception:
        return False


def _normalize_sqlite_db(app: Flask) -> None:
    """
    Production-hardening for SQLite under gunicorn/systemd:
    - normalize relative sqlite paths to absolute
    - ensure DB path points to a writable location
    - add connect timeout + NullPool to reduce 'database is locked'
    """
    uri = (app.config.get("SQLALCHEMY_DATABASE_URI") or "").strip()
    if not uri.startswith("sqlite:"):
        return
    # Never rewrite in-memory SQLite (used for tests).
    if app.config.get("TESTING") or ":memory:" in uri:
        return

    # Extract path (best-effort) from sqlite URL.
    db_path = None
    if uri.startswith("sqlite:////"):
        db_path = "/" + uri.split("sqlite:////", 1)[1]
    elif uri.startswith("sqlite:///"):
        db_path = uri.split("sqlite:///", 1)[1]

    base_dir = app.config.get("BASE_DIR") or os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

    def _abs(p: str) -> str:
        if not p:
            return p
        if os.path.isabs(p):
            return p
        return os.path.abspath(os.path.join(str(base_dir), p))

    if db_path:
        db_path = _abs(db_path)

    # Candidate DB files (keep existing DB if present).
    existing_candidates = []
    if db_path:
        existing_candidates.append(db_path)
    existing_candidates.append(os.path.join(str(base_dir), "sonacip.db"))

    chosen = None
    for p in existing_candidates:
        try:
            if p and os.path.exists(p):
                chosen = p
                break
        except Exception:
            continue

    if chosen:
        # If existing DB is not writable by the process, attempt to copy it to a writable dir.
        try:
            if not os.access(chosen, os.W_OK):
                # Prefer uploads dir (usually writable) then instance path then home.
                candidates = [
                    app.config.get("UPLOAD_FOLDER"),
                    app.instance_path,
                    os.path.expanduser("~/.sonacip"),
                ]
                target_dir = None
                for d in candidates:
                    if not d:
                        continue
                    try:
                        os.makedirs(d, exist_ok=True)
                        if os.access(d, os.W_OK):
                            target_dir = d
                            break
                    except Exception:
                        continue
                if target_dir:
                    import shutil
                    target = os.path.join(target_dir, "sonacip.db")
                    if not os.path.exists(target):
                        shutil.copy2(chosen, target)
                    chosen = target
        except Exception:
            pass
    else:
        # No DB file found: choose a writable location for new installs.
        candidates = [
            app.config.get("UPLOAD_FOLDER"),
            app.instance_path,
            os.path.expanduser("~/.sonacip"),
            "/tmp",
        ]
        for d in candidates:
            if not d:
                continue
            try:
                os.makedirs(d, exist_ok=True)
                if os.access(d, os.W_OK):
                    chosen = os.path.join(d, "sonacip.db")
                    break
            except Exception:
                continue

    if chosen:
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{chosen}"

    # SQLite engine options: reduce lock errors under concurrency.
    opts = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS") or {})
    connect_args = dict(opts.get("connect_args") or {})
    # NOTE: this is seconds for sqlite3.connect timeout
    connect_args.setdefault("timeout", int(app.config.get("SQLITE_TIMEOUT", 60)))
    connect_args.setdefault("check_same_thread", False)
    opts["connect_args"] = connect_args
    opts.setdefault("poolclass", NullPool)
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = opts


def _sqlite_add_missing_columns(app: Flask, _db) -> None:
    """
    SQLite does not add columns to existing tables via db.create_all().
    This inspects every model table and adds any missing columns with
    ALTER TABLE ADD COLUMN (which SQLite supports).
    """
    try:
        from sqlalchemy import inspect as sa_inspect, text
        from app import models as _models  # noqa: F401 — ensure metadata is populated

        inspector = sa_inspect(_db.engine)
        existing_tables = set(inspector.get_table_names())

        def _sa_type_to_sqlite(col_type) -> str:
            type_name = type(col_type).__name__.upper()
            type_str = str(col_type).split('(')[0].upper()
            integer_types = {'INTEGER', 'SMALLINT', 'SMALLINTEGER', 'BIGINT',
                             'BIGINTEGER', 'INT', 'TINYINT'}
            real_types = {'FLOAT', 'REAL', 'DOUBLE', 'NUMERIC', 'DECIMAL'}
            text_types = {'VARCHAR', 'STRING', 'TEXT', 'CHAR', 'NVARCHAR',
                          'NCHAR', 'CLOB', 'UUID', 'ENUM', 'JSON'}
            blob_types = {'BLOB', 'LARGEBINARY', 'BINARY', 'VARBINARY',
                          'LONGBLOB', 'MEDIUMBLOB'}
            if type_name in integer_types or type_str in integer_types:
                return 'INTEGER'
            if type_name == 'BOOLEAN' or type_str == 'BOOLEAN':
                return 'INTEGER'
            if type_name in real_types or type_str in real_types:
                return 'REAL'
            if type_name in blob_types or type_str in blob_types:
                return 'BLOB'
            if type_name in ('DATE', 'DATETIME', 'TIMESTAMP', 'TIME'):
                return 'TEXT'
            if type_name in text_types or type_str in text_types:
                return 'TEXT'
            return 'TEXT'

        def _default_sql(col) -> str:
            if col.default is not None:
                try:
                    if col.default.is_scalar:
                        val = col.default.arg
                        if isinstance(val, bool):
                            return f' DEFAULT {1 if val else 0}'
                        if isinstance(val, (int, float)):
                            return f' DEFAULT {val}'
                        if isinstance(val, str):
                            return f" DEFAULT '{val.replace(chr(39), chr(39)+chr(39))}'"
                except Exception:
                    pass
            if col.server_default is not None:
                try:
                    raw = col.server_default.arg
                    sd = str(raw.text) if hasattr(raw, 'text') else str(raw)
                    sd = sd.strip("'\"")
                    if sd.upper() in ('CURRENT_TIMESTAMP', 'NOW()'):
                        return " DEFAULT CURRENT_TIMESTAMP"
                    if sd.upper() in ('TRUE', 'FALSE'):
                        return f" DEFAULT {1 if sd.upper() == 'TRUE' else 0}"
                    try:
                        numeric = float(sd)
                        return f" DEFAULT {numeric}"
                    except (ValueError, TypeError):
                        pass
                    return f" DEFAULT '{sd.replace(chr(39), chr(39)+chr(39))}'"
                except Exception:
                    pass
            if col.nullable is not False:
                return ' DEFAULT NULL'
            sqlite_type = _sa_type_to_sqlite(col.type)
            if sqlite_type == 'INTEGER':
                return ' DEFAULT 0'
            if sqlite_type == 'REAL':
                return ' DEFAULT 0.0'
            return " DEFAULT ''"

        added_count = 0
        checked_tables = 0
        for table_name, table_obj in _db.metadata.tables.items():
            if table_name not in existing_tables:
                continue
            checked_tables += 1

            existing_cols = {c['name'] for c in inspector.get_columns(table_name)}

            for col in table_obj.columns:
                if col.name in existing_cols:
                    continue

                sqlite_type = _sa_type_to_sqlite(col.type)
                default_clause = _default_sql(col)

                sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{col.name}" {sqlite_type}{default_clause}'
                try:
                    _db.session.execute(text(sql))
                    _db.session.commit()
                    added_count += 1
                    app.logger.info("SQLite: added column %s.%s (%s%s)", table_name, col.name, sqlite_type, default_clause)
                except Exception as col_err:
                    _db.session.rollback()
                    app.logger.warning("SQLite: could not add column %s.%s: %s", table_name, col.name, col_err)
        app.logger.info("SQLite schema check complete: %d tables inspected, %d columns added", checked_tables, added_count)
    except Exception:
        try:
            app.logger.exception("SQLite missing-column check failed")
        except Exception:
            pass


def _auto_seed(app: Flask) -> None:
    """
    Run idempotent seed on startup so roles + super admin always exist.
    Safe to call multiple times (seed_defaults is idempotent).
    Ensures database tables exist before seeding.
    """
    try:
        from app.core.seed import seed_defaults
        from sqlalchemy.exc import SQLAlchemyError
        with app.app_context():
            # Ensure database tables exist before seeding
            try:
                from sqlalchemy import inspect
                inspector = inspect(db.engine)
                tables = set(inspector.get_table_names())
                
                # If critical tables don't exist, create all tables
                if 'role' not in tables or 'user' not in tables:
                    db.create_all()
                    app.logger.info("Database tables created")
            except SQLAlchemyError as e:
                # If inspection fails, try create_all anyway (idempotent)
                app.logger.warning("Unable to inspect database schema, falling back to table creation: %s", e)
                try:
                    db.create_all()
                    app.logger.info("Database tables created via fallback")
                except SQLAlchemyError as create_err:
                    app.logger.error("Failed to create database tables - seeding may fail: %s", create_err)
                    # Continue anyway - seed might still work if tables were created elsewhere
            
            summary = seed_defaults(app)
            created = sum(v for v in summary.values() if isinstance(v, int))
            if created:
                app.logger.info("Auto-seed completed: %s", summary)
    except Exception as e:
        app.logger.exception("Auto-seed failed (non-fatal)")


def _auto_upgrade_db(app: Flask) -> None:
    """
    Ensure DB schema is upgraded without manual commands.

    This is critical for deployments where an old DB schema would otherwise
    crash login/registration with OperationalError (missing tables/columns).
    Works with both SQLite and PostgreSQL databases.
    Uses a file lock (SQLite) or advisory approach to avoid concurrent upgrades.
    
    SAFETY: Only runs when:
    - Not in TESTING mode
    - RUN_MAIN environment variable is set to "true"
    
    NOTE: RUN_MAIN is a Werkzeug-specific flag set during development server reloads.
    For production (Gunicorn/uWSGI), set RUN_MAIN=true explicitly if you want auto-migrations.
    Otherwise, run migrations manually via "flask db upgrade" before starting the server.
    """
    if app.config.get("TESTING"):
        return
    
    # Only run auto-upgrade when RUN_MAIN is "true"
    # This prevents conflicts with Flask CLI commands like "flask db upgrade"
    # and gives operators explicit control over when auto-migrations occur
    if os.getenv("RUN_MAIN") != "true":
        return

    uri = (app.config.get("SQLALCHEMY_DATABASE_URI") or "").strip()
    is_sqlite = uri.startswith("sqlite:")

    base_dir = app.config.get("BASE_DIR") or os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir)
    )
    migrate_dir = app.config.get("MIGRATIONS_DIR") or os.path.join(base_dir, "migrations")

    def _try_alembic_upgrade_strict() -> None:
        from flask_migrate import upgrade as migrate_upgrade
        with app.app_context():
            migrate_upgrade(directory=migrate_dir, revision="heads")

    def _ensure_schema():
        # In production, Alembic is the only source of truth.
        # We keep create_all only for test/dev SQLite paths (never for production PG).
        with app.app_context():
            from app import models as _models  # noqa: F401
            db.create_all()
            if is_sqlite:
                _sqlite_add_missing_columns(app, db)

    # PostgreSQL: strict Alembic upgrade only (fail-fast).
    # SQLite: best-effort (dev/testing only).
    if not is_sqlite:
        _try_alembic_upgrade_strict()
        return

    # SQLite path (dev/testing): keep old behavior but never crash the app.
    try:
        db_path = None
        if uri.startswith("sqlite:////"):
            db_path = "/" + uri.split("sqlite:////", 1)[1]
        elif uri.startswith("sqlite:///"):
            db_path = uri.split("sqlite:///", 1)[1]

        if db_path:
            lock_dir = os.path.dirname(db_path) or base_dir
            lock_path = os.path.join(lock_dir, ".sonacip_alembic_upgrade.lock")
            os.makedirs(lock_dir, exist_ok=True)

            import fcntl
            with open(lock_path, "w", encoding="utf-8") as lockf:
                start = time.time()
                while True:
                    try:
                        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.time() - start > 30:
                            _ensure_schema()
                            return
                        time.sleep(0.2)
                try:
                    _try_alembic_upgrade_strict()
                except Exception:
                    _ensure_schema()
        else:
            try:
                _try_alembic_upgrade_strict()
            except Exception:
                _ensure_schema()
    except Exception:
        _ensure_schema()


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application."""
    _load_dotenv_if_present()
    configure_logging()
    app = Flask(__name__)

    if config_name is None:
        # When running tests under pytest, default to the dedicated TestingConfig.
        # This prevents auto-upgrades/seeding from polluting unit tests and ensures
        # the DB URI is set before SQLAlchemy initializes.
        import sys
        if os.environ.get("PYTEST_CURRENT_TEST") is not None or "pytest" in sys.modules:
            config_name = 'testing'
        else:
            config_name = os.environ.get('APP_ENV') or os.environ.get('FLASK_ENV') or 'development'

    if config_name not in config:
        config_name = 'development'

    config_class = config[config_name]
    app.config.from_object(config_class)

    # Re-read SUPERADMIN credentials from os.environ after dotenv loading.
    # The Config class attributes are evaluated at import time (before dotenv),
    # so we need to refresh them with values now available from .env.
    for _key in ('SUPERADMIN_EMAIL', 'SUPERADMIN_PASSWORD'):
        _val = os.environ.get(_key) or None
        if _val is not None:
            app.config[_key] = _val

    # Ensure DB URI is resolved *after* dotenv is loaded.
    # Use config default (SQLite) if DATABASE_URL not provided
    if not app.config.get("TESTING"):
        base_dir = app.config.get("BASE_DIR") or os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        uploads_dir = os.path.join(str(base_dir), "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        for _sub in ("avatars", "covers", "posts", "groups", "group_avatars",
                      "stories", "marketplace", "message_attachments",
                      "message_photos", "icons", "invoice_logos"):
            os.makedirs(os.path.join(uploads_dir, _sub), exist_ok=True)

        db_uri = (os.environ.get("DATABASE_URL") or "").strip()
        if db_uri.startswith("postgres://"):
            db_uri = db_uri.replace("postgres://", "postgresql://", 1)
        
        # If no DATABASE_URL, use the config default (SQLite for dev)
        if not db_uri:
            db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        
        # Update config with resolved URI
        if db_uri:
            app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    def _configure_redis_backends() -> None:
        """
        Optional Redis integration:
        - Sessions backend
        - Flask-Limiter storage
        Falls back safely if Redis is not reachable.
        """
        # Set default SESSION_TYPE to prevent "Unrecognized value for SESSION_TYPE: null" error
        app.config.setdefault("SESSION_TYPE", "filesystem")
        
        redis_url = (os.environ.get("REDIS_URL") or app.config.get("REDIS_URL") or "").strip()
        if not redis_url:
            return
        try:
            import redis as _redis  # type: ignore
        except Exception:
            try:
                app.logger.warning("REDIS_URL is set but python 'redis' package is missing")
            except Exception:
                pass
            return
        try:
            client = _redis.from_url(redis_url)
            client.ping()
        except Exception as exc:
            try:
                app.logger.warning("Redis not reachable (%s): %s", redis_url, exc)
            except Exception:
                pass
            return

        # Sessions (server-side) if Flask-Session is installed
        if session_ext is not None:
            try:
                app.config.setdefault("SESSION_TYPE", "redis")
                app.config.setdefault("SESSION_USE_SIGNER", True)
                app.config.setdefault("SESSION_PERMANENT", True)
                app.config.setdefault("SESSION_REDIS", client)
            except Exception:
                pass

        # Limiter storage (only if not explicitly set)
        if not (os.environ.get("RATELIMIT_STORAGE_URI") or app.config.get("RATELIMIT_STORAGE_URI")):
            # Use separate DB in Redis by default to keep it isolated from cache
            if redis_url.rstrip("/").endswith("/0"):
                app.config["RATELIMIT_STORAGE_URI"] = redis_url.rsplit("/", 1)[0] + "/1"
            else:
                app.config["RATELIMIT_STORAGE_URI"] = redis_url

    _configure_redis_backends()

    _ensure_secret_key(app)
    _normalize_sqlite_db(app)

    # Safety log: show effective DB target at startup (do not leak passwords)
    try:
        from sqlalchemy.engine import make_url

        raw = app.config.get("SQLALCHEMY_DATABASE_URI")
        safe = raw
        try:
            safe = make_url(raw).render_as_string(hide_password=True) if raw else raw
        except Exception:
            # Fallback: strip password in basic "user:pass@" pattern
            import re

            if isinstance(raw, str):
                safe = re.sub(r"://([^:/@]+):([^@]+)@", r"://\1:***@", raw)
        
        logger = logging.getLogger(__name__)
        logger.info(f"Database connected to: {safe}")
    except Exception:
        pass

    if hasattr(config_class, 'validate_config'):
        # Only validate config for non-CLI contexts (avoid crashing during "flask db upgrade")
        # Check if we're running under Flask CLI
        import sys
        is_flask_cli = False
        try:
            # More robust check: use Flask's CLI context
            from flask import cli
            is_flask_cli = cli.get_current_context(silent=True) is not None
        except Exception:
            # Fallback: check sys.argv if available
            if len(sys.argv) > 0:
                is_flask_cli = "flask" in sys.argv[0] or any("flask" in str(arg) for arg in sys.argv)
        
        if not is_flask_cli:
            config_class.validate_config()

    if app.config.get('USE_PROXYFIX'):
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=app.config.get('PROXYFIX_X_FOR', 1),
            x_proto=app.config.get('PROXYFIX_X_PROTO', 1),
            x_host=app.config.get('PROXYFIX_X_HOST', 1),
            x_port=app.config.get('PROXYFIX_X_PORT', 1),
            x_prefix=app.config.get('PROXYFIX_X_PREFIX', 0),
        )

    app.config.setdefault('RATELIMIT_STORAGE_URI', 'memory://')

    uri = (app.config.get("SQLALCHEMY_DATABASE_URI") or "").strip()
    if uri.startswith("postgresql") or uri.startswith("postgres"):
        pg_opts = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS") or {})
        pg_opts.setdefault("pool_pre_ping", True)
        pg_opts.setdefault("pool_recycle", 300)
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = pg_opts

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    oauth.init_app(app)
    
    # Initialize compression for better performance
    try:
        compress = Compress()
        compress.init_app(app)
        app.config.setdefault('COMPRESS_MIMETYPES', [
            'text/html', 'text/css', 'text/xml', 'text/plain',
            'application/json', 'application/javascript', 'application/xml',
            'application/x-javascript', 'text/javascript'
        ])
        app.config.setdefault('COMPRESS_LEVEL', 6)
        app.config.setdefault('COMPRESS_MIN_SIZE', 500)
    except Exception:
        # Compression is optional; app should work without it
        try:
            app.logger.warning("Flask-Compress not available, compression disabled")
        except Exception:
            pass
    
    if session_ext is not None:
        try:
            session_ext.init_app(app)
        except Exception:
            # Sessions must not crash startup; cookie sessions will be used instead.
            try:
                app.logger.exception("Failed to init Flask-Session (non-fatal)")
            except Exception:
                pass

    # Security event logger
    from app.security.logger import security_logger
    security_logger.init_app(app)
    app.security_logger = security_logger
    
    # Setup file logging with rotation
    from app.core.logging import setup_file_logging
    setup_file_logging(app)

    # Schema alignment removed: migrations must run via CLI only
    # Production deployments should run "flask db upgrade" separately
    # App must start even if DB is empty

    login_manager.login_view = 'auth.login'

    def _wants_json() -> bool:
        try:
            if request.is_json:
                return True
            best = request.accept_mimetypes.best or ""
            return "json" in best
        except Exception:
            return False

    @app.errorhandler(CSRFError)
    def handle_csrf_error(err: CSRFError):
        # Do not show Werkzeug default HTML (it leaks implementation details).
        if _wants_json():
            return {"error": "csrf_failed"}, 400

        flash("Sessione scaduta o richiesta non valida. Riprova.", "warning")

        # Prefer redirecting back to the relevant form.
        if request.endpoint in ("auth.login", "auth.register", "auth.register_society"):
            return redirect(url_for(request.endpoint))

        ref = request.referrer
        if _is_safe_referrer(app, ref):
            return redirect(ref)

        return redirect(url_for("main.index"))

    @app.errorhandler(TooManyRequests)
    def handle_rate_limited(err: TooManyRequests):
        if _wants_json():
            return {"error": "rate_limited"}, 429

        # Friendly page instead of default 429 HTML
        return (
            "<!doctype html><html lang='it'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Troppe richieste</title></head><body>"
            "<h1>Troppe richieste</h1>"
            "<p>Hai effettuato troppe operazioni in poco tempo. Attendi e riprova.</p>"
            "<p><a href='/'>Torna alla home</a></p>"
            "</body></html>",
            429,
        )

    @app.errorhandler(BadRequest)
    def handle_bad_request(err: BadRequest):
        if _wants_json():
            return {"error": "bad_request"}, 400
        return (
            "<!doctype html><html lang='it'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Richiesta non valida</title></head><body>"
            "<h1>Richiesta non valida</h1>"
            "<p>La richiesta non è valida o la sessione è scaduta. Riprova.</p>"
            "<p><a href='/'>Torna alla home</a></p>"
            "</body></html>",
            400,
        )

    @app.errorhandler(RequestEntityTooLarge)
    def handle_file_too_large(err: RequestEntityTooLarge):
        max_size_mb = app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024) / (1024 * 1024)
        msg = f"File troppo grande. La dimensione massima consentita è {max_size_mb:.0f} MB."
        
        if _wants_json():
            return {"error": "file_too_large", "message": msg, "max_size_mb": max_size_mb}, 413
        
        flash(msg, "danger")
        
        # Try to redirect back to referrer
        ref = request.referrer
        if _is_safe_referrer(app, ref):
            return redirect(ref)
        
        return redirect(url_for("main.index"))

    @app.errorhandler(RequestURITooLarge)
    def handle_uri_too_large(err: RequestURITooLarge):
        if _wants_json():
            return {"error": "uri_too_large"}, 414
        
        flash("L'URL della richiesta è troppo lungo. Riduci la dimensione dei dati inviati.", "danger")
        
        # Try to redirect back to referrer
        ref = request.referrer
        if _is_safe_referrer(app, ref):
            return redirect(ref)
        
        return redirect(url_for("main.index"))

    from flask import render_template as _rt

    def _error_page(template: str, code: int, fallback_title: str, fallback_msg: str):
        try:
            return _rt(template), code
        except Exception as template_err:
            app.logger.error(f"Failed to render error template {template}: {template_err}")
            return (
                f"<!doctype html><html lang='it'><head><meta charset='utf-8'>"
                f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
                f"<title>{fallback_title}</title></head><body>"
                f"<h1>{fallback_title}</h1><p>{fallback_msg}</p>"
                f"<p><a href='/'>Torna alla home</a></p></body></html>"
            ), code

    @app.errorhandler(Forbidden)
    def handle_forbidden(err: Forbidden):
        if _wants_json():
            return {"error": "forbidden"}, 403
        return _error_page("errors/403.html", 403, "Accesso negato", "Non hai i permessi per accedere a questa risorsa.")

    @app.errorhandler(NotFound)
    def handle_not_found(err: NotFound):
        if _wants_json():
            return {"error": "not_found"}, 404
        return _error_page("errors/404.html", 404, "Pagina non trovata", "La pagina richiesta non esiste.")

    @app.errorhandler(InternalServerError)
    def handle_internal_server_error(err: InternalServerError):
        # Log dettagliato dell'errore per il debugging
        try:
            from flask_login import current_user
            user_info = f"User ID: {current_user.id}" if current_user and current_user.is_authenticated else "Anonymous"
            app.logger.error(
                f"500 Internal Server Error - {request.method} {request.url} - {user_info} - IP: {request.remote_addr}"
            )
            app.logger.exception("Dettagli dell'errore 500:")
        except Exception:
            app.logger.exception("500 Internal Server Error (failed to log context):")
        
        if _wants_json():
            return {"error": "internal_server_error"}, 500
        return _error_page("errors/500.html", 500, "Errore del server", "Riprova tra qualche istante.")

    @app.errorhandler(Exception)
    def handle_unexpected_error(err: Exception):
        """Cattura tutte le eccezioni non gestite e le logga."""
        try:
            from flask_login import current_user
            user_info = f"User ID: {current_user.id}" if current_user and current_user.is_authenticated else "Anonymous"
            app.logger.error(
                f"Unhandled Exception - {request.method} {request.url} - {user_info} - IP: {request.remote_addr}"
            )
            app.logger.exception(f"Tipo eccezione: {type(err).__name__} - Dettagli:")
        except Exception:
            app.logger.exception("Unhandled Exception (failed to log context):")
        
        if _wants_json():
            return {"error": "internal_server_error"}, 500
        return _error_page("errors/500.html", 500, "Errore del server", "Riprova tra qualche istante.")

    @login_manager.user_loader
    def load_user(user_id):
        try:
            from app.models import User
            return db.session.get(User, int(user_id))
        except Exception:
            return None

    from app.utils import timeago, datetime_format
    app.template_filter('timeago')(timeago)
    app.template_filter('datetime_format')(datetime_format)
    app.template_filter('strftime')(datetime_format)
    # JSON helper for admin templates (safe).
    def _fromjson(val):
        import json as _json
        if val is None:
            return None
        if isinstance(val, (dict, list)):
            return val
        try:
            return _json.loads(val)
        except Exception:
            return []
    app.template_filter('fromjson')(_fromjson)

    # Add version helper for cache busting
    # Note: Cache is bounded by the number of static files in the app (typically small)
    # For apps with many dynamic static files, consider adding a size limit
    _static_versions = {}
    
    def static_versioned(filename):
        """Generate versioned URL for static files for cache busting.
        
        Uses file modification time as version parameter to ensure browsers
        get fresh files when they change, while maintaining long cache times.
        """
        if filename in _static_versions:
            return _static_versions[filename]
        
        try:
            # Get file modification time as version
            static_path = os.path.join(app.static_folder or '', filename)
            if os.path.exists(static_path):
                # Use mtime directly - simpler and equally effective
                version = str(int(os.path.getmtime(static_path)))
                versioned_url = url_for('static', filename=filename, v=version)
                _static_versions[filename] = versioned_url
                return versioned_url
        except Exception:
            pass
        
        # Fallback to regular URL
        return url_for('static', filename=filename)
    
    app.jinja_env.globals['static_versioned'] = static_versioned

    from app.core.bootstrap import discover_and_register_modules
    _register_blueprints(app)
    discover_and_register_modules(app, strict=False)

    # Register automation builder blueprint
    try:
        from app.automation.builder import automation_builder
        app.register_blueprint(automation_builder)
    except Exception:
        app.logger.debug("Automation builder blueprint not loaded (non-fatal)")

    # External drop-in plugins (filesystem-based)
    # PRODUCTION FIX: Ignore invalid files like README.md
    try:
        from app.core.plugins import load_external_plugins
        loaded_plugins = load_external_plugins(app)
        if loaded_plugins:
            app.logger.info(f"[OK] Loaded {len(loaded_plugins)} external plugins")
    except Exception as e:
        app.logger.error(f"[WARNING] External plugins load failed (non-fatal): {e}")

    @app.context_processor
    def inject_platform_context():
        """Globals used by base templates (theme, privacy, counts, per-page content)."""
        from flask_login import current_user

        from app.utils import can as can_fn, get_active_society_id

        appearance = None
        privacy = None
        site = None
        page = None
        nav_links = None
        sidebar_menu_config = None
        society_scopes = []
        active_society = None
        active_society_id = None

        try:
            from app.models import (
                AppearanceSetting,
                CustomizationKV,
                Message,
                Notification,
                PageCustomization,
                PrivacySetting,
                SiteCustomization,
            )

            appearance = AppearanceSetting.query.filter_by(scope='global').order_by(AppearanceSetting.id.desc()).first()
            privacy = PrivacySetting.query.order_by(PrivacySetting.id.desc()).first()
            site = SiteCustomization.query.order_by(SiteCustomization.id.desc()).first()

            endpoint = request.endpoint or ''
            if endpoint:
                page = PageCustomization.query.filter_by(slug=endpoint).first()

            # Admin-configurable navigation links (site scope)
            nav_row = CustomizationKV.query.filter_by(scope='site', scope_key=None, key='navbar.links').first()
            nav_links = nav_row.get_value(default=None) if nav_row else None

            # Admin-configurable sidebar menu order
            sidebar_menu_config = None
            try:
                menu_row = CustomizationKV.query.filter_by(scope='site', scope_key=None, key='sidebar.menu_order').first()
                if menu_row:
                    sidebar_menu_config = menu_row.get_value(default=None)
            except Exception:
                pass

            def _get_unread_notifications_count():
                if not current_user.is_authenticated:
                    return 0
                return Notification.query.filter_by(user_id=current_user.id, is_read=False).count()

            def _get_unread_messages_count():
                if not current_user.is_authenticated:
                    return 0
                return Message.query.filter_by(recipient_id=current_user.id, is_read=False).count()

            # Society scope switcher (when user has multiple memberships)
            try:
                from app.models import SocietyMembership, Society

                if current_user.is_authenticated:
                    scopes = []
                    # Society users own their society profile
                    if current_user.is_society() and getattr(current_user, "society_profile", None):
                        scopes.append(current_user.society_profile)
                    # Membership-based scopes
                    ms = SocietyMembership.query.filter_by(user_id=current_user.id, status='active').all()
                    for m in ms:
                        if m.society:
                            scopes.append(m.society)
                    # Deduplicate by id
                    uniq = {}
                    for s in scopes:
                        try:
                            uniq[int(s.id)] = s
                        except Exception:
                            continue
                    society_scopes = list(uniq.values())
                    active_society_id = get_active_society_id(current_user)
                    if active_society_id:
                        active_society = uniq.get(int(active_society_id)) or db.session.get(Society, int(active_society_id))
            except Exception:
                society_scopes = []
                active_society = None
                active_society_id = None

        except Exception:
            # DB not initialized yet or models unavailable: keep templates functional.
            app.logger.warning("Platform context injection failed (DB may not be initialized yet)", exc_info=True)
            def _get_unread_notifications_count():
                return 0

            def _get_unread_messages_count():
                return 0

        from app.translations import t, get_user_language, SUPPORTED_LANGUAGES, LANGUAGE_NAMES, LANGUAGE_FLAGS
        user_lang = get_user_language()

        def translate(key):
            return t(key, user_lang)

        def feature_enabled(feature_key):
            if current_user and current_user.is_authenticated and current_user.is_admin():
                return True
            try:
                from app.models import PlatformFeature
                pf = PlatformFeature.query.filter_by(key=feature_key).first()
                if pf and not pf.is_enabled:
                    return False
            except Exception:
                pass
            return True

        return {
            'can': can_fn,
            'appearance': appearance,
            'privacy': privacy,
            'site': site,
            'page': page,
            'nav_links': nav_links,
            'sidebar_menu_config': sidebar_menu_config,
            'society_scopes': society_scopes,
            'active_society': active_society,
            'active_society_id': active_society_id,
            'get_unread_notifications_count': _get_unread_notifications_count,
            'get_unread_messages_count': _get_unread_messages_count,
            't': translate,
            'user_lang': user_lang,
            'current_language': user_lang,
            'supported_languages': SUPPORTED_LANGUAGES,
            'language_names': LANGUAGE_NAMES,
            'language_flags': LANGUAGE_FLAGS,
            'feature_enabled': feature_enabled,
        }

    # Cache duration constants for HTTP headers
    STATIC_CACHE_MAX_AGE = 31536000  # 1 year for versioned static files
    UPLOAD_CACHE_MAX_AGE = 86400     # 1 day for uploads

    @app.after_request
    def apply_security_headers(resp):
        """Security headers (safe defaults; CSP optional)."""
        try:
            if not app.config.get("SECURITY_HEADERS_ENABLED", True):
                return resp

            resp.headers.setdefault("X-Content-Type-Options", "nosniff")
            resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            resp.headers.setdefault("X-Frame-Options", "DENY")
            resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(self), camera=(self)")

            # Add caching headers for static files to improve performance
            if request.path.startswith('/static/'):
                # Static files cache with long duration - safe with versioned URLs
                # Version query parameters ensure cache busting when files change
                resp.headers.setdefault("Cache-Control", f"public, max-age={STATIC_CACHE_MAX_AGE}, immutable")
            elif request.path.startswith('/uploads/'):
                # Uploaded files cache for moderate time
                resp.headers.setdefault("Cache-Control", f"public, max-age={UPLOAD_CACHE_MAX_AGE}")

            # HSTS only on HTTPS
            try:
                if request.is_secure and app.config.get("HSTS_ENABLED", True):
                    max_age = int(app.config.get("HSTS_MAX_AGE", 63072000))  # 2 years
                    hsts_value = f"max-age={max_age}"
                    if app.config.get("HSTS_INCLUDE_SUBDOMAINS", True):
                        hsts_value += "; includeSubDomains"
                    if app.config.get("HSTS_PRELOAD", False):
                        hsts_value += "; preload"
                    resp.headers.setdefault("Strict-Transport-Security", hsts_value)
            except Exception:
                pass

            # CSP (enabled by default for security)
            if app.config.get("CSP_ENABLED", True):
                # Get CSP policy from config or use defaults
                csp_policy = app.config.get("CSP_POLICY", {})
                if csp_policy:
                    # Build CSP from dictionary
                    csp_parts = []
                    for directive, values in csp_policy.items():
                        if isinstance(values, list):
                            csp_parts.append(f"{directive} {' '.join(values)}")
                        else:
                            csp_parts.append(f"{directive} {values}")
                    csp = "; ".join(csp_parts)
                else:
                    # Fallback to hardcoded CSP
                    csp = (
                        "default-src 'self'; "
                        "base-uri 'self'; "
                        "object-src 'none'; "
                        "frame-ancestors 'none'; "
                        "img-src 'self' data: https:; "
                        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
                        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                        "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
                        "connect-src 'self' https:; "
                        "manifest-src 'self'; "
                    )
                header = "Content-Security-Policy-Report-Only" if app.config.get("CSP_REPORT_ONLY", False) else "Content-Security-Policy"
                resp.headers.setdefault(header, csp)
        except Exception:
            return resp
        return resp

    # Initialize SocketIO for real-time features
    if socketio is not None:
        try:
            # Configure SocketIO with async mode for better performance
            socketio_kwargs = {
                'cors_allowed_origins': '*',  # Configure based on production needs
                'async_mode': 'threading',  # Use threading for compatibility
                'logger': False,
                'engineio_logger': False
            }
            socketio.init_app(app, **socketio_kwargs)
        except Exception as exc:
            try:
                app.logger.warning(f"SocketIO initialization failed (non-fatal): {exc}")
            except Exception:
                pass

    # Auto-seed database to ensure required roles and admin exist
    # This is idempotent and safe to run on every startup
    # Skip if SKIP_AUTO_SEED is set (used by init_db.py to avoid conflicts)
    if not app.config.get("TESTING") and not os.environ.get("SKIP_AUTO_SEED"):
        try:
            _auto_seed(app)
        except Exception as e:
            app.logger.error(f"[ERROR] Auto-seed failed: {e}")
            # Don't crash on seed failure - log and continue

    # Load MAX_CONTENT_LENGTH from admin StorageSetting if available
    if not app.config.get("TESTING"):
        try:
            with app.app_context():
                from app.models import StorageSetting as _SS
                _ss = _SS.query.first()
                if _ss and getattr(_ss, 'max_upload_mb', None):
                    app.config['MAX_CONTENT_LENGTH'] = _ss.max_upload_mb * 1024 * 1024
        except Exception:
            pass  # DB not ready or column missing; keep default

    return app
