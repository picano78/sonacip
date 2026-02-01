"""
Authentication routes
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from app import db, limiter
from app.auth.forms import LoginForm, RegistrationForm, SocietyRegistrationForm
from app.models import User, AuditLog, Subscription, Plan, Dashboard, DashboardTemplate, Society, Role
from datetime import datetime
import json

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('social.feed'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user is None or not user.check_password(form.password.data):
            flash('Email o password non validi', 'danger')
            return redirect(url_for('auth.login'))
        
        if not user.is_active:
            flash('Account disabilitato. Contatta l\'amministratore.', 'warning')
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=form.remember_me.data)
        user.last_seen = datetime.utcnow()
        db.session.commit()
        
        # Log the login
        log = AuditLog(
            user_id=user.id,
            action='login',
            entity_type='User',
            entity_id=user.id,
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'Benvenuto, {user.get_full_name()}!', 'success')
        
        # Redirect to next page or dashboard
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('social.feed')
        return redirect(next_page)
    
    return render_template('auth/login.html', form=form)


@bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per hour")
def register():
    """Registration page for individuals (Appassionato only)."""
    if current_user.is_authenticated:
        return redirect(url_for('social.feed'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        role_name = 'appassionato'
        role_obj = Role.query.filter_by(name=role_name).first()
        if not role_obj:
            flash('Sistema non inizializzato: ruolo appassionato mancante.', 'danger')
            return redirect(url_for('auth.register'))

        user = User(
            email=form.email.data,
            username=form.username.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            phone=form.phone.data,
            role=role_name,
            is_active=True,
            is_verified=False,
            role_obj=role_obj,
            role_legacy=role_name,
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

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
            db.session.commit()
        except Exception:
            db.session.rollback()

        # Auto-attach free plan subscription for individuals
        free_plan = Plan.query.filter_by(slug='free').first()
        if free_plan:
            existing_sub = Subscription.query.filter_by(user_id=user.id, status='active').first()
            if not existing_sub:
                sub = Subscription(
                    user_id=user.id,
                    plan_id=free_plan.id,
                    status='active',
                    billing_cycle='monthly',
                    start_date=datetime.utcnow(),
                    amount=0,
                    auto_renew=False
                )
                db.session.add(sub)
        
        # Log the registration
        log = AuditLog(
            user_id=user.id,
            action='register',
            entity_type='User',
            entity_id=user.id,
            details=f'New {role_name} registered',
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash('Registrazione completata! Effettua il login.', 'success')
        return redirect(url_for('auth.login', next=url_for('social.feed')))
    
    return render_template('auth/register.html', form=form)


@bp.route('/register/society', methods=['GET', 'POST'])
@limiter.limit("2 per hour")
def register_society():
    """Registration page for societies (CRM-style)."""
    if current_user.is_authenticated:
        return redirect(url_for('social.feed'))

    form = SocietyRegistrationForm()
    if form.validate_on_submit():
        role_name = 'societa'
        role_obj = Role.query.filter_by(name=role_name).first()
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
