"""
Authentication routes
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from app import db, limiter
from app.auth.forms import LoginForm, RegistrationForm
from app.models import User, AuditLog, Subscription, Plan
from datetime import datetime

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
    """Registration page for individuals"""
    if current_user.is_authenticated:
        return redirect(url_for('social.feed'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data,
            username=form.username.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            phone=form.phone.data,
            role=form.role.data,
            is_active=True,
            is_verified=False
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

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
            details=f'New {form.role.data} registered',
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash('Registrazione completata! Effettua il login.', 'success')
        return redirect(url_for('auth.login', next=url_for('social.feed')))
    
    return render_template('auth/register.html', form=form)


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
