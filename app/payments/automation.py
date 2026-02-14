"""
Automated Payment Features
Handles payment reminders, automated invoices, and subscription management
Modern social-like payment automation with super admin controls
"""
from datetime import datetime, timezone, timedelta
from app import db
from app.models import User, FeePayment, SocietyFee
from app.notifications.utils import create_notification
import logging

logger = logging.getLogger(__name__)

# Auto-approval threshold in euros (configurable by super admin)
AUTO_APPROVE_THRESHOLD = 50.0


def send_payment_reminders():
    """
    Automated task to send payment reminders for unpaid fees
    Should be run daily via cron or celery beat
    """
    try:
        # Find fees that are:
        # 1. Status = pending
        # 2. Due within next 7 days or overdue
        # 3. Haven't been reminded in last 24 hours
        
        now = datetime.now(timezone.utc)
        remind_threshold = now + timedelta(days=7)
        
        pending_fees = SocietyFee.query.filter(
            SocietyFee.status == 'pending',
            SocietyFee.due_on <= remind_threshold
        ).all()
        
        reminded_count = 0
        for fee in pending_fees:
            # Check if already reminded recently
            last_reminder = getattr(fee, 'last_reminder_at', None)
            if last_reminder and (now - last_reminder).days < 1:
                continue
            
            # Calculate days until/past due
            days_diff = (fee.due_on - now.date()).days
            
            if days_diff < 0:
                message = f"Il pagamento di {fee.amount_cents/100:.2f}€ per {fee.description} è scaduto da {abs(days_diff)} giorni."
            elif days_diff == 0:
                message = f"Il pagamento di {fee.amount_cents/100:.2f}€ per {fee.description} è dovuto oggi!"
            else:
                message = f"Promemoria: il pagamento di {fee.amount_cents/100:.2f}€ per {fee.description} è dovuto tra {days_diff} giorni."
            
            # Create notification
            create_notification(
                user_id=fee.user_id,
                notification_type='payment_reminder',
                title='Promemoria Pagamento',
                message=message,
                link=f'/payments/fee/{fee.id}/pay'
            )
            
            # Mark as reminded (if field exists)
            if hasattr(fee, 'last_reminder_at'):
                fee.last_reminder_at = now
                db.session.add(fee)
            
            reminded_count += 1
        
        if reminded_count > 0:
            db.session.commit()
            logger.info(f"Sent {reminded_count} payment reminders")
        
        return reminded_count
        
    except Exception as e:
        logger.error(f"Error sending payment reminders: {e}")
        db.session.rollback()
        return 0


def generate_payment_invoices():
    """
    Automated task to generate invoices for completed payments
    Should be run hourly via cron or celery beat
    """
    try:
        # Find completed payments without invoice
        payments = FeePayment.query.filter(
            FeePayment.status == 'completed',
            FeePayment.invoice_generated.is_(False)
        ).all()
        
        generated_count = 0
        for payment in payments:
            # Generate invoice number
            invoice_number = f"INV-{payment.id}-{datetime.now().year}"
            
            # Mark as invoice generated
            payment.invoice_generated = True
            payment.invoice_number = invoice_number
            payment.invoice_generated_at = datetime.now(timezone.utc)
            db.session.add(payment)
            
            # Notify user
            create_notification(
                user_id=payment.user_id,
                notification_type='invoice_generated',
                title='Fattura Generata',
                message=f'La tua fattura {invoice_number} è pronta.',
                link=f'/payments/receipt/{payment.id}'
            )
            
            generated_count += 1
        
        if generated_count > 0:
            db.session.commit()
            logger.info(f"Generated {generated_count} invoices")
        
        return generated_count
        
    except Exception as e:
        logger.error(f"Error generating invoices: {e}")
        db.session.rollback()
        return 0


