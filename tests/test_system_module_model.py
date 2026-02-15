"""
Simple test for SystemModule model functionality
"""
import pytest
from app import create_app, db
from app.models import User, Role, SystemModule


def test_system_module_model():
    """Test SystemModule model creation and basic operations"""
    app = create_app('testing')
    
    with app.app_context():
        db.create_all()
        
        # Create a user first
        admin_role = Role(name='super_admin', display_name='Super Admin', level=100)
        db.session.add(admin_role)
        
        admin = User(
            email='admin@test.com',
            username='admin',
            role='super_admin',
            is_active=True
        )
        admin.set_password('password123')
        db.session.add(admin)
        db.session.commit()
        
        # Create a module
        module = SystemModule(
            name='Test Module',
            version='1.0.0',
            filename='test.zip',
            description='A test module for testing',
            uploaded_by=admin.id,
            enabled=False
        )
        db.session.add(module)
        db.session.commit()
        
        # Query it back
        retrieved = SystemModule.query.filter_by(name='Test Module').first()
        assert retrieved is not None
        assert retrieved.version == '1.0.0'
        assert retrieved.enabled is False
        assert retrieved.uploader.username == 'admin'
        
        # Test enable/disable
        retrieved.enabled = True
        db.session.commit()
        
        retrieved = SystemModule.query.filter_by(name='Test Module').first()
        assert retrieved.enabled is True
        
        # Test deletion
        db.session.delete(retrieved)
        db.session.commit()
        
        retrieved = SystemModule.query.filter_by(name='Test Module').first()
        assert retrieved is None
        
        print("✓ All SystemModule model tests passed")
        
        db.session.remove()
        db.drop_all()


if __name__ == '__main__':
    test_system_module_model()
