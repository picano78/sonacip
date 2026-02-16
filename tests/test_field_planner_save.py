"""
Test field planner save operations (create/edit) do not return 500 errors.
Regression tests for the legacy URL POST fix and error handling.
"""
import pytest
from datetime import datetime, timedelta, time as dt_time


@pytest.fixture
def app():
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SERVER_NAME'] = 'localhost'
    return app


@pytest.fixture
def db_session(app):
    from app import db
    with app.app_context():
        db.create_all()
        yield db.session
        db.session.rollback()
        db.drop_all()


@pytest.fixture
def seeded_client(app, db_session):
    """Create test client with seeded permissions and an authenticated user"""
    from app.models import User, Society, SocietyMembership, Role, Facility, Permission

    # Seed Permission records
    for name, resource, action in [
        ('field_planner:view', 'field_planner', 'view'),
        ('field_planner:manage', 'field_planner', 'manage'),
    ]:
        p = Permission(name=name, resource=resource, action=action, is_active=True)
        db_session.add(p)
    db_session.flush()

    role = Role(name='societa', display_name='Società', level=50)
    db_session.add(role)
    db_session.flush()

    perms = Permission.query.all()
    for p in perms:
        role.permissions.append(p)
    db_session.flush()

    user = User(
        username='testsocieta',
        email='societa@example.com',
        first_name='Test',
        last_name='Societa',
        role_id=role.id
    )
    user.set_password('testpass')
    db_session.add(user)
    db_session.flush()

    society = Society(
        id=user.id,
        legal_name='ASD Test Club',
        vat_number='12345678901'
    )
    db_session.add(society)
    db_session.flush()

    membership = SocietyMembership(
        society_id=society.id,
        user_id=user.id,
        role_name='societa',
        status='active',
        can_manage_planner=True,
        receive_planner_notifications=True
    )
    db_session.add(membership)
    db_session.flush()

    facility = Facility(
        society_id=society.id,
        name='Campo A',
        created_by=user.id
    )
    db_session.add(facility)
    db_session.commit()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)

    return {
        'client': client,
        'user_id': user.id,
        'society_id': society.id,
        'facility_id': facility.id,
    }


def test_create_single_event_no_500(seeded_client):
    """Creating a single event via POST should not return 500"""
    client = seeded_client['client']
    facility_id = seeded_client['facility_id']
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

    resp = client.post('/field_planner/new', data={
        'facility_id': facility_id,
        'event_type': 'training',
        'title': 'Allenamento',
        'start_date': tomorrow,
        'start_time': '10:00',
        'end_time': '12:00',
        'color': '#28a745',
    }, follow_redirects=False)

    assert resp.status_code < 500


def test_create_recurring_event_no_500(seeded_client):
    """Creating a recurring event via POST should not return 500"""
    client = seeded_client['client']
    facility_id = seeded_client['facility_id']
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

    resp = client.post('/field_planner/new', data={
        'facility_id': facility_id,
        'event_type': 'training',
        'title': 'Allenamento Ricorrente',
        'start_date': tomorrow,
        'start_time': '15:00',
        'end_time': '17:00',
        'color': '#28a745',
        'is_recurring': 'y',
        'recurrence_pattern': 'weekly',
    }, follow_redirects=False)

    assert resp.status_code < 500


def test_edit_event_no_500(app, db_session, seeded_client):
    """Editing an event via POST should not return 500"""
    from app.models import FieldPlannerEvent

    data = seeded_client
    client = data['client']
    base_time = datetime.now() + timedelta(days=2)

    event = FieldPlannerEvent(
        society_id=data['society_id'],
        facility_id=data['facility_id'],
        created_by=data['user_id'],
        event_type='training',
        title='Original',
        start_datetime=datetime.combine(base_time.date(), dt_time(10, 0)),
        end_datetime=datetime.combine(base_time.date(), dt_time(12, 0)),
        color='#28a745'
    )
    db_session.add(event)
    db_session.commit()

    resp = client.post(f'/field_planner/event/{event.id}/edit', data={
        'facility_id': data['facility_id'],
        'event_type': 'match',
        'title': 'Partita',
        'start_date': base_time.strftime('%Y-%m-%d'),
        'start_time': '14:00',
        'end_time': '16:00',
        'color': '#0dcaf0',
    }, follow_redirects=False)

    assert resp.status_code < 500


def test_legacy_url_post_no_500(seeded_client):
    """POST to legacy URL /field-planner/new should redirect, not 500"""
    client = seeded_client['client']
    facility_id = seeded_client['facility_id']
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

    resp = client.post('/field-planner/new', data={
        'facility_id': facility_id,
        'event_type': 'training',
        'title': 'Legacy URL Test',
        'start_date': tomorrow,
        'start_time': '10:00',
        'end_time': '12:00',
        'color': '#28a745',
    }, follow_redirects=False)

    assert resp.status_code < 500, f"Legacy POST returned {resp.status_code}"
    assert resp.status_code == 307  # 307 preserves POST method


def test_legacy_url_get_redirects(seeded_client):
    """GET to legacy URL /field-planner/new should redirect with 302"""
    client = seeded_client['client']

    resp = client.get('/field-planner/new', follow_redirects=False)

    assert resp.status_code == 302
    assert '/field_planner/new' in resp.headers.get('Location', '')
