"""
Test super admin initialization and login functionality.
Ensures the fixed credentials work correctly.
"""
import pytest
from app import create_app, db
from app.models import User, Role


# Test credentials (as configured in config.py for non-production)
TEST_ADMIN_EMAIL = 'Picano78@gmail.com'
TEST_ADMIN_PASSWORD = 'Simone78'


class TestSuperAdminInitialization:
    """Test super admin user creation and login"""
    
    @pytest.fixture
    def app(self):
        """Create test app with in-memory database"""
        app = create_app('testing')
        with app.app_context():
            db.create_all()
            # Seed roles and admin
            from app.core.seed import seed_defaults
            seed_defaults(app)
            yield app
            # Proper cleanup - close session first, then drop all
            db.session.close()
            db.session.remove()
            # Drop all with proper constraint handling
            db.engine.dispose()
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    def test_super_admin_exists(self, app):
        """Test that super admin user is created with correct credentials"""
        with app.app_context():
            admin = User.query.filter_by(email=TEST_ADMIN_EMAIL).first()
            assert admin is not None, "Super admin user not found"
            assert admin.username == TEST_ADMIN_EMAIL
            assert admin.role == 'super_admin'
            assert admin.is_active is True
            assert admin.is_verified is True
            assert admin.email_confirmed is True
    
    def test_super_admin_password(self, app):
        """Test that super admin password is correct"""
        with app.app_context():
            admin = User.query.filter_by(email=TEST_ADMIN_EMAIL).first()
            assert admin is not None
            assert admin.check_password(TEST_ADMIN_PASSWORD), "Password verification failed"
            # Verify wrong password doesn't work
            assert not admin.check_password('wrongpassword')
    
    def test_super_admin_role_methods(self, app):
        """Test that super admin has correct role methods"""
        with app.app_context():
            admin = User.query.filter_by(email=TEST_ADMIN_EMAIL).first()
            assert admin is not None
            assert admin.is_admin() is True
            assert admin.role_display_name == 'Super Admin'
    
    def test_no_is_superadmin_attribute(self, app):
        """Test that User model doesn't have is_superadmin attribute"""
        with app.app_context():
            admin = User.query.filter_by(email=TEST_ADMIN_EMAIL).first()
            assert admin is not None
            # Verify that is_superadmin attribute doesn't exist
            assert not hasattr(User, 'is_superadmin'), "User model should not have is_superadmin attribute"
            # Verify role-based system is used instead
            assert hasattr(admin, 'role'), "User should have role attribute"
            assert admin.role == 'super_admin'
    
    def test_login_with_fixed_credentials(self, app, client):
        """Test login with the fixed credentials"""
        # Test login endpoint
        response = client.post('/auth/login', data={
            'email': TEST_ADMIN_EMAIL,
            'password': TEST_ADMIN_PASSWORD
        }, follow_redirects=False)
        
        # Should redirect on successful login (302) or show success
        # The exact behavior depends on the login implementation
        assert response.status_code in [200, 302], f"Login failed with status {response.status_code}"
        
        # If we get redirected, it should be to a valid page (not back to login)
        if response.status_code == 302:
            assert '/auth/login' not in response.location, "Should not redirect back to login page"


class TestRoleBasedSystem:
    """Test that the role-based system works correctly"""
    
    @pytest.fixture
    def app(self):
        """Create test app"""
        app = create_app('testing')
        with app.app_context():
            db.create_all()
            from app.core.seed import seed_defaults
            seed_defaults(app)
            yield app
            # Proper cleanup
            db.session.close()
            db.session.remove()
            db.engine.dispose()
    
    def test_super_admin_role_exists(self, app):
        """Test that super_admin role exists in database"""
        with app.app_context():
            role = Role.query.filter_by(name='super_admin').first()
            assert role is not None
            assert role.display_name == 'Super Admin'
            assert role.level == 100
    
    def test_all_required_roles_exist(self, app):
        """Test that all required roles are seeded"""
        with app.app_context():
            required_roles = [
                'super_admin', 'admin', 'moderator', 
                'society_admin', 'societa', 'staff', 
                'coach', 'atleta', 'appassionato'
            ]
            for role_name in required_roles:
                role = Role.query.filter_by(name=role_name).first()
                assert role is not None, f"Role {role_name} not found"
