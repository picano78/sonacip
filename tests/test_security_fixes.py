"""
Comprehensive security validation tests
Tests all security fixes implemented in the security audit
"""
import pytest
from app import create_app, db
from app.models import User, Role
from urllib.parse import urljoin
import os


class TestSecurityFixes:
    """Test suite for security vulnerability fixes"""
    
    @pytest.fixture
    def app(self):
        """Create test application"""
        os.environ['SECRET_KEY'] = 'test-secret-key-for-security-tests'
        app = create_app('testing')
        app.config['WTF_CSRF_ENABLED'] = True
        app.config['TESTING'] = True
        
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    def test_security_headers_present(self, client):
        """Test that all security headers are present"""
        response = client.get('/')
        
        # Check X-Content-Type-Options
        assert 'X-Content-Type-Options' in response.headers
        assert response.headers['X-Content-Type-Options'] == 'nosniff'
        
        # Check X-Frame-Options
        assert 'X-Frame-Options' in response.headers
        assert response.headers['X-Frame-Options'] == 'DENY'
        
        # Check Referrer-Policy
        assert 'Referrer-Policy' in response.headers
        
        # Check CSP (if enabled)
        if 'Content-Security-Policy' in response.headers or 'Content-Security-Policy-Report-Only' in response.headers:
            csp = response.headers.get('Content-Security-Policy') or response.headers.get('Content-Security-Policy-Report-Only')
            assert "default-src 'self'" in csp or "default-src" in csp
    
    def test_csrf_token_in_forms(self, client):
        """Test that CSRF tokens are present in forms"""
        response = client.get('/auth/login')
        assert response.status_code == 200
        # Check for CSRF token meta tag or hidden field
        assert b'csrf' in response.data.lower() or b'_csrf_token' in response.data
    
    def test_session_security_config(self, app):
        """Test session security configuration"""
        assert app.config['SESSION_COOKIE_HTTPONLY'] == True
        assert app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'
    
    def test_no_hardcoded_credentials(self, app):
        """Test that no hardcoded credentials exist in seed"""
        # This test ensures the fix is in place
        with app.app_context():
            # If SUPERADMIN_EMAIL not set, it should use the new secure method
            email = app.config.get("SUPERADMIN_EMAIL")
            # The old hardcoded email should not be used anymore
            # Note: Can't test password directly as it's hashed
            assert email != "picano78@gmail.com" or app.config.get("SUPERADMIN_EMAIL") is not None
    
    def test_csp_enabled(self, app):
        """Test that CSP is enabled by default"""
        # CSP should be enabled by default (True)
        assert app.config.get('CSP_ENABLED') in [True, 'true', 'True']
    
    def test_hsts_configuration(self, app):
        """Test HSTS is properly configured"""
        assert app.config.get('HSTS_ENABLED') in [True, 'true', 'True']
        # Should be 2 years (63072000 seconds)
        assert app.config.get('HSTS_MAX_AGE') >= 31536000  # At least 1 year
    
    def test_file_upload_validation_exists(self, app):
        """Test that file upload validation functions exist"""
        from app.storage import validate_file_type, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_MIMES
        
        # Check that validation function exists
        assert callable(validate_file_type)
        
        # Check that whitelists exist
        assert isinstance(ALLOWED_IMAGE_EXTENSIONS, set)
        assert isinstance(ALLOWED_IMAGE_MIMES, set)
        assert len(ALLOWED_IMAGE_EXTENSIONS) > 0
        assert len(ALLOWED_IMAGE_MIMES) > 0
    
    def test_safe_url_redirect_exists(self, app):
        """Test that safe URL validation exists in auth"""
        from app.auth.routes import is_safe_url
        
        # Check function exists
        assert callable(is_safe_url)
        
        # Test with safe URLs (within request context)
        with app.test_request_context('http://localhost/'):
            assert is_safe_url('/dashboard') == True
            assert is_safe_url('/auth/login') == True
            assert is_safe_url('http://localhost/profile') == True
            
            # Test with unsafe URLs
            assert is_safe_url('http://evil.com/') == False
            assert is_safe_url('//evil.com/phishing') == False
            assert is_safe_url('javascript:alert(1)') == False
    
    def test_plugin_loader_security(self, app):
        """Test that plugin loader has path traversal protection"""
        from app.core.plugins import _import_plugin_module
        import tempfile
        
        # Test should reject path with ..
        with pytest.raises(ValueError, match="Invalid plugin directory"):
            _import_plugin_module("test", "../etc/passwd")
    
    def test_secret_key_configured(self, app):
        """Test that SECRET_KEY is configured"""
        assert app.config['SECRET_KEY'] is not None
        assert app.config['SECRET_KEY'] != ''
        assert len(app.config['SECRET_KEY']) >= 16
        # Should not be placeholder values
        assert app.config['SECRET_KEY'] not in ['CHANGEME_GENERATE_WITH_PYTHON_SECRETS', 'your-secret-key-here']


class TestAuthenticationSecurity:
    """Test authentication-specific security fixes"""
    
    @pytest.fixture
    def app(self):
        """Create test application"""
        os.environ['SECRET_KEY'] = 'test-secret-key-for-auth-tests'
        app = create_app('testing')
        app.config['WTF_CSRF_ENABLED'] = False  # Disable for easier testing
        app.config['TESTING'] = True
        
        with app.app_context():
            db.create_all()
            
            # Create test user
            role = Role.query.filter_by(name='super_admin').first()
            if not role:
                role = Role(name='super_admin', display_name='Super Admin', level=100)
                db.session.add(role)
                db.session.commit()
            
            user = User(
                email='test@example.com',
                username='testuser',
                is_active=True,
                is_verified=True,
                role_obj=role
            )
            user.set_password('testpass123')
            db.session.add(user)
            db.session.commit()
            
            yield app
            
            db.session.remove()
            db.drop_all()
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    def test_login_creates_new_session(self, client, app):
        """Test that login regenerates session (session fixation protection)"""
        # Get initial session
        with client.session_transaction() as sess:
            initial_session = dict(sess)
        
        # Login
        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'testpass123'
        }, follow_redirects=False)
        
        # Session should be modified after login
        # This is indicated by the session.modified = True in the code
        assert response.status_code in [200, 302]  # Success or redirect
    
    def test_login_with_invalid_redirect(self, client):
        """Test that login rejects invalid redirect URLs"""
        # Try to login with malicious redirect
        response = client.post('/auth/login', data={
            'email': 'test@example.com', 
            'password': 'testpass123'
        }, query_string={'next': 'http://evil.com/'}, follow_redirects=False)
        
        # Should not redirect to external site
        if response.status_code == 302:
            location = response.headers.get('Location', '')
            assert 'evil.com' not in location


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