def process_subscription_renewals():
    """
    Automated task to handle subscription renewals
    Should be run daily via cron or celery beat
    """
    try:
        from app.models import Subscription
        
        now = datetime.now(timezone.utc)
        renewal_threshold = now + timedelta(days=3)  # Notify 3 days before expiry
        
        # Find subscriptions expiring soon
        expiring_subs = Subscription.query.filter(
            Subscription.is_active.is_(True),
            Subscription.expires_at <= renewal_threshold,
            Subscription.expires_at > now
        ).all()
        
        notified_count = 0
        for sub in expiring_subs:
            days_left = (sub.expires_at - now).days
            
            # Check if already notified recently
            last_notification = getattr(sub, 'last_renewal_notification', None)
            if last_notification and (now - last_notification).days < 1:
                continue
            
            message = f"Il tuo abbonamento {sub.plan_name} scade tra {days_left} giorni. Rinnova ora per continuare ad usufruire dei servizi."
            
            create_notification(
                user_id=sub.user_id,
                notification_type='subscription_renewal',
                title='Rinnovo Abbonamento',
                message=message,
                link='/subscription'
            )
            
            if hasattr(sub, 'last_renewal_notification'):
                sub.last_renewal_notification = now
                db.session.add(sub)
            
            notified_count += 1
        
        # Deactivate expired subscriptions
        expired_subs = Subscription.query.filter(
            Subscription.is_active.is_(True),
            Subscription.expires_at <= now
        ).all()
        
        deactivated_count = 0
        for sub in expired_subs:
            sub.is_active = False
            db.session.add(sub)
            
            create_notification(
                user_id=sub.user_id,
                notification_type='subscription_expired',
                title='Abbonamento Scaduto',
                message=f'Il tuo abbonamento {sub.plan_name} è scaduto. Rinnova per continuare.',
                link='/subscription'
            )
            
            deactivated_count += 1
        
        if notified_count > 0 or deactivated_count > 0:
            db.session.commit()
            logger.info(f"Processed subscriptions: {notified_count} notified, {deactivated_count} deactivated")
        
        return {'notified': notified_count, 'deactivated': deactivated_count}
        
    except Exception as e:
        logger.error(f"Error processing subscription renewals: {e}")
        db.session.rollback()
        return {'notified': 0, 'deactivated': 0}


def calculate_payment_analytics():
    """
    Calculate and cache payment analytics
    Should be run daily via cron or celery beat
    """
    try:
        from sqlalchemy import func
        
        now = datetime.now(timezone.utc)
        
        # Today's revenue
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_revenue = db.session.query(
            func.coalesce(func.sum(FeePayment.amount), 0)
        ).filter(
            FeePayment.status == 'completed',
            FeePayment.paid_at >= today_start
        ).scalar()
        
        # This month's revenue
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_revenue = db.session.query(
            func.coalesce(func.sum(FeePayment.amount), 0)
        ).filter(
            FeePayment.status == 'completed',
            FeePayment.paid_at >= month_start
        ).scalar()
        
        # Total revenue
        total_revenue = db.session.query(
            func.coalesce(func.sum(FeePayment.amount), 0)
        ).filter(
            FeePayment.status == 'completed'
        ).scalar()
        
        # Pending amount
        pending_amount = db.session.query(
            func.coalesce(func.sum(FeePayment.amount), 0)
        ).filter(
            FeePayment.status == 'pending'
        ).scalar()
        
        analytics = {
            'today_revenue': float(today_revenue or 0),
            'month_revenue': float(month_revenue or 0),
            'total_revenue': float(total_revenue or 0),
            'pending_amount': float(pending_amount or 0),
            'updated_at': now.isoformat()
        }
        
        logger.info(f"Payment analytics calculated: {analytics}")
        return analytics
        
    except Exception as e:
        logger.error(f"Error calculating payment analytics: {e}")
        return None


def auto_approve_small_payments():
    """
    Automatically approve small payments (modern social network feature)
    Payments under threshold are auto-approved and marked as manual
    Should be run every few minutes via cron or celery beat
    """
    try:
        # Find pending manual payments under threshold
        pending_payments = FeePayment.query.filter(
            FeePayment.status == 'pending',
            FeePayment.payment_method.in_(['contanti', 'bonifico', 'manual']),
            FeePayment.amount <= AUTO_APPROVE_THRESHOLD
        ).all()
        
        approved_count = 0
        for payment in pending_payments:
            # Auto-approve
            payment.status = 'completed'
            payment.paid_at = datetime.now(timezone.utc)
            payment.notes = (payment.notes or '') + '\n[AUTO] Approvato automaticamente (importo minore di €{:.2f})'.format(AUTO_APPROVE_THRESHOLD)
            db.session.add(payment)
            
            # Update fee status
            if payment.fee and payment.fee.status != 'paid':
                payment.fee.status = 'paid'
                payment.fee.paid_at = datetime.now(timezone.utc)
                db.session.add(payment.fee)
            
            # Notify user with social-like notification
            create_notification(
                user_id=payment.user_id,
                notification_type='payment_approved',
                title='✅ Pagamento Approvato',
                message=f'Il tuo pagamento di €{payment.amount:.2f} è stato approvato automaticamente!',
                link=f'/payments/receipt/{payment.id}'
            )
            
            approved_count += 1
        
        if approved_count > 0:
            db.session.commit()
            logger.info(f"Auto-approved {approved_count} small payments")
        
        return approved_count
        
    except Exception as e:
        logger.error(f"Error auto-approving small payments: {e}")
        db.session.rollback()
        return 0


