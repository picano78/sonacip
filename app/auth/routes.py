"""
Authentication routes
"""
from flask import Blueprint, current_app, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user
from sqlalchemy import func, or_
from app import db, limiter, oauth
from app.auth.forms import (
    LoginForm,
    RegistrationForm,
    SocietyRegistrationForm,
    ResetPasswordRequestForm,
    ResetPasswordForm,
)
from app.models import User, AuditLog, Subscription, Plan, Dashboard, DashboardTemplate, Society, Role, EnterpriseSSOSetting, EmailConfirmationSetting
from app.auth.email_confirm import is_email_confirmation_required, send_confirmation_email, can_resend, verify_token, get_confirmation_settings
from datetime import datetime
import json
import secrets

bp = Blueprint('auth', __name__, url_prefix='/auth')

def _safe_commit(context: str) -> bool:
    """
    Best-effort commit helper.

    In production with SQLite (or partially upgraded schemas), auxiliary writes
    like audit logs/subscriptions must never break login/registration flows.
    """
    try:
        db.session.commit()
        return True
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            current_app.logger.exception("DB commit failed (%s)", context)
        except Exception:
            pass
        return False


def _reset_serializer():
    from itsdangerous import URLSafeTimedSerializer
    return URLSafeTimedSerializer(current_app.config.get("SECRET_KEY"))


def _generate_reset_token(user_id: int) -> str:
    return _reset_serializer().dumps({"user_id": int(user_id)}, salt="password-reset")


def _verify_reset_token(token: str, max_age_seconds: int = 3600) -> int | None:
    try:
        data = _reset_serializer().loads(token, salt="password-reset", max_age=max_age_seconds)
        uid = int((data or {}).get("user_id"))
        return uid
    except Exception:
        return None


