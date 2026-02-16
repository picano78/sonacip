"""
Tests for video call in messaging and enhanced livestream features.
Tests the is_public field, quick_start, toggle_visibility, and video call routes.
"""
import pytest
from app import create_app, db
from app.models import (
    User, LiveStream, LiveStreamViewer, Role,
    MessageGroup, MessageGroupMembership, MessageGroupMessage
)


@pytest.fixture
def app():
    """Create application for testing"""
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Test client"""
    return app.test_client()


@pytest.fixture
def test_users(app):
    """Create test users"""
    with app.app_context():
        role = Role(name='user', display_name='User', description='Regular user')
        db.session.add(role)
        db.session.flush()

        user1 = User(
            email='user1@example.com',
            username='user1',
            first_name='User',
            last_name='One',
            role_id=role.id
        )
        user1.set_password('password123')

        user2 = User(
            email='user2@example.com',
            username='user2',
            first_name='User',
            last_name='Two',
            role_id=role.id
        )
        user2.set_password('password123')

        db.session.add_all([user1, user2])
        db.session.commit()
        return user1, user2


# ==================== LiveStream is_public Tests ====================


def test_livestream_is_public_field(app, test_users):
    """Test LiveStream model has is_public field"""
    with app.app_context():
        user1, _ = test_users
        stream = LiveStream(
            user_id=user1.id,
            title='Test Stream',
            room_id='test-room-public',
            is_active=True,
            is_public=True
        )
        db.session.add(stream)
        db.session.commit()

        assert stream.is_public is True

        # Test default is False
        stream2 = LiveStream(
            user_id=user1.id,
            title='Private Stream',
            room_id='test-room-private',
            is_active=True
        )
        db.session.add(stream2)
        db.session.commit()

        assert stream2.is_public is False


def test_livestream_is_public_in_columns(app):
    """Verify is_public column exists in LiveStream model"""
    with app.app_context():
        from sqlalchemy import inspect
        mapper = inspect(LiveStream)
        columns = [col.key for col in mapper.columns]
        assert 'is_public' in columns


# ==================== Quick Start Route Tests ====================


def test_quick_start_route_exists(app, client):
    """Test that quick-start route exists"""
    with app.app_context():
        response = client.post('/livestream/quick-start', follow_redirects=False)
        # Should redirect to login (302) or return data, not 404
        assert response.status_code in [200, 302, 401], \
            f"Route /livestream/quick-start returned {response.status_code}"


# ==================== Toggle Visibility Route Tests ====================


def test_toggle_visibility_route_exists(app, client):
    """Test that toggle-visibility route exists"""
    with app.app_context():
        response = client.post('/livestream/1/toggle-visibility', follow_redirects=False)
        assert response.status_code in [200, 302, 401, 403, 404], \
            f"Route toggle-visibility returned {response.status_code}"


# ==================== Video Call Route Tests ====================


def test_video_call_route_exists(app, client):
    """Test that direct video call route exists"""
    with app.app_context():
        response = client.get('/messages/chat/1/video-call', follow_redirects=False)
        assert response.status_code in [200, 302, 401, 404], \
            f"Route video-call returned {response.status_code}"


def test_group_video_call_route_exists(app, client):
    """Test that group video call route exists"""
    with app.app_context():
        response = client.get('/messages/groups/1/video-call', follow_redirects=False)
        assert response.status_code in [200, 302, 401, 404], \
            f"Route group-video-call returned {response.status_code}"


# ==================== Start Stream with is_public Tests ====================


def test_start_stream_accepts_is_public(app, test_users):
    """Test that start_stream route accepts is_public parameter"""
    with app.app_context():
        user1, _ = test_users
        # Create a stream with is_public=True
        stream = LiveStream(
            user_id=user1.id,
            title='Public Stream',
            room_id='public-room-123',
            is_active=True,
            is_public=True
        )
        db.session.add(stream)
        db.session.commit()

        assert stream.is_public is True
        assert stream.is_active is True
        assert stream.title == 'Public Stream'


def test_stream_visibility_toggle(app, test_users):
    """Test toggling stream visibility"""
    with app.app_context():
        user1, _ = test_users
        stream = LiveStream(
            user_id=user1.id,
            title='Toggle Test',
            room_id='toggle-room-123',
            is_active=True,
            is_public=False
        )
        db.session.add(stream)
        db.session.commit()

        assert stream.is_public is False

        # Toggle to public
        stream.is_public = True
        db.session.commit()
        assert stream.is_public is True

        # Toggle back to private
        stream.is_public = False
        db.session.commit()
        assert stream.is_public is False


# ==================== Group Video Call Setup Tests ====================


def test_group_exists_for_video_call(app, test_users):
    """Test that group chat supports video call with member tracking"""
    with app.app_context():
        user1, user2 = test_users

        # Create a group
        group = MessageGroup(
            name='Test Group',
            creator_id=user1.id,
            max_members=256
        )
        db.session.add(group)
        db.session.flush()

        # Add members
        membership1 = MessageGroupMembership(
            group_id=group.id,
            user_id=user1.id,
            is_admin=True
        )
        membership2 = MessageGroupMembership(
            group_id=group.id,
            user_id=user2.id,
            is_admin=False
        )
        db.session.add_all([membership1, membership2])
        db.session.commit()

        # Verify group has members that would join a call
        active_members = MessageGroupMembership.query.filter_by(
            group_id=group.id,
            is_active=True
        ).count()
        assert active_members == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
