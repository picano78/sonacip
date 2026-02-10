"""SONACIP application factory and shared extensions."""
from __future__ import annotations

import importlib
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
from werkzeug.exceptions import BadRequest, Forbidden, InternalServerError, NotFound, TooManyRequests
from werkzeug.middleware.proxy_fix import ProxyFix
from authlib.integrations.flask_client import OAuth

from app.core.config import config

# Single source of truth for extensions
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
csrf = CSRFProtect()
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
    'subscription',
    'marketplace',
    'groups',
    'stories',
    'polls',
    'stats',
    'payments',
    'documents',
    'gamification',
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


def _load_dotenv_if_present() -> None:
    """
    Load `.env` from repo root if present.

    We deliberately keep this dependency-free at runtime (python-dotenv is already
    in requirements.txt) and do not require systemd EnvironmentFile tweaks.
    """
    try:
        from dotenv import load_dotenv
    except Exception:
        return

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    env_path = os.path.join(repo_root, ".env")
    # Do not override already-exported environment variables
    try:
        load_dotenv(env_path, override=False)
    except Exception:
        return


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
    """
    try:
        from app.core.seed import seed_defaults
        with app.app_context():
            summary = seed_defaults(app)
            created = sum(v for v in summary.values() if isinstance(v, int))
            if created:
                app.logger.info("Auto-seed completed: %s", summary)
    except Exception:
        app.logger.exception("Auto-seed failed (non-fatal)")


def _auto_upgrade_db(app: Flask) -> None:
    """
    Ensure DB schema is upgraded without manual commands.

    This is critical for deployments where an old DB schema would otherwise
    crash login/registration with OperationalError (missing tables/columns).
    Works with both SQLite and PostgreSQL databases.
    Uses a file lock (SQLite) or advisory approach to avoid concurrent upgrades.
    """
    if app.config.get("TESTING"):
        return

    uri = (app.config.get("SQLALCHEMY_DATABASE_URI") or "").strip()
    is_sqlite = uri.startswith("sqlite:")

    base_dir = app.config.get("BASE_DIR") or os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir)
    )
    migrate_dir = app.config.get("MIGRATIONS_DIR") or os.path.join(base_dir, "migrations")

    def _try_alembic_upgrade():
        try:
            from flask_migrate import upgrade as migrate_upgrade
            with app.app_context():
                migrate_upgrade(directory=migrate_dir, revision="heads")
            return True
        except Exception:
            try:
                app.logger.exception("Alembic upgrade failed, falling back to create_all")
            except Exception:
                pass
            return False

    def _ensure_schema():
        try:
            with app.app_context():
                from app import models as _models  # noqa: F401
                db.create_all()
                if is_sqlite:
                    _sqlite_add_missing_columns(app, db)
        except Exception:
            try:
                app.logger.exception("db.create_all fallback also failed")
            except Exception:
                pass

    def _fallback_create_all():
        _ensure_schema()

    try:
        if is_sqlite:
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
                                _fallback_create_all()
                                return
                            time.sleep(0.2)

                    if not _try_alembic_upgrade():
                        _fallback_create_all()
                    else:
                        _ensure_schema()
            else:
                if not _try_alembic_upgrade():
                    _fallback_create_all()
                else:
                    _ensure_schema()
        else:
            if not _try_alembic_upgrade():
                _fallback_create_all()
            else:
                _ensure_schema()
    except Exception:
        try:
            app.logger.exception("Auto-upgrade DB wrapper failed")
        except Exception:
            pass
        _fallback_create_all()


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application."""
    _load_dotenv_if_present()
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

    _ensure_secret_key(app)
    _normalize_sqlite_db(app)

    if hasattr(config_class, 'validate_config'):
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

    # Keep schema aligned automatically (production/dev). Skip in tests.
    if not app.config.get("TESTING"):
        _auto_upgrade_db(app)
        _auto_seed(app)

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

    from flask import render_template as _rt

    def _error_page(template: str, code: int, fallback_title: str, fallback_msg: str):
        try:
            return _rt(template), code
        except Exception:
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
        if _wants_json():
            return {"error": "internal_server_error"}, 500
        return _error_page("errors/500.html", 500, "Errore del server", "Riprova tra qualche istante.")

    @login_manager.user_loader
    def load_user(user_id):
        try:
            from app.models import User
            return User.query.get(int(user_id))
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

    from app.core.bootstrap import discover_and_register_modules
    _register_blueprints(app)
    discover_and_register_modules(app, strict=False)

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
                        active_society = uniq.get(int(active_society_id)) or Society.query.get(int(active_society_id))
            except Exception:
                society_scopes = []
                active_society = None
                active_society_id = None

        except Exception:
            # DB not initialized yet or models unavailable: keep templates functional.
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

    @app.after_request
    def apply_security_headers(resp):
        """Security headers (safe defaults; CSP optional)."""
        try:
            if not app.config.get("SECURITY_HEADERS_ENABLED", True):
                return resp

            resp.headers.setdefault("X-Content-Type-Options", "nosniff")
            resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            resp.headers.setdefault("X-Frame-Options", "DENY")
            resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")

            # HSTS only on HTTPS
            try:
                if request.is_secure and app.config.get("HSTS_ENABLED", True):
                    max_age = int(app.config.get("HSTS_MAX_AGE", 31536000))
                    resp.headers.setdefault("Strict-Transport-Security", f"max-age={max_age}; includeSubDomains")
            except Exception:
                pass

            # Optional CSP (off by default due to external CDNs and inline scripts/styles)
            if app.config.get("CSP_ENABLED", False):
                csp = (
                    "default-src 'self'; "
                    "base-uri 'self'; "
                    "object-src 'none'; "
                    "frame-ancestors 'none'; "
                    "img-src 'self' data: https:; "
                    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
                    "connect-src 'self' https:; "
                    "manifest-src 'self'; "
                )
                header = "Content-Security-Policy-Report-Only" if app.config.get("CSP_REPORT_ONLY", False) else "Content-Security-Policy"
                resp.headers.setdefault(header, csp)
        except Exception:
            return resp
        return resp

    return app
