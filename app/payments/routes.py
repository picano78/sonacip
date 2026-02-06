from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app import db, csrf
from app.models import FeePayment, SocietyFee, User
from app.utils import admin_required, log_action
from datetime import datetime
import os
import json
import stripe

bp = Blueprint('payments', __name__, url_prefix='/payments')

ALLOWED_STATUSES = {'pending', 'completed', 'failed'}


@bp.before_request
def _check_feature():
    from app.utils import check_feature_enabled
    if not check_feature_enabled('payments_online'):
        flash('Questa funzionalità non è attualmente disponibile.', 'warning')
        return redirect(url_for('main.dashboard'))


def _init_stripe():
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY') or current_app.config.get('STRIPE_SECRET_KEY')


def _base_url():
    domain = os.environ.get('REPLIT_DOMAINS', '').split(',')[0].strip()
    if domain:
        return f'https://{domain}'
    return request.host_url.rstrip('/')


@bp.route('/')
@login_required
def index():
    status_filter = request.args.get('status', '').strip()
    q = FeePayment.query.filter_by(user_id=current_user.id)
    if status_filter in ALLOWED_STATUSES:
        q = q.filter_by(status=status_filter)
    payments = q.order_by(FeePayment.created_at.desc()).all()
    return render_template('payments/index.html', payments=payments, status_filter=status_filter)


@bp.route('/fee/<int:fee_id>/pay')
@login_required
def pay(fee_id):
    fee = SocietyFee.query.get_or_404(fee_id)
    if fee.user_id != current_user.id:
        flash('Accesso negato.', 'danger')
        return redirect(url_for('payments.index'))
    if fee.status == 'paid':
        flash('Questa quota è già stata pagata.', 'info')
        return redirect(url_for('payments.index'))
    amount_eur = round(float(fee.amount_cents or 0) / 100.0, 2)
    return render_template('payments/pay.html', fee=fee, amount_eur=amount_eur)


@bp.route('/fee/<int:fee_id>/checkout', methods=['POST'])
@login_required
def checkout(fee_id):
    fee = SocietyFee.query.get_or_404(fee_id)
    if fee.user_id != current_user.id:
        flash('Accesso negato.', 'danger')
        return redirect(url_for('payments.index'))
    if fee.status == 'paid':
        flash('Questa quota è già stata pagata.', 'info')
        return redirect(url_for('payments.index'))

    _init_stripe()
    if not stripe.api_key:
        flash('Stripe non è configurato. Contatta l\'amministratore.', 'danger')
        return redirect(url_for('payments.pay', fee_id=fee_id))

    amount_cents = int(fee.amount_cents or 0)
    if amount_cents <= 0:
        flash('Importo non valido.', 'danger')
        return redirect(url_for('payments.pay', fee_id=fee_id))

    base = _base_url()
    currency = (fee.currency or 'EUR').lower()

    fp = FeePayment.query.filter_by(fee_id=fee.id, user_id=current_user.id, status='pending').first()
    if not fp:
        fp = FeePayment(
            fee_id=fee.id,
            user_id=current_user.id,
            amount=round(amount_cents / 100.0, 2),
            payment_method='stripe',
            status='pending',
        )
        db.session.add(fp)
        db.session.commit()

    try:
        sess = stripe.checkout.Session.create(
            mode='payment',
            line_items=[{
                'price_data': {
                    'currency': currency,
                    'unit_amount': amount_cents,
                    'product_data': {
                        'name': fee.description or f'Quota società #{fee.id}',
                    },
                },
                'quantity': 1,
            }],
            success_url=f'{base}{url_for("payments.success")}?session_id={{CHECKOUT_SESSION_ID}}&fp_id={fp.id}',
            cancel_url=f'{base}{url_for("payments.cancel")}?fee_id={fee.id}',
            metadata={
                'fee_id': str(fee.id),
                'fee_payment_id': str(fp.id),
                'user_id': str(current_user.id),
            },
        )
        return redirect(sess.url, code=303)
    except Exception as exc:
        flash(f'Errore Stripe: {exc}', 'danger')
        return redirect(url_for('payments.pay', fee_id=fee_id))


@bp.route('/success')
@login_required
def success():
    fp_id = request.args.get('fp_id', type=int)
    session_id = request.args.get('session_id', '')
    fp = None
    if fp_id:
        fp = FeePayment.query.get(fp_id)
        if fp and fp.user_id == current_user.id and fp.status == 'pending':
            fp.status = 'completed'
            fp.paid_at = datetime.utcnow()
            fp.stripe_payment_id = session_id
            db.session.add(fp)
            if fp.fee:
                fp.fee.status = 'paid'
                fp.fee.paid_at = datetime.utcnow()
                db.session.add(fp.fee)
            db.session.commit()
    return render_template('payments/success.html', payment=fp)


