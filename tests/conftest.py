"""
Pytest configuration and fixtures for all tests.
Sets up default environment variables for testing.
"""
import os


def pytest_configure(config):
    """
    Configure pytest and set up test environment.
    This runs before test collection, so environment variables are available
    when config modules are imported.
    
    Note: Some tests explicitly test environment variable behavior and will
    override these defaults using mock.patch.dict.
    """
    # Set default test credentials for tests that need them
    # Use test-specific values that are clearly not production credentials
    # Only set if not already set (allows tests to override)
    os.environ.setdefault('SUPERADMIN_EMAIL', 'test@example.com')
    os.environ.setdefault('SUPERADMIN_PASSWORD', 'TestPassword123!')
