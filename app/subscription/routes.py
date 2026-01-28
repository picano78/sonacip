"""
Subscription routes
Plans, subscriptions, and payment management
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Plan, Subscription, Payment, User
from app.utils import admin_required, log_action, check_permission
from datetime import datetime, timedelta

bp = Blueprint('subscription', __name__)


@bp.route('/plans')
def plans():
    """Display available subscription plans"""
    active_plans = Plan.query.filter_by(is_active=True).order_by(Plan.display_order).all()
    
    current_subscription = None
    if current_user.is_authenticated:
        current_subscription = current_user.get_active_subscription()
    
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
        start_date=datetime.utcnow(),
        amount=amount,
        auto_renew=True
    )
    
    # Calculate next billing date
    if billing_cycle == 'monthly':
        subscription.next_billing_date = datetime.utcnow() + timedelta(days=30)
    else:
        subscription.next_billing_date = datetime.utcnow() + timedelta(days=365)
    
    db.session.add(subscription)
    db.session.commit()
    
    # Log action
    log_action('subscribe', 'Subscription', subscription.id, 
              f'Subscribed to {plan.name} - {billing_cycle}')
    
    if amount == 0:
        flash(f'Sottoscrizione a {plan.name} completata!', 'success')
        return redirect(url_for('subscription.my_subscription'))
    else:
        flash(f'Procedi con il pagamento per attivare {plan.name}.', 'info')
        return redirect(url_for('subscription.payment', subscription_id=subscription.id))


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
    subscription.cancelled_at = datetime.utcnow()
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
    
    # Create payment record
    payment = Payment(
        user_id=current_user.id,
        society_id=society.id if society else None,
        subscription_id=subscription.id,
        amount=subscription.amount,
        currency='EUR',
        status='completed',  # Would be 'pending' in real implementation
        payment_method=payment_method,
        payment_date=datetime.utcnow(),
        description=f'Payment for {subscription.plan.name} subscription',
        transaction_id=f'TEST_{datetime.utcnow().timestamp()}'  # Would come from gateway
    )
    
    db.session.add(payment)
    
    # Activate subscription
    subscription.status = 'active'
    subscription.start_date = datetime.utcnow()
    
    db.session.commit()
    
    # Log action
    log_action('payment_completed', 'Payment', payment.id, 
              f'Payment of {payment.amount} EUR completed')
    
    flash('Pagamento completato! La tua sottoscrizione è ora attiva.', 'success')
    return redirect(url_for('subscription.my_subscription'))


# ==============================
# ADMIN ROUTES
# ==============================

@bp.route('/admin/plans')
@login_required
@admin_required
def admin_plans():
    """Admin: Manage subscription plans"""
    plans = Plan.query.order_by(Plan.display_order).all()
    return render_template('subscription/admin_plans.html', plans=plans)


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
    payment.notes = f'Refunded: {reason}'
    payment.updated_at = datetime.utcnow()
    
    # Cancel associated subscription if active
    if payment.subscription and payment.subscription.status == 'active':
        payment.subscription.status = 'cancelled'
        payment.subscription.cancelled_at = datetime.utcnow()
    
    db.session.commit()
    
    log_action('refund_payment', 'Payment', payment.id, f'Refunded payment: {reason}')
    flash('Pagamento rimborsato con successo.', 'success')
    
    return redirect(url_for('subscription.admin_payments'))