@bp.route("/reset-password", methods=["GET", "POST"])
def reset_password_request():
    """Request a password reset link."""
    if current_user.is_authenticated:
        return redirect(url_for("social.feed"))

    form = ResetPasswordRequestForm()
    try:
        valid = form.validate_on_submit()
    except Exception:
        current_app.logger.exception("Reset password request validation failed")
        flash("Errore temporaneo. Riprova tra qualche istante.", "danger")
        return render_template("auth/reset_password_request.html", form=form)

    if valid:
        # Always respond with the same message for privacy.
        try:
            user = User.query.filter_by(email=form.email.data).first()
        except Exception:
            current_app.logger.exception("User lookup failed during reset request")
            user = None

        if user:
            try:
                from app.notifications.utils import send_email

                token = _generate_reset_token(user.id)
                link = url_for("auth.reset_password", token=token, _external=True)
                subject = "Recupero password SONACIP"
                body = (
                    "Hai richiesto il recupero password.\n\n"
                    f"Apri questo link per impostare una nuova password:\n{link}\n\n"
                    "Se non hai richiesto tu questa operazione, ignora questa email."
                )
                send_email(user.email, subject, body)
            except Exception:
                current_app.logger.exception("Failed to send reset password email")

        flash("Se l'email esiste, riceverai un link per reimpostare la password.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password_request.html", form=form)


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    """Reset password using a time-limited token."""
    if current_user.is_authenticated:
        return redirect(url_for("social.feed"))

    user_id = _verify_reset_token(token)
    if not user_id:
        flash("Link non valido o scaduto. Richiedi di nuovo il recupero password.", "warning")
        return redirect(url_for("auth.reset_password_request"))

    form = ResetPasswordForm()
    try:
        valid = form.validate_on_submit()
    except Exception:
        current_app.logger.exception("Reset password validation failed")
        flash("Errore temporaneo. Riprova tra qualche istante.", "danger")
        return render_template("auth/reset_password.html", form=form)

    if valid:
        try:
            user = User.query.get(int(user_id))
        except Exception:
            current_app.logger.exception("User load failed during reset")
            flash("Servizio temporaneamente non disponibile. Riprova tra qualche istante.", "danger")
            return redirect(url_for("auth.reset_password_request"))

        if not user:
            flash("Utente non trovato. Richiedi di nuovo il recupero password.", "warning")
            return redirect(url_for("auth.reset_password_request"))

        user.set_password(form.password.data)
        db.session.add(user)
        _safe_commit("auth.reset_password:set_password")
        flash("Password aggiornata. Ora puoi effettuare il login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form)

def _enterprise_oidc_client():
    sso = EnterpriseSSOSetting.query.first()
    if not sso or not sso.enabled or not sso.issuer_url or not sso.client_id or not sso.client_secret:
        return None
    issuer = (sso.issuer_url or "").rstrip("/")
    server_metadata_url = issuer + "/.well-known/openid-configuration"
    # Register (safe if repeated with same name)
    try:
        oauth.register(
            name="enterprise_oidc",
            client_id=sso.client_id,
            client_secret=sso.client_secret,
            server_metadata_url=server_metadata_url,
            client_kwargs={"scope": (sso.scopes or "openid email profile")},
        )
    except Exception:
        pass
    return oauth.create_client("enterprise_oidc")


@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('social.feed'))
    
    form = LoginForm()
    try:
        valid = form.validate_on_submit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Login form validation failed")
        flash('Errore temporaneo durante il login. Riprova tra qualche istante.', 'danger')
        return redirect(url_for('auth.login'))

    if valid:
        identifier = (form.identifier.data or "").strip()
        identifier_lower = identifier.lower()
        try:
            user = User.query.filter(
                or_(
                    func.lower(User.email) == identifier_lower,
                    func.lower(User.username) == identifier_lower,
                )
            ).first()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("User lookup failed during login")
            flash('Servizio temporaneamente non disponibile. Riprova tra qualche istante.', 'danger')
            return redirect(url_for('auth.login'))
        
        if user is None or not user.check_password(form.password.data):
            flash('Credenziali non valide', 'danger')
            return redirect(url_for('auth.login'))
        
        if not user.is_active:
            flash('Account disabilitato. Contatta l\'amministratore.', 'warning')
            return redirect(url_for('auth.login'))

        if is_email_confirmation_required() and not user.email_confirmed:
            role_name = user.role_obj.name if user.role_obj else ''
            if role_name != 'super_admin':
                session['_email_confirm_uid'] = user.id
                flash('Devi confermare il tuo indirizzo email prima di effettuare il login.', 'warning')
                return redirect(url_for('auth.email_confirm_pending', user_id=user.id))
        
        login_user(user, remember=form.remember_me.data)
        user.last_seen = datetime.utcnow()
        _safe_commit("auth.login:last_seen")

        try:
            from app.gamification.engine import update_login_streak
            update_login_streak(user.id)
        except Exception:
            pass
        
        # Log the login
        try:
            db.session.add(
                AuditLog(
                    user_id=user.id,
                    action='login',
                    entity_type='User',
                    entity_id=user.id,
                    ip_address=request.remote_addr,
                )
            )
            _safe_commit("auth.login:audit_log")
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
        
        flash(f'Benvenuto, {user.get_full_name()}!', 'success')
        
        # Redirect to next page or dashboard
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('social.feed')
        return redirect(next_page)
    
    return render_template('auth/login.html', form=form)


@bp.route('/sso/login')
def sso_login():
    """Enterprise SSO login (OIDC)."""
    if current_user.is_authenticated:
        return redirect(url_for('social.feed'))
    client = _enterprise_oidc_client()
    if not client:
        flash('SSO non configurato.', 'warning')
        return redirect(url_for('auth.login'))
    redirect_uri = url_for('auth.sso_callback', _external=True)
    return client.authorize_redirect(redirect_uri)


