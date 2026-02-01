"""
CRM Routes
Contact and opportunity management
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.crm.forms import ContactForm, OpportunityForm, ActivityForm, MedicalCertificateForm, SocietyFeeForm
from app.models import Contact, Opportunity, CRMActivity, User, AuditLog, MedicalCertificate, SocietyFee
from app.utils import permission_required, check_permission, feature_required, get_active_society_id
from datetime import datetime
from app.utils import log_action
from sqlalchemy.orm import joinedload
from datetime import date, timedelta

bp = Blueprint('crm', __name__, url_prefix='/crm')


def _society_scope_id():
    # Admin can operate cross-society; if an active scope is selected, use it to filter.
    if check_permission(current_user, 'admin', 'access'):
        return get_active_society_id(current_user)
    return get_active_society_id(current_user)


def _enforce_scope(entity_society_id, redirect_endpoint):
    scope_id = _society_scope_id()
    if scope_id and entity_society_id != scope_id:
        flash('Accesso non autorizzato.', 'danger')
        return redirect(url_for(redirect_endpoint))
    return None


@bp.route('/')
@login_required
@permission_required('crm', 'access', society_id_func=_society_scope_id)
@feature_required('crm')
def index():
    """CRM Dashboard"""
    # Get statistics
    scope_id = _society_scope_id()
    if scope_id:
        contacts = Contact.query.filter_by(society_id=scope_id).all()
        opportunities = Opportunity.query.filter_by(society_id=scope_id).all()
    else:
        if check_permission(current_user, 'admin', 'access'):
            contacts = Contact.query.all()
            opportunities = Opportunity.query.all()
        else:
            contacts = []
            opportunities = []
    
    # Calculate stats
    total_contacts = len(contacts)
    new_contacts = len([c for c in contacts if c.status == 'new'])
    converted_contacts = len([c for c in contacts if c.status == 'converted'])
    
    total_opportunities = len(opportunities)
    open_opportunities = len([o for o in opportunities if o.stage not in ['closed_won', 'closed_lost']])
    won_opportunities = len([o for o in opportunities if o.stage == 'closed_won'])
    
    try:
        total_value = sum([float(o.value or 0) for o in opportunities if o.value and o.stage not in ['closed_lost']])
    except (ValueError, TypeError):
        total_value = 0
    
    return render_template('crm/index.html',
                         total_contacts=total_contacts,
                         new_contacts=new_contacts,
                         converted_contacts=converted_contacts,
                         total_opportunities=total_opportunities,
                         open_opportunities=open_opportunities,
                         won_opportunities=won_opportunities,
                         total_value=total_value,
                         recent_contacts=contacts[:5],
                         recent_opportunities=opportunities[:5])


@bp.route('/contacts')
@login_required
@permission_required('crm', 'access', society_id_func=_society_scope_id)
@feature_required('crm')
def contacts():
    """List all contacts"""
    # Filter by society
    scope_id = _society_scope_id()
    if scope_id:
        contacts = Contact.query.filter_by(society_id=scope_id).order_by(Contact.created_at.desc()).all()
    else:
        contacts = Contact.query.order_by(Contact.created_at.desc()).all() if check_permission(current_user, 'admin', 'access') else []
    
    # Filter by status if requested
    status_filter = request.args.get('status')
    if status_filter:
        contacts = [c for c in contacts if c.status == status_filter]
    
    return render_template('crm/contacts.html', contacts=contacts, status_filter=status_filter)


@bp.route('/contacts/new', methods=['GET', 'POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def new_contact():
    """Create new contact"""
    form = ContactForm()
    
    if form.validate_on_submit():
        # Determine society_id
        society_id = _society_scope_id()
        
        contact = Contact(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data,
            phone=form.phone.data,
            company=form.company.data,
            position=form.position.data,
            contact_type=form.contact_type.data,
            status=form.status.data,
            source=form.source.data,
            notes=form.notes.data,
            address=form.address.data,
            city=form.city.data,
            postal_code=form.postal_code.data,
            society_id=society_id,
            created_by=current_user.id
        )
        
        db.session.add(contact)
        db.session.commit()
        
        flash('Contatto creato con successo!', 'success')
        return redirect(url_for('crm.contacts'))
    
    return render_template('crm/contact_form.html', form=form, title='Nuovo Contatto')


@bp.route('/contacts/<int:contact_id>')
@login_required
@permission_required('crm', 'access', society_id_func=_society_scope_id)
@feature_required('crm')
def contact_detail(contact_id):
    """View contact details"""
    contact = Contact.query.get_or_404(contact_id)

    scoped = _enforce_scope(contact.society_id, 'crm.contacts')
    if scoped:
        return scoped
    
    # Get related opportunities and activities
    opportunities = Opportunity.query.filter_by(contact_id=contact_id).all()
    activities = CRMActivity.query.filter_by(contact_id=contact_id).order_by(CRMActivity.created_at.desc()).all()
    
    return render_template('crm/contact_detail.html', 
                         contact=contact, 
                         opportunities=opportunities,
                         activities=activities)


@bp.route('/contacts/<int:contact_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def edit_contact(contact_id):
    """Edit contact"""
    contact = Contact.query.get_or_404(contact_id)

    scoped = _enforce_scope(contact.society_id, 'crm.contacts')
    if scoped:
        return scoped
    
    form = ContactForm(obj=contact)
    
    if form.validate_on_submit():
        contact.first_name = form.first_name.data
        contact.last_name = form.last_name.data
        contact.email = form.email.data
        contact.phone = form.phone.data
        contact.company = form.company.data
        contact.position = form.position.data
        contact.contact_type = form.contact_type.data
        contact.status = form.status.data
        contact.source = form.source.data
        contact.notes = form.notes.data
        contact.address = form.address.data
        contact.city = form.city.data
        contact.postal_code = form.postal_code.data
        contact.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash('Contatto aggiornato!', 'success')
        return redirect(url_for('crm.contact_detail', contact_id=contact_id))
    
    return render_template('crm/contact_form.html', form=form, title='Modifica Contatto', contact=contact)


@bp.route('/opportunities')
@login_required
@permission_required('crm', 'access', society_id_func=_society_scope_id)
@feature_required('crm')
def opportunities():
    """List all opportunities"""
    # Filter by society
    scope_id = _society_scope_id()
    if scope_id:
        opportunities = Opportunity.query.filter_by(society_id=scope_id).order_by(Opportunity.created_at.desc()).all()
    else:
        opportunities = Opportunity.query.order_by(Opportunity.created_at.desc()).all()
    
    return render_template('crm/opportunities.html', opportunities=opportunities)


@bp.route('/opportunities/new', methods=['GET', 'POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def new_opportunity():
    """Create new opportunity"""
    form = OpportunityForm()
    
    # Populate contact choices
    scope_id = _society_scope_id()
    if scope_id:
        contacts = Contact.query.filter_by(society_id=scope_id).all()
    else:
        contacts = Contact.query.all()
    
    form.contact_id.choices = [(0, 'Nessuno')] + [(c.id, f'{c.first_name} {c.last_name}') for c in contacts]
    
    if form.validate_on_submit():
        # Determine society_id
        society_id = _society_scope_id()
        
        opportunity = Opportunity(
            title=form.title.data,
            description=form.description.data,
            opportunity_type=form.opportunity_type.data,
            stage=form.stage.data,
            value=form.value.data,
            probability=form.probability.data,
            expected_close_date=form.expected_close_date.data,
            contact_id=form.contact_id.data if form.contact_id.data != 0 else None,
            society_id=society_id,
            created_by=current_user.id
        )
        
        db.session.add(opportunity)
        db.session.commit()
        
        flash('Opportunità creata con successo!', 'success')
        return redirect(url_for('crm.opportunities'))
    
    return render_template('crm/opportunity_form.html', form=form, title='Nuova Opportunità')


@bp.route('/opportunities/<int:opp_id>')
@login_required
@permission_required('crm', 'access', society_id_func=_society_scope_id)
@feature_required('crm')
def opportunity_detail(opp_id):
    """View opportunity details"""
    opportunity = Opportunity.query.get_or_404(opp_id)

    scoped = _enforce_scope(opportunity.society_id, 'crm.opportunities')
    if scoped:
        return scoped
    
    # Get related activities
    activities = CRMActivity.query.filter_by(opportunity_id=opp_id).order_by(CRMActivity.created_at.desc()).all()
    
    return render_template('crm/opportunity_detail.html', 
                         opportunity=opportunity,
                         activities=activities)


@bp.route('/activities/new', methods=['GET', 'POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def new_activity():
    """Log new activity"""
    form = ActivityForm()
    
    # Populate choices
    scope_id = _society_scope_id()
    if scope_id:
        contacts = Contact.query.filter_by(society_id=scope_id).all()
        opportunities = Opportunity.query.filter_by(society_id=scope_id).all()
    else:
        contacts = Contact.query.all()
        opportunities = Opportunity.query.all()
    
    form.contact_id.choices = [(0, 'Nessuno')] + [(c.id, f'{c.first_name} {c.last_name}') for c in contacts]
    form.opportunity_id.choices = [(0, 'Nessuna')] + [(o.id, o.title) for o in opportunities]
    
    if form.validate_on_submit():
        activity = CRMActivity(
            activity_type=form.activity_type.data,
            subject=form.subject.data,
            description=form.description.data,
            activity_date=form.activity_date.data or datetime.utcnow(),
            completed=form.completed.data,
            contact_id=form.contact_id.data if form.contact_id.data != 0 else None,
            opportunity_id=form.opportunity_id.data if form.opportunity_id.data != 0 else None,
            created_by=current_user.id
        )
        
        db.session.add(activity)
        db.session.commit()
        
        flash('Attività registrata!', 'success')
        
        # Redirect based on context
        if activity.opportunity_id:
            return redirect(url_for('crm.opportunity_detail', opp_id=activity.opportunity_id))
        elif activity.contact_id:
            return redirect(url_for('crm.contact_detail', contact_id=activity.contact_id))
        else:
            return redirect(url_for('crm.index'))
    
    # Pre-fill from query params
    contact_id = request.args.get('contact_id', type=int)
    opportunity_id = request.args.get('opportunity_id', type=int)
    
    if contact_id:
        form.contact_id.data = contact_id
    if opportunity_id:
        form.opportunity_id.data = opportunity_id
    
    return render_template('crm/activity_form.html', form=form, title='Nuova Attività')


@bp.route('/compliance')
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def compliance():
    """Society compliance: medical certificates and fees."""
    scope_id = _society_scope_id()
    if not scope_id:
        flash('Seleziona una società (scope) per gestire compliance.', 'warning')
        return redirect(url_for('crm.index'))

    # Filters
    cert_filter = (request.args.get('cert') or '').strip()
    fee_filter = (request.args.get('fee') or '').strip()

    cert_q = MedicalCertificate.query.options(joinedload(MedicalCertificate.user)).filter_by(society_id=scope_id)
    fee_q = SocietyFee.query.options(joinedload(SocietyFee.user)).filter_by(society_id=scope_id)

    today = date.today()
    soon = today + timedelta(days=14)
    if cert_filter == 'expiring':
        cert_q = cert_q.filter(MedicalCertificate.expires_on <= soon, MedicalCertificate.status == 'valid')
    elif cert_filter == 'expired':
        cert_q = cert_q.filter(MedicalCertificate.expires_on < today)

    if fee_filter == 'pending':
        fee_q = fee_q.filter(SocietyFee.status == 'pending')
    elif fee_filter == 'overdue':
        fee_q = fee_q.filter(SocietyFee.status == 'pending', SocietyFee.due_on < today)

    certificates = cert_q.order_by(MedicalCertificate.expires_on.asc()).all()
    fees = fee_q.order_by(SocietyFee.due_on.asc()).all()

    expiring_count = (
        MedicalCertificate.query.filter_by(society_id=scope_id)
        .filter(MedicalCertificate.status == 'valid', MedicalCertificate.expires_on <= soon, MedicalCertificate.expires_on >= today)
        .count()
    )
    overdue_fees_count = (
        SocietyFee.query.filter_by(society_id=scope_id)
        .filter(SocietyFee.status == 'pending', SocietyFee.due_on < today)
        .count()
    )

    cert_form = MedicalCertificateForm(society_id=scope_id)
    fee_form = SocietyFeeForm(society_id=scope_id)

    return render_template(
        'crm/compliance.html',
        certificates=certificates,
        fees=fees,
        cert_form=cert_form,
        fee_form=fee_form,
        cert_filter=cert_filter,
        fee_filter=fee_filter,
        expiring_count=expiring_count,
        overdue_fees_count=overdue_fees_count,
    )


@bp.route('/compliance/certificates/new', methods=['POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def compliance_certificate_new():
    scope_id = _society_scope_id()
    form = MedicalCertificateForm(society_id=scope_id)
    if not form.validate_on_submit():
        flash('Dati certificato non validi.', 'danger')
        return redirect(url_for('crm.compliance'))

    cert = MedicalCertificate(
        society_id=scope_id,
        user_id=form.user_id.data,
        issued_on=form.issued_on.data,
        expires_on=form.expires_on.data,
        status=form.status.data,
        notes=form.notes.data,
        created_by=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.session.add(cert)
    db.session.commit()
    log_action('create_medical_certificate', 'MedicalCertificate', cert.id, f'user_id={cert.user_id} expires={cert.expires_on}', society_id=scope_id)
    flash('Certificato inserito.', 'success')
    return redirect(url_for('crm.compliance'))


@bp.route('/compliance/certificates/<int:cert_id>/delete', methods=['POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def compliance_certificate_delete(cert_id):
    scope_id = _society_scope_id()
    cert = MedicalCertificate.query.get_or_404(cert_id)
    scoped = _enforce_scope(cert.society_id, 'crm.compliance')
    if scoped:
        return scoped
    db.session.delete(cert)
    db.session.commit()
    log_action('delete_medical_certificate', 'MedicalCertificate', cert_id, 'deleted', society_id=scope_id)
    flash('Certificato eliminato.', 'success')
    return redirect(url_for('crm.compliance'))


@bp.route('/compliance/certificates/<int:cert_id>/update', methods=['POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def compliance_certificate_update(cert_id):
    scope_id = _society_scope_id()
    cert = MedicalCertificate.query.get_or_404(cert_id)
    scoped = _enforce_scope(cert.society_id, 'crm.compliance')
    if scoped:
        return scoped

    status = (request.form.get('status') or '').strip()
    if status not in ('valid', 'expired', 'revoked'):
        flash('Stato non valido.', 'danger')
        return redirect(url_for('crm.compliance'))

    try:
        expires_on = request.form.get('expires_on') or ''
        cert.expires_on = datetime.strptime(expires_on, '%Y-%m-%d').date()
    except Exception:
        pass

    cert.status = status
    db.session.commit()
    log_action('update_medical_certificate', 'MedicalCertificate', cert.id, f'status={status}', society_id=scope_id)
    flash('Certificato aggiornato.', 'success')
    return redirect(url_for('crm.compliance'))


@bp.route('/compliance/fees/new', methods=['POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def compliance_fee_new():
    scope_id = _society_scope_id()
    form = SocietyFeeForm(society_id=scope_id)
    if not form.validate_on_submit():
        flash('Dati quota non validi.', 'danger')
        return redirect(url_for('crm.compliance'))

    try:
        amount = (form.amount_eur.data or '').replace(',', '.').strip()
        amount_cents = int(round(float(amount) * 100))
    except Exception:
        flash('Importo non valido.', 'danger')
        return redirect(url_for('crm.compliance'))

    fee = SocietyFee(
        society_id=scope_id,
        user_id=form.user_id.data,
        description=form.description.data or None,
        amount_cents=amount_cents,
        currency='EUR',
        due_on=form.due_on.data,
        status=form.status.data,
        paid_at=datetime.utcnow() if form.status.data == 'paid' else None,
        created_by=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.session.add(fee)
    db.session.commit()
    log_action('create_society_fee', 'SocietyFee', fee.id, f'user_id={fee.user_id} due={fee.due_on} cents={fee.amount_cents}', society_id=scope_id)
    flash('Quota inserita.', 'success')
    return redirect(url_for('crm.compliance'))


@bp.route('/compliance/fees/<int:fee_id>/delete', methods=['POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def compliance_fee_delete(fee_id):
    scope_id = _society_scope_id()
    fee = SocietyFee.query.get_or_404(fee_id)
    scoped = _enforce_scope(fee.society_id, 'crm.compliance')
    if scoped:
        return scoped
    db.session.delete(fee)
    db.session.commit()
    log_action('delete_society_fee', 'SocietyFee', fee_id, 'deleted', society_id=scope_id)
    flash('Quota eliminata.', 'success')
    return redirect(url_for('crm.compliance'))


@bp.route('/compliance/fees/<int:fee_id>/update', methods=['POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def compliance_fee_update(fee_id):
    scope_id = _society_scope_id()
    fee = SocietyFee.query.get_or_404(fee_id)
    scoped = _enforce_scope(fee.society_id, 'crm.compliance')
    if scoped:
        return scoped

    status = (request.form.get('status') or '').strip()
    if status not in ('pending', 'paid', 'cancelled'):
        flash('Stato non valido.', 'danger')
        return redirect(url_for('crm.compliance'))

    # Optionally update due date
    try:
        due_on = request.form.get('due_on') or ''
        fee.due_on = datetime.strptime(due_on, '%Y-%m-%d').date()
    except Exception:
        pass

    fee.status = status
    fee.paid_at = datetime.utcnow() if status == 'paid' else None
    db.session.commit()
    log_action('update_society_fee', 'SocietyFee', fee.id, f'status={status}', society_id=scope_id)
    flash('Quota aggiornata.', 'success')
    return redirect(url_for('crm.compliance'))


@bp.route('/compliance/export.csv')
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def compliance_export():
    """CSV export for compliance data."""
    import csv
    import io
    from flask import Response

    scope_id = _society_scope_id()
    if not scope_id:
        flash('Scope società non valido.', 'danger')
        return redirect(url_for('crm.index'))

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['type', 'user_id', 'user_name', 'status', 'date', 'amount_eur', 'description'])

    certs = MedicalCertificate.query.options(joinedload(MedicalCertificate.user)).filter_by(society_id=scope_id).all()
    for c in certs:
        w.writerow(['certificate', c.user_id, c.user.get_full_name() if c.user else '', c.status, c.expires_on.isoformat(), '', ''])

    fees = SocietyFee.query.options(joinedload(SocietyFee.user)).filter_by(society_id=scope_id).all()
    for f in fees:
        w.writerow(['fee', f.user_id, f.user.get_full_name() if f.user else '', f.status, f.due_on.isoformat(), round((f.amount_cents or 0) / 100.0, 2), f.description or ''])

    resp = Response(out.getvalue(), mimetype='text/csv')
    resp.headers['Content-Disposition'] = 'attachment; filename="sonacip_compliance.csv"'
    return resp


@bp.route('/compliance/certificates/<int:cert_id>/remind', methods=['POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def compliance_certificate_remind(cert_id):
    """Send a manual reminder for a certificate via AutomationRule."""
    from app.automation.utils import execute_rules
    from app.models import MedicalCertificateReminderSent

    scope_id = _society_scope_id()
    cert = MedicalCertificate.query.get_or_404(cert_id)
    scoped = _enforce_scope(cert.society_id, 'crm.compliance')
    if scoped:
        return scoped

    kind = 'manual'
    exists = MedicalCertificateReminderSent.query.filter_by(
        certificate_id=cert.id, user_id=cert.user_id, kind=kind
    ).first()
    if exists:
        flash('Promemoria già inviato (manual).', 'info')
        return redirect(url_for('crm.compliance'))

    today = date.today()
    payload = {
        "society_id": cert.society_id,
        "user_id": cert.user_id,
        "certificate_id": cert.id,
        "expires_on": cert.expires_on.isoformat(),
        "days_left": (cert.expires_on - today).days if cert.expires_on else None,
        "kind": kind,
    }
    execute_rules("medical_certificate.expiring", payload=payload)
    db.session.add(MedicalCertificateReminderSent(certificate_id=cert.id, user_id=cert.user_id, kind=kind, sent_at=datetime.utcnow()))
    db.session.commit()
    log_action('manual_certificate_reminder', 'MedicalCertificate', cert.id, 'manual reminder sent', society_id=scope_id)
    flash('Promemoria inviato.', 'success')
    return redirect(url_for('crm.compliance'))


@bp.route('/compliance/fees/<int:fee_id>/remind', methods=['POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def compliance_fee_remind(fee_id):
    """Send a manual reminder for a fee via AutomationRule."""
    from app.automation.utils import execute_rules
    from app.models import SocietyFeeReminderSent

    scope_id = _society_scope_id()
    fee = SocietyFee.query.get_or_404(fee_id)
    scoped = _enforce_scope(fee.society_id, 'crm.compliance')
    if scoped:
        return scoped

    kind = 'manual'
    exists = SocietyFeeReminderSent.query.filter_by(
        fee_id=fee.id, user_id=fee.user_id, kind=kind
    ).first()
    if exists:
        flash('Sollecito già inviato (manual).', 'info')
        return redirect(url_for('crm.compliance'))

    today = date.today()
    payload = {
        "society_id": fee.society_id,
        "user_id": fee.user_id,
        "fee_id": fee.id,
        "due_on": fee.due_on.isoformat(),
        "amount_cents": fee.amount_cents,
        "amount_eur": round((fee.amount_cents or 0) / 100.0, 2),
        "currency": fee.currency,
        "description": fee.description or "",
        "days_left": (fee.due_on - today).days if fee.due_on else None,
        "kind": kind,
    }
    execute_rules("fee.due", payload=payload)
    db.session.add(SocietyFeeReminderSent(fee_id=fee.id, user_id=fee.user_id, kind=kind, sent_at=datetime.utcnow()))
    db.session.commit()
    log_action('manual_fee_reminder', 'SocietyFee', fee.id, 'manual reminder sent', society_id=scope_id)
    flash('Sollecito inviato.', 'success')
    return redirect(url_for('crm.compliance'))
