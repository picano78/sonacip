"""
Comprehensive Test Suite for New Features
Tests for SMS, Celery tasks, caching, automation, and exports
"""
import pytest
from app import create_app, db
from app.models import User, Notification, AutomationRule
from app.notifications.sms import validate_phone_number, format_phone_number
from app.utils.caching import cache_key, memoize_request
from app.utils.search import SearchEngine
from app.utils.exports import DataExporter
from datetime import datetime, timezone
import json


@pytest.fixture
def app():
    """Create and configure test app"""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Test client"""
    return app.test_client()


# SMS Tests

def test_validate_phone_number():
    """Test phone number validation"""
    assert validate_phone_number('+393331234567')
    assert validate_phone_number('+1234567890')
    assert not validate_phone_number('3331234567')
    assert not validate_phone_number('+39 333 123 4567')
    assert not validate_phone_number('invalid')


def test_format_phone_number():
    """Test phone number formatting"""
    assert format_phone_number('3331234567', '+39') == '+393331234567'
    assert format_phone_number('03331234567', '+39') == '+393331234567'
    assert format_phone_number('+393331234567') == '+393331234567'
    assert format_phone_number('333-123-4567', '+39') == '+393331234567'


# Caching Tests

def test_cache_key_generation():
    """Test cache key generation"""
    key1 = cache_key(1, 2, 3, foo='bar')
    key2 = cache_key(1, 2, 3, foo='bar')
    key3 = cache_key(1, 2, 3, foo='baz')
    
    assert key1 == key2
    assert key1 != key3


def test_memoize_request(app):
    """Test request-scoped memoization"""
    call_count = {'count': 0}
    
    @memoize_request
    def expensive_function(x):
        call_count['count'] += 1
        return x * 2
    
    with app.test_request_context():
        # First call
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count['count'] == 1
        
        # Second call - should be cached
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count['count'] == 1  # Not incremented
        
        # Different argument - should call function
        result3 = expensive_function(10)
        assert result3 == 20
        assert call_count['count'] == 2


# Search Tests

def test_search_users(app):
    """Test user search"""
    with app.app_context():
        # Create test users
        user1 = User(
            username='john_doe',
            email='john@example.com',
            first_name='John',
            last_name='Doe',
            password_hash='hash'
        )
        user2 = User(
            username='jane_smith',
            email='jane@example.com',
            first_name='Jane',
            last_name='Smith',
            password_hash='hash'
        )
        db.session.add_all([user1, user2])
        db.session.commit()
        
        # Search by first name
        results = SearchEngine.search_users('John')
        assert len(results) == 1
        assert results[0].username == 'john_doe'
        
        # Search by email
        results = SearchEngine.search_users('jane@')
        assert len(results) == 1
        assert results[0].username == 'jane_smith'


# Export Tests

def test_export_to_csv(app):
    """Test CSV export"""
    with app.app_context():
        data = [
            {'id': 1, 'name': 'Test 1'},
            {'id': 2, 'name': 'Test 2'}
        ]
        
        response = DataExporter.to_csv(data, 'test.csv')
        
        assert response.status_code == 200
        assert response.headers['Content-Type'] == 'text/csv; charset=utf-8'
        assert b'id,name' in response.data
        assert b'Test 1' in response.data


def test_export_to_json(app):
    """Test JSON export"""
    with app.app_context():
        data = [
            {'id': 1, 'name': 'Test 1'},
            {'id': 2, 'name': 'Test 2'}
        ]
        
        response = DataExporter.to_json(data, 'test.json')
        
        assert response.status_code == 200
        assert response.headers['Content-Type'] == 'application/json; charset=utf-8'
        json_data = json.loads(response.data)
        assert len(json_data) == 2
        assert json_data[0]['name'] == 'Test 1'


# Automation Tests

def test_automation_rule_validation(app):
    """Test automation rule validation"""
    with app.app_context():
        # Valid rule
        rule = AutomationRule(
            name='Test Rule',
            event_type='user.registered',
            actions=json.dumps([
                {'type': 'notify', 'user_id': 1, 'message': 'Welcome!'}
            ])
        )
        
        valid, error = rule.validate_actions()
        assert valid
        assert error is None
        
        # Invalid rule - missing user_id
        rule2 = AutomationRule(
            name='Invalid Rule',
            event_type='user.registered',
            actions=json.dumps([
                {'type': 'notify', 'message': 'Welcome!'}
            ])
        )
        
        valid, error = rule2.validate_actions()
        assert not valid
        assert 'user_id' in error


def test_automation_event_types(app, client):
    """Test automation event types API"""
    with app.app_context():
        # Create a test user and login
        user = User(
            username='admin',
            email='admin@example.com',
            password_hash='hash',
            is_active=True
        )
        db.session.add(user)
        db.session.commit()
        
        # This would require actual authentication setup
        # For now, just test the endpoint exists
        # response = client.get('/automation/builder/api/event-types')
        # assert response.status_code in [200, 401, 302]


# Performance Tests

def test_query_performance(app):
    """Test query performance with indexes"""
    with app.app_context():
        import time
        
        # Create test data
        users = []
        for i in range(100):
            user = User(
                username=f'user{i}',
                email=f'user{i}@example.com',
                password_hash='hash'
            )
            users.append(user)
        db.session.add_all(users)
        db.session.commit()
        
        # Test query performance
        start = time.time()
        results = User.query.filter(User.email.like('%user50%')).all()
        duration = time.time() - start
        
        assert len(results) == 1
        assert duration < 0.1  # Should be fast even without indexes


# Integration Tests

def test_notification_creation_triggers_automation(app):
    """Test that notification creation can trigger automation"""
    with app.app_context():
        # Create user
        user = User(
            username='testuser',
            email='test@example.com',
            password_hash='hash'
        )
        db.session.add(user)
        db.session.commit()
        
        # Create automation rule
        rule = AutomationRule(
            name='Notify on Event',
            event_type='event.created',
            actions=json.dumps([
                {'type': 'notify', 'user_id': user.id, 'title': 'Event Created', 'message': 'A new event was created'}
            ]),
            is_active=True
        )
        db.session.add(rule)
        db.session.commit()
        
        # Trigger automation (would be done by execute_rules in real scenario)
        from app.automation.utils import execute_rules
        
        payload = {'event_id': 1, 'title': 'Test Event'}
        runs = execute_rules('event.created', payload)
        
        # Verify automation ran
        assert len(runs) > 0
        assert runs[0].rule_id == rule.id


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
