"""
Celery background tasks for SONACIP
"""
from celery_app import celery
from app import db, mail
from app.models import User, Notification, AutomationRun, AutomationRule
from app.notifications.utils import send_email as sync_send_email
from flask import current_app
from flask_mail import Message
from datetime import datetime, timezone, timedelta
import json
import requests
import traceback


@celery.task(name='app.tasks.send_email_async', bind=True, max_retries=3)
def send_email_async(self, recipient, subject, body, html_body=None):
    """
    Send email asynchronously with retry logic
    """
    try:
        success = sync_send_email(recipient, subject, body, html_body)
        if not success:
            raise Exception("Email sending failed")
        return {'status': 'sent', 'recipient': recipient}
    except Exception as exc:
        # Retry with exponential backoff: 60s, 120s, 240s
        retry_delay = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=retry_delay)


@celery.task(name='app.tasks.send_sms_async', bind=True, max_retries=3)
def send_sms_async(self, phone_number, message):
    """
    Send SMS asynchronously via Twilio
    """
    try:
        from app.notifications.sms import send_sms_twilio
        success = send_sms_twilio(phone_number, message)
        if not success:
            raise Exception("SMS sending failed")
        return {'status': 'sent', 'phone': phone_number}
    except Exception as exc:
        retry_delay = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=retry_delay)


@celery.task(name='app.tasks.send_confirmation_email_async', bind=True, max_retries=3)
def send_confirmation_email_async(self, user_id):
    """
    Send email confirmation asynchronously to avoid blocking registration
    
    This task is critical for preventing 502 Bad Gateway errors during registration.
    By sending confirmation emails in the background, the registration endpoint
    can respond immediately without waiting for SMTP operations.
    """
    try:
        from app.models import User
        from app.auth.email_confirm import send_confirmation_email
        
        user = User.query.get(user_id)
        if not user:
            raise Exception(f"User {user_id} not found")
        
        # Skip if already confirmed
        if user.email_confirmed:
            return {'status': 'already_confirmed', 'user_id': user_id}
        
        success = send_confirmation_email(user)
        if not success:
            raise Exception("Email sending failed")
        
        return {'status': 'sent', 'user_id': user_id, 'email': user.email}
    except Exception as exc:
        # Retry with exponential backoff: 60s, 120s, 240s
        retry_delay = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=retry_delay)


@celery.task(name='app.tasks.process_webhook_async', bind=True, max_retries=3)
def process_webhook_async(self, url, payload, headers=None):
    """
    Process webhook with retry logic and SSRF protection
    """
    try:
        from app.automation.utils import is_url_safe
        
        # SSRF protection
        if not is_url_safe(url):
            raise ValueError(f"URL not allowed: {url}")
        
        headers = headers or {}
        headers.setdefault('Content-Type', 'application/json')
        headers.setdefault('User-Agent', 'SONACIP-Webhook/1.0')
        
        response = requests.post(
            url, 
            json=payload, 
            headers=headers,
            timeout=10,
            allow_redirects=False
        )
        response.raise_for_status()
        
        return {
            'status': 'success',
            'status_code': response.status_code,
            'response': response.text[:500]
        }
    except Exception as exc:
        retry_delay = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=retry_delay)


@celery.task(name='app.tasks.bulk_notify_users')
def bulk_notify_users(user_ids, title, message, notification_type='system', link=None):
    """
    Send notifications to multiple users in bulk
    """
    success_count = 0
    error_count = 0
    
    for user_id in user_ids:
        try:
            notification = Notification(
                user_id=user_id,
                title=title,
                message=message,
                notification_type=notification_type,
                link=link
            )
            db.session.add(notification)
            success_count += 1
        except Exception as e:
            error_count += 1
            current_app.logger.error(f"Failed to notify user {user_id}: {e}")
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to commit bulk notifications: {e}")
        raise
    
    return {
        'success': success_count,
        'errors': error_count,
        'total': len(user_ids)
    }


