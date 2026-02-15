"""
Pytest configuration and fixtures for all tests.
Sets up default environment variables for testing.
"""
import os
import sys
from pathlib import Path
import pytest

# Ensure project root is importable for all tests
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def clean_config_state():
    """Ensure app.core.config is reloaded fresh for each test."""
    sys.modules.pop('app.core.config', None)
    try:
        import app.core  # type: ignore
        if hasattr(app.core, 'config'):
            delattr(app.core, 'config')
    except (ImportError, AttributeError):
        pass
    yield
    sys.modules.pop('app.core.config', None)
    try:
        import app.core  # type: ignore
        if hasattr(app.core, 'config'):
            delattr(app.core, 'config')
    except (ImportError, AttributeError):
        pass


def pytest_configure(config):
    """
    Configure pytest and set up test environment.
    This runs before test collection, so environment variables are available
    when config modules are imported.
    
    Note: Some tests explicitly test environment variable behavior and will
    override these defaults using mock.patch.dict.
    """
    # Set default test credentials only if not in a test that explicitly
    # tests environment variable handling
    # Only set if not already set (allows tests to override)
    os.environ.setdefault('SUPERADMIN_EMAIL', 'Picano78@gmail.com')
    os.environ.setdefault('SUPERADMIN_PASSWORD', 'Simone78')
