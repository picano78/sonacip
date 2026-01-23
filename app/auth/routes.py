"""
Authentication routes
"""
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from app import db
from app.auth import bp
from app.auth.forms import LoginForm, RegistrationForm, SocietyRegistrationForm
from app.models import User, AuditLog
from datetime import datetime


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
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
            next_page = url_for('main.dashboard')
        return redirect(next_page)
    
    return render_template('auth/login.html', form=form)


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page for individuals"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
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
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', form=form)


@bp.route('/register/society', methods=['GET', 'POST'])
def register_society():
    """Registration page for sports societies"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = SocietyRegistrationForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data,
            username=form.username.data,
            phone=form.phone.data,
            role='societa',
            is_active=True,
            is_verified=False,
            # Society specific fields
            company_name=form.company_name.data,
            company_type=form.company_type.data,
            fiscal_code=form.fiscal_code.data,
            vat_number=form.vat_number.data,
            address=form.address.data,
            city=form.city.data,
            province=form.province.data.upper(),
            postal_code=form.postal_code.data,
            website=form.website.data
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        # Log the registration
        log = AuditLog(
            user_id=user.id,
            action='register_society',
            entity_type='User',
            entity_id=user.id,
            details=f'New society registered: {form.company_name.data}',
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash('Registrazione società completata! Effettua il login.', 'success')
        return redirect(url_for('auth.login'))
    
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
    return redirect(url_for('main.index'))
