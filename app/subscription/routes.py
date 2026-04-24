"""
Subscription routes
Plans, subscriptions, and payment management
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import AddOn, AddOnEntitlement, Plan, Subscription, Payment, User, Coupon, CouponRedemption
from app.utils import admin_required, log_action, check_permission
from datetime import datetime, timedelta, timezone
import json
import stripe

from app.subscription.stripe_utils import (
    stripe_enabled,
    create_checkout_session,
    create_addon_checkout_session,
    create_billing_portal_session,
    handle_stripe_event,
)

bp = Blueprint('subscription', __name__, url_prefix='/subscription')

def _apply_coupon(plan: Plan, amount: float, coupon_code: str | None) -> tuple[float, Coupon | None, float]:
    """Return (final_amount, coupon, discount_amount)."""
    if not coupon_code:
        return amount, None, 0.0
    code = coupon_code.strip().upper()
    if not code:
        return amount, None, 0.0

    c = Coupon.query.filter_by(code=code, is_active=True).first()
    if not c:
        raise ValueError("Coupon non valido.")
    now = datetime.now(timezone.utc)
    if c.valid_from and now < c.valid_from:
        raise ValueError("Coupon non ancora valido.")
    if c.valid_until and now > c.valid_until:
        raise ValueError("Coupon scaduto.")
    if c.plan_id and c.plan_id != plan.id:
        raise ValueError("Coupon non applicabile a questo piano.")
    if c.max_redemptions is not None and (c.redeemed_count or 0) >= c.max_redemptions:
        raise ValueError("Coupon esaurito.")

    discount = 0.0
    if c.discount_type == 'percent':
        pct = max(0, min(int(c.discount_value or 0), 100))
        discount = round((amount * pct) / 100.0, 2)
    else:
        discount = round(((c.discount_value or 0) / 100.0), 2)

    final_amount = max(0.0, round(amount - discount, 2))
    return final_amount, c, discount


@bp.route('/plans')
def plans():
    """Display available subscription plans"""
    try:
        active_plans = Plan.query.filter_by(is_active=True).order_by(Plan.display_order).all()
    except Exception:
        active_plans = []
    
    current_subscription = None
    if current_user.is_authenticated:
        try:
            current_subscription = current_user.get_active_subscription()
        except Exception:
            current_subscription = None
    
    return render_template('subscription/plans.html', 
                         plans=active_plans,
                         current_subscription=current_subscription)


@bp.route('/subscribe/<int:plan_id>', methods=['POST'])
@login_required
def subscribe(plan_id):
    """Subscribe to a plan"""
    plan = Plan.query.get_or_404(plan_id)
    
    if not plan.is_active:
        flash('Questo piano non è attualmente disponibile.', 'warning')
        return redirect(url_for('subscription.plans'))
    
    # Check if user already has an active subscription
    existing = current_user.get_active_subscription()
    if existing:
        flash('Hai già una sottoscrizione attiva. Annullala prima di sottoscriverne un\'altra.', 'warning')
        return redirect(url_for('subscription.my_subscription'))
    
    # Get billing cycle
    billing_cycle = request.form.get('billing_cycle', 'monthly')
    if billing_cycle not in ['monthly', 'yearly']:
        billing_cycle = 'monthly'
    
    # Calculate amount
    amount = plan.price_monthly if billing_cycle == 'monthly' else plan.price_yearly
    
    # Create subscription
    society = current_user.get_primary_society()
    subscription = Subscription(
        user_id=None if society else current_user.id,
        society_id=society.id if society else None,
        plan_id=plan.id,
        status='active' if amount == 0 else 'pending',  # Free plans are immediately active
        billing_cycle=billing_cycle,
        start_date=datetime.now(timezone.utc),
        amount=amount,
        auto_renew=True
    )
    
    # Calculate next billing date
    if billing_cycle == 'monthly':
        subscription.next_billing_date = datetime.now(timezone.utc) + timedelta(days=30)
    else:
        subscription.next_billing_date = datetime.now(timezone.utc) + timedelta(days=365)
    
    db.session.add(subscription)
    db.session.commit()
    
    # Log action
    log_action('subscribe', 'Subscription', subscription.id, 
              f'Subscribed to {plan.name} - {billing_cycle}')
    
    if amount == 0:
        flash(f'Sottoscrizione a {plan.name} completata!', 'success')
        return redirect(url_for('subscription.my_subscription'))
    else:
        # Stripe-first (real billing) when configured
        if stripe_enabled():
            try:
                success_url = url_for('subscription.stripe_success', subscription_id=subscription.id, _external=True)
                cancel_url = url_for('subscription.payment', subscription_id=subscription.id, _external=True)
                checkout_url = create_checkout_session(subscription, plan, billing_cycle, success_url, cancel_url)
                return redirect(checkout_url)
            except Exception as exc:
                flash(f'Stripe non disponibile per questo piano: {exc}', 'warning')
        flash(f'Procedi con il pagamento per attivare {plan.name}.', 'info')
        return redirect(url_for('subscription.payment', subscription_id=subscription.id))


@bp.route('/stripe/success/<int:subscription_id>')
@login_required
def stripe_success(subscription_id):
    """Return page after Stripe checkout (webhook will finalize)."""
    subscription = Subscription.query.get_or_404(subscription_id)
    flash('Pagamento completato (in verifica). Se non vedi l’attivazione immediata, aggiorna tra pochi secondi.', 'success')
    return redirect(url_for('subscription.my_subscription'))


@bp.route('/stripe/portal', methods=['POST'])
@login_required
def stripe_portal():
    """Open Stripe customer portal for current subscription."""
    subscription = current_user.get_active_subscription()
    if not subscription or not subscription.stripe_customer_id:
        flash('Portale Stripe non disponibile per questa sottoscrizione.', 'warning')
        return redirect(url_for('subscription.my_subscription'))
    # Only society owners should manage society billing
    if subscription.society_id and (not current_user.is_society()) and (not check_permission(current_user, 'admin', 'access')):
        flash('Solo la società può gestire la fatturazione.', 'danger')
        return redirect(url_for('subscription.my_subscription'))
    if not stripe_enabled():
        flash('Stripe non configurato.', 'warning')
        return redirect(url_for('subscription.my_subscription'))
    try:
        return_url = (
            current_app.config.get("STRIPE_PORTAL_RETURN_URL")
            or url_for('subscription.my_subscription', _external=True)
        )
        portal_url = create_billing_portal_session(subscription.stripe_customer_id, return_url=return_url)
        return redirect(portal_url)
    except Exception as exc:
        flash(f'Errore Stripe portal: {exc}', 'danger')
        return redirect(url_for('subscription.my_subscription'))


@bp.route('/stripe/webhook', methods=['POST'])
def stripe_webhook():
    """Stripe webhook endpoint (no auth)."""
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    wh_secret = current_app.config.get("STRIPE_WEBHOOK_SECRET")

    if wh_secret and sig_header:
        try:
            event = stripe.Webhook.construct_event(payload=payload, sig_header=sig_header, secret=wh_secret)
        except Exception:
            return ("bad signature", 400)
    else:
        # Dev fallback (NOT recommended in production)
        try:
            event = json.loads(payload.decode("utf-8"))
        except Exception:
            return ("bad payload", 400)

    try:
        handle_stripe_event(event)
    except Exception:
        return ("handler error", 500)
    return ("ok", 200)


@bp.route('/my-subscription')
@login_required
def my_subscription():
    """View current subscription details"""
    subscription = current_user.get_active_subscription()
    society = current_user.get_primary_society()
    if society:
        all_subscriptions = Subscription.query.filter_by(society_id=society.id)\
            .order_by(Subscription.created_at.desc()).all()
        payments = Payment.query.filter_by(society_id=society.id)\
            .order_by(Payment.created_at.desc()).limit(10).all()
    else:
        all_subscriptions = Subscription.query.filter_by(user_id=current_user.id)\
            .order_by(Subscription.created_at.desc()).all()
        payments = Payment.query.filter_by(user_id=current_user.id)\
            .order_by(Payment.created_at.desc()).limit(10).all()
    
    return render_template('subscription/my_subscription.html',
                         subscription=subscription,
                         all_subscriptions=all_subscriptions,
                         payments=payments)


@bp.route('/addons')
@login_required
def addons():
    """List available add-ons and current entitlements."""
    addons = AddOn.query.filter_by(is_active=True).order_by(AddOn.display_order.asc(), AddOn.created_at.desc()).all()
    society = current_user.get_primary_society()
    if society:
        entitlements = AddOnEntitlement.query.filter_by(society_id=society.id, status='active').order_by(AddOnEntitlement.created_at.desc()).all()
    else:
        entitlements = AddOnEntitlement.query.filter_by(user_id=current_user.id, status='active').order_by(AddOnEntitlement.created_at.desc()).all()
    ent_by_feature = {e.feature_key: e for e in entitlements}
    return render_template('subscription/addons.html', addons=addons, entitlements=entitlements, ent_by_feature=ent_by_feature)


@bp.route('/addons/<int:addon_id>/buy', methods=['POST'])
@login_required
def buy_addon(addon_id):
    """Purchase an add-on (Stripe if configured, otherwise local placeholder)."""
    addon = AddOn.query.get_or_404(addon_id)
    if not addon.is_active:
        flash('Add-on non disponibile.', 'warning')
        return redirect(url_for('subscription.addons'))

    society = current_user.get_primary_society()
    scope_society_id = society.id if society else None

    # Already active?
    existing = AddOnEntitlement.query.filter_by(
        feature_key=addon.feature_key,
        status='active',
        society_id=scope_society_id,
        user_id=None if society else current_user.id,
    ).first()
    if existing and (not existing.end_date or existing.end_date > datetime.now(timezone.utc)):
        flash('Add-on già attivo.', 'info')
        return redirect(url_for('subscription.addons'))

    # Stripe checkout (one-time)
    if stripe_enabled() and addon.stripe_price_one_time_id:
        try:
            success_url = url_for('subscription.addons', _external=True) + "?success=1"
            cancel_url = url_for('subscription.addons', _external=True)
            checkout_url = create_addon_checkout_session(
                addon,
                user_id=current_user.id,
                society_id=scope_society_id,
                success_url=success_url,
                cancel_url=cancel_url,
            )
            return redirect(checkout_url)
        except Exception as exc:
            flash(f'Stripe non disponibile per questo add-on: {exc}', 'warning')

    # Local fallback: mark as paid + enable immediately
    payment = Payment(
        user_id=current_user.id,
        society_id=scope_society_id,
        subscription_id=None,
        amount=float(addon.price_one_time or 0),
        currency=(addon.currency or 'EUR'),
        status='completed',
        payment_method='manual',
        payment_date=datetime.now(timezone.utc),
        description=f'Add-on: {addon.name}',
        transaction_id=f'LOCAL_ADDON_{addon.id}_{datetime.now(timezone.utc).timestamp()}',
        gateway='local',
    )
    payment.payment_metadata = json.dumps({"addon_id": addon.id, "feature_key": addon.feature_key})
    db.session.add(payment)
    db.session.flush()
    db.session.add(
        AddOnEntitlement(
            addon_id=addon.id,
            feature_key=addon.feature_key,
            user_id=None if society else current_user.id,
            society_id=scope_society_id,
            payment_id=payment.id,
            status='active',
            source='local',
            start_date=datetime.now(timezone.utc),
        )
    )
    db.session.commit()
    log_action('buy_addon', 'AddOn', addon.id, f'feature={addon.feature_key}')
    flash('Add-on attivato.', 'success')
    return redirect(url_for('subscription.addons'))


@bp.route('/cancel/<int:subscription_id>', methods=['POST'])
@login_required
def cancel_subscription(subscription_id):
    """Cancel a subscription"""
    subscription = Subscription.query.get_or_404(subscription_id)
    
    # Verify ownership
    society = current_user.get_primary_society()
    if not check_permission(current_user, 'admin', 'access'):
        if society and subscription.society_id != society.id:
            flash('Accesso negato.', 'danger')
            return redirect(url_for('subscription.my_subscription'))
        if not society and subscription.user_id != current_user.id:
            flash('Accesso negato.', 'danger')
            return redirect(url_for('subscription.my_subscription'))
    
    if subscription.status not in ['active', 'trial']:
        flash('Questa sottoscrizione non può essere annullata.', 'warning')
        return redirect(url_for('subscription.my_subscription'))
    
    # Cancel subscription
    subscription.status = 'cancelled'
    subscription.cancelled_at = datetime.now(timezone.utc)
    subscription.auto_renew = False
    
    db.session.commit()
    
    # Log action
    log_action('cancel_subscription', 'Subscription', subscription.id)
    
    flash('Sottoscrizione annullata.', 'info')
    return redirect(url_for('subscription.my_subscription'))


@bp.route('/payment/<int:subscription_id>')
@login_required
def payment(subscription_id):
    """Payment page for a subscription"""
    subscription = Subscription.query.get_or_404(subscription_id)
    
    # Verify ownership
    society = current_user.get_primary_society()
    if society and subscription.society_id != society.id:
        flash('Accesso negato.', 'danger')
        return redirect(url_for('subscription.plans'))
    if not society and subscription.user_id != current_user.id:
        flash('Accesso negato.', 'danger')
        return redirect(url_for('subscription.plans'))
    
    return render_template('subscription/payment.html', subscription=subscription)


@bp.route('/payment/<int:subscription_id>/process', methods=['POST'])
@login_required
def process_payment(subscription_id):
    """Process payment (placeholder for payment gateway integration)"""
    subscription = Subscription.query.get_or_404(subscription_id)
    
    # Verify ownership
    society = current_user.get_primary_society()
    if society and subscription.society_id != society.id:
        flash('Accesso negato.', 'danger')
        return redirect(url_for('subscription.plans'))
    if not society and subscription.user_id != current_user.id:
        flash('Accesso negato.', 'danger')
        return redirect(url_for('subscription.plans'))
    
    # This is a placeholder - integrate with real payment gateway (Stripe, PayPal, etc.)
    payment_method = request.form.get('payment_method', 'card')
    coupon_code = request.form.get('coupon_code') or None

    amount_to_pay = float(subscription.amount or 0)
    coupon = None
    discount = 0.0
    if coupon_code:
        try:
            amount_to_pay, coupon, discount = _apply_coupon(subscription.plan, amount_to_pay, coupon_code)
        except ValueError as exc:
            flash(str(exc), 'danger')
            return redirect(url_for('subscription.payment', subscription_id=subscription.id))
    
    # Create payment record
    payment = Payment(
        user_id=current_user.id,
        society_id=society.id if society else None,
        subscription_id=subscription.id,
        amount=amount_to_pay,
        currency='EUR',
        status='completed',  # Would be 'pending' in real implementation
        payment_method=payment_method,
        payment_date=datetime.now(timezone.utc),
        description=f'Payment for {subscription.plan.name} subscription',
        transaction_id=f'TEST_{datetime.now(timezone.utc).timestamp()}'  # Would come from gateway
    )
    payment.payment_metadata = json.dumps({
        "coupon_code": (coupon.code if coupon else None),
        "discount": discount,
        "original_amount": float(subscription.amount or 0),
        "final_amount": amount_to_pay,
    })
    
    db.session.add(payment)
    db.session.flush()

    if coupon:
        coupon.redeemed_count = int(coupon.redeemed_count or 0) + 1
        db.session.add(
            CouponRedemption(
                coupon_id=coupon.id,
                user_id=current_user.id,
                society_id=society.id if society else None,
                subscription_id=subscription.id,
                payment_id=payment.id,
            )
        )
    
    # Activate subscription
    subscription.status = 'active'
    subscription.start_date = datetime.now(timezone.utc)
    
    db.session.commit()
    
    # Log action
    log_action('payment_completed', 'Payment', payment.id, 
              f'Payment of {payment.amount} EUR completed')
    
    flash('Pagamento completato! La tua sottoscrizione è ora attiva.', 'success')
    return redirect(url_for('subscription.my_subscription'))


@bp.route('/admin/coupons', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_coupons():
    """Admin: Manage coupon codes."""
    if request.method == 'POST':
        code = (request.form.get('code') or '').strip().upper()
        discount_type = (request.form.get('discount_type') or 'percent').strip()
        description = (request.form.get('description') or '').strip() or None
        discount_value = int(request.form.get('discount_value') or 0)
        max_redemptions = request.form.get('max_redemptions')
        plan_id = request.form.get('plan_id')
        valid_until = request.form.get('valid_until')

        if not code or len(code) < 4:
            flash('Codice coupon non valido.', 'danger')
            return redirect(url_for('subscription.admin_coupons'))
        if discount_type not in ('percent', 'fixed'):
            discount_type = 'percent'

        existing = Coupon.query.filter_by(code=code).first()
        if existing:
            flash('Codice già esistente.', 'danger')
            return redirect(url_for('subscription.admin_coupons'))

        mr = None
        try:
            mr = int(max_redemptions) if max_redemptions else None
        except Exception:
            mr = None

        pid = None
        try:
            pid = int(plan_id) if plan_id else None
        except Exception:
            pid = None

        vu = None
        try:
            vu = datetime.strptime(valid_until, '%Y-%m-%d') if valid_until else None
        except Exception:
            vu = None

        c = Coupon(
            code=code,
            description=description,
            discount_type=discount_type,
            discount_value=discount_value,
            max_redemptions=mr,
            redeemed_count=0,
            is_active=True,
            valid_from=datetime.now(timezone.utc),
            valid_until=vu,
            plan_id=pid,
            created_by=current_user.id,
        )
        db.session.add(c)
        db.session.commit()
        log_action('create_coupon', 'Coupon', c.id, f'code={code}')
        flash('Coupon creato.', 'success')
        return redirect(url_for('subscription.admin_coupons'))

    coupons = Coupon.query.order_by(Coupon.created_at.desc()).limit(200).all()
    plans = Plan.query.order_by(Plan.display_order).all()
    return render_template('subscription/admin_coupons.html', coupons=coupons, plans=plans)


@bp.route('/admin/coupons/<int:coupon_id>/toggle', methods=['POST'])
@login_required
@admin_required
def admin_coupon_toggle(coupon_id):
    c = Coupon.query.get_or_404(coupon_id)
    c.is_active = not bool(c.is_active)
    db.session.commit()
    log_action('toggle_coupon', 'Coupon', c.id, f'active={c.is_active}')
    flash('Coupon aggiornato.', 'success')
    return redirect(url_for('subscription.admin_coupons'))


# ==============================
# ADMIN ROUTES
# ==============================

@bp.route('/admin/addons', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_addons():
    """Admin: Manage add-ons."""
    if request.method == 'POST':
        slug = (request.form.get('slug') or '').strip().lower()
        name = (request.form.get('name') or '').strip()
        feature_key = (request.form.get('feature_key') or '').strip()
        description = (request.form.get('description') or '').strip() or None
        currency = (request.form.get('currency') or 'EUR').strip().upper()
        stripe_price_one_time_id = (request.form.get('stripe_price_one_time_id') or '').strip() or None
        display_order = int(request.form.get('display_order') or 0)
        try:
            price_one_time = float(request.form.get('price_one_time') or 0)
        except Exception:
            price_one_time = 0.0

        if not slug or len(slug) < 3:
            flash('Slug non valido.', 'danger')
            return redirect(url_for('subscription.admin_addons'))
        if not name:
            flash('Nome richiesto.', 'danger')
            return redirect(url_for('subscription.admin_addons'))
        if not feature_key:
            flash('Feature key richiesta.', 'danger')
            return redirect(url_for('subscription.admin_addons'))

        existing = AddOn.query.filter_by(slug=slug).first()
        if existing:
            flash('Slug già esistente.', 'danger')
            return redirect(url_for('subscription.admin_addons'))

        row = AddOn(
            slug=slug,
            name=name,
            description=description,
            feature_key=feature_key,
            price_one_time=price_one_time,
            currency=currency,
            stripe_price_one_time_id=stripe_price_one_time_id,
            is_active=True,
            display_order=display_order,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(row)
        db.session.commit()
        log_action('create_addon', 'AddOn', row.id, f'feature={feature_key}')
        flash('Add-on creato.', 'success')
        return redirect(url_for('subscription.admin_addons'))

    addons = AddOn.query.order_by(AddOn.display_order.asc(), AddOn.created_at.desc()).limit(300).all()
    return render_template('subscription/admin_addons.html', addons=addons)


@bp.route('/admin/addons/<int:addon_id>/toggle', methods=['POST'])
@login_required
@admin_required
def admin_addon_toggle(addon_id):
    addon = AddOn.query.get_or_404(addon_id)
    addon.is_active = not bool(addon.is_active)
    db.session.commit()
    log_action('toggle_addon', 'AddOn', addon.id, f'active={addon.is_active}')
    flash('Add-on aggiornato.', 'success')
    return redirect(url_for('subscription.admin_addons'))

@bp.route('/admin/plans')
@login_required
@admin_required
def admin_plans():
    """Admin: Manage subscription plans"""
    plans = Plan.query.order_by(Plan.display_order).all()
    return render_template('subscription/admin_plans.html', plans=plans)


@bp.route('/admin/plans/<int:plan_id>/stripe', methods=['POST'])
@login_required
@admin_required
def admin_plan_stripe(plan_id):
    """Admin: update Stripe price ids for a plan."""
    p = Plan.query.get_or_404(plan_id)
    monthly = (request.form.get('stripe_price_monthly_id') or '').strip() or None
    yearly = (request.form.get('stripe_price_yearly_id') or '').strip() or None
    if monthly is not None:
        p.stripe_price_monthly_id = monthly
    if yearly is not None:
        p.stripe_price_yearly_id = yearly
    db.session.commit()
    log_action('plan_stripe_update', 'Plan', p.id, f'monthly={bool(monthly)} yearly={bool(yearly)}')
    flash('Piano aggiornato (Stripe).', 'success')
    return redirect(url_for('subscription.admin_plans'))


@bp.route('/admin/subscriptions')
@login_required
@admin_required
def admin_subscriptions():
    """Admin: View all subscriptions"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    pagination = Subscription.query.order_by(Subscription.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    subscriptions = pagination.items
    
    # Statistics
    stats = {
        'total_subscriptions': Subscription.query.count(),
        'active_subscriptions': Subscription.query.filter_by(status='active').count(),
        'cancelled_subscriptions': Subscription.query.filter_by(status='cancelled').count(),
        'total_revenue': db.session.query(db.func.sum(Payment.amount))\
            .filter_by(status='completed').scalar() or 0
    }
    
    return render_template('subscription/admin_subscriptions.html',
                         subscriptions=subscriptions,
                         pagination=pagination,
                         stats=stats)


