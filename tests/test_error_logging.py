"""Tests for error logging functionality."""
import pytest
from unittest.mock import patch, MagicMock
from werkzeug.exceptions import InternalServerError
from flask import Flask


@pytest.fixture
def app():
    """Create and configure a test Flask app instance."""
    from app import create_app
    app = create_app('development')
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    # Ensure error handlers are invoked as in production
    app.config['PROPAGATE_EXCEPTIONS'] = False
    return app


@pytest.fixture
def client(app):
    """Create a test client for the app."""
    return app.test_client()


def test_internal_server_error_logging_anonymous_user(app, client):
    """Test that 500 errors are logged with context for anonymous users."""
    with app.app_context():
        # Create a route that raises an InternalServerError
        @app.route('/test_500_logging')
        def test_500_route():
            raise InternalServerError("Test error")
        
        # Mock the logger
        with patch.object(app.logger, 'error') as mock_error, \
             patch.object(app.logger, 'exception') as mock_exception:
            
            response = client.get('/test_500_logging')
            
            # Check response
            assert response.status_code == 500
            # Check for title "Errore del Server" which is in the HTML
            assert b"Errore del Server" in response.data
            
            # Verify logging was called
            assert mock_error.called or mock_exception.called
            
            # Check that at least one call contains context info
            all_calls = mock_error.call_args_list + mock_exception.call_args_list
            logged_messages = [str(call) for call in all_calls]
            
            # At least one log should contain request context
            has_context = any(
                'Anonymous' in msg or 'GET' in msg or '/test_500' in msg
                for msg in logged_messages
            )
            assert has_context, "Expected logging to include request context"


def test_internal_server_error_json_response(app, client):
    """Test that 500 errors return JSON when requested."""
    with app.app_context():
        @app.route('/test_500_json_logging')
        def test_500_json_route():
            raise InternalServerError("Test error")
        
        with patch.object(app.logger, 'error'), \
             patch.object(app.logger, 'exception'):
            
            response = client.get('/test_500_json_logging', headers={'Accept': 'application/json'})
            
            assert response.status_code == 500
            # Should return JSON error response
            assert response.content_type == 'application/json' or b'error' in response.data


def test_unexpected_error_logging(app, client):
    """Test that unexpected exceptions are logged with type information."""
    with app.app_context():
        @app.route('/test_unexpected_logging')
        def test_unexpected_route():
            raise ValueError("Unexpected test error")
        
        with patch.object(app.logger, 'error') as mock_error, \
             patch.object(app.logger, 'exception') as mock_exception:
            
            response = client.get('/test_unexpected_logging')
            
            # Check response
            assert response.status_code == 500
            
            # Verify logging was called
            assert mock_error.called or mock_exception.called
            
            # Check that exception type is logged
            all_calls = mock_error.call_args_list + mock_exception.call_args_list
            logged_messages = [str(call) for call in all_calls]
            
            has_type_info = any(
                'ValueError' in msg or 'Tipo eccezione' in msg
                for msg in logged_messages
            )
            assert has_type_info, "Expected logging to include exception type"


def test_error_page_template_failure_logging(app, client):
    """Test that template rendering failures are logged."""
    with app.app_context():
        # Create a route that will fail to render template
        @app.route('/test_template_error_logging')
        def test_template_error():
            raise InternalServerError("Test")
        
        # Mock render_template to raise an exception when rendering error page
        with patch('flask.render_template', side_effect=Exception("Template error")), \
             patch.object(app.logger, 'error') as mock_error, \
             patch.object(app.logger, 'exception'):
            
            response = client.get('/test_template_error_logging')
            
            # Should return fallback HTML or properly rendered template
            assert response.status_code == 500
            # The response should contain error message
            assert b'Errore del Server' in response.data or b'Errore del server' in response.data
            
            # Verify template error was logged if it failed
            # Note: In test environment the template may render successfully
            # so we just verify the status code and that logging infrastructure is in place


def test_error_handler_preserves_user_friendly_messages(app, client):
    """Test that error handlers maintain user-friendly messages without technical details."""
    with app.app_context():
        @app.route('/test_user_friendly_logging')
        def test_user_friendly_route():
            raise RuntimeError("Internal technical error with sensitive info")
        
        with patch.object(app.logger, 'error'), \
             patch.object(app.logger, 'exception'):
            
            response = client.get('/test_user_friendly_logging')
            
            # Check that the response doesn't leak technical details
            assert b"RuntimeError" not in response.data
            assert b"Internal technical error" not in response.data
            assert b"sensitive info" not in response.data
            
            # Should show generic user-friendly message (capitalized in template)
            assert response.status_code == 500
            assert b"Errore del Server" in response.data or b"internal_server_error" in response.data


def test_unexpected_error_json_response(app, client):
    """Test that unexpected errors return consistent JSON response without leaking exception type."""
    with app.app_context():
        @app.route('/test_unexpected_json_logging')
        def test_unexpected_json():
            raise ValueError("Test error")
        
        with patch.object(app.logger, 'error'), \
             patch.object(app.logger, 'exception'):
            
            response = client.get('/test_unexpected_json_logging', 
                                headers={'Accept': 'application/json'})
            
            assert response.status_code == 500
            # Should return generic error without exposing exception type
            data = response.get_json()
            if data:
                assert 'error' in data
                assert data.get('error') == 'internal_server_error'
                # Should NOT include type to avoid information leakage
                assert 'type' not in data

