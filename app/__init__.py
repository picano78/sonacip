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
limiter = Limiter(key_func=get_remote_address, swallow_errors=True)
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


def _auto_upgrade_db(app: Flask) -> None:
    """
    Ensure DB schema is upgraded without manual commands.

    This is critical for SQLite deployments where an old DB schema would otherwise
    crash login/registration with OperationalError (missing tables/columns).
    Uses a file lock to avoid concurrent upgrades across gunicorn workers.
    """
    try:
        uri = (app.config.get("SQLALCHEMY_DATABASE_URI") or "").strip()
        if not uri.startswith("sqlite:"):
            return
        if app.config.get("TESTING"):
            return

        # Only auto-upgrade in production to avoid slowing dev.
        env = (os.environ.get("APP_ENV") or os.environ.get("FLASK_ENV") or "").lower()
        if env and env not in ("production", "prod"):
            return

        # Determine db file path
        db_path = None
        if uri.startswith("sqlite:////"):
            db_path = "/" + uri.split("sqlite:////", 1)[1]
        elif uri.startswith("sqlite:///"):
            db_path = uri.split("sqlite:///", 1)[1]
        if not db_path:
            return

        lock_path = os.path.join(os.path.dirname(db_path), ".sonacip_alembic_upgrade.lock")
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)

        import fcntl
        from flask_migrate import upgrade as migrate_upgrade

        with open(lock_path, "w", encoding="utf-8") as lockf:
            # Wait briefly for another worker to finish upgrades
            start = time.time()
            while True:
                try:
                    fcntl.flock(lockf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.time() - start > 30:
                        return
                    time.sleep(0.2)

            try:
                # Run migrations using Flask-Migrate (alembic env uses current_app)
                with app.app_context():
                    migrate_dir = app.config.get("MIGRATIONS_DIR") or os.path.join(
                        app.config.get("BASE_DIR") or os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)),
                        "migrations",
                    )
                    migrate_upgrade(directory=migrate_dir)
            except Exception:
                app.logger.exception("Auto-upgrade DB failed")
                return
    except Exception:
        try:
            app.logger.exception("Auto-upgrade DB wrapper failed")
        except Exception:
            pass


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application."""
    _load_dotenv_if_present()
    app = Flask(__name__)

    if config_name is None:
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

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    oauth.init_app(app)

    # Keep schema aligned automatically (production SQLite).
    _auto_upgrade_db(app)

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

    @app.errorhandler(Forbidden)
    def handle_forbidden(err: Forbidden):
        if _wants_json():
            return {"error": "forbidden"}, 403
        return (
            "<!doctype html><html lang='it'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Accesso negato</title></head><body>"
            "<h1>Accesso negato</h1>"
            "<p>Non hai i permessi per accedere a questa risorsa.</p>"
            "<p><a href='/'>Torna alla home</a></p>"
            "</body></html>",
            403,
        )

    @app.errorhandler(NotFound)
    def handle_not_found(err: NotFound):
        if _wants_json():
            return {"error": "not_found"}, 404
        return (
            "<!doctype html><html lang='it'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Pagina non trovata</title></head><body>"
            "<h1>Pagina non trovata</h1>"
            "<p>La pagina richiesta non esiste.</p>"
            "<p><a href='/'>Torna alla home</a></p>"
            "</body></html>",
            404,
        )

    @app.errorhandler(InternalServerError)
    def handle_internal_server_error(err: InternalServerError):
        # Keep it generic: avoid leaking details in production.
        if _wants_json():
            return {"error": "internal_server_error"}, 500
        return (
            "<!doctype html><html lang='it'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Errore</title></head><body>"
            "<h1>Si è verificato un errore</h1>"
            "<p>Riprova tra qualche istante.</p>"
            "<p><a href='/'>Torna alla home</a></p>"
            "</body></html>",
            500,
        )

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

            def get_unread_notifications_count():
                if not current_user.is_authenticated:
                    return 0
                return Notification.query.filter_by(user_id=current_user.id, is_read=False).count()

            def get_unread_messages_count():
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
            def get_unread_notifications_count():
                return 0

            def get_unread_messages_count():
                return 0

        return {
            'can': can_fn,
            'appearance': appearance,
            'privacy': privacy,
            'site': site,
            'page': page,
            'nav_links': nav_links,
            'society_scopes': society_scopes,
            'active_society': active_society,
            'active_society_id': active_society_id,
            'get_unread_notifications_count': get_unread_notifications_count,
            'get_unread_messages_count': get_unread_messages_count,
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
