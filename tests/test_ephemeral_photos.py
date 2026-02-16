"""
Test ephemeral photo messaging feature.
Photos in messages expire after 7 days and auto-delete.
"""
import io
import os
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from PIL import Image

from app import create_app, db
from app.models import (
    Role, User, StorageSetting, Message, MessageAttachment,
    MessageGroup, MessageGroupMembership, MessageGroupMessage,
)


PHOTO_EXPIRY_DAYS = 7


def _make_test_image():
    """Create a minimal in-memory JPEG for upload tests."""
    buf = io.BytesIO()
    img = Image.new('RGB', (100, 100), color='red')
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


@pytest.fixture
def two_users(app):
    """Create two users for direct messaging tests."""
    with app.app_context():
        role = Role.query.filter_by(name='user').first()
        u1 = User(email='a@test.com', username='alice', first_name='Alice',
                   last_name='A', is_active=True, role_id=role.id)
        u1.set_password('pass')
        u2 = User(email='b@test.com', username='bob', first_name='Bob',
                   last_name='B', is_active=True, role_id=role.id)
        u2.set_password('pass')
        db.session.add_all([u1, u2])
        db.session.commit()
        return u1, u2


# ---- Model tests ----

class TestMessageAttachmentExpiry:
    def test_is_expired_false_when_no_expires_at(self, app, two_users):
        with app.app_context():
            u1, u2 = two_users
            msg = Message(sender_id=u1.id, recipient_id=u2.id, body='hi')
            db.session.add(msg)
            db.session.flush()
            att = MessageAttachment(
                message_id=msg.id, filename='f.jpg',
                original_filename='f.jpg', file_path='/tmp/f.jpg',
                expires_at=None,
            )
            db.session.add(att)
            db.session.commit()
            assert att.is_expired is False

    def test_is_expired_false_when_future(self, app, two_users):
        with app.app_context():
            u1, u2 = two_users
            msg = Message(sender_id=u1.id, recipient_id=u2.id, body='hi')
            db.session.add(msg)
            db.session.flush()
            att = MessageAttachment(
                message_id=msg.id, filename='f.jpg',
                original_filename='f.jpg', file_path='/tmp/f.jpg',
                expires_at=datetime.now(timezone.utc) + timedelta(days=3),
            )
            db.session.add(att)
            db.session.commit()
            assert att.is_expired is False

    def test_is_expired_true_when_past(self, app, two_users):
        with app.app_context():
            u1, u2 = two_users
            msg = Message(sender_id=u1.id, recipient_id=u2.id, body='hi')
            db.session.add(msg)
            db.session.flush()
            att = MessageAttachment(
                message_id=msg.id, filename='f.jpg',
                original_filename='f.jpg', file_path='/tmp/f.jpg',
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
            db.session.add(att)
            db.session.commit()
            assert att.is_expired is True


class TestGroupMessagePhotoExpiry:
    def test_is_photo_expired_false_when_no_date(self, app, two_users):
        with app.app_context():
            u1, _ = two_users
            grp = MessageGroup(name='G', creator_id=u1.id)
            db.session.add(grp)
            db.session.flush()
            gm = MessageGroupMessage(
                group_id=grp.id, sender_id=u1.id, body='hi',
                photo_expires_at=None,
            )
            db.session.add(gm)
            db.session.commit()
            assert gm.is_photo_expired is False

    def test_is_photo_expired_true_when_past(self, app, two_users):
        with app.app_context():
            u1, _ = two_users
            grp = MessageGroup(name='G', creator_id=u1.id)
            db.session.add(grp)
            db.session.flush()
            gm = MessageGroupMessage(
                group_id=grp.id, sender_id=u1.id, body='hi',
                photo_path='message_photos/test.webp',
                photo_expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
            db.session.add(gm)
            db.session.commit()
            assert gm.is_photo_expired is True


# ---- Celery cleanup task tests ----

class TestCleanupExpiredMessagePhotos:
    def test_cleanup_deletes_expired_dm_attachments(self, app, two_users, tmp_path):
        with app.app_context():
            u1, u2 = two_users
            msg = Message(sender_id=u1.id, recipient_id=u2.id, body='photo')
            db.session.add(msg)
            db.session.flush()

            # Create a temp file to simulate photo on disk
            photo_file = tmp_path / 'uploads' / 'message_photos' / 'test_photo.webp'
            photo_file.write_bytes(b'fake-image-data')
            assert photo_file.exists()

            att = MessageAttachment(
                message_id=msg.id, filename='test_photo.webp',
                original_filename='photo.jpg',
                file_path=str(photo_file), file_size=100,
                mime_type='image/webp',
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
            db.session.add(att)
            db.session.commit()
            att_id = att.id

            from app.messages.utils import cleanup_expired_photos
            result = cleanup_expired_photos()
            assert result['dm_photos_deleted'] >= 1

            # The attachment record should be deleted
            assert db.session.get(MessageAttachment, att_id) is None
            # The file should be removed
            assert not photo_file.exists()

    def test_cleanup_nullifies_expired_group_photos(self, app, two_users, tmp_path):
        with app.app_context():
            u1, _ = two_users
            grp = MessageGroup(name='TestGrp', creator_id=u1.id)
            db.session.add(grp)
            db.session.flush()

            photo_file = tmp_path / 'uploads' / 'message_photos' / 'grp_photo.webp'
            photo_file.write_bytes(b'fake-image-data')

            gm = MessageGroupMessage(
                group_id=grp.id, sender_id=u1.id, body='📷 Foto',
                photo_path='message_photos/grp_photo.webp',
                photo_expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
            db.session.add(gm)
            db.session.commit()
            gm_id = gm.id

            from app.messages.utils import cleanup_expired_photos
            result = cleanup_expired_photos()
            assert result['group_photos_deleted'] >= 1

            gm = db.session.get(MessageGroupMessage, gm_id)
            assert gm.photo_path is None
            assert gm.photo_expires_at is None


# ---- Migration test ----

class TestMigrationColumns:
    def test_message_attachment_has_expires_at(self, app):
        with app.app_context():
            att = MessageAttachment.__table__
            assert 'expires_at' in [c.name for c in att.columns]

    def test_group_message_has_photo_fields(self, app):
        with app.app_context():
            gm = MessageGroupMessage.__table__
            cols = [c.name for c in gm.columns]
            assert 'photo_path' in cols
            assert 'photo_expires_at' in cols
