"""
Test the super admin site restart functionality.
"""
import pytest
from app import create_app, db
from app.models import User, Role, AuditLog


TEST_ADMIN_EMAIL = 'Picano78@gmail.com'
TEST_ADMIN_PASSWORD = 'Simone78'


class TestRestartSite:
    """Test the restart-site admin route."""

    @pytest.fixture
    def app(self):
        app = create_app('testing')
        app.config['WTF_CSRF_ENABLED'] = False
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

    def _login(self, client):
        client.post('/auth/login', data={
            'identifier': TEST_ADMIN_EMAIL,
            'password': TEST_ADMIN_PASSWORD,
        }, follow_redirects=True)

    def test_restart_requires_login(self, client):
        """Unauthenticated POST should redirect to login."""
        resp = client.post('/admin/restart-site', follow_redirects=False)
        assert resp.status_code in (302, 303)

    def test_restart_as_admin(self, app, client):
        """Super admin should be able to restart the site."""
        self._login(client)
        resp = client.post('/admin/restart-site', follow_redirects=True)
        assert resp.status_code == 200
        assert 'Riavvio del sito eseguito con successo' in resp.get_data(as_text=True)

    def test_restart_creates_audit_log(self, app, client):
        """Restart action should be logged in audit log."""
        self._login(client)
        with app.app_context():
            before_count = AuditLog.query.filter_by(action='restart_site').count()
        client.post('/admin/restart-site', follow_redirects=True)
        with app.app_context():
            after_count = AuditLog.query.filter_by(action='restart_site').count()
            assert after_count == before_count + 1

    def test_restart_button_visible_on_dashboard(self, app, client):
        """The restart button should appear on the admin dashboard."""
        self._login(client)
        resp = client.get('/admin/dashboard')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Riavvio Sito' in html
        assert '/admin/restart-site' in html
