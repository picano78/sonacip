"""
Test post photo retention feature.
Admin can configure photo_retention_hours (0=forever, 12, 24, 36, 48).
When a user posts a photo, they are notified of the expiry time.
Expired photos are deleted from disk by the cleanup task.
"""
import io
import os
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from PIL import Image

from app import create_app, db
from app.models import (
    Role, User, Post, Notification, SocialSetting, StorageSetting,
)


def _make_test_image():
    """Create a minimal in-memory JPEG for upload tests."""
    buf = io.BytesIO()
    img = Image.new('RGB', (100, 100), color='blue')
    img.save(buf, format='JPEG')
    buf.seek(0)
    buf.name = 'test_photo.jpg'
    return buf


@pytest.fixture
def app(tmp_path):
    """Create test app with temporary upload directory."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()

        for name in ('admin', 'user'):
            if not Role.query.filter_by(name=name).first():
                db.session.add(Role(name=name, display_name=name.title(), description=name))

        upload_dir = str(tmp_path / 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        for sub in ('posts', 'avatars', 'covers', 'groups', 'group_avatars',
                     'stories', 'marketplace', 'message_attachments',
                     'message_photos', 'icons', 'invoice_logos'):
            os.makedirs(os.path.join(upload_dir, sub), exist_ok=True)

        ss = StorageSetting(
            storage_backend='local',
            base_path=upload_dir,
            preferred_image_format='webp',
            preferred_video_format='mp4',
            image_quality=75,
            video_bitrate=1200,
            video_max_width=1280,
            max_image_mb=8,
            max_video_mb=64,
        )
        db.session.add(ss)
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


# ---- Model tests ----

class TestSocialSettingPhotoRetention:
    def test_default_retention_is_forever(self, app):
        """photo_retention_hours defaults to 0 (forever)."""
        with app.app_context():
            setting = SocialSetting()
            db.session.add(setting)
            db.session.commit()
            assert setting.photo_retention_hours == 0

    def test_set_retention_hours(self, app):
        """Admin can set photo_retention_hours to 12, 24, 36, or 48."""
        with app.app_context():
            setting = SocialSetting(photo_retention_hours=24)
            db.session.add(setting)
            db.session.commit()
            assert setting.photo_retention_hours == 24


class TestPostPhotoExpiresAt:
    def test_post_without_expiry(self, app):
        """Post without photo has no expiry."""
        with app.app_context():
            role = Role.query.filter_by(name='user').first()
            user = User(email='test@test.com', username='tester',
                        first_name='T', last_name='U', is_active=True, role_id=role.id)
            user.set_password('pass')
            db.session.add(user)
            db.session.flush()
            post = Post(user_id=user.id, content='no photo')
            db.session.add(post)
            db.session.commit()
            assert post.photo_expires_at is None

    def test_post_with_expiry(self, app):
        """Post with photo_expires_at set correctly."""
        with app.app_context():
            role = Role.query.filter_by(name='user').first()
            user = User(email='test@test.com', username='tester',
                        first_name='T', last_name='U', is_active=True, role_id=role.id)
            user.set_password('pass')
            db.session.add(user)
            db.session.flush()
            expires = datetime.now(timezone.utc) + timedelta(hours=24)
            post = Post(user_id=user.id, content='with photo', image='posts/test.jpg',
                        photo_expires_at=expires)
            db.session.add(post)
            db.session.commit()
            assert post.photo_expires_at is not None


# ---- Cleanup task tests ----

class TestCleanupExpiredPostPhotos:
    def test_cleanup_removes_expired_photos(self, app, tmp_path):
        """Expired post photos are deleted from disk and image field is cleared."""
        with app.app_context():
            role = Role.query.filter_by(name='user').first()
            user = User(email='c@test.com', username='cleaner',
                        first_name='C', last_name='L', is_active=True, role_id=role.id)
            user.set_password('pass')
            db.session.add(user)
            db.session.flush()

            # Create a temp file to simulate photo on disk
            photo_file = tmp_path / 'uploads' / 'posts' / 'expired_photo.webp'
            photo_file.write_bytes(b'fake-image-data')
            assert photo_file.exists()

            post = Post(
                user_id=user.id,
                content='expiring photo',
                image='posts/expired_photo.webp',
                photo_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
            db.session.add(post)
            db.session.commit()
            post_id = post.id

            from app.social.utils import cleanup_expired_post_photos
            result = cleanup_expired_post_photos()
            assert result['post_photos_deleted'] >= 1

            post = db.session.get(Post, post_id)
            assert post.image is None
            assert post.photo_expires_at is None
            assert not photo_file.exists()

    def test_cleanup_ignores_non_expired_photos(self, app, tmp_path):
        """Photos not yet expired are not deleted."""
        with app.app_context():
            role = Role.query.filter_by(name='user').first()
            user = User(email='d@test.com', username='keeper',
                        first_name='K', last_name='P', is_active=True, role_id=role.id)
            user.set_password('pass')
            db.session.add(user)
            db.session.flush()

            photo_file = tmp_path / 'uploads' / 'posts' / 'valid_photo.webp'
            photo_file.write_bytes(b'fake-image-data')

            post = Post(
                user_id=user.id,
                content='keeping photo',
                image='posts/valid_photo.webp',
                photo_expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
            )
            db.session.add(post)
            db.session.commit()
            post_id = post.id

            from app.social.utils import cleanup_expired_post_photos
            result = cleanup_expired_post_photos()
            assert result['post_photos_deleted'] == 0

            post = db.session.get(Post, post_id)
            assert post.image is not None
            assert photo_file.exists()

    def test_cleanup_ignores_forever_photos(self, app, tmp_path):
        """Photos without expiry (forever) are never deleted."""
        with app.app_context():
            role = Role.query.filter_by(name='user').first()
            user = User(email='e@test.com', username='forever',
                        first_name='F', last_name='V', is_active=True, role_id=role.id)
            user.set_password('pass')
            db.session.add(user)
            db.session.flush()

            post = Post(
                user_id=user.id,
                content='forever photo',
                image='posts/forever_photo.webp',
                photo_expires_at=None,
            )
            db.session.add(post)
            db.session.commit()
            post_id = post.id

            from app.social.utils import cleanup_expired_post_photos
            result = cleanup_expired_post_photos()
            assert result['post_photos_deleted'] == 0

            post = db.session.get(Post, post_id)
            assert post.image is not None


# ---- Migration column tests ----

class TestMigrationColumnsRetention:
    def test_social_setting_has_photo_retention_hours(self, app):
        with app.app_context():
            tbl = SocialSetting.__table__
            assert 'photo_retention_hours' in [c.name for c in tbl.columns]

    def test_post_has_photo_expires_at(self, app):
        with app.app_context():
            tbl = Post.__table__
            assert 'photo_expires_at' in [c.name for c in tbl.columns]
