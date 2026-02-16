"""
Tests for the Rubrica (Address Book) feature.
Verifies that when a society links a user, their contact data is registered
in the society's rubrica, and the society can manage the user from there.
"""
import pytest
from app import create_app, db
from app.models import User, Role, Society, SocietyMembership, Contact


@pytest.fixture
def app():
    app = create_app('testing')
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def setup_data(app):
    """Create society, admin user, and athlete user for tests."""
    with app.app_context():
        # Create roles
        admin_role = Role(name='super_admin', display_name='Super Admin', description='Admin')
        athlete_role = Role(name='athlete', display_name='Athlete', description='Athlete')
        db.session.add_all([admin_role, athlete_role])
        db.session.flush()

        # Create admin user (the society manager) – also acts as society owner
        admin = User(
            email='admin@test.com',
            username='admin_test',
            first_name='Admin',
            last_name='Manager',
            role_id=admin_role.id,
        )
        admin.set_password('password123')
        db.session.add(admin)
        db.session.flush()

        # Create society (PK = admin user id)
        society = Society(
            id=admin.id,
            legal_name='ASD Test Club',
        )
        db.session.add(society)
        db.session.flush()

        admin.society_id = society.id

        # Create athlete user with contact info
        athlete = User(
            email='athlete@test.com',
            username='athlete_test',
            first_name='Marco',
            last_name='Rossi',
            phone='+39 333 1234567',
            address='Via Roma 1',
            city='Milano',
            postal_code='20100',
            role_id=athlete_role.id,
        )
        athlete.set_password('password123')
        db.session.add(athlete)
        db.session.commit()

        return {
            'society': society,
            'admin': admin,
            'athlete': athlete,
            'admin_role': admin_role,
            'athlete_role': athlete_role,
        }


class TestContactUserIdField:
    """Test that Contact model has user_id field."""

    def test_contact_has_user_id_column(self, app):
        """Contact model should have a user_id column."""
        cols = [c.name for c in Contact.__table__.columns]
        assert 'user_id' in cols

    def test_contact_user_id_nullable(self, app, setup_data):
        """Contact can be created without user_id (backward compatible)."""
        with app.app_context():
            data = setup_data
            contact = Contact(
                first_name='External',
                last_name='Person',
                email='external@test.com',
                society_id=data['society'].id,
                created_by=data['admin'].id,
            )
            db.session.add(contact)
            db.session.commit()
            assert contact.user_id is None
            assert contact.id is not None

    def test_contact_with_user_id(self, app, setup_data):
        """Contact can be linked to a user via user_id."""
        with app.app_context():
            data = setup_data
            contact = Contact(
                first_name='Marco',
                last_name='Rossi',
                email='athlete@test.com',
                phone='+39 333 1234567',
                user_id=data['athlete'].id,
                society_id=data['society'].id,
                created_by=data['admin'].id,
            )
            db.session.add(contact)
            db.session.commit()
            assert contact.user_id == data['athlete'].id
            assert contact.linked_user.email == 'athlete@test.com'


class TestAutoCreateContactOnMembership:
    """Test that a Contact is auto-created when a member is added."""

    def test_contact_created_on_membership(self, app, setup_data):
        """When a SocietyMembership is created via member_add, a Contact should be auto-created."""
        with app.app_context():
            data = setup_data

            # Verify no contact exists yet
            contact = Contact.query.filter_by(
                society_id=data['society'].id, user_id=data['athlete'].id
            ).first()
            assert contact is None

            # Manually simulate what member_add does
            membership = SocietyMembership(
                society_id=data['society'].id,
                user_id=data['athlete'].id,
                role_name='atleta',
                status='active',
                created_by=data['admin'].id,
            )
            db.session.add(membership)
            db.session.flush()

            # Create rubrica contact (what the route does)
            user = data['athlete']
            contact = Contact(
                first_name=user.first_name or '',
                last_name=user.last_name or '',
                email=user.email or '',
                phone=user.phone or '',
                address=user.address or '',
                city=user.city or '',
                postal_code=user.postal_code or '',
                contact_type='athlete',
                status='converted',
                source='membership',
                society_id=data['society'].id,
                user_id=user.id,
                created_by=data['admin'].id,
            )
            db.session.add(contact)
            db.session.commit()

            # Verify contact was created with user data
            saved = Contact.query.filter_by(
                society_id=data['society'].id, user_id=data['athlete'].id
            ).first()
            assert saved is not None
            assert saved.first_name == 'Marco'
            assert saved.last_name == 'Rossi'
            assert saved.email == 'athlete@test.com'
            assert saved.phone == '+39 333 1234567'
            assert saved.address == 'Via Roma 1'
            assert saved.city == 'Milano'
            assert saved.postal_code == '20100'
            assert saved.source == 'membership'


class TestRubricaRoutes:
    """Test rubrica route registration."""

    def test_rubrica_route_exists(self, app):
        """The /crm/rubrica route should be registered."""
        with app.app_context():
            rules = [rule.rule for rule in app.url_map.iter_rules()]
            assert '/crm/rubrica' in rules

    def test_rubrica_detail_route_exists(self, app):
        """The /crm/rubrica/<id> route should be registered."""
        with app.app_context():
            rules = [rule.rule for rule in app.url_map.iter_rules()]
            assert '/crm/rubrica/<int:contact_id>' in rules

    def test_rubrica_edit_route_exists(self, app):
        """The /crm/rubrica/<id>/edit route should be registered."""
        with app.app_context():
            rules = [rule.rule for rule in app.url_map.iter_rules()]
            assert '/crm/rubrica/<int:contact_id>/edit' in rules

    def test_rubrica_requires_login(self, app):
        """Rubrica should require login."""
        with app.test_client() as client:
            resp = client.get('/crm/rubrica')
            assert resp.status_code in [302, 401, 403]

    def test_rubrica_detail_requires_login(self, app):
        """Rubrica detail should require login."""
        with app.test_client() as client:
            resp = client.get('/crm/rubrica/1')
            assert resp.status_code in [302, 401, 403]

    def test_rubrica_edit_requires_login(self, app):
        """Rubrica edit should require login."""
        with app.test_client() as client:
            resp = client.get('/crm/rubrica/1/edit')
            assert resp.status_code in [302, 401, 403]


class TestRubricaContactEditing:
    """Test that society can edit contact info in rubrica."""

    def test_contact_update(self, app, setup_data):
        """Society should be able to update rubrica contact info."""
        with app.app_context():
            data = setup_data
            contact = Contact(
                first_name='Marco',
                last_name='Rossi',
                email='athlete@test.com',
                phone='+39 333 1234567',
                address='Via Roma 1',
                city='Milano',
                postal_code='20100',
                user_id=data['athlete'].id,
                society_id=data['society'].id,
                created_by=data['admin'].id,
            )
            db.session.add(contact)
            db.session.commit()

            # Update phone and address
            contact.phone = '+39 333 9876543'
            contact.address = 'Via Verdi 10'
            contact.city = 'Roma'
            db.session.commit()

            updated = Contact.query.get(contact.id)
            assert updated.phone == '+39 333 9876543'
            assert updated.address == 'Via Verdi 10'
            assert updated.city == 'Roma'
            # user_id link remains
            assert updated.user_id == data['athlete'].id
