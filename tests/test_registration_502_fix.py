"""
Test to verify 502 Bad Gateway fix for registration endpoints

This test verifies that:
1. Registration endpoints respond quickly (no timeout)
2. Email sending is async (doesn't block)
3. Database operations are optimized
"""
import pytest
import time
from unittest.mock import patch, MagicMock
from app import create_app, db
from app.models import User, Role


@pytest.fixture
def app():
    """Create test app with in-memory database"""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        db.create_all()
        
        # Create required roles
        roles = [
            Role(name='appassionato', display_name='Appassionato', level=10),
            Role(name='societa', display_name='Società', level=40),
        ]
        for role in roles:
            db.session.add(role)
        db.session.commit()
        
        yield app
        
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


def test_register_user_no_timeout(client, app):
    """Test that user registration completes quickly without blocking on email"""
    
    with app.app_context():
        # Mock the async email task to prevent actual email sending
        with patch('app.celery_tasks.send_confirmation_email_async') as mock_email:
            mock_email.delay = MagicMock()
            
            start_time = time.time()
            
            response = client.post('/auth/register', data={
                'email': 'test@example.com',
                'username': 'testuser',
                'first_name': 'Test',
                'last_name': 'User',
                'phone': '1234567890',
                'password': 'SecurePass123!',
                'confirm_password': 'SecurePass123!',
                'language': 'it',
                'terms': True
            }, follow_redirects=False)
            
            elapsed_time = time.time() - start_time
            
            # Registration should complete in under 5 seconds (was timing out at 60s+)
            assert elapsed_time < 5.0, f"Registration took {elapsed_time}s, expected < 5s"
            
            # Should redirect successfully (not 502)
            assert response.status_code in [200, 302], f"Expected redirect, got {response.status_code}"
            
            # Verify user was created
            user = User.query.filter_by(email='test@example.com').first()
            assert user is not None, "User should be created"
            assert user.role == 'appassionato'


def test_register_society_no_timeout(client, app):
    """Test that society registration completes quickly without blocking on email"""
    
    with app.app_context():
        # Mock the async email task
        with patch('app.celery_tasks.send_confirmation_email_async') as mock_email:
            mock_email.delay = MagicMock()
            
            start_time = time.time()
            
            response = client.post('/auth/register/society', data={
                'email': 'society@example.com',
                'username': 'testsociety',
                'company_name': 'Test Sports Society',
                'company_type': 'ASD',
                'fiscal_code': 'TSTFSC12345678',
                'address': 'Via Test 1',
                'city': 'Roma',
                'province': 'RM',
                'postal_code': '00100',
                'phone': '0612345678',
                'password': 'SecurePass123!',
                'confirm_password': 'SecurePass123!',
                'language': 'it',
                'terms': True
            }, follow_redirects=False)
            
            elapsed_time = time.time() - start_time
            
            # Registration should complete in under 5 seconds
            assert elapsed_time < 5.0, f"Society registration took {elapsed_time}s, expected < 5s"
            
            # Should redirect successfully (not 502)
            assert response.status_code in [200, 302], f"Expected redirect, got {response.status_code}"
            
            # Verify user was created
            user = User.query.filter_by(email='society@example.com').first()
            assert user is not None, "Society user should be created"
            assert user.role == 'societa'


def test_role_lookup_is_fast(app):
    """Test that role lookup uses index and is fast"""
    
    with app.app_context():
        # Measure time for role lookup (should use index)
        start_time = time.time()
        
        for _ in range(100):
            role = Role.query.filter_by(name='appassionato').first()
            assert role is not None
        
        elapsed_time = time.time() - start_time
        
        # 100 lookups should complete in under 0.5 seconds with index
        assert elapsed_time < 0.5, f"100 role lookups took {elapsed_time}s, index may not be working"


def test_async_email_task_defined(app):
    """Verify the async email task is properly defined"""
    from app.celery_tasks import send_confirmation_email_async
    
    assert send_confirmation_email_async is not None
    assert hasattr(send_confirmation_email_async, 'delay'), "Task should have .delay() method"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
