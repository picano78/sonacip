"""
Notification utilities
"""
from flask import current_app
from flask_mail import Message
from app import mail, db
from app.models import Notification, User, SmtpSetting
from datetime import datetime, timedelta, timezone
import os
import smtplib
from email.message import EmailMessage


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
    # Canonical membership resolution (SocietyMembership)
    try:
        from app.models import SocietyMembership
        member_ids = (
            SocietyMembership.query.filter_by(society_id=society_id, status='active')
            .with_entities(SocietyMembership.user_id)
            .all()
        )
        member_ids = [row[0] for row in member_ids]
        members = User.query.filter(User.id.in_(member_ids)).all() if member_ids else []
    except Exception:
        members = []
    
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
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
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


def notify_planner_change(society_id, title, message, link=None):
    """
    Notify all society members who have enabled planner notifications
    """
    try:
        from app.models import SocietyMembership
        
        # Get all active members who want planner notifications
        memberships = (
            SocietyMembership.query
            .filter_by(society_id=society_id, status='active')
            .filter_by(receive_planner_notifications=True)
            .all()
        )
        
        notifications = []
        for membership in memberships:
            notif = create_notification(
                membership.user_id,
                title,
                message,
                notification_type='calendar',
                link=link
            )
            if notif:
                notifications.append(notif)
        
        return notifications
    except Exception as e:
        print(f"Error sending planner notifications: {e}")
        return []


def notify_event_change(event_id, title, message, include_creator=True):
    """
    Notify all convocated athletes and optionally the creator about event changes
    """
    try:
        from app.models import Event, event_athletes
        
        event = Event.query.get(event_id)
        if not event:
            return []
        
        # Get all convocated athletes
        athlete_ids = db.session.execute(
            db.select(event_athletes.c.user_id).where(
                event_athletes.c.event_id == event_id
            )
        ).scalars().all()
        
        # Add creator if requested
        user_ids = set(athlete_ids)
        if include_creator and event.creator_id:
            user_ids.add(event.creator_id)
        
        notifications = []
        link = f'/events/{event_id}'
        
        for user_id in user_ids:
            notif = create_notification(
                user_id,
                title,
                message,
                notification_type='event',
                link=link
            )
            if notif:
                notifications.append(notif)
        
        return notifications
    except Exception as e:
        print(f"Error sending event notifications: {e}")
        return []


def send_email(recipient, subject, body, html_body=None):
    """
    Send email notification
    Returns True if successful, False otherwise
    """
    try:
        # Prefer DB-managed SMTP settings (super admin).
        settings = None
        try:
            settings = SmtpSetting.query.first()
        except Exception:
            settings = None

        recipients = [recipient] if isinstance(recipient, str) else list(recipient)

        if settings and settings.enabled and settings.host and settings.port and settings.default_sender:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = settings.default_sender
            msg["To"] = ", ".join(recipients)
            msg.set_content(body or "")
            if html_body:
                msg.add_alternative(html_body, subtype="html")

            server = smtplib.SMTP(settings.host, settings.port, timeout=20)
            try:
                server.ehlo()
                if settings.use_tls:
                    server.starttls()
                    server.ehlo()
                if settings.username and settings.password:
                    server.login(settings.username, settings.password)
                server.send_message(msg)
            finally:
                try:
                    server.quit()
                except Exception:
                    pass
            return True

        # Fallback: env-based Flask-Mail
        if not current_app.config.get('MAIL_USERNAME'):
            return False
        
        msg = Message(
            subject=subject,
            recipients=recipients,
            body=body,
            html=html_body,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER') or 'noreply@sonacip.it'
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


