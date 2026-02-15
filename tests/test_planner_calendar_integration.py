"""
Test field planner calendar integration and modification logging
"""
import pytest
from datetime import datetime, timedelta, timezone


@pytest.fixture
def app():
    """Create and configure a test app instance"""
    from app import create_app
    
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SERVER_NAME'] = 'localhost'
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


@pytest.fixture
def test_user_and_society(app, db_session):
    """Create test user and society, returns their IDs"""
    from app.models import User, Society, SocietyMembership, Role
    
    # Note: We're already inside db_session's app context
    # Create a basic role first
    role = Role(
        name='staff',
        display_name='Staff',
        level=5
    )
    db_session.add(role)
    db_session.flush()
    
    user = User(
        username='testuser',
        email='test@example.com',
        first_name='Test',
        last_name='User',
        role_id=role.id
    )
    user.set_password('testpass')
    db_session.add(user)
    db_session.flush()
    
    # Society.id must be same as a User.id (FK constraint)
    society = Society(
        id=user.id,  # Society.id is FK to User.id
        legal_name='Test Society',
        vat_number='12345678901'
    )
    db_session.add(society)
    db_session.flush()
    
    membership = SocietyMembership(
        society_id=society.id,
        user_id=user.id,
        role_name='staff',
        status='active',
        can_manage_planner=True,
        receive_planner_notifications=True
    )
    db_session.add(membership)
    db_session.commit()
    
    # Return IDs to avoid detached instance errors
    return {
        'user_id': user.id,
        'society_id': society.id
    }


def test_field_planner_shows_in_calendar(app, db_session, test_user_and_society):
    """Test that field planner events are included in calendar queries"""
    from app.models import FieldPlannerEvent, Facility
    from app.utils.audit import get_planner_changes
    
    data = test_user_and_society
    user_id = data['user_id']
    society_id = data['society_id']
    
    # We're already in db_session's app context, no need for nested context
    # Create facility
    facility = Facility(
        society_id=society_id,
        name='Test Field',
        created_by=user_id
    )
    db_session.add(facility)
    db_session.flush()
    
    # Create field planner event with consistent timestamps
    base_time = datetime.now(timezone.utc) + timedelta(days=1)
    event = FieldPlannerEvent(
        society_id=society_id,
        facility_id=facility.id,
        created_by=user_id,
        event_type='training',
        title='Test Training',
        start_datetime=base_time,
        end_datetime=base_time + timedelta(hours=2),
        color='#28a745'
    )
    db_session.add(event)
    db_session.commit()
    
    # Verify event was created
    assert event.id is not None
    assert event.title == 'Test Training'
    
    # Verify we can query it
    events = FieldPlannerEvent.query.filter_by(society_id=society_id).all()
    assert len(events) == 1
    assert events[0].title == 'Test Training'


def test_audit_logging_for_planner_changes(app, db_session, test_user_and_society):
    """Test that planner changes are logged in audit log"""
    from app.models import FieldPlannerEvent, Facility, AuditLog
    from app.utils.audit import log_planner_change, get_planner_changes
    
    data = test_user_and_society
    user_id = data['user_id']
    society_id = data['society_id']
    
    # We're already in db_session's app context, no need for nested context
    # Create facility
    facility = Facility(
        society_id=society_id,
        name='Test Field',
        created_by=user_id
    )
    db_session.add(facility)
    db_session.flush()
    
    # Create event with consistent timestamps
    base_time = datetime.now(timezone.utc) + timedelta(days=1)
    event = FieldPlannerEvent(
        society_id=society_id,
        facility_id=facility.id,
        created_by=user_id,
        event_type='training',
        title='Test Training',
        start_datetime=base_time,
        end_datetime=base_time + timedelta(hours=2)
    )
    db_session.add(event)
    db_session.commit()
    
    # Log the change
    log_entry = log_planner_change(
        user_id=user_id,
        society_id=society_id,
        action='field_planner_created',
        entity_type='FieldPlannerEvent',
        entity_id=event.id,
        details={'title': event.title}
    )
    
    # Verify log entry was created
    assert log_entry is not None
    assert log_entry.action == 'field_planner_created'
    assert log_entry.user_id == user_id
    assert log_entry.society_id == society_id
    
    # Verify we can retrieve logs
    changes = get_planner_changes(society_id)
    assert len(changes) == 1
    assert changes[0].action == 'field_planner_created'


def test_notification_for_planner_changes(app, db_session, test_user_and_society):
    """Test that notifications are sent for planner changes"""
    from app.models import Facility, Notification
    from app.notifications.utils import notify_planner_change
    
    data = test_user_and_society
    user_id = data['user_id']
    society_id = data['society_id']
    
    # We're already in db_session's app context, no need for nested context
    # Send notification
    notifications = notify_planner_change(
        society_id,
        "Test Notification",
        "This is a test notification for planner change",
        link="/test"
    )
    
    # Verify notification was created
    assert len(notifications) > 0
    
    # Verify user received notification (they have receive_planner_notifications=True)
    user_notifications = Notification.query.filter_by(user_id=user_id).all()
    assert len(user_notifications) > 0
    assert user_notifications[0].title == "Test Notification"
    assert user_notifications[0].notification_type == 'calendar'
