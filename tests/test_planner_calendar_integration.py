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
    """Create test user and society"""
    from app.models import User, Society, SocietyMembership, Role
    
    with app.app_context():
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
        
        society = Society(
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
        
        return user, society


def test_field_planner_shows_in_calendar(app, db_session, test_user_and_society):
    """Test that field planner events are included in calendar queries"""
    from app.models import FieldPlannerEvent, Facility
    from app.utils.audit import get_planner_changes
    
    user, society = test_user_and_society
    
    with app.app_context():
        # Create facility
        facility = Facility(
            society_id=society.id,
            name='Test Field',
            created_by=user.id
        )
        db_session.add(facility)
        db_session.flush()
        
        # Create field planner event
        event = FieldPlannerEvent(
            society_id=society.id,
            facility_id=facility.id,
            created_by=user.id,
            event_type='training',
            title='Test Training',
            start_datetime=datetime.now(timezone.utc) + timedelta(days=1),
            end_datetime=datetime.now(timezone.utc) + timedelta(days=1, hours=2),
            color='#28a745'
        )
        db_session.add(event)
        db_session.commit()
        
        # Verify event was created
        assert event.id is not None
        assert event.title == 'Test Training'
        
        # Verify we can query it
        events = FieldPlannerEvent.query.filter_by(society_id=society.id).all()
        assert len(events) == 1
        assert events[0].title == 'Test Training'


def test_audit_logging_for_planner_changes(app, db_session, test_user_and_society):
    """Test that planner changes are logged in audit log"""
    from app.models import FieldPlannerEvent, Facility, AuditLog
    from app.utils.audit import log_planner_change, get_planner_changes
    
    user, society = test_user_and_society
    
    with app.app_context():
        # Create facility
        facility = Facility(
            society_id=society.id,
            name='Test Field',
            created_by=user.id
        )
        db_session.add(facility)
        db_session.flush()
        
        # Create event
        event = FieldPlannerEvent(
            society_id=society.id,
            facility_id=facility.id,
            created_by=user.id,
            event_type='training',
            title='Test Training',
            start_datetime=datetime.now(timezone.utc) + timedelta(days=1),
            end_datetime=datetime.now(timezone.utc) + timedelta(days=1, hours=2)
        )
        db_session.add(event)
        db_session.commit()
        
        # Log the change
        log_entry = log_planner_change(
            user_id=user.id,
            society_id=society.id,
            action='field_planner_created',
            entity_type='FieldPlannerEvent',
            entity_id=event.id,
            details={'title': event.title}
        )
        
        # Verify log entry was created
        assert log_entry is not None
        assert log_entry.action == 'field_planner_created'
        assert log_entry.user_id == user.id
        assert log_entry.society_id == society.id
        
        # Verify we can retrieve logs
        changes = get_planner_changes(society.id)
        assert len(changes) == 1
        assert changes[0].action == 'field_planner_created'


def test_notification_for_planner_changes(app, db_session, test_user_and_society):
    """Test that notifications are sent for planner changes"""
    from app.models import Facility, Notification
    from app.notifications.utils import notify_planner_change
    
    user, society = test_user_and_society
    
    with app.app_context():
        # Send notification
        notifications = notify_planner_change(
            society.id,
            "Test Notification",
            "This is a test notification for planner change",
            link="/test"
        )
        
        # Verify notification was created
        assert len(notifications) > 0
        
        # Verify user received notification (they have receive_planner_notifications=True)
        user_notifications = Notification.query.filter_by(user_id=user.id).all()
        assert len(user_notifications) > 0
        assert user_notifications[0].title == "Test Notification"
        assert user_notifications[0].notification_type == 'calendar'
