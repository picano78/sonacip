"""
Test admin refresh cache and restart site routes.
"""
import pytest
from unittest.mock import patch
from app import create_app, db
from app.models import User, Role


TEST_ADMIN_EMAIL = 'Picano78@gmail.com'
TEST_ADMIN_PASSWORD = 'Simone78'


class TestAdminRefreshRestart:
    """Test refresh cache and restart site admin actions."""

    @pytest.fixture
    def app(self):
        app = create_app('testing')
        with app.app_context():
            db.create_all()
            from app.core.seed import seed_defaults
            seed_defaults(app)
            yield app
            db.session.close()
            db.session.remove()
            db.engine.dispose()

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    @pytest.fixture
    def logged_in_client(self, client):
        client.post('/auth/login', data={
            'identifier': TEST_ADMIN_EMAIL,
            'password': TEST_ADMIN_PASSWORD,
        }, follow_redirects=True)
        return client

    def test_refresh_cache_requires_login(self, client):
        """Unauthenticated users should be redirected."""
        resp = client.post('/admin/refresh-cache', follow_redirects=False)
        assert resp.status_code in (302, 401)

    def test_refresh_cache_clears_cache(self, logged_in_client, app):
        """POST /admin/refresh-cache should clear the cache and redirect."""
        from app.cache import get_cache
        with app.app_context():
            cache = get_cache()
            cache.set('test_key', 'test_value', ttl=300)
            assert cache.get('test_key') == 'test_value'

            resp = logged_in_client.post('/admin/refresh-cache', follow_redirects=False)
            assert resp.status_code == 302
            assert '/admin/dashboard' in resp.headers.get('Location', '')
            assert cache.get('test_key') is None

    def test_restart_site_requires_login(self, client):
        """Unauthenticated users should be redirected."""
        resp = client.post('/admin/restart-site', follow_redirects=False)
        assert resp.status_code in (302, 401)

    @patch('builtins.open', side_effect=FileNotFoundError)
    @patch('app.admin.routes.os.kill')
    @patch('app.admin.routes.os.getppid', return_value=12345)
    def test_restart_site_sends_sighup(self, mock_getppid, mock_kill, mock_open, logged_in_client, app):
        """POST /admin/restart-site should send SIGHUP to the parent process."""
        import signal
        with app.app_context():
            resp = logged_in_client.post('/admin/restart-site', follow_redirects=False)
            assert resp.status_code == 302
            assert '/admin/dashboard' in resp.headers.get('Location', '')
            mock_kill.assert_called_once_with(12345, signal.SIGHUP)

    def test_refresh_cache_get_not_allowed(self, logged_in_client):
        """GET should not be allowed on the refresh-cache endpoint."""
        resp = logged_in_client.get('/admin/refresh-cache')
        assert resp.status_code in (405, 500)

    def test_restart_site_get_not_allowed(self, logged_in_client):
        """GET should not be allowed on the restart-site endpoint."""
        resp = logged_in_client.get('/admin/restart-site')
        assert resp.status_code in (405, 500)
