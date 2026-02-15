"""
Test module upload and management functionality
"""
import pytest
import os
import io
from app import create_app, db
from app.models import User, Role, SystemModule


@pytest.fixture
def app():
    """Create test app"""
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        db.create_all()
        
        # Create super admin role
        admin_role = Role(name='super_admin', display_name='Super Admin', level=100)
        db.session.add(admin_role)
        
        # Create admin user
        admin = User(
            email='admin@test.com',
            username='admin',
            role='super_admin',
            is_active=True
        )
        admin.set_password('password123')
        db.session.add(admin)
        db.session.commit()
        
        yield app
        
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def auth_client(client, app):
    """Create authenticated client"""
    with app.app_context():
        # Login
        response = client.post('/auth/login', data={
            'email': 'admin@test.com',
            'password': 'password123'
        }, follow_redirects=True)
        assert response.status_code == 200
    return client


def test_module_list_page_loads(auth_client):
    """Test that module list page loads"""
    response = auth_client.get('/admin/modules')
    assert response.status_code == 200
    assert b'Gestione Moduli' in response.data or b'moduli' in response.data.lower()


def test_module_upload_page_loads(auth_client):
    """Test that module upload page loads"""
    response = auth_client.get('/admin/modules/upload')
    assert response.status_code == 200


def test_module_upload_functionality(auth_client, app):
    """Test uploading a module"""
    # Create a fake zip file
    data = {
        'name': 'Test Module',
        'version': '1.0.0',
        'description': 'A test module',
        'module_file': (io.BytesIO(b'PK\x03\x04test zip content'), 'test_module.zip')
    }
    
    response = auth_client.post('/admin/modules/upload', data=data, 
                                content_type='multipart/form-data',
                                follow_redirects=True)
    
    # Check response
    assert response.status_code == 200
    
    # Verify module was created in database
    with app.app_context():
        module = SystemModule.query.filter_by(name='Test Module').first()
        assert module is not None
        assert module.version == '1.0.0'
        assert module.enabled == False  # Should be disabled by default


def test_module_toggle(auth_client, app):
    """Test enabling/disabling a module"""
    # First create a module
    with app.app_context():
        admin = User.query.filter_by(email='admin@test.com').first()
        module = SystemModule(
            name='Toggle Test',
            version='1.0.0',
            filename='test.zip',
            uploaded_by=admin.id,
            enabled=False
        )
        db.session.add(module)
        db.session.commit()
        module_id = module.id
    
    # Toggle it on
    response = auth_client.post(f'/admin/modules/{module_id}/toggle',
                                follow_redirects=True)
    assert response.status_code == 200
    
    # Verify it's enabled
    with app.app_context():
        module = SystemModule.query.get(module_id)
        assert module.enabled == True
    
    # Toggle it off
    response = auth_client.post(f'/admin/modules/{module_id}/toggle',
                                follow_redirects=True)
    assert response.status_code == 200
    
    # Verify it's disabled
    with app.app_context():
        module = SystemModule.query.get(module_id)
        assert module.enabled == False


def test_module_delete(auth_client, app):
    """Test deleting a module"""
    # First create a module
    with app.app_context():
        admin = User.query.filter_by(email='admin@test.com').first()
        module = SystemModule(
            name='Delete Test',
            version='1.0.0',
            filename='delete_test.zip',
            uploaded_by=admin.id
        )
        db.session.add(module)
        db.session.commit()
        module_id = module.id
    
    # Delete it
    response = auth_client.post(f'/admin/modules/{module_id}/delete',
                                follow_redirects=True)
    assert response.status_code == 200
    
    # Verify it's gone
    with app.app_context():
        module = SystemModule.query.get(module_id)
        assert module is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
