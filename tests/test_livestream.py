"""
Tests for Live Streaming feature
Verifies basic functionality of livestream routes and models
"""
import pytest
from datetime import datetime, timezone
from app import create_app, db
from app.models import User, LiveStream, LiveStreamViewer


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
def authenticated_user(app):
    """Create and login a test user"""
    with app.app_context():
        # Create a default role first
        from app.models import Role
        role = Role(name='user', display_name='User', description='Regular user')
        db.session.add(role)
        db.session.flush()
        
        user = User(
            email='test@example.com',
            username='testuser',
            first_name='Test',
            last_name='User',
            role_id=role.id
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        return user


def test_livestream_model_creation(app):
    """Test LiveStream model can be created"""
    with app.app_context():
        from app.models import Role
        role = Role(name='user', display_name='User', description='Regular user')
        db.session.add(role)
        db.session.flush()
        
        user = User(
            email='streamer@example.com',
            username='streamer',
            first_name='Live',
            last_name='Streamer',
            role_id=role.id
        )
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
        
        stream = LiveStream(
            user_id=user.id,
            title='Test Stream',
            description='This is a test stream',
            room_id='test-room-123',
            is_active=True
        )
        db.session.add(stream)
        db.session.commit()
        
        assert stream.id is not None
        assert stream.title == 'Test Stream'
        assert stream.is_active is True
        assert stream.room_id == 'test-room-123'


def test_livestream_viewer_tracking(app):
    """Test LiveStreamViewer model for analytics"""
    with app.app_context():
        from app.models import Role
        role = Role(name='user', display_name='User', description='Regular user')
        db.session.add(role)
        db.session.flush()
        
        # Create streamer
        streamer = User(
            email='streamer@example.com',
            username='streamer',
            first_name='Live',
            last_name='Streamer',
            role_id=role.id
        )
        streamer.set_password('password')
        db.session.add(streamer)
        
        # Create viewer
        viewer = User(
            email='viewer@example.com',
            username='viewer',
            first_name='View',
            last_name='Er',
            role_id=role.id
        )
        viewer.set_password('password')
        db.session.add(viewer)
        db.session.commit()
        
        # Create stream
        stream = LiveStream(
            user_id=streamer.id,
            title='Test Stream',
            room_id='test-room-456',
            is_active=True
        )
        db.session.add(stream)
        db.session.commit()
        
        # Track viewer
        viewer_record = LiveStreamViewer(
            stream_id=stream.id,
            viewer_id=viewer.id
        )
        db.session.add(viewer_record)
        db.session.commit()
        
        assert viewer_record.id is not None
        assert viewer_record.stream_id == stream.id
        assert viewer_record.viewer_id == viewer.id
        assert viewer_record.left_at is None


def test_livestream_duration_calculation(app):
    """Test stream duration calculation"""
    with app.app_context():
        from app.models import Role
        role = Role(name='user', display_name='User', description='Regular user')
        db.session.add(role)
        db.session.flush()
        
        user = User(
            email='streamer@example.com',
            username='streamer',
            first_name='Live',
            last_name='Streamer',
            role_id=role.id
        )
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
        
        stream = LiveStream(
            user_id=user.id,
            title='Test Stream',
            room_id='test-room-789',
            is_active=True
        )
        db.session.add(stream)
        db.session.commit()
        
        # Duration should be >= 0 for active stream
        assert stream.duration_seconds >= 0


def test_livestream_blueprint_registered(app):
    """Test that livestream blueprint is registered"""
    assert 'livestream' in [bp.name for bp in app.blueprints.values()]


def test_livestream_routes_exist(app, client):
    """Test that main livestream routes are accessible"""
    with app.app_context():
        # These routes should exist (may require auth)
        routes = [
            '/livestream/',
            '/livestream/active',
        ]
        
        for route in routes:
            response = client.get(route, follow_redirects=False)
            # Should redirect to login (302) or return data (200), not 404
            assert response.status_code in [200, 302, 401], f"Route {route} returned {response.status_code}"


def test_no_video_storage_in_model(app):
    """Verify that LiveStream model does NOT have video storage fields"""
    with app.app_context():
        from app.models import LiveStream
        from sqlalchemy import inspect
        
        # Get all column names
        mapper = inspect(LiveStream)
        columns = [col.key for col in mapper.columns]
        
        # Ensure no video/media storage columns exist
        forbidden_columns = ['video_url', 'video_data', 'media_file', 'video_path', 'stream_data']
        for col in forbidden_columns:
            assert col not in columns, f"Found video storage column '{col}' - violates no-storage requirement"
        
        # Verify only metadata columns exist
        assert 'title' in columns
        assert 'room_id' in columns
        assert 'is_active' in columns
        assert 'viewer_count' in columns


def test_stream_metadata_only(app):
    """Test that streams only store metadata, not video data"""
    with app.app_context():
        from app.models import Role
        role = Role(name='user', display_name='User', description='Regular user')
        db.session.add(role)
        db.session.flush()
        
        user = User(
            email='streamer@example.com',
            username='streamer',
            first_name='Live',
            last_name='Streamer',
            role_id=role.id
        )
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
        
        stream = LiveStream(
            user_id=user.id,
            title='Metadata Only Test',
            description='Testing metadata storage',
            room_id='metadata-test-123',
            is_active=True
        )
        db.session.add(stream)
        db.session.commit()
        
        # Verify only metadata is stored
        assert hasattr(stream, 'title')
        assert hasattr(stream, 'description')
        assert hasattr(stream, 'room_id')
        assert hasattr(stream, 'viewer_count')
        assert hasattr(stream, 'peak_viewers')
        
        # Verify NO video data storage
        assert not hasattr(stream, 'video_data')
        assert not hasattr(stream, 'video_url')
        assert not hasattr(stream, 'media_file')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
