"""
Invoice generation utilities
Automatic invoice generation after payment completion
"""
import logging
from datetime import datetime, timezone
from app import db
from app.models import Invoice, InvoiceSettings, FeePayment, User

logger = logging.getLogger(__name__)


def generate_invoice_for_payment(fee_payment_id):
    """
    Generate an invoice automatically for a completed fee payment
    
    Args:
        fee_payment_id: ID of the FeePayment record
        
    Returns:
        Invoice object if created, None if already exists or error
    """
    try:
        # Check if invoice already exists
        existing = Invoice.query.filter_by(fee_payment_id=fee_payment_id).first()
        if existing:
            return existing
        
        # Get fee payment
        fee_payment = db.session.get(FeePayment, fee_payment_id)
        if not fee_payment or fee_payment.status != 'completed':
            return None
        
        # Get invoice settings
        settings = InvoiceSettings.query.first()
        
        # Get user billing information
        user = db.session.get(User, fee_payment.user_id)
        
        # Calculate tax
        tax_rate = settings.default_tax_rate if settings else 22.0
        amount = fee_payment.amount
        tax_amount = round(amount * tax_rate / 100, 2)
        total_amount = round(amount + tax_amount, 2)
        
        # Create invoice with temporary invoice number
        # We'll update it after flush to get the actual ID
        year = datetime.now(timezone.utc).year
        prefix = settings.invoice_prefix if settings and settings.invoice_prefix else 'INV'
        temp_invoice_number = f'{prefix}-{year}-TEMP-{fee_payment_id}'
        
        invoice = Invoice(
            user_id=fee_payment.user_id,
            fee_payment_id=fee_payment_id,
            invoice_number=temp_invoice_number,
            amount=amount,
            tax_amount=tax_amount,
            total_amount=total_amount,
            currency='EUR',
            status='paid',
            invoice_date=datetime.now(timezone.utc),
            paid_date=fee_payment.paid_at,
            description=f"Pagamento quota - {fee_payment.fee.description if fee_payment.fee else 'Fee Payment'}"
        )
        
        # Add customer billing information
        if user:
            # Use user's full name or username as billing name
            if hasattr(user, 'first_name') and hasattr(user, 'last_name'):
                full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                invoice.billing_name = full_name if full_name else user.username
            else:
                invoice.billing_name = user.username
            
        db.session.add(invoice)
        db.session.flush()  # Get invoice ID
        
        # Update with actual invoice number based on ID
        invoice.invoice_number = generate_invoice_number(invoice.id, settings)
        
        db.session.commit()
        
        return invoice
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error generating invoice: {e}", exc_info=True)
        return None


def generate_invoice_number(invoice_id, settings=None):
    """
    Generate unique invoice number
    
    Args:
        invoice_id: Invoice ID
        settings: InvoiceSettings object (optional)
        
    Returns:
        Formatted invoice number string
    """
    year = datetime.now().year
    prefix = settings.invoice_prefix if settings and settings.invoice_prefix else 'INV'
    
    # Format: PREFIX-YYYY-XXXXX (e.g., INV-2026-00001)
    return f'{prefix}-{year}-{str(invoice_id).zfill(5)}'


def send_to_electronic_invoice_provider(invoice_id):
    """
    Send invoice to electronic invoice provider (e.g., Fatture in Cloud, Aruba)
    
    Args:
        invoice_id: Invoice ID
        
    Returns:
        dict with success status and response
    """
    try:
        invoice = db.session.get(Invoice, invoice_id)
        if not invoice:
            return {'success': False, 'error': 'Invoice not found'}
        
        settings = InvoiceSettings.query.first()
        if not settings or not settings.enable_electronic_invoice:
            return {'success': False, 'error': 'Electronic invoicing not enabled'}
        
        # Check provider
        if settings.e_invoice_provider == 'fatture_in_cloud':
            return send_to_fatture_in_cloud(invoice, settings)
        elif settings.e_invoice_provider == 'aruba':
            return send_to_aruba(invoice, settings)
        else:
            return {'success': False, 'error': 'Unknown provider'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}


def send_to_fatture_in_cloud(invoice, settings):
    """
    Send invoice to Fatture in Cloud API
    
    This is a placeholder for actual implementation
    Documentation: https://docs.fattureincloud.it/
    """
    # TODO: Implement Fatture in Cloud API integration
    # This would require:
    # 1. Install requests library
    # 2. Authenticate with API key/secret
    # 3. Format invoice data according to FIC API schema
    # 4. POST to FIC API endpoint
    # 5. Handle response and store tracking info
    
    return {
        'success': False,
        'error': 'Fatture in Cloud integration not yet implemented',
        'message': 'Configure API integration in production'
    }


def send_to_aruba(invoice, settings):
    """
    Send invoice to Aruba Fatturazione Elettronica API
    
    This is a placeholder for actual implementation
    """
    # TODO: Implement Aruba API integration
    
    return {
        'success': False,
        'error': 'Aruba integration not yet implemented',
        'message': 'Configure API integration in production'
    }
