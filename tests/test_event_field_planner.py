"""
Test event and field planner integration
"""
import pytest
from datetime import datetime, timedelta


@pytest.fixture
def app():
    """Create and configure a test app instance"""
    from app import create_app
    
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    return app


@pytest.fixture
def db_session(app):
    """Create a database session for tests"""
    from app import db
    
    with app.app_context():
        db.create_all()
        yield db.session
        db.session.rollback()
        db.drop_all()


def test_event_model_has_facility_fields(app):
    """Test that Event model has facility_id and color fields"""
    from app.models import Event
    
    # Check that the model has the new fields
    assert hasattr(Event, 'facility_id')
    assert hasattr(Event, 'color')
    assert hasattr(Event, 'facility')


def test_society_calendar_event_has_event_id(app):
    """Test that SocietyCalendarEvent model has event_id field"""
    from app.models import SocietyCalendarEvent
    
    # Check that the model has the event_id field
    assert hasattr(SocietyCalendarEvent, 'event_id')
    assert hasattr(SocietyCalendarEvent, 'linked_event')


def test_event_form_has_facility_fields(app):
    """Test that EventForm has facility and color fields"""
    from app.events.forms import EventForm
    from app.models import User
    
    with app.app_context():
        # Create a mock user for testing
        form = EventForm()
        
        # Check that the form has the new fields
        assert hasattr(form, 'facility_id')
        assert hasattr(form, 'color')


def test_event_creation_with_facility(app, db_session):
    """Test creating an event with a facility"""
    from app.models import Event, User, Society, Facility
    from datetime import datetime
    
    with app.app_context():
        # Create test user and society
        user = User(
            username='testuser',
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        user.set_password('testpass')
        db_session.add(user)
        db_session.flush()
        
        society = Society(
            legal_name='Test Society',
            vat_number='12345678901'
        )
        db_session.add(society)
        db_session.flush()
        
        facility = Facility(
            society_id=society.id,
            name='Test Field',
            created_by=user.id
        )
        db_session.add(facility)
        db_session.flush()
        
        # Create event with facility
        event = Event(
            title='Test Training',
            event_type='allenamento',
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(hours=2),
            creator_id=user.id,
            facility_id=facility.id,
            color='#0dcaf0'
        )
        db_session.add(event)
        db_session.commit()
        
        # Verify event was created with facility
        assert event.id is not None
        assert event.facility_id == facility.id
        assert event.color == '#0dcaf0'
        assert event.facility.name == 'Test Field'
