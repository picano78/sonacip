"""
Automation Task Scheduler
Celery tasks for automated operations
"""
from celery import Celery
from celery.schedules import crontab
import os
import logging

logger = logging.getLogger(__name__)

# Initialize Celery
celery = Celery(
    'sonacip',
    broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

# Configure Celery
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/Rome',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
)


@celery.task(name='automation.send_payment_reminders')
def task_send_payment_reminders():
    """Daily task to send payment reminders"""
    try:
        from app.payments.automation import send_payment_reminders
        count = send_payment_reminders()
        logger.info(f"Payment reminders task completed: {count} reminders sent")
        return {'success': True, 'count': count}
    except Exception as e:
        logger.error(f"Payment reminders task failed: {e}")
        return {'success': False, 'error': str(e)}


@celery.task(name='automation.generate_payment_invoices')
def task_generate_payment_invoices():
    """Hourly task to generate payment invoices"""
    try:
        from app.payments.automation import generate_payment_invoices
        count = generate_payment_invoices()
        logger.info(f"Invoice generation task completed: {count} invoices generated")
        return {'success': True, 'count': count}
    except Exception as e:
        logger.error(f"Invoice generation task failed: {e}")
        return {'success': False, 'error': str(e)}


@celery.task(name='automation.process_subscription_renewals')
def task_process_subscription_renewals():
    """Daily task to process subscription renewals"""
    try:
        from app.payments.automation import process_subscription_renewals
        result = process_subscription_renewals()
        logger.info(f"Subscription renewals task completed: {result}")
        return {'success': True, 'result': result}
    except Exception as e:
        logger.error(f"Subscription renewals task failed: {e}")
        return {'success': False, 'error': str(e)}


@celery.task(name='automation.rotate_ads_autopilot')
def task_rotate_ads_autopilot():
    """Hourly task to rotate ad campaigns"""
    try:
        from app.ads.automation import rotate_ads_autopilot
        count = rotate_ads_autopilot()
        logger.info(f"Ad rotation task completed: {count} campaigns updated")
        return {'success': True, 'count': count}
    except Exception as e:
        logger.error(f"Ad rotation task failed: {e}")
        return {'success': False, 'error': str(e)}


@celery.task(name='automation.calculate_ad_performance')
def task_calculate_ad_performance():
    """Daily task to calculate ad performance"""
    try:
        from app.ads.automation import calculate_ad_performance
        performance = calculate_ad_performance()
        logger.info(f"Ad performance calculation completed: {len(performance)} campaigns")
        return {'success': True, 'count': len(performance), 'data': performance}
    except Exception as e:
        logger.error(f"Ad performance calculation failed: {e}")
        return {'success': False, 'error': str(e)}


@celery.task(name='automation.optimize_ad_targeting')
def task_optimize_ad_targeting():
    """Daily task to optimize ad targeting"""
    try:
        from app.ads.automation import optimize_ad_targeting
        count = optimize_ad_targeting()
        logger.info(f"Ad targeting optimization completed: {count} creatives optimized")
        return {'success': True, 'count': count}
    except Exception as e:
        logger.error(f"Ad targeting optimization failed: {e}")
        return {'success': False, 'error': str(e)}


@celery.task(name='automation.cleanup_old_data')
def task_cleanup_old_data():
    """Weekly task to cleanup old data"""
    try:
        from datetime import datetime, timezone, timedelta
        from app import db
        from app.models import AdEvent
        
        # Delete ad events older than 90 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        deleted = AdEvent.query.filter(AdEvent.timestamp < cutoff).delete()
        db.session.commit()
        
        logger.info(f"Data cleanup completed: {deleted} old records deleted")
        return {'success': True, 'deleted': deleted}
    except Exception as e:
        logger.error(f"Data cleanup task failed: {e}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}


@celery.task(name='automation.backup_database')
def task_backup_database():
    """Daily task to backup database"""
    try:
        from app.backup.utils import create_backup
        
        backup_path = create_backup(
            description="Automated daily backup",
            include_files=True
        )
        
        logger.info(f"Database backup completed: {backup_path}")
        return {'success': True, 'backup_path': backup_path}
    except Exception as e:
        logger.error(f"Database backup task failed: {e}")
        return {'success': False, 'error': str(e)}


# Configure periodic tasks (Celery Beat)
celery.conf.beat_schedule = {
    # Payment automation - daily at 9:00 AM
    'send-payment-reminders': {
        'task': 'automation.send_payment_reminders',
        'schedule': crontab(hour=9, minute=0),
    },
    # Invoice generation - every hour
    'generate-payment-invoices': {
        'task': 'automation.generate_payment_invoices',
        'schedule': crontab(minute=0),
    },
    # Subscription renewals - daily at 8:00 AM
    'process-subscription-renewals': {
        'task': 'automation.process_subscription_renewals',
        'schedule': crontab(hour=8, minute=0),
    },
    # Ad rotation - every 15 minutes
    'rotate-ads-autopilot': {
        'task': 'automation.rotate_ads_autopilot',
        'schedule': crontab(minute='*/15'),
    },
    # Ad performance - daily at 1:00 AM
    'calculate-ad-performance': {
        'task': 'automation.calculate_ad_performance',
        'schedule': crontab(hour=1, minute=0),
    },
    # Ad targeting optimization - daily at 2:00 AM
    'optimize-ad-targeting': {
        'task': 'automation.optimize_ad_targeting',
        'schedule': crontab(hour=2, minute=0),
    },
    # Data cleanup - weekly on Sunday at 3:00 AM
    'cleanup-old-data': {
        'task': 'automation.cleanup_old_data',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),
    },
    # Database backup - daily at 4:00 AM
    'backup-database': {
        'task': 'automation.backup_database',
        'schedule': crontab(hour=4, minute=0),
    },
}
