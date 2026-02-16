"""
CRM Routes
Sports Society Member Management
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.crm.forms import (
    ContactForm,
    OpportunityForm,
    ActivityForm,
    MedicalCertificateForm,
    SocietyFeeForm,
    PipelineStageForm,
    MemberSearchForm,
    MemberAddForm,
)
from app.models import (
    User,
    SocietyMembership,
    Society,
    MedicalCertificate,
    SocietyFee,
    Event,
    event_athletes,
    Notification,
    Contact,
    CRMActivity,
    MedicalCertificateReminderSent,
    SocietyFeeReminderSent,
    Payment,
    PlatformFeeSetting,
    PlatformTransaction,
)
from app.notifications.utils import create_notification
from app.utils import permission_required, check_permission, feature_required, get_active_society_id
from datetime import datetime, timezone
from app.utils import log_action
from sqlalchemy.orm import joinedload
from sqlalchemy import or_, func
from datetime import date, timedelta
from app.subscription.stripe_utils import stripe_enabled, create_fee_checkout_session

bp = Blueprint('crm', __name__, url_prefix='/crm')


@bp.route('/my-fees')
@login_required
def my_fees():
    scope_id = get_active_society_id(current_user)
    q = SocietyFee.query.options(joinedload(SocietyFee.society)).filter_by(user_id=current_user.id)
    if scope_id:
        q = q.filter(SocietyFee.society_id == scope_id)
    fees = q.order_by(SocietyFee.due_on.asc()).all()
    return render_template('crm/my_fees.html', fees=fees, scope_id=scope_id)


@bp.route('/fees/<int:fee_id>/pay', methods=['POST'])
@login_required
def pay_fee(fee_id: int):
    fee = SocietyFee.query.get_or_404(fee_id)
    if fee.user_id != current_user.id:
        flash('Accesso negato.', 'danger')
        return redirect(url_for('crm.my_fees'))
    if fee.status != 'pending':
        flash('Quota non pagabile (stato non pending).', 'warning')
        return redirect(url_for('crm.my_fees'))

    if stripe_enabled():
        try:
            success_url = url_for('crm.my_fees', _external=True) + "?paid=1"
            cancel_url = url_for('crm.my_fees', _external=True)
            checkout_url = create_fee_checkout_session(fee, success_url=success_url, cancel_url=cancel_url)
            return redirect(checkout_url)
        except Exception as exc:
            flash(f'Stripe non disponibile: {exc}', 'warning')

    amount_eur = round(float(fee.amount_cents or 0) / 100.0, 2)
    payment = Payment(
        user_id=current_user.id,
        society_id=fee.society_id,
        subscription_id=None,
        amount=amount_eur,
        currency=(fee.currency or 'EUR'),
        status='completed',
        payment_method='manual',
        payment_date=datetime.now(timezone.utc),
        description=f'Fee payment (SocietyFee #{fee.id})',
        transaction_id=f'LOCAL_FEE_{fee.id}_{datetime.now(timezone.utc).timestamp()}',
        gateway='local',
    )
    db.session.add(payment)
    db.session.flush()

    fee.status = 'paid'
    fee.paid_at = datetime.now(timezone.utc)
    db.session.add(fee)

    settings = PlatformFeeSetting.query.first()
    pct = int(settings.take_rate_percent or 0) if settings else 0
    min_cents = int(settings.min_fee_cents or 0) if settings else 0
    gross_cents = int(fee.amount_cents or 0)
    fee_cents = int(round((gross_cents * max(0, pct)) / 100.0))
    fee_cents = max(fee_cents, max(0, min_cents))
    fee_cents = min(fee_cents, gross_cents)
    platform_fee = round(fee_cents / 100.0, 2)
    net = round((gross_cents - fee_cents) / 100.0, 2)

    db.session.add(
        PlatformTransaction(
            society_id=fee.society_id,
            user_id=current_user.id,
            payment_id=payment.id,
            entity_type='SocietyFee',
            entity_id=fee.id,
            gross_amount=amount_eur,
            platform_fee_amount=platform_fee,
            net_amount=net,
            currency=(fee.currency or 'EUR'),
            status='collected',
            created_at=datetime.now(timezone.utc),
        )
    )
    db.session.commit()
    flash('Pagamento completato.', 'success')
    return redirect(url_for('crm.my_fees'))


def _society_scope_id():
    if check_permission(current_user, 'admin', 'access'):
        return get_active_society_id(current_user)
    return get_active_society_id(current_user)


def _enforce_scope(entity_society_id, redirect_endpoint):
    scope_id = _society_scope_id()
    if scope_id and entity_society_id != scope_id:
        flash('Accesso non autorizzato.', 'danger')
        return redirect(url_for(redirect_endpoint))
    return None


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@bp.route('/')
@login_required
@permission_required('crm', 'access', society_id_func=_society_scope_id)
@feature_required('crm')
def index():
    scope_id = _society_scope_id()

    total_members = 0
    total_athletes = 0
    expiring_certs = 0
    overdue_fees = 0
    recent_members = []
    upcoming_events = []
    expiring_cert_list = []
    overdue_fee_list = []

    if scope_id:
        members_q = SocietyMembership.query.filter_by(society_id=scope_id, status='active')
        total_members = members_q.count()
        total_athletes = members_q.filter(SocietyMembership.role_name.in_(['atleta', 'athlete'])).count()

        today = date.today()
        soon = today + timedelta(days=14)
        expiring_certs = (
            MedicalCertificate.query.filter_by(society_id=scope_id)
            .filter(MedicalCertificate.status == 'valid', MedicalCertificate.expires_on <= soon, MedicalCertificate.expires_on >= today)
            .count()
        )
        overdue_fees = (
            SocietyFee.query.filter_by(society_id=scope_id)
            .filter(SocietyFee.status == 'pending', SocietyFee.due_on < today)
            .count()
        )

        recent_members = (
            SocietyMembership.query.options(joinedload(SocietyMembership.user))
            .filter_by(society_id=scope_id, status='active')
            .order_by(SocietyMembership.created_at.desc())
            .limit(5)
            .all()
        )

        upcoming_events = (
            Event.query
            .filter(Event.start_date >= datetime.now(timezone.utc))
            .order_by(Event.start_date.asc())
            .limit(5)
            .all()
        )

        expiring_cert_list = (
            MedicalCertificate.query.options(joinedload(MedicalCertificate.user))
            .filter_by(society_id=scope_id)
            .filter(MedicalCertificate.status == 'valid', MedicalCertificate.expires_on <= soon, MedicalCertificate.expires_on >= today)
            .order_by(MedicalCertificate.expires_on.asc())
            .limit(5)
            .all()
        )

        overdue_fee_list = (
            SocietyFee.query.options(joinedload(SocietyFee.user))
            .filter_by(society_id=scope_id)
            .filter(SocietyFee.status == 'pending', SocietyFee.due_on < today)
            .order_by(SocietyFee.due_on.asc())
            .limit(5)
            .all()
        )

    return render_template(
        'crm/index.html',
        total_members=total_members,
        total_athletes=total_athletes,
        expiring_certs=expiring_certs,
        overdue_fees=overdue_fees,
        recent_members=recent_members,
        upcoming_events=upcoming_events,
        expiring_cert_list=expiring_cert_list,
        overdue_fee_list=overdue_fee_list,
    )


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------
@bp.route('/members')
@login_required
@permission_required('crm', 'access', society_id_func=_society_scope_id)
@feature_required('crm')
def members():
    scope_id = _society_scope_id()
    if not scope_id:
        flash('Seleziona una società per gestire i membri.', 'warning')
        return redirect(url_for('crm.index'))

    role_filter = request.args.get('role', '').strip()
    name_filter = request.args.get('q', '').strip()

    q = (
        SocietyMembership.query
        .options(joinedload(SocietyMembership.user))
        .filter_by(society_id=scope_id, status='active')
    )
    if role_filter:
        q = q.filter(SocietyMembership.role_name == role_filter)

    memberships = q.order_by(SocietyMembership.created_at.desc()).all()

    if name_filter:
        lower_q = name_filter.lower()
        memberships = [
            m for m in memberships
            if m.user and (lower_q in (m.user.first_name or '').lower()
                           or lower_q in (m.user.last_name or '').lower()
                           or lower_q in (m.user.email or '').lower())
        ]

    today = date.today()
    soon = today + timedelta(days=14)
    member_data = []
    for m in memberships:
        cert = (
            MedicalCertificate.query
            .filter_by(society_id=scope_id, user_id=m.user_id)
            .order_by(MedicalCertificate.expires_on.desc())
            .first()
        )
        pending_fees = (
            SocietyFee.query
            .filter_by(society_id=scope_id, user_id=m.user_id, status='pending')
            .count()
        )
        cert_status = 'none'
        if cert:
            if cert.status == 'valid' and cert.expires_on and cert.expires_on >= today:
                if cert.expires_on <= soon:
                    cert_status = 'expiring'
                else:
                    cert_status = 'valid'
            else:
                cert_status = 'expired'
        member_data.append({
            'membership': m,
            'cert_status': cert_status,
            'pending_fees': pending_fees,
        })

    return render_template(
        'crm/members.html',
        member_data=member_data,
        role_filter=role_filter,
        name_filter=name_filter,
    )


@bp.route('/members/search')
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def member_search():
    scope_id = _society_scope_id()
    q = (request.args.get('q') or '').strip()
    if not q or len(q) < 2:
        return jsonify([])

    pattern = f'%{q}%'
    users = (
        User.query
        .filter(User.is_active == True)
        .filter(
            or_(
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
                User.email.ilike(pattern),
            )
        )
        .limit(20)
        .all()
    )

    existing_ids = set()
    if scope_id:
        rows = (
            SocietyMembership.query
            .filter_by(society_id=scope_id, status='active')
            .with_entities(SocietyMembership.user_id)
            .all()
        )
        existing_ids = {r[0] for r in rows}

    results = []
    for u in users:
        results.append({
            'id': u.id,
            'first_name': u.first_name or '',
            'last_name': u.last_name or '',
            'email': u.email,
            'avatar_url': u.avatar_url if hasattr(u, 'avatar_url') and u.avatar_url else '',
            'already_member': u.id in existing_ids,
        })

    return jsonify(results)


@bp.route('/members/add', methods=['GET', 'POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def member_add():
    scope_id = _society_scope_id()
    if not scope_id:
        flash('Seleziona una società.', 'warning')
        return redirect(url_for('crm.index'))

    form = MemberAddForm()

    if form.validate_on_submit():
        user_id = int(form.user_id.data)
        role_name = form.role_name.data

        existing = SocietyMembership.query.filter_by(society_id=scope_id, user_id=user_id).first()
        if existing:
            if existing.status == 'active':
                flash('Utente già membro attivo della società.', 'warning')
                return redirect(url_for('crm.members'))
            existing.status = 'active'
            existing.role_name = role_name
            existing.updated_by = current_user.id
            existing.updated_at = datetime.now(timezone.utc)
        else:
            membership = SocietyMembership(
                society_id=scope_id,
                user_id=user_id,
                role_name=role_name,
                status='active',
                created_by=current_user.id,
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(membership)

        db.session.flush()

        # Auto-create rubrica contact for this member if not already present
        user = User.query.get(user_id)
        if user:
            existing_contact = Contact.query.filter_by(
                society_id=scope_id, user_id=user_id
            ).first()
            if not existing_contact:
                contact = Contact(
                    first_name=user.first_name or '',
                    last_name=user.last_name or '',
                    email=user.email or '',
                    phone=user.phone or '',
                    address=user.address or '',
                    city=user.city or '',
                    postal_code=user.postal_code or '',
                    contact_type='athlete' if role_name == 'atleta' else 'other',
                    status='converted',
                    source='membership',
                    society_id=scope_id,
                    user_id=user_id,
                    created_by=current_user.id,
                )
                db.session.add(contact)

        db.session.commit()
        flash('Membro aggiunto con successo!', 'success')
        return redirect(url_for('crm.members'))

    return render_template('crm/member_add.html', form=form)


@bp.route('/members/<int:membership_id>')
@login_required
@permission_required('crm', 'access', society_id_func=_society_scope_id)
@feature_required('crm')
def member_detail(membership_id):
    membership = SocietyMembership.query.options(joinedload(SocietyMembership.user)).get_or_404(membership_id)

    scoped = _enforce_scope(membership.society_id, 'crm.members')
    if scoped:
        return scoped

    scope_id = membership.society_id
    user = membership.user

    certificates = (
        MedicalCertificate.query
        .filter_by(society_id=scope_id, user_id=user.id)
        .order_by(MedicalCertificate.expires_on.desc())
        .all()
    )
    fees = (
        SocietyFee.query
        .filter_by(society_id=scope_id, user_id=user.id)
        .order_by(SocietyFee.due_on.desc())
        .all()
    )

    convocations = []
    try:
        rows = db.session.execute(
            db.select(event_athletes.c.event_id, event_athletes.c.status)
            .where(event_athletes.c.user_id == user.id)
        ).fetchall()
        event_ids = [r[0] for r in rows]
        status_map = {r[0]: r[1] for r in rows}
        if event_ids:
            events = Event.query.filter(Event.id.in_(event_ids)).order_by(Event.start_date.desc()).limit(20).all()
            for ev in events:
                convocations.append({
                    'event': ev,
                    'status': status_map.get(ev.id, 'pending'),
                })
    except Exception:
        pass

    cert_form = MedicalCertificateForm(society_id=scope_id)
    cert_form.user_id.choices = [(user.id, user.get_full_name())]
    cert_form.user_id.data = user.id

    fee_form = SocietyFeeForm(society_id=scope_id)
    fee_form.user_id.choices = [(user.id, user.get_full_name())]
    fee_form.user_id.data = user.id

    rubrica_contact = Contact.query.filter_by(society_id=scope_id, user_id=user.id).first()

    return render_template(
        'crm/member_detail.html',
        membership=membership,
        user=user,
        certificates=certificates,
        fees=fees,
        convocations=convocations,
        cert_form=cert_form,
        fee_form=fee_form,
        rubrica_contact=rubrica_contact,
    )


@bp.route('/members/<int:membership_id>/role', methods=['POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def member_role_update(membership_id):
    membership = SocietyMembership.query.get_or_404(membership_id)
    scoped = _enforce_scope(membership.society_id, 'crm.members')
    if scoped:
        return scoped

    new_role = (request.form.get('role_name') or '').strip()
    valid_roles = ['atleta', 'coach', 'dirigente', 'staff', 'appassionato']
    if new_role not in valid_roles:
        flash('Ruolo non valido.', 'danger')
        return redirect(url_for('crm.member_detail', membership_id=membership_id))

    membership.role_name = new_role
    membership.updated_by = current_user.id
    membership.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    log_action('member_role_update', 'SocietyMembership', membership.id, f'role={new_role}', society_id=membership.society_id)
    flash('Ruolo aggiornato.', 'success')
    return redirect(url_for('crm.member_detail', membership_id=membership_id))


@bp.route('/members/<int:membership_id>/remove', methods=['POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def member_remove(membership_id):
    membership = SocietyMembership.query.get_or_404(membership_id)
    scoped = _enforce_scope(membership.society_id, 'crm.members')
    if scoped:
        return scoped

    membership.status = 'revoked'
    membership.updated_by = current_user.id
    membership.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    log_action('member_remove', 'SocietyMembership', membership.id, 'status=revoked', society_id=membership.society_id)
    flash('Membro rimosso dalla società.', 'success')
    return redirect(url_for('crm.members'))


@bp.route('/members/<int:membership_id>/fee', methods=['POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def member_fee_create(membership_id):
    membership = SocietyMembership.query.get_or_404(membership_id)
    scoped = _enforce_scope(membership.society_id, 'crm.members')
    if scoped:
        return scoped

    scope_id = membership.society_id
    form = SocietyFeeForm(society_id=scope_id)
    form.user_id.choices = [(membership.user_id, '')]
    form.user_id.data = membership.user_id

    if not form.validate_on_submit():
        flash('Dati quota non validi.', 'danger')
        return redirect(url_for('crm.member_detail', membership_id=membership_id))

    try:
        amount = (form.amount_eur.data or '').replace(',', '.').strip()
        amount_cents = int(round(float(amount) * 100))
    except Exception:
        flash('Importo non valido.', 'danger')
        return redirect(url_for('crm.member_detail', membership_id=membership_id))

    fee = SocietyFee(
        society_id=scope_id,
        user_id=membership.user_id,
        description=form.description.data or None,
        amount_cents=amount_cents,
        currency='EUR',
        due_on=form.due_on.data,
        status=form.status.data,
        paid_at=datetime.now(timezone.utc) if form.status.data == 'paid' else None,
        created_by=current_user.id,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(fee)
    db.session.commit()
    log_action('create_society_fee', 'SocietyFee', fee.id, f'user_id={fee.user_id} via member_detail', society_id=scope_id)
    flash('Quota creata.', 'success')
    return redirect(url_for('crm.member_detail', membership_id=membership_id))


@bp.route('/members/<int:membership_id>/certificate', methods=['POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def member_certificate_create(membership_id):
    membership = SocietyMembership.query.get_or_404(membership_id)
    scoped = _enforce_scope(membership.society_id, 'crm.members')
    if scoped:
        return scoped

    scope_id = membership.society_id
    form = MedicalCertificateForm(society_id=scope_id)
    form.user_id.choices = [(membership.user_id, '')]
    form.user_id.data = membership.user_id

    if not form.validate_on_submit():
        flash('Dati certificato non validi.', 'danger')
        return redirect(url_for('crm.member_detail', membership_id=membership_id))

    cert = MedicalCertificate(
        society_id=scope_id,
        user_id=membership.user_id,
        issued_on=form.issued_on.data,
        expires_on=form.expires_on.data,
        status=form.status.data,
        notes=form.notes.data,
        created_by=current_user.id,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(cert)
    db.session.commit()
    log_action('create_medical_certificate', 'MedicalCertificate', cert.id, f'user_id={cert.user_id} via member_detail', society_id=scope_id)
    flash('Certificato inserito.', 'success')
    return redirect(url_for('crm.member_detail', membership_id=membership_id))


# ---------------------------------------------------------------------------
# Convocations
# ---------------------------------------------------------------------------
@bp.route('/convocations')
@login_required
@permission_required('crm', 'access', society_id_func=_society_scope_id)
@feature_required('crm')
def convocations():
    scope_id = _society_scope_id()
    if not scope_id:
        flash('Seleziona una società.', 'warning')
        return redirect(url_for('crm.index'))

    member_ids = [
        r[0] for r in
        SocietyMembership.query.filter_by(society_id=scope_id, status='active')
        .with_entities(SocietyMembership.user_id).all()
    ]

    now = datetime.now(timezone.utc)
    events = (
        Event.query
        .filter(Event.start_date >= now)
        .order_by(Event.start_date.asc())
        .all()
    )

    event_data = []
    for ev in events:
        rows = db.session.execute(
            db.select(event_athletes.c.user_id, event_athletes.c.status)
            .where(event_athletes.c.event_id == ev.id)
        ).fetchall()

        society_convocated = [r for r in rows if r[0] in member_ids] if member_ids else []
        total = len(society_convocated)
        accepted = len([r for r in society_convocated if r[1] == 'accepted'])
        pending = len([r for r in society_convocated if r[1] == 'pending'])
        declined = len([r for r in society_convocated if r[1] == 'rejected'])

        if total > 0:
            event_data.append({
                'event': ev,
                'total': total,
                'accepted': accepted,
                'pending': pending,
                'declined': declined,
            })

    return render_template('crm/convocations.html', event_data=event_data)


@bp.route('/convocations/<int:event_id>/notify', methods=['POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def convocation_notify(event_id):
    scope_id = _society_scope_id()
    ev = Event.query.get_or_404(event_id)

    rows = db.session.execute(
        db.select(event_athletes.c.user_id)
        .where(event_athletes.c.event_id == ev.id)
    ).fetchall()

    member_ids = set()
    if scope_id:
        m_rows = (
            SocietyMembership.query.filter_by(society_id=scope_id, status='active')
            .with_entities(SocietyMembership.user_id).all()
        )
        member_ids = {r[0] for r in m_rows}

    count = 0
    for r in rows:
        uid = r[0]
        if member_ids and uid not in member_ids:
            continue
        create_notification(
            user_id=uid,
            title='Convocazione Evento',
            message=f'Sei convocato per "{ev.title}" il {ev.start_date.strftime("%d/%m/%Y %H:%M") if ev.start_date else "TBD"}. Rispondi alla convocazione.',
            notification_type='event',
            link=url_for('events.detail', event_id=ev.id),
        )
        count += 1

    flash(f'Notifica inviata a {count} atleti.', 'success')
    return redirect(url_for('crm.convocations'))


# ---------------------------------------------------------------------------
# Rubrica (Address Book) – society-scoped member contacts
# ---------------------------------------------------------------------------
@bp.route('/rubrica')
@login_required
@permission_required('crm', 'access', society_id_func=_society_scope_id)
@feature_required('crm')
def rubrica():
    scope_id = _society_scope_id()
    if not scope_id:
        flash('Seleziona una società.', 'warning')
        return redirect(url_for('crm.index'))

    q_filter = request.args.get('q', '').strip()
    role_filter = request.args.get('role', '').strip()

    query = (
        Contact.query
        .filter(Contact.society_id == scope_id, Contact.user_id.isnot(None))
        .order_by(Contact.last_name.asc(), Contact.first_name.asc())
    )
    if q_filter:
        like = f'%{q_filter}%'
        query = query.filter(
            or_(Contact.first_name.ilike(like), Contact.last_name.ilike(like), Contact.email.ilike(like))
        )

    contacts = query.all()

    # Build membership map for role badges & detail links
    user_ids = [c.user_id for c in contacts if c.user_id]
    memberships = {}
    if user_ids:
        ms = SocietyMembership.query.filter(
            SocietyMembership.society_id == scope_id,
            SocietyMembership.user_id.in_(user_ids),
            SocietyMembership.status == 'active',
        ).all()
        memberships = {m.user_id: m for m in ms}

    if role_filter:
        contacts = [c for c in contacts if memberships.get(c.user_id) and memberships[c.user_id].role_name == role_filter]

    return render_template(
        'crm/rubrica.html',
        contacts=contacts,
        memberships=memberships,
        q_filter=q_filter,
        role_filter=role_filter,
    )


@bp.route('/rubrica/<int:contact_id>')
@login_required
@permission_required('crm', 'access', society_id_func=_society_scope_id)
@feature_required('crm')
def rubrica_detail(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    scoped = _enforce_scope(contact.society_id, 'crm.rubrica')
    if scoped:
        return scoped
    if not contact.user_id:
        flash('Questo contatto non è collegato a un utente.', 'warning')
        return redirect(url_for('crm.contacts'))

    scope_id = contact.society_id
    user = User.query.get(contact.user_id)
    membership = SocietyMembership.query.filter_by(
        society_id=scope_id, user_id=contact.user_id, status='active'
    ).first()

    certificates = (
        MedicalCertificate.query
        .filter_by(society_id=scope_id, user_id=contact.user_id)
        .order_by(MedicalCertificate.expires_on.desc())
        .all()
    )
    fees = (
        SocietyFee.query
        .filter_by(society_id=scope_id, user_id=contact.user_id)
        .order_by(SocietyFee.due_on.desc())
        .all()
    )
    convocations = []
    try:
        rows = db.session.execute(
            db.select(event_athletes.c.event_id, event_athletes.c.status)
            .where(event_athletes.c.user_id == contact.user_id)
        ).fetchall()
        event_ids = [r[0] for r in rows]
        status_map = {r[0]: r[1] for r in rows}
        if event_ids:
            events = Event.query.filter(Event.id.in_(event_ids)).order_by(Event.start_date.desc()).limit(20).all()
            for ev in events:
                convocations.append({'event': ev, 'status': status_map.get(ev.id, 'pending')})
    except Exception:
        pass

    return render_template(
        'crm/rubrica_detail.html',
        contact=contact,
        user=user,
        membership=membership,
        certificates=certificates,
        fees=fees,
        convocations=convocations,
    )


@bp.route('/rubrica/<int:contact_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def rubrica_edit(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    scoped = _enforce_scope(contact.society_id, 'crm.rubrica')
    if scoped:
        return scoped
    if not contact.user_id:
        flash('Questo contatto non è collegato a un utente.', 'warning')
        return redirect(url_for('crm.contacts'))

    form = ContactForm(obj=contact)

    if form.validate_on_submit():
        contact.first_name = form.first_name.data
        contact.last_name = form.last_name.data
        contact.email = form.email.data
        contact.phone = form.phone.data
        contact.address = form.address.data
        contact.city = form.city.data
        contact.postal_code = form.postal_code.data
        contact.notes = form.notes.data
        contact.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        flash('Contatto rubrica aggiornato!', 'success')
        return redirect(url_for('crm.rubrica_detail', contact_id=contact_id))

    return render_template('crm/rubrica_edit.html', form=form, contact=contact)


# ---------------------------------------------------------------------------
# Reminders (manual trigger)
# ---------------------------------------------------------------------------
@bp.route('/reminders/run', methods=['POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def reminders_run():
    scope_id = _society_scope_id()
    if not scope_id:
        flash('Seleziona una società.', 'warning')
        return redirect(url_for('crm.index'))

    today = date.today()
    sent_count = 0

    for kind, delta in [('14d', 14), ('7d', 7)]:
        threshold = today + timedelta(days=delta)
        certs = (
            MedicalCertificate.query
            .filter_by(society_id=scope_id, status='valid')
            .filter(MedicalCertificate.expires_on <= threshold, MedicalCertificate.expires_on >= today)
            .all()
        )
        for cert in certs:
            already = MedicalCertificateReminderSent.query.filter_by(
                certificate_id=cert.id, user_id=cert.user_id, kind=kind
            ).first()
            if already:
                continue
            create_notification(
                user_id=cert.user_id,
                title='Certificato Medico in Scadenza',
                message=f'Il tuo certificato medico scade il {cert.expires_on.strftime("%d/%m/%Y")}. Rinnova al più presto.',
                notification_type='reminder',
                link=url_for('crm.my_fees'),
            )
            db.session.add(MedicalCertificateReminderSent(
                certificate_id=cert.id, user_id=cert.user_id, kind=kind, sent_at=datetime.now(timezone.utc)
            ))
            sent_count += 1

    overdue_fees = (
        SocietyFee.query
        .filter_by(society_id=scope_id, status='pending')
        .filter(SocietyFee.due_on < today)
        .all()
    )
    for fee in overdue_fees:
        kind = 'overdue'
        already = SocietyFeeReminderSent.query.filter_by(
            fee_id=fee.id, user_id=fee.user_id, kind=kind
        ).first()
        if already:
            continue
        create_notification(
            user_id=fee.user_id,
            title='Quota Societaria Scaduta',
            message=f'La tua quota "{fee.description or "Quota"}" di €{(fee.amount_cents or 0)/100:.2f} è scaduta il {fee.due_on.strftime("%d/%m/%Y")}. Provvedi al pagamento.',
            notification_type='reminder',
            link=url_for('crm.my_fees'),
        )
        db.session.add(SocietyFeeReminderSent(
            fee_id=fee.id, user_id=fee.user_id, kind=kind, sent_at=datetime.now(timezone.utc)
        ))
        sent_count += 1

    db.session.commit()
    flash(f'Promemoria inviati: {sent_count}.', 'success')
    return redirect(url_for('crm.index'))


# ---------------------------------------------------------------------------
# Contacts (Contatti Esterni)
# ---------------------------------------------------------------------------
@bp.route('/contacts')
@login_required
@permission_required('crm', 'access', society_id_func=_society_scope_id)
@feature_required('crm')
def contacts():
    scope_id = _society_scope_id()
    if scope_id:
        contacts_list = Contact.query.filter_by(society_id=scope_id).order_by(Contact.created_at.desc()).all()
    else:
        contacts_list = Contact.query.order_by(Contact.created_at.desc()).all() if check_permission(current_user, 'admin', 'access') else []

    status_filter = request.args.get('status')
    if status_filter:
        contacts_list = [c for c in contacts_list if c.status == status_filter]

    return render_template('crm/contacts.html', contacts=contacts_list, status_filter=status_filter)


@bp.route('/contacts/new', methods=['GET', 'POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def new_contact():
    form = ContactForm()

    if form.validate_on_submit():
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
    contact = Contact.query.get_or_404(contact_id)
    scoped = _enforce_scope(contact.society_id, 'crm.contacts')
    if scoped:
        return scoped

    activities = CRMActivity.query.filter_by(contact_id=contact_id).order_by(CRMActivity.created_at.desc()).all()

    return render_template('crm/contact_detail.html',
                           contact=contact,
                           activities=activities)


@bp.route('/contacts/<int:contact_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def edit_contact(contact_id):
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
        contact.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        flash('Contatto aggiornato!', 'success')
        return redirect(url_for('crm.contact_detail', contact_id=contact_id))

    return render_template('crm/contact_form.html', form=form, title='Modifica Contatto', contact=contact)


# ---------------------------------------------------------------------------
# Activity logging
# ---------------------------------------------------------------------------
@bp.route('/activities/new', methods=['GET', 'POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def new_activity():
    form = ActivityForm()

    scope_id = _society_scope_id()
    if scope_id:
        contacts_list = Contact.query.filter_by(society_id=scope_id).all()
    else:
        contacts_list = Contact.query.all()

    form.contact_id.choices = [(0, 'Nessuno')] + [(c.id, f'{c.first_name} {c.last_name}') for c in contacts_list]

    if form.validate_on_submit():
        activity = CRMActivity(
            activity_type=form.activity_type.data,
            subject=form.subject.data,
            description=form.description.data,
            activity_date=form.activity_date.data or datetime.now(timezone.utc),
            completed=form.completed.data,
            contact_id=form.contact_id.data if form.contact_id.data != 0 else None,
            opportunity_id=None,
            created_by=current_user.id
        )
        db.session.add(activity)
        db.session.commit()
        flash('Attività registrata!', 'success')

        if activity.contact_id:
            return redirect(url_for('crm.contact_detail', contact_id=activity.contact_id))
        else:
            return redirect(url_for('crm.index'))

    contact_id = request.args.get('contact_id', type=int)
    if contact_id:
        form.contact_id.data = contact_id

    return render_template('crm/activity_form.html', form=form, title='Nuova Attività')


# ---------------------------------------------------------------------------
# Compliance routes (unchanged)
# ---------------------------------------------------------------------------
@bp.route('/compliance')
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def compliance():
    scope_id = _society_scope_id()
    if not scope_id:
        flash('Seleziona una società (scope) per gestire compliance.', 'warning')
        return redirect(url_for('crm.index'))

    cert_filter = (request.args.get('cert') or '').strip()
    fee_filter = (request.args.get('fee') or '').strip()

    certificates = []
    fees = []
    expiring_count = 0
    overdue_fees_count = 0
    cert_form = MedicalCertificateForm(society_id=scope_id)
    fee_form = SocietyFeeForm(society_id=scope_id)

    try:
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
    except Exception:
        if current_app:
            current_app.logger.exception('Compliance load failed')
        flash('Impossibile caricare la sezione compliance.', 'danger')

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
        created_at=datetime.now(timezone.utc),
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
        paid_at=datetime.now(timezone.utc) if form.status.data == 'paid' else None,
        created_by=current_user.id,
        created_at=datetime.now(timezone.utc),
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

    try:
        due_on = request.form.get('due_on') or ''
        fee.due_on = datetime.strptime(due_on, '%Y-%m-%d').date()
    except Exception:
        pass

    fee.status = status
    fee.paid_at = datetime.now(timezone.utc) if status == 'paid' else None
    db.session.commit()
    log_action('update_society_fee', 'SocietyFee', fee.id, f'status={status}', society_id=scope_id)
    flash('Quota aggiornata.', 'success')
    return redirect(url_for('crm.compliance'))


@bp.route('/compliance/export.csv')
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def compliance_export():
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
    from app.automation.utils import execute_rules

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
    db.session.add(MedicalCertificateReminderSent(certificate_id=cert.id, user_id=cert.user_id, kind=kind, sent_at=datetime.now(timezone.utc)))
    db.session.commit()
    log_action('manual_certificate_reminder', 'MedicalCertificate', cert.id, 'manual reminder sent', society_id=scope_id)
    flash('Promemoria inviato.', 'success')
    return redirect(url_for('crm.compliance'))


@bp.route('/compliance/fees/<int:fee_id>/remind', methods=['POST'])
@login_required
@permission_required('crm', 'manage', society_id_func=_society_scope_id)
@feature_required('crm')
def compliance_fee_remind(fee_id):
    from app.automation.utils import execute_rules

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
    db.session.add(SocietyFeeReminderSent(fee_id=fee.id, user_id=fee.user_id, kind=kind, sent_at=datetime.now(timezone.utc)))
    db.session.commit()
    log_action('manual_fee_reminder', 'SocietyFee', fee.id, 'manual reminder sent', society_id=scope_id)
    flash('Sollecito inviato.', 'success')
    return redirect(url_for('crm.compliance'))
