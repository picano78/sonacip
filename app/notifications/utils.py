"""
Notification utilities
"""
from flask import current_app
from flask_mail import Message
from app import mail, db
from app.models import Notification
import os


def create_notification(user_id, title, message, notification_type='system', link=None):
    """
    Create internal notification
    """
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