@bp.route('/sso/callback')
def sso_callback():
    """OIDC callback."""
    client = _enterprise_oidc_client()
    if not client:
        flash('SSO non configurato.', 'warning')
        return redirect(url_for('auth.login'))
    try:
        token = client.authorize_access_token()
    except Exception:
        flash('SSO fallito.', 'danger')
        return redirect(url_for('auth.login'))

    userinfo = None
    try:
        userinfo = client.parse_id_token(token)
    except Exception:
        userinfo = None
    if not userinfo:
        try:
            userinfo = client.get('userinfo').json()
        except Exception:
            userinfo = None
    if not userinfo:
        flash('SSO: userinfo mancante.', 'danger')
        return redirect(url_for('auth.login'))

    email = (userinfo.get('email') or '').strip().lower()
    if not email:
        flash('SSO: email mancante.', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first()
    if not user:
        role_name = 'appassionato'
        role_obj = Role.query.filter_by(name=role_name).first()
        if not role_obj:
            flash('Sistema non inizializzato: ruolo appassionato mancante.', 'danger')
            return redirect(url_for('auth.login'))

        base_username = email.split("@")[0][:40] or "user"
        username = base_username
        while User.query.filter_by(username=username).first():
            username = f"{base_username}{secrets.randbelow(9999)}"

        user = User(
            email=email,
            username=username,
            first_name=(userinfo.get('given_name') or ''),
            last_name=(userinfo.get('family_name') or ''),
            phone=None,
            role=role_name,
            is_active=True,
            is_verified=True,
            role_obj=role_obj,
            role_legacy=role_name,
        )
        user.set_password(secrets.token_urlsafe(24))
        db.session.add(user)
        db.session.commit()

    if not user.is_active:
        flash('Account disabilitato. Contatta l\'amministratore.', 'warning')
        return redirect(url_for('auth.login'))

    login_user(user, remember=True)
    user.last_seen = datetime.utcnow()
    _safe_commit("auth.sso:last_seen")

    try:
        db.session.add(
            AuditLog(
                user_id=user.id,
                action='sso_login',
                entity_type='User',
                entity_id=user.id,
                ip_address=request.remote_addr,
            )
        )
        _safe_commit("auth.sso:audit_log")
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
    flash(f'Benvenuto, {user.get_full_name()}!', 'success')
    return redirect(url_for('social.feed'))


@bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per hour", methods=["POST"])
def register():
    """Registration page for individuals (Appassionato only)."""
    if current_user.is_authenticated:
        return redirect(url_for('social.feed'))
    
    form = RegistrationForm()
    try:
        valid = form.validate_on_submit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Registration form validation failed")
        flash('Errore temporaneo durante la registrazione. Riprova tra qualche istante.', 'danger')
        return render_template('auth/register.html', form=form)

    if valid:
        role_name = 'appassionato'
        try:
            role_obj = Role.query.filter_by(name=role_name).first()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Role lookup failed during registration")
            flash('Sistema non disponibile al momento. Riprova più tardi.', 'danger')
            return render_template('auth/register.html', form=form)
        if not role_obj:
            flash('Sistema non inizializzato: ruolo appassionato mancante.', 'danger')
            return redirect(url_for('auth.register'))

        user = User(
            email=form.email.data,
            username=form.username.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            phone=form.phone.data,
            language=form.language.data,
            role=role_name,
            is_active=True,
            is_verified=False,
            role_obj=role_obj,
            role_legacy=role_name,
        )
        user.set_password(form.password.data)

        db.session.add(user)
        if not _safe_commit("auth.register:create_user"):
            flash('Errore durante la registrazione. Riprova.', 'danger')
            return redirect(url_for('auth.register'))

        # Provision a default personal dashboard for the new user
        try:
            tpl = DashboardTemplate.query.filter_by(role_name=role_name).first()
            if not tpl:
                tpl = DashboardTemplate.query.filter_by(role_name=None).first()
            widgets = []
            layout = 'grid'
            if tpl:
                try:
                    widgets = json.loads(tpl.widgets or '[]')
                except Exception:
                    widgets = []
                layout = tpl.layout or 'grid'
            if not widgets:
                widgets = [
                    {"type": "quick_links"},
                    {"type": "stats"},
                    {"type": "recent_notifications"},
                ]
            dash = Dashboard(
                name='Il mio cruscotto',
                description='Dashboard personale',
                user_id=user.id,
                widgets=json.dumps(widgets),
                layout=layout,
                is_default=True,
            )
            db.session.add(dash)
            _safe_commit("auth.register:dashboard")
        except Exception:
            db.session.rollback()

        # Auto-attach free plan subscription for individuals
        try:
            free_plan = Plan.query.filter_by(slug='free').first()
            if free_plan:
                existing_sub = Subscription.query.filter_by(user_id=user.id, status='active').first()
                if not existing_sub:
                    db.session.add(
                        Subscription(
                            user_id=user.id,
                            plan_id=free_plan.id,
                            status='active',
                            billing_cycle='monthly',
                            start_date=datetime.utcnow(),
                            amount=0,
                            auto_renew=False,
                        )
                    )
                    _safe_commit("auth.register:subscription")
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
        
        # Log the registration
        try:
            db.session.add(
                AuditLog(
                    user_id=user.id,
                    action='register',
                    entity_type='User',
                    entity_id=user.id,
                    details=f'New {role_name} registered',
                    ip_address=request.remote_addr,
                )
            )
            _safe_commit("auth.register:audit_log")
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
        
        if is_email_confirmation_required():
            session['_email_confirm_uid'] = user.id
            session['_email_confirm_resends'] = 0
            email_sent = send_confirmation_email(user)
            if email_sent:
                flash('Registrazione completata! Ti abbiamo inviato un\'email di conferma. Controlla la tua casella di posta.', 'success')
            else:
                flash('Registrazione completata! Non è stato possibile inviare l\'email di conferma. Puoi richiederne una nuova.', 'warning')
            return redirect(url_for('auth.email_confirm_pending', user_id=user.id))
        else:
            flash('Registrazione completata! Effettua il login.', 'success')
            return redirect(url_for('auth.login', next=url_for('social.feed')))
    
    return render_template('auth/register.html', form=form)


@bp.route('/register/society', methods=['GET', 'POST'])
@limiter.limit("2 per hour", methods=["POST"])
def register_society():
    """Registration page for societies (CRM-style)."""
    if current_user.is_authenticated:
        return redirect(url_for('social.feed'))

    form = SocietyRegistrationForm()
    try:
        valid = form.validate_on_submit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Society registration form validation failed")
        flash('Errore temporaneo durante la registrazione. Riprova tra qualche istante.', 'danger')
        return render_template('auth/register_society.html', form=form)

    if valid:
        role_name = 'societa'
        try:
            role_obj = Role.query.filter_by(name=role_name).first()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Role lookup failed during society registration")
            flash('Sistema non disponibile al momento. Riprova più tardi.', 'danger')
            return render_template('auth/register_society.html', form=form)
        if not role_obj:
            flash('Sistema non inizializzato: ruolo societa mancante.', 'danger')
            return redirect(url_for('auth.register_society'))

        user = User(
            email=form.email.data,
            username=form.username.data,
            company_name=form.company_name.data,
            company_type=form.company_type.data,
            vat_number=form.vat_number.data or None,
            fiscal_code=form.fiscal_code.data,
            address=form.address.data,
            city=form.city.data,
            province=form.province.data,
            postal_code=form.postal_code.data,
            phone=form.phone.data,
            website=form.website.data or None,
            language=form.language.data,
            role=role_name,
            is_active=True,
            is_verified=False,
            role_obj=role_obj,
            role_legacy=role_name,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        # Create Society profile row (1:1 mapped by user.id)
        society = Society(
            id=user.id,
            legal_name=form.company_name.data,
            company_type=form.company_type.data,
            vat_number=form.vat_number.data or None,
            fiscal_code=form.fiscal_code.data,
            email=form.email.data,
            phone=form.phone.data,
            website=form.website.data or None,
            address=form.address.data,
            city=form.city.data,
            province=form.province.data,
            postal_code=form.postal_code.data,
        )
        db.session.add(society)
        db.session.commit()

        # Create default dashboard for the new society user
        try:
            tpl = DashboardTemplate.query.filter_by(role_name=role_name).first()
            if not tpl:
                tpl = DashboardTemplate.query.filter_by(role_name=None).first()
            widgets = []
            layout = 'grid'
            if tpl:
                try:
                    widgets = json.loads(tpl.widgets or '[]')
                except Exception:
                    widgets = []
                layout = tpl.layout or 'grid'
            if not widgets:
                widgets = [
                    {"type": "quick_links"},
                    {"type": "stats"},
                    {"type": "recent_notifications"},
                ]
            dash = Dashboard(
                name='Cruscotto Società',
                description='Dashboard gestione società',
                user_id=user.id,
                society_id=user.id,
                widgets=json.dumps(widgets),
                layout=layout,
                is_default=True,
            )
            db.session.add(dash)
            db.session.commit()
        except Exception:
            db.session.rollback()

        # Attach free plan subscription to society (until paid plans configured)
        free_plan = Plan.query.filter_by(slug='free').first()
        if free_plan:
            existing_sub = Subscription.query.filter_by(society_id=user.id, status='active').first()
            if not existing_sub:
                sub = Subscription(
                    society_id=user.id,
                    plan_id=free_plan.id,
                    status='active',
                    billing_cycle='monthly',
                    start_date=datetime.utcnow(),
                    amount=0,
                    auto_renew=False
                )
                db.session.add(sub)
                db.session.commit()

        log = AuditLog(
            user_id=user.id,
            action='register_society',
            entity_type='User',
            entity_id=user.id,
            details='New society registered',
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()

        if is_email_confirmation_required():
            session['_email_confirm_uid'] = user.id
            session['_email_confirm_resends'] = 0
            email_sent = send_confirmation_email(user)
            if email_sent:
                flash('Registrazione società completata! Ti abbiamo inviato un\'email di conferma. Controlla la tua casella di posta.', 'success')
            else:
                flash('Registrazione società completata! Non è stato possibile inviare l\'email di conferma. Puoi richiederne una nuova.', 'warning')
            return redirect(url_for('auth.email_confirm_pending', user_id=user.id))
        else:
            flash('Registrazione società completata! Effettua il login.', 'success')
            return redirect(url_for('auth.login', next=url_for('main.dashboard')))

    return render_template('auth/register_society.html', form=form)


@bp.route('/logout')
def logout():
    """Logout"""
    if current_user.is_authenticated:
        # Log the logout
        log = AuditLog(
            user_id=current_user.id,
            action='logout',
            entity_type='User',
            entity_id=current_user.id,
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
    
    logout_user()
    flash('Logout effettuato con successo.', 'info')
    return redirect(url_for('social.feed'))


@bp.route('/confirm-email/<token>')
def confirm_email(token):
    user, message = verify_token(token)
    if user:
        flash(message, 'success')
        return redirect(url_for('auth.login'))
    else:
        flash(message, 'danger')
        return redirect(url_for('auth.login'))


def _mask_email(email):
    if not email or '@' not in email:
        return '***'
    local, domain = email.rsplit('@', 1)
    if len(local) <= 2:
        masked_local = local[0] + '***'
    else:
        masked_local = local[0] + '***' + local[-1]
    return f'{masked_local}@{domain}'


@bp.route('/email-confirm-pending/<int:user_id>')
def email_confirm_pending(user_id):
    pending_uid = session.get('_email_confirm_uid')
    if pending_uid != user_id:
        flash('Effettua il login per continuare.', 'info')
        return redirect(url_for('auth.login'))
    user = User.query.get(user_id)
    if not user:
        flash('Effettua il login per continuare.', 'info')
        return redirect(url_for('auth.login'))
    if user.email_confirmed:
        session.pop('_email_confirm_uid', None)
        flash('Email già confermata. Puoi effettuare il login.', 'success')
        return redirect(url_for('auth.login'))
    masked_email = _mask_email(user.email)
    return render_template('auth/email_confirm_pending.html', user=user, masked_email=masked_email)


@bp.route('/resend-confirmation/<int:user_id>', methods=['POST'])
@limiter.limit("3 per hour")
def resend_confirmation(user_id):
    pending_uid = session.get('_email_confirm_uid')
    if pending_uid != user_id:
        flash('Sessione scaduta. Effettua il login.', 'warning')
        return redirect(url_for('auth.login'))

    user = User.query.get(user_id)
    if not user or user.email_confirmed:
        flash('Operazione non valida.', 'info')
        return redirect(url_for('auth.login'))

    setting = get_confirmation_settings()
    resend_count = session.get('_email_confirm_resends', 0)
    if resend_count >= (setting.max_resends or 5):
        flash('Hai raggiunto il numero massimo di reinvii. Contatta il supporto.', 'warning')
        return redirect(url_for('auth.email_confirm_pending', user_id=user.id))

    ok, msg = can_resend(user)
    if not ok:
        flash(msg, 'warning')
        return redirect(url_for('auth.email_confirm_pending', user_id=user.id))

    email_sent = send_confirmation_email(user)
    if email_sent:
        session['_email_confirm_resends'] = resend_count + 1
        flash('Email di conferma inviata! Controlla la tua casella di posta.', 'success')
    else:
        flash('Non è stato possibile inviare l\'email. Riprova più tardi.', 'danger')
    return redirect(url_for('auth.email_confirm_pending', user_id=user.id))
