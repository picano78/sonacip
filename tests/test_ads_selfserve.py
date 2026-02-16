"""
Tests for the automated ad creation system:
- Model fields (target_audience, payment_status, min/max duration)
- Self-serve ad creation with audience targeting, duration, pricing
- Expired ads cleanup
- Ad delivery audience filtering
"""
import io
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    os.environ.setdefault('SUPERADMIN_EMAIL', 'Picano78@gmail.com')
    os.environ.setdefault('SUPERADMIN_PASSWORD', 'Simone78')
    from app import create_app, db as _db
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SERVER_NAME'] = 'localhost'
    app.config['SECRET_KEY'] = 'test-secret'

    with app.app_context():
        _db.create_all()
        from app.core.seed import seed_defaults
        seed_defaults(app)
        yield app
        _db.session.close()
        _db.session.remove()
        _db.engine.dispose()
        _db.drop_all()


@pytest.fixture
def db(app):
    from app import db as _db
    return _db


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def test_user(app, db):
    from app.models import User, Role
    with app.app_context():
        role = Role.query.filter_by(name='user').first()
        if not role:
            role = Role.query.first()
        user = User(
            email='aduser@test.com',
            username='aduser',
            first_name='Ad',
            last_name='User',
            is_active=True,
            email_confirmed=True,
            role_id=role.id if role else None,
        )
        user.set_password('testpass123')
        db.session.add(user)
        db.session.commit()
        return user


def _login(client, email='aduser@test.com', password='testpass123'):
    return client.post('/auth/login', data={
        'identifier': email,
        'password': password,
    }, follow_redirects=True)


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------

class TestAdModels:
    """Verify new model fields exist and have correct defaults."""

    def test_ads_setting_duration_bounds(self, app, db):
        from app.models import AdsSetting
        with app.app_context():
            s = AdsSetting.query.first()
            if not s:
                s = AdsSetting()
                db.session.add(s)
                db.session.commit()
            assert hasattr(s, 'min_duration_days')
            assert hasattr(s, 'max_duration_days')
            # defaults
            assert (s.min_duration_days or 1) >= 1
            assert (s.max_duration_days or 90) >= 1

    def test_ad_campaign_target_audience(self, app, db):
        from app.models import AdCampaign
        with app.app_context():
            c = AdCampaign(name='Test', target_audience='societies', payment_status='pending')
            db.session.add(c)
            db.session.commit()
            assert c.target_audience == 'societies'
            assert c.payment_status == 'pending'

    def test_ad_campaign_defaults(self, app, db):
        from app.models import AdCampaign
        with app.app_context():
            c = AdCampaign(name='Defaults Test')
            db.session.add(c)
            db.session.commit()
            assert c.target_audience == 'all'
            assert c.payment_status == 'completed'


# ---------------------------------------------------------------------------
# Route Tests
# ---------------------------------------------------------------------------

class TestSelfServeRoutes:
    """Test self-serve ad creation routes."""

    def test_selfserve_requires_login(self, client):
        resp = client.get('/ads/selfserve')
        assert resp.status_code in (302, 401)

    def test_selfserve_dashboard_accessible(self, app, client, test_user, db):
        with app.app_context():
            _login(client)
            resp = client.get('/ads/selfserve')
            assert resp.status_code == 200

    def test_selfserve_create_ad(self, app, client, test_user, db):
        from app.models import AdCampaign, AdCreative
        with app.app_context():
            _login(client)
            resp = client.post('/ads/selfserve/new', data={
                'name': 'My Ad',
                'placement': 'feed_inline',
                'link_url': '/',
                'headline': 'Test Headline',
                'body': 'Test Body',
                'target_audience': 'societies',
                'duration_days': '7',
            }, follow_redirects=True)
            assert resp.status_code == 200

            camp = AdCampaign.query.filter_by(name='My Ad').first()
            assert camp is not None
            assert camp.target_audience == 'societies'
            assert camp.ends_at is not None
            assert camp.is_self_serve is True
            # Without Stripe, campaign should be activated immediately
            assert camp.is_active is True
            assert camp.payment_status == 'completed'

            creative = AdCreative.query.filter_by(campaign_id=camp.id).first()
            assert creative is not None
            assert creative.headline == 'Test Headline'

    def test_selfserve_invalid_audience_defaults_to_all(self, app, client, test_user, db):
        from app.models import AdCampaign
        with app.app_context():
            _login(client)
            client.post('/ads/selfserve/new', data={
                'name': 'Bad Audience',
                'placement': 'feed_inline',
                'link_url': '/',
                'target_audience': 'invalid_value',
                'duration_days': '5',
            }, follow_redirects=True)
            camp = AdCampaign.query.filter_by(name='Bad Audience').first()
            assert camp is not None
            assert camp.target_audience == 'all'

    def test_selfserve_duration_clamped_by_admin_settings(self, app, client, test_user, db):
        from app.models import AdCampaign, AdsSetting
        with app.app_context():
            settings = AdsSetting.query.first()
            if not settings:
                settings = AdsSetting()
                db.session.add(settings)
            settings.min_duration_days = 3
            settings.max_duration_days = 30
            settings.price_per_day = 10.0
            db.session.commit()

            _login(client)
            # Try duration = 1 (below min 3)
            client.post('/ads/selfserve/new', data={
                'name': 'Clamped Min',
                'placement': 'feed_inline',
                'link_url': '/',
                'duration_days': '1',
            }, follow_redirects=True)
            camp = AdCampaign.query.filter_by(name='Clamped Min').first()
            assert camp is not None
            # Duration should be clamped to min (3 days) → budget = 3 * 10 * 100 = 3000 cents
            assert camp.budget_cents == 3000

            # Try duration = 100 (above max 30)
            client.post('/ads/selfserve/new', data={
                'name': 'Clamped Max',
                'placement': 'feed_inline',
                'link_url': '/',
                'duration_days': '100',
            }, follow_redirects=True)
            camp2 = AdCampaign.query.filter_by(name='Clamped Max').first()
            assert camp2 is not None
            # Duration should be clamped to max (30 days) → budget = 30 * 10 * 100 = 30000 cents
            assert camp2.budget_cents == 30000

    def test_selfserve_topup_requires_owner(self, app, client, test_user, db):
        from app.models import AdCampaign
        with app.app_context():
            # Create a campaign owned by a different user
            camp = AdCampaign(
                name='Other User Ad',
                is_self_serve=True,
                advertiser_user_id=9999,  # not our user
            )
            db.session.add(camp)
            db.session.commit()

            _login(client)
            resp = client.post(f'/ads/selfserve/{camp.id}/topup', data={
                'amount_eur': '10',
            })
            assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Cleanup Tests
