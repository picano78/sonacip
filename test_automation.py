"""
Comprehensive test suite for automation system.
"""
import pytest  # type: ignore
import json
from datetime import datetime
from app import create_app
from app.core.extensions import db
from app.models import User, AutomationRule, AutomationRun, Notification, Post, Task
from app.automation.utils import execute_rules
from app.automation.validation import evaluate_condition, validate_action_schema


@pytest.fixture
def app():
    """Create test app."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        db.create_all()
        
        # Create test user
        user = User(
            username='testuser',
            email='test@example.com',
            role='super_admin',
            is_active=True
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        
        yield app
        
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def test_user(app):
    """Get test user."""
    with app.app_context():
        return User.query.filter_by(username='testuser').first()


class TestConditionEvaluation:
    """Test condition evaluation."""
    
    def test_empty_condition(self):
        """Empty condition should always match."""
        assert evaluate_condition('', {'status': 'completed'})
        assert evaluate_condition(None, {'status': 'pending'})
    
    def test_simple_equality(self):
        """Test simple equality expressions."""
        payload = {'status': 'completed', 'score': 100}
        
        assert evaluate_condition('status == "completed"', payload)
        assert not evaluate_condition('status == "pending"', payload)
        assert not evaluate_condition('status == "failed"', payload)
    
    def test_numeric_comparison(self):
        """Test numeric comparisons."""
        payload = {'score': 85, 'count': 10}
        
        assert evaluate_condition('score > 80', payload)
        assert not evaluate_condition('score > 90', payload)
        assert evaluate_condition('score < 90', payload)
        assert evaluate_condition('count >= 10', payload)
    
    def test_contains_operator(self):
        """Test contains operator."""
        payload = {'title': 'urgent task', 'description': 'needs attention'}
        
        assert evaluate_condition('title contains "urgent"', payload)
        assert not evaluate_condition('title contains "normal"', payload)
        assert evaluate_condition('description contains "attention"', payload)
    
    def test_json_condition(self):
        """Test JSON-based conditions."""
        payload = {'status': 'completed', 'score': 95}
        
        # AND condition
        condition = json.dumps({
            'all': [
                {'field': 'status', 'op': '==', 'value': 'completed'},
                {'field': 'score', 'op': '>', 'value': 90}
            ]
        })
        assert evaluate_condition(condition, payload)
        
        # OR condition
        condition = json.dumps({
            'any': [
                {'field': 'status', 'op': '==', 'value': 'pending'},
                {'field': 'score', 'op': '>', 'value': 90}
            ]
        })
        assert evaluate_condition(condition, payload)


class TestActionValidation:
    """Test action schema validation."""
    
    def test_notify_action(self):
        """Test notify action validation."""
        valid = {'type': 'notify', 'user_id': 1, 'title': 'Test', 'message': 'Hello'}
        is_valid, error = validate_action_schema(valid)
        assert is_valid
        assert error == ''
        
        invalid = {'type': 'notify', 'title': 'Test'}
        is_valid, error = validate_action_schema(invalid)
        assert not is_valid
        assert 'user_id' in error
    
    def test_email_action(self):
        """Test email action validation."""
        valid = {'type': 'email', 'user_id': 1, 'subject': 'Test', 'body': 'Message'}
        is_valid, error = validate_action_schema(valid)
        assert is_valid
        
        invalid = {'type': 'email', 'subject': 'Test'}
        is_valid, error = validate_action_schema(invalid)
        assert not is_valid
    
    def test_webhook_action(self):
        """Test webhook action validation."""
        valid = {'type': 'webhook', 'url': 'https://example.com/hook', 'method': 'POST'}
        is_valid, error = validate_action_schema(valid)
        assert is_valid
        
        invalid = {'type': 'webhook', 'url': 'not-a-url'}
        is_valid, error = validate_action_schema(invalid)
        assert not is_valid
    
    def test_unknown_action(self):
        """Test unknown action type."""
        invalid = {'type': 'unknown_action'}
        is_valid, error = validate_action_schema(invalid)
        assert not is_valid
        assert 'Unknown action type' in error


class TestAutomationExecution:
    """Test automation execution."""
    
    def test_execute_notify_action(self, app, test_user):
        """Test notification action execution."""
        with app.app_context():
            # Create automation rule
            actions = json.dumps([{
                'type': 'notify',
                'user_id': test_user.id,
                'title': 'Test Notification',
                'message': 'This is a test'
            }])
            
            rule = AutomationRule(
                name='Test Notify',
                event_type='test.event',
                actions=actions,
                is_active=True,
                created_by=test_user.id
            )
            db.session.add(rule)
            db.session.commit()
            
            # Execute
            payload = {'test_id': 123}
            runs = execute_rules('test.event', payload)
            
            assert len(runs) == 1
            assert runs[0].status == 'success'
            
            # Check notification created
            notification = Notification.query.filter_by(user_id=test_user.id).first()
            assert notification is not None
            assert notification.title == 'Test Notification'
    
    def test_execute_with_condition(self, app, test_user):
        """Test execution with condition."""
        with app.app_context():
            actions = json.dumps([{
                'type': 'notify',
                'user_id': test_user.id,
                'title': 'Condition Met',
                'message': 'Success'
            }])
            
            rule = AutomationRule(
                name='Test Condition',
                event_type='test.event',
                condition='status == "completed"',
                actions=actions,
                is_active=True,
                created_by=test_user.id
            )
            db.session.add(rule)
            db.session.commit()
            
            # Should execute
            runs = execute_rules('test.event', {'status': 'completed'})
            assert len(runs) == 1
            assert runs[0].status == 'success'
            
            # Should skip
            runs = execute_rules('test.event', {'status': 'pending'})
            assert len(runs) == 1
            assert runs[0].status == 'skipped'
    
    def test_invalid_json_actions(self, app, test_user):
        """Test handling of invalid JSON actions."""
        with app.app_context():
            rule = AutomationRule(
                name='Invalid Actions',
                event_type='test.event',
                actions='not valid json',
                is_active=True,
                created_by=test_user.id
            )
            db.session.add(rule)
            db.session.commit()
            
            runs = execute_rules('test.event', {})
            
            assert len(runs) == 1
            assert runs[0].status == 'failed'
            assert 'Invalid JSON' in runs[0].error_message


class TestAutomationModel:
    """Test AutomationRule model methods."""
    
    def test_validate_actions_valid(self, app, test_user):
        """Test valid actions validation."""
        with app.app_context():
            actions = json.dumps([{
                'type': 'notify',
                'user_id': 1,
                'title': 'Test',
                'message': 'Message'
            }])
            
            rule = AutomationRule(
                name='Test',
                event_type='test.event',
                actions=actions,
                created_by=test_user.id
            )
            
            is_valid, error = rule.validate_actions()
            assert is_valid
            assert error is None
    
    def test_validate_actions_invalid(self, app, test_user):
        """Test invalid actions validation."""
        with app.app_context():
            # Invalid action type
            actions = json.dumps([{
                'type': 'invalid_type',
                'user_id': 1
            }])
            
            rule = AutomationRule(
                name='Test',
                event_type='test.event',
                actions=actions,
                created_by=test_user.id
            )
            
            is_valid, error = rule.validate_actions()
            assert not is_valid
            assert error is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
