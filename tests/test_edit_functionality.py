"""
Test edit functionality for field planner and calendar events
"""
import pytest
from datetime import datetime, timedelta, date, time as dt_time
from app import create_app, db
from app.models import User, Society, FieldPlannerEvent, SocietyCalendarEvent, Facility


@pytest.fixture
def app():
    """Create and configure a test app"""
    app = create_app('testing')
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
    """Test client for the app"""
    return app.test_client()


@pytest.fixture
def auth_user(app):
    """Create an authenticated user with a society"""
    with app.app_context():
        # Create a society
        society = Society(
            name='Test Society',
            description='Test',
            sport_type='football'
        )
        db.session.add(society)
        db.session.flush()
        
        # Create a user
        user = User(
            email='test@example.com',
            username='testuser',
            first_name='Test',
            last_name='User',
            role='director'
        )
        user.set_password('password123')
        user.society_id = society.id
        db.session.add(user)
        
        # Create a facility
        facility = Facility(
            name='Test Field',
            society_id=society.id,
            address='Test Address'
        )
        db.session.add(facility)
        
        db.session.commit()
        
        return user, society, facility


def test_field_planner_edit_route_exists(client, auth_user):
    """Test that field planner edit route exists"""
    user, society, facility = auth_user
    
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
    
    # Create a test event
    with client.application.app_context():
        event = FieldPlannerEvent(
            society_id=society.id,
            facility_id=facility.id,
            created_by=user.id,
            event_type='training',
            title='Test Training',
            start_datetime=datetime.now() + timedelta(days=1),
            end_datetime=datetime.now() + timedelta(days=1, hours=2),
        )
        db.session.add(event)
        db.session.commit()
        event_id = event.id
    
    # Test GET request to edit route
    response = client.get(f'/field_planner/event/{event_id}/edit')
    # Should either show the form or redirect (depending on permissions)
    assert response.status_code in [200, 302, 403]


def test_calendar_edit_route_exists(client, auth_user):
    """Test that calendar edit route exists"""
    user, society, facility = auth_user
    
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
    
    # Create a test event
    with client.application.app_context():
        event = SocietyCalendarEvent(
            society_id=society.id,
            facility_id=facility.id,
            created_by=user.id,
            event_type='training',
            title='Test Calendar Event',
            start_datetime=datetime.now() + timedelta(days=1),
            end_datetime=datetime.now() + timedelta(days=1, hours=2),
        )
        db.session.add(event)
        db.session.commit()
        event_id = event.id
    
    # Test GET request to edit route
    response = client.get(f'/scheduler/calendar/{event_id}/edit')
    # Should either show the form or redirect (depending on permissions)
    assert response.status_code in [200, 302, 403]


def test_field_planner_routes_available(app):
    """Test that field planner edit route is registered"""
    app.config['SERVER_NAME'] = 'localhost'
    with app.app_context():
        from flask import url_for
        # Should not raise an exception
        try:
            url = url_for('field_planner.edit', event_id=1)
            assert 'edit' in url and 'event/1' in url
        except Exception as e:
            pytest.fail(f"Route not registered: {e}")


def test_calendar_routes_available(app):
    """Test that calendar edit route is registered"""
    app.config['SERVER_NAME'] = 'localhost'
    with app.app_context():
        from flask import url_for
        # Should not raise an exception
        try:
            url = url_for('calendar.edit', event_id=1)
            assert '/scheduler/calendar/1/edit' in url
        except Exception as e:
            pytest.fail(f"Route not registered: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