def send_social_payment_notifications():
    """
    Send modern social-style payment notifications
    Creates engaging, user-friendly notifications for payment events
    """
    try:
        from sqlalchemy import func
        
        now = datetime.now(timezone.utc)
        notifications_sent = 0
        
        # Find recently completed payments (last hour) without notification
        recent_payments = FeePayment.query.filter(
            FeePayment.status == 'completed',
            FeePayment.paid_at >= now - timedelta(hours=1),
            FeePayment.paid_at <= now
        ).all()
        
        for payment in recent_payments:
            # Skip if already notified (check notes)
            if payment.notes and '[NOTIFIED]' in payment.notes:
                continue
            
            # Send social-style congratulations notification
            emojis = ['🎉', '👍', '✅', '💰', '🌟']
            emoji = emojis[payment.id % len(emojis)]
            
            create_notification(
                user_id=payment.user_id,
                notification_type='payment_completed',
                title=f'{emoji} Pagamento Completato!',
                message=f'Grazie! Il tuo pagamento di €{payment.amount:.2f} è stato ricevuto con successo.',
                link=f'/payments/receipt/{payment.id}'
            )
            
            # Mark as notified
            payment.notes = (payment.notes or '') + '\n[NOTIFIED]'
            db.session.add(payment)
            notifications_sent += 1
        
        if notifications_sent > 0:
            db.session.commit()
            logger.info(f"Sent {notifications_sent} social payment notifications")
        
        return notifications_sent
        
    except Exception as e:
        logger.error(f"Error sending social payment notifications: {e}")
        db.session.rollback()
        return 0


def quick_payment_summary_for_admin():
    """
    Generate quick payment summary for super admin dashboard
    Returns recent activity in social-feed style
    """
    try:
        from sqlalchemy import func, desc
        
        now = datetime.now(timezone.utc)
        
        # Get last 24 hours activity
        day_start = now - timedelta(hours=24)
        
        recent_payments = FeePayment.query.filter(
            FeePayment.created_at >= day_start
        ).order_by(desc(FeePayment.created_at)).limit(10).all()
        
        # Count by status
        status_counts = db.session.query(
            FeePayment.status,
            func.count(FeePayment.id)
        ).filter(
            FeePayment.created_at >= day_start
        ).group_by(FeePayment.status).all()
        
        # Total amounts
        total_completed_today = db.session.query(
            func.coalesce(func.sum(FeePayment.amount), 0)
        ).filter(
            FeePayment.status == 'completed',
            FeePayment.paid_at >= day_start
        ).scalar()
        
        total_pending_today = db.session.query(
            func.coalesce(func.sum(FeePayment.amount), 0)
        ).filter(
            FeePayment.status == 'pending',
            FeePayment.created_at >= day_start
        ).scalar()
        
        summary = {
            'recent_payments': [
                {
                    'id': p.id,
                    'user': p.user.get_full_name() if p.user else 'Unknown',
                    'amount': float(p.amount),
                    'status': p.status,
                    'created_at': p.created_at.strftime('%H:%M'),
                    'description': p.fee.description if p.fee else f'Payment #{p.id}'
                }
                for p in recent_payments
            ],
            'status_counts': {status: count for status, count in status_counts},
            'total_completed_today': float(total_completed_today or 0),
            'total_pending_today': float(total_pending_today or 0),
            'updated_at': now.isoformat()
        }
        
        return summary
        
    except Exception as e:
        logger.error(f"Error generating admin payment summary: {e}")
        return None

