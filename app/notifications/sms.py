"""
SMS Integration with Twilio
"""
from flask import current_app
from typing import Optional
import os


def send_sms_twilio(phone_number: str, message: str) -> bool:
    """
    Send SMS via Twilio
    
    Args:
        phone_number: Recipient phone number (E.164 format, e.g., +393331234567)
        message: SMS message content
        
    Returns:
        True if SMS sent successfully, False otherwise
    """
    try:
        # Check if Twilio is configured
        account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
        from_number = os.environ.get('TWILIO_FROM_NUMBER')
        
        if not all([account_sid, auth_token, from_number]):
            current_app.logger.warning(
                'Twilio not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER'
            )
            return False
        
        # Import Twilio client
        try:
            from twilio.rest import Client
        except ImportError:
            current_app.logger.error('Twilio package not installed. Run: pip install twilio')
            return False
        
        # Validate phone number format
        if not phone_number.startswith('+'):
            current_app.logger.error(f'Invalid phone number format: {phone_number}. Use E.164 format (e.g., +393331234567)')
            return False
        
        # Create Twilio client
        client = Client(account_sid, auth_token)
        
        # Send SMS
        sms = client.messages.create(
            to=phone_number,
            from_=from_number,
            body=message
        )
        
        current_app.logger.info(f'SMS sent successfully. SID: {sms.sid}, To: {phone_number}')
        return True
        
    except Exception as e:
        current_app.logger.error(f'Failed to send SMS to {phone_number}: {str(e)}')
        return False


def send_sms_bulk(recipients: list, message: str) -> dict:
    """
    Send SMS to multiple recipients
    
    Args:
        recipients: List of phone numbers in E.164 format
        message: SMS message content
        
    Returns:
        Dictionary with success/failure counts
    """
    results = {
        'success': 0,
        'failed': 0,
        'total': len(recipients),
        'errors': []
    }
    
    for phone_number in recipients:
        try:
            if send_sms_twilio(phone_number, message):
                results['success'] += 1
            else:
                results['failed'] += 1
                results['errors'].append({'phone': phone_number, 'error': 'Send failed'})
        except Exception as e:
            results['failed'] += 1
            results['errors'].append({'phone': phone_number, 'error': str(e)})
    
    return results


def validate_phone_number(phone_number: str) -> bool:
    """
    Validate phone number format
    
    Args:
        phone_number: Phone number to validate
        
    Returns:
        True if valid E.164 format, False otherwise
    """
    import re
    # E.164 format: + followed by 1-15 digits
    pattern = r'^\+[1-9]\d{1,14}$'
    return bool(re.match(pattern, phone_number))


def format_phone_number(phone_number: str, country_code: str = '+39') -> Optional[str]:
    """
    Format phone number to E.164 format
    
    Args:
        phone_number: Phone number to format
        country_code: Default country code (default: +39 for Italy)
        
    Returns:
        Formatted phone number or None if invalid
    """
    import re
    
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone_number)
    
    # If already has +, validate and return
    if cleaned.startswith('+'):
        return cleaned if validate_phone_number(cleaned) else None
    
    # Add country code
    formatted = f"{country_code}{cleaned.lstrip('0')}"
    
    return formatted if validate_phone_number(formatted) else None