# ---------------------------------------------------------------------------

class TestExpiredAdsCleanup:
    """Test the automatic cleanup of expired ad campaigns."""

    def test_cleanup_deactivates_expired_campaigns(self, app, db):
        from app.models import AdCampaign, AdCreative
        from app.ads.automation import cleanup_expired_ads

        with app.app_context():
            past = datetime.now(timezone.utc) - timedelta(days=1)
            camp = AdCampaign(
                name='Expired Ad',
                is_active=True,
                starts_at=past - timedelta(days=10),
                ends_at=past,
            )
            db.session.add(camp)
            db.session.flush()

            creative = AdCreative(
                campaign_id=camp.id,
                placement='feed_inline',
                link_url='/',
                is_active=True,
            )
            db.session.add(creative)
            db.session.commit()

            cleaned = cleanup_expired_ads()
            assert cleaned >= 1

            db.session.refresh(camp)
            assert camp.is_active is False

    def test_cleanup_ignores_active_campaigns(self, app, db):
        from app.models import AdCampaign
        from app.ads.automation import cleanup_expired_ads

        with app.app_context():
            future = datetime.now(timezone.utc) + timedelta(days=10)
            camp = AdCampaign(
                name='Active Ad',
                is_active=True,
                starts_at=datetime.now(timezone.utc),
                ends_at=future,
            )
            db.session.add(camp)
            db.session.commit()

            cleanup_expired_ads()

            db.session.refresh(camp)
            assert camp.is_active is True


# ---------------------------------------------------------------------------
# Audience Targeting Tests
# ---------------------------------------------------------------------------

class TestAudienceTargeting:
    """Test ad delivery filters by audience."""

    def test_eligible_creatives_filters_by_audience(self, app, db):
        from app.models import AdCampaign, AdCreative
        from app.ads.utils import _eligible_creatives

        with app.app_context():
            now = datetime.now(timezone.utc)
            # Campaign targeting societies only
            camp = AdCampaign(
                name='Societies Only',
                is_active=True,
                target_audience='societies',
                payment_status='completed',
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(days=7),
            )
            db.session.add(camp)
            db.session.flush()
            creative = AdCreative(
                campaign_id=camp.id,
                placement='feed_inline',
                link_url='/',
                is_active=True,
            )
            db.session.add(creative)
            db.session.commit()

            # Society user should see it
            class FakeSocietyUser:
                role = 'societa'

            results = _eligible_creatives('feed_inline', None, user=FakeSocietyUser())
            assert any(c.campaign_id == camp.id for c in results)

            # Regular user should NOT see it
            class FakeRegularUser:
                role = 'user'

            results2 = _eligible_creatives('feed_inline', None, user=FakeRegularUser())
            assert not any(c.campaign_id == camp.id for c in results2)

    def test_all_audience_visible_to_everyone(self, app, db):
        from app.models import AdCampaign, AdCreative
        from app.ads.utils import _eligible_creatives

        with app.app_context():
            now = datetime.now(timezone.utc)
            camp = AdCampaign(
                name='For Everyone',
                is_active=True,
                target_audience='all',
                payment_status='completed',
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(days=7),
            )
            db.session.add(camp)
            db.session.flush()
            creative = AdCreative(
                campaign_id=camp.id,
                placement='sidebar_card',
                link_url='/',
                is_active=True,
            )
            db.session.add(creative)
            db.session.commit()

            class FakeUser:
                role = 'athlete'

            results = _eligible_creatives('sidebar_card', None, user=FakeUser())
            assert any(c.campaign_id == camp.id for c in results)

    def test_pending_payment_not_shown(self, app, db):
        from app.models import AdCampaign, AdCreative
        from app.ads.utils import _eligible_creatives

        with app.app_context():
            now = datetime.now(timezone.utc)
            camp = AdCampaign(
                name='Unpaid Ad',
                is_active=True,
                target_audience='all',
                payment_status='pending',
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(days=7),
            )
            db.session.add(camp)
            db.session.flush()
            db.session.add(AdCreative(
                campaign_id=camp.id,
                placement='feed_inline',
                link_url='/',
                is_active=True,
            ))
            db.session.commit()

            results = _eligible_creatives('feed_inline', None)
            assert not any(c.campaign_id == camp.id for c in results)