@bp.route('/cancel')
@login_required
def cancel():
    fee_id = request.args.get('fee_id', type=int)
    return render_template('payments/cancel.html', fee_id=fee_id)


@bp.route('/webhook', methods=['POST'])
@csrf.exempt
def webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    wh_secret = os.environ.get('STRIPE_WEBHOOK_SECRET') or current_app.config.get('STRIPE_WEBHOOK_SECRET')

    if wh_secret and sig_header:
        try:
            event = stripe.Webhook.construct_event(payload=payload, sig_header=sig_header, secret=wh_secret)
        except Exception:
            return ('bad signature', 400)
    else:
        try:
            event = json.loads(payload.decode('utf-8'))
        except Exception:
            return ('bad payload', 400)

    if event.get('type') == 'checkout.session.completed':
        session_obj = event['data']['object']
        meta = session_obj.get('metadata', {})
        fp_id = meta.get('fee_payment_id')
        fee_id = meta.get('fee_id')
        if fp_id:
            fp = FeePayment.query.get(int(fp_id))
            if fp and fp.status == 'pending':
                fp.status = 'completed'
                fp.paid_at = datetime.utcnow()
                fp.stripe_payment_id = session_obj.get('payment_intent') or session_obj.get('id')
                db.session.add(fp)
                if fp.fee and fp.fee.status != 'paid':
                    fp.fee.status = 'paid'
                    fp.fee.paid_at = datetime.utcnow()
                    db.session.add(fp.fee)
                db.session.commit()

    return ('ok', 200)


@bp.route('/receipt/<int:payment_id>')
@login_required
def receipt(payment_id):
    fp = FeePayment.query.get_or_404(payment_id)
    if fp.user_id != current_user.id and not current_user.is_admin():
        flash('Accesso negato.', 'danger')
        return redirect(url_for('payments.index'))
    fee = fp.fee
    amount_eur = fp.amount
    return render_template('payments/receipt.html', payment=fp, fee=fee, amount_eur=amount_eur)


@bp.route('/admin')
@login_required
@admin_required
def admin():
    status_filter = request.args.get('status', '').strip()
    user_filter = request.args.get('user', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    q = FeePayment.query
    if status_filter in ALLOWED_STATUSES:
        q = q.filter_by(status=status_filter)
    if user_filter:
        q = q.join(User, FeePayment.user_id == User.id).filter(
            (User.username.ilike(f'%{user_filter}%')) | (User.first_name.ilike(f'%{user_filter}%')) | (User.last_name.ilike(f'%{user_filter}%'))
        )
    if date_from:
        try:
            q = q.filter(FeePayment.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        try:
            q = q.filter(FeePayment.created_at <= datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
        except ValueError:
            pass

    payments = q.order_by(FeePayment.created_at.desc()).all()

    from sqlalchemy import func
    total_received = db.session.query(func.coalesce(func.sum(FeePayment.amount), 0)).filter_by(status='completed').scalar()
    total_pending = db.session.query(func.coalesce(func.sum(FeePayment.amount), 0)).filter_by(status='pending').scalar()
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month = db.session.query(func.coalesce(func.sum(FeePayment.amount), 0)).filter(
        FeePayment.status == 'completed', FeePayment.paid_at >= month_start
    ).scalar()

    pending_fees = SocietyFee.query.filter_by(status='pending').order_by(SocietyFee.due_on.desc()).limit(50).all()

    return render_template('payments/admin.html',
                           payments=payments,
                           total_received=total_received,
                           total_pending=total_pending,
                           this_month=this_month,
                           status_filter=status_filter,
                           user_filter=user_filter,
                           date_from=date_from,
                           date_to=date_to,
                           pending_fees=pending_fees)


@bp.route('/manual/<int:fee_id>', methods=['POST'])
@login_required
@admin_required
def manual_payment(fee_id):
    fee = SocietyFee.query.get_or_404(fee_id)
    if fee.status == 'paid':
        flash('Questa quota è già stata pagata.', 'info')
        return redirect(url_for('payments.admin'))

    method = request.form.get('payment_method', 'contanti')
    notes = request.form.get('notes', '')

    fp = FeePayment(
        fee_id=fee.id,
        user_id=fee.user_id,
        amount=round(float(fee.amount_cents or 0) / 100.0, 2),
        payment_method=method,
        status='completed',
        paid_at=datetime.utcnow(),
        notes=notes,
    )
    db.session.add(fp)

    fee.status = 'paid'
    fee.paid_at = datetime.utcnow()
    db.session.add(fee)
    db.session.commit()

    log_action('manual_payment', 'FeePayment', fp.id, f'Pagamento manuale registrato per quota #{fee.id}')
    flash('Pagamento manuale registrato con successo.', 'success')
    return redirect(url_for('payments.admin'))
