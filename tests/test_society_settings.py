"""
Test society settings – year-end member policy.
"""
import pytest
from app import create_app, db
from app.models import User, Society, Role, Permission


@pytest.fixture
def app():
    app = create_app('testing')
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def society_user(app):
    """Create an authenticated society user with required permission rows."""
    with app.app_context():
        role = Role(name='societa', display_name='Società', level=40)
        db.session.add(role)
        db.session.flush()

        # Seed the permission row needed by check_permission
        perm = Permission(name='society_manage', resource='society', action='manage')
        db.session.add(perm)

        user = User(
            email='society@example.com',
            username='socuser',
            first_name='Soc',
            last_name='User',
            role_id=role.id,
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.flush()

        society = Society(
            id=user.id,
            legal_name='Test Society',
            company_type='ASD',
        )
        db.session.add(society)
        db.session.flush()

        user.society_id = society.id
        db.session.commit()

        return user, society


def test_society_model_default_policy(app, society_user):
    """members_year_end_policy defaults to 'keep'."""
    _, society = society_user
    with app.app_context():
        s = db.session.get(Society, society.id)
        assert s.members_year_end_policy == 'keep'


def test_settings_get_requires_login(client):
    """GET /social/society/settings redirects unauthenticated users."""
    resp = client.get('/social/society/settings', follow_redirects=False)
    assert resp.status_code in (302, 308)


def test_settings_get_page(client, society_user):
    """Authenticated society user can view settings page."""
    user, _ = society_user
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)

    resp = client.get('/social/society/settings')
    assert resp.status_code == 200
    assert 'Gestione Membri a Fine Anno'.encode() in resp.data


def test_settings_post_keep(client, society_user):
    """POST with policy=keep persists value."""
    user, society = society_user
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)

    resp = client.post('/social/society/settings', data={
        'members_year_end_policy': 'keep',
    }, follow_redirects=True)
    assert resp.status_code == 200

    with client.application.app_context():
        s = db.session.get(Society, society.id)
        assert s.members_year_end_policy == 'keep'


def test_settings_post_remove(client, society_user):
    """POST with policy=remove persists value."""
    user, society = society_user
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)

    resp = client.post('/social/society/settings', data={
        'members_year_end_policy': 'remove',
    }, follow_redirects=True)
    assert resp.status_code == 200

    with client.application.app_context():
        s = db.session.get(Society, society.id)
        assert s.members_year_end_policy == 'remove'


def test_settings_post_invalid_falls_back_to_keep(client, society_user):
    """POST with an invalid policy value falls back to 'keep'."""
    user, society = society_user
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)

    resp = client.post('/social/society/settings', data={
        'members_year_end_policy': 'invalid_value',
    }, follow_redirects=True)
    assert resp.status_code == 200

    with client.application.app_context():
        s = db.session.get(Society, society.id)
        assert s.members_year_end_policy == 'keep'


def test_dashboard_has_settings_button(client, society_user):
    """Society dashboard contains a link to the settings page."""
    user, _ = society_user
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)

    resp = client.get('/social/society/dashboard')
    assert resp.status_code == 200
    assert b'society/settings' in resp.data
    assert 'Impostazioni'.encode() in resp.data
