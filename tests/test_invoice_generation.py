"""
Test invoice generation functionality
"""
import pytest
from datetime import datetime, timezone
from app import create_app, db
from app.models import User, FeePayment, Invoice, InvoiceSettings, SocietyFee
from app.payments.invoice_utils import generate_invoice_for_payment, generate_invoice_number


@pytest.fixture
def app():
    """Create and configure a test app instance"""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """A test client for the app"""
    return app.test_client()


def test_invoice_settings_creation(app):
    """Test InvoiceSettings model creation"""
    with app.app_context():
        settings = InvoiceSettings(
            company_name='Test Company S.r.l.',
            company_vat='IT12345678901',
            company_tax_code='12345678901',
            invoice_prefix='TEST',
            default_tax_rate=22.0,
            enable_electronic_invoice=False
        )
        db.session.add(settings)
        db.session.commit()
        
        # Verify settings were created
        saved_settings = InvoiceSettings.query.first()
        assert saved_settings is not None
        assert saved_settings.company_name == 'Test Company S.r.l.'
        assert saved_settings.company_vat == 'IT12345678901'
        assert saved_settings.default_tax_rate == 22.0


def test_generate_invoice_number(app):
    """Test invoice number generation"""
    with app.app_context():
        # Create settings
        settings = InvoiceSettings(invoice_prefix='INV')
        db.session.add(settings)
        db.session.commit()
        
        # Generate invoice number
        invoice_number = generate_invoice_number(1, settings)
        year = datetime.now().year
        
        assert invoice_number == f'INV-{year}-00001'


def test_automatic_invoice_generation(app):
    """Test automatic invoice generation after payment"""
    with app.app_context():
        # Create a role first
        from app.models import Role
        role = Role(name='appassionato', display_name='Appassionato', level=10)
        db.session.add(role)
        db.session.flush()
        
        # Create a test user
        user = User(
            email='test@example.com',
            username='testuser',
            password_hash='hashed_password',
            role_id=role.id
        )
        db.session.add(user)
        db.session.flush()
        
        # Create invoice settings
        settings = InvoiceSettings(
            company_name='SONACIP S.r.l.',
            invoice_prefix='INV',
            default_tax_rate=22.0
        )
        db.session.add(settings)
        
        # Create a society fee
        fee = SocietyFee(
            user_id=user.id,
            description='Test Fee',
            amount_cents=10000,  # €100.00
            status='pending',
            currency='EUR'
        )
        db.session.add(fee)
        db.session.flush()
        
        # Create a completed payment
        payment = FeePayment(
            fee_id=fee.id,
            user_id=user.id,
            amount=100.00,
            payment_method='stripe',
            status='completed',
            paid_at=datetime.now(timezone.utc)
        )
        db.session.add(payment)
        db.session.commit()
        
        # Generate invoice
        invoice = generate_invoice_for_payment(payment.id)
        
        # Verify invoice was created
        assert invoice is not None
        assert invoice.user_id == user.id
        assert invoice.fee_payment_id == payment.id
        assert invoice.amount == 100.00
        assert invoice.tax_amount == 22.00  # 22% of 100
        assert invoice.total_amount == 122.00
        assert invoice.status == 'paid'
        assert invoice.invoice_number is not None
        assert 'INV-' in invoice.invoice_number


def test_invoice_not_duplicated(app):
    """Test that invoice is not created twice for same payment"""
    with app.app_context():
        # Create a role first
        from app.models import Role
        role = Role(name='appassionato', display_name='Appassionato', level=10)
        db.session.add(role)
        db.session.flush()
        
        # Create test user
        user = User(
            email='test@example.com',
            username='testuser',
            password_hash='hashed_password',
            role_id=role.id
        )
        db.session.add(user)
        db.session.flush()
        
        # Create invoice settings
        settings = InvoiceSettings(
            company_name='SONACIP S.r.l.',
            invoice_prefix='INV',
            default_tax_rate=22.0
        )
        db.session.add(settings)
        
        # Create fee and payment
        fee = SocietyFee(
            user_id=user.id,
            description='Test Fee',
            amount_cents=10000,
            status='paid',
            currency='EUR'
        )
        db.session.add(fee)
        db.session.flush()
        
        payment = FeePayment(
            fee_id=fee.id,
            user_id=user.id,
            amount=100.00,
            payment_method='stripe',
            status='completed',
            paid_at=datetime.now(timezone.utc)
        )
        db.session.add(payment)
        db.session.commit()
        
        # Generate invoice first time
        invoice1 = generate_invoice_for_payment(payment.id)
        
        # Try to generate invoice again
        invoice2 = generate_invoice_for_payment(payment.id)
        
        # Should return the same invoice
        assert invoice1.id == invoice2.id
        
        # Only one invoice should exist
        invoice_count = Invoice.query.filter_by(fee_payment_id=payment.id).count()
        assert invoice_count == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