@celery.task(name='app.tasks.bulk_email_users', bind=True)
def bulk_email_users(self, recipients, subject, body, html_body=None):
    """
    Send emails to multiple recipients with batch processing
    """
    results = []
    batch_size = 50  # Process in batches to avoid overwhelming SMTP server
    
    for i in range(0, len(recipients), batch_size):
        batch = recipients[i:i+batch_size]
        for recipient in batch:
            try:
                send_email_async.delay(recipient, subject, body, html_body)
                results.append({'recipient': recipient, 'status': 'queued'})
            except Exception as e:
                results.append({'recipient': recipient, 'status': 'failed', 'error': str(e)})
        
        # Small delay between batches
        if i + batch_size < len(recipients):
            import time
            time.sleep(1)
    
    return {
        'total': len(recipients),
        'queued': len([r for r in results if r['status'] == 'queued']),
        'failed': len([r for r in results if r['status'] == 'failed'])
    }


@celery.task(name='app.tasks.retry_failed_automations')
def retry_failed_automations():
    """
    Retry failed automation runs that are eligible for retry
    """
    from datetime import datetime, timezone
    
    # Find automation runs that need retry
    runs_to_retry = AutomationRun.query.filter(
        AutomationRun.status == 'retrying',
        AutomationRun.next_retry_at <= datetime.now(timezone.utc)
    ).all()
    
    retry_count = 0
    for run in runs_to_retry:
        try:
            rule = run.rule
            if not rule or not rule.is_active:
                run.status = 'failed'
                run.error_message = 'Rule not found or inactive'
                run.completed_at = datetime.now(timezone.utc)
                db.session.add(run)
                continue
            
            payload = json.loads(run.payload) if run.payload else {}
            actions = json.loads(rule.actions) if rule.actions else []
            
            from app.automation.utils import _apply_actions
            _apply_actions(actions, payload)
            
            run.status = 'success'
            run.completed_at = datetime.now(timezone.utc)
            db.session.add(run)
            retry_count += 1
            
        except Exception as e:
            run.retry_count += 1
            if run.retry_count >= rule.max_retries:
                run.status = 'failed'
                run.error_message = f"Max retries exceeded: {str(e)}"
                run.completed_at = datetime.now(timezone.utc)
            else:
                run.status = 'retrying'
                run.error_message = str(e)
                retry_delay = rule.retry_delay * (2 ** run.retry_count)
                run.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
            db.session.add(run)
    
    db.session.commit()
    return {'retried': retry_count, 'total': len(runs_to_retry)}


@celery.task(name='app.tasks.cleanup_old_data')
def cleanup_old_data():
    """
    Clean up old notifications, logs, and expired sessions
    """
    from app.notifications.utils import cleanup_old_notifications
    from datetime import datetime, timedelta, timezone
    
    results = {}
    
    # Clean up old notifications (90 days)
    results['notifications_cleaned'] = cleanup_old_notifications(days=90)
    
    # Clean up old automation runs (180 days)
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=180)
    deleted_runs = AutomationRun.query.filter(
        AutomationRun.created_at < cutoff_date,
        AutomationRun.status.in_(['success', 'failed'])
    ).delete()
    results['automation_runs_cleaned'] = deleted_runs
    
    db.session.commit()
    return results


@celery.task(name='app.tasks.generate_analytics_report')
def generate_analytics_report(user_id, report_type, params=None):
    """
    Generate analytics reports asynchronously
    """
    try:
        params = params or {}
        # This would integrate with the analytics module
        # For now, return a placeholder
        return {
            'status': 'completed',
            'user_id': user_id,
            'report_type': report_type,
            'generated_at': datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        current_app.logger.error(f"Report generation failed: {e}")
        raise


@celery.task(name='app.tasks.export_data_async')
def export_data_async(user_id, export_type, format='csv', filters=None):
    """
    Export data asynchronously (CSV, Excel, PDF)
    """
    try:
        # This would integrate with export functionality
        return {
            'status': 'completed',
            'user_id': user_id,
            'export_type': export_type,
            'format': format,
            'exported_at': datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        current_app.logger.error(f"Data export failed: {e}")
        raise


# Periodic tasks configuration
@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    Setup periodic tasks using Celery Beat
    """
    # Retry failed automations every 5 minutes
    sender.add_periodic_task(
        300.0,  # 5 minutes
        retry_failed_automations.s(),
        name='retry-failed-automations'
    )
    
    # Clean up old data daily at 3 AM
    from celery.schedules import crontab
    sender.add_periodic_task(
        crontab(hour=3, minute=0),
        cleanup_old_data.s(),
        name='cleanup-old-data-daily'
    )
