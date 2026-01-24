"""
Notification utilities
"""
from flask import current_app
from flask_mail import Message
from app import mail, db
from app.models import Notification, User
from datetime import datetime, timedelta
import os


def create_notification(user_id, title, message, notification_type='system', link=None):
    """
    Create internal notification
    """
    try:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link
        )
        db.session.add(notification)
        db.session.commit()
        return notification
    except Exception as e:
        db.session.rollback()
        print(f"Error creating notification: {e}")
        return None


def notify_user(user, title, message, notification_type='system', link=None):
    """
    Notify a user (accepts User object or user_id)
    """
    user_id = user.id if hasattr(user, 'id') else user
    return create_notification(user_id, title, message, notification_type, link)


def notify_followers(user, title, message, notification_type='social', link=None):
    """
    Notify all followers of a user
    """
    if not hasattr(user, 'followers'):
        return []
    
    notifications = []
    for follower in user.followers:
        notif = create_notification(
            follower.id, 
            title, 
            message, 
            notification_type, 
            link
        )
        if notif:
            notifications.append(notif)
    
    return notifications


def notify_society_members(society_id, title, message, notification_type='system', link=None):
    """
    Notify all members (staff and athletes) of a society
    """
    members = User.query.filter(
        db.or_(
            User.society_id == society_id,
            User.athlete_society_id == society_id
        )
    ).all()
    
    notifications = []
    for member in members:
        notif = create_notification(
            member.id,
            title,
            message,
            notification_type,
            link
        )
        if notif:
            notifications.append(notif)
    
    return notifications


def get_unread_count(user_id):
    """
    Get count of unread notifications for a user
    """
    try:
        return Notification.query.filter_by(
            user_id=user_id,
            is_read=False
        ).count()
    except Exception:
        return 0


def cleanup_old_notifications(days=90):
    """
    Delete read notifications older than specified days
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    try:
        count = Notification.query.filter(
            Notification.is_read == True,
            Notification.read_at < cutoff_date
        ).delete()
        db.session.commit()
        return count
    except Exception as e:
        db.session.rollback()
        print(f"Error cleaning up notifications: {e}")
        return 0


def send_email(recipient, subject, body, html_body=None):
    """
    Send email notification
    Returns True if successful, False otherwise
    """
    try:
        if not current_app.config.get('MAIL_USERNAME'):
            # Email not configured
            return False
        
        msg = Message(
            subject=subject,
            recipients=[recipient] if isinstance(recipient, str) else recipient,
            body=body,
            html=html_body,
            sender=current_app.config['MAIL_DEFAULT_SENDER']
        )
        
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f'Failed to send email: {str(e)}')
        return False


def send_sms(phone_number, message):
    """
    Send SMS notification
    Ready for integration with SMS provider (Twilio, etc.)
    """
    provider = current_app.config.get('SMS_PROVIDER')
    
    if not provider:
        # SMS not configured
        return False
    
    # TODO: Integrate with actual SMS provider
    # Example for Twilio:
    # from twilio.rest import Client
    # client = Client(config['SMS_API_KEY'], config['SMS_API_SECRET'])
    # client.messages.create(
    #     to=phone_number,
    #     from_=config['SMS_FROM_NUMBER'],
    #     body=message
    # )
    
    current_app.logger.info(f'SMS would be sent to {phone_number}: {message}')
    return True