@bp.route('/admin/payments')
@login_required
@admin_required
def admin_payments():
    """Admin: View all payments"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    pagination = Payment.query.order_by(Payment.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    payments = pagination.items
    
    return render_template('subscription/admin_payments.html',
                         payments=payments,
                         pagination=pagination)


@bp.route('/admin/payment/<int:payment_id>/refund', methods=['POST'])
@login_required
@admin_required
def refund_payment(payment_id):
    """Process refund for a payment"""
    payment = Payment.query.get_or_404(payment_id)
    
    if payment.status != 'completed':
        flash('Solo pagamenti completati possono essere rimborsati.', 'warning')
        return redirect(url_for('subscription.admin_payments'))
    
    reason = request.form.get('reason', 'Rimborsato dall\'admin')
    
    # Mark payment as refunded
    payment.status = 'refunded'
    try:
        meta = json.loads(payment.payment_metadata or '{}')
    except Exception:
        meta = {}
    meta['refund_reason'] = reason
    meta['refunded_at'] = datetime.now(timezone.utc).isoformat()
    payment.payment_metadata = json.dumps(meta)
    payment.updated_at = datetime.now(timezone.utc)
    
    # Cancel associated subscription if active
    if payment.subscription and payment.subscription.status == 'active':
        payment.subscription.status = 'cancelled'
        payment.subscription.cancelled_at = datetime.now(timezone.utc)
    
    db.session.commit()
    
    log_action('refund_payment', 'Payment', payment.id, f'Refunded payment: {reason}')
    flash('Pagamento rimborsato con successo.', 'success')
    
    return redirect(url_for('subscription.admin_payments'))
