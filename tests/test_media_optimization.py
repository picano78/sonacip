"""
Test media optimization across all upload paths.
Ensures every module routes image/video uploads through the
centralized save_image_light / save_video_light helpers.
"""
import io
import os
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image

from app import create_app, db
from app.models import Role, StorageSetting


@pytest.fixture
def app(tmp_path):
    """Create test app with temporary upload directory."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()

        # Create required roles
        for name in ('admin', 'user'):
            if not Role.query.filter_by(name=name).first():
                db.session.add(Role(name=name, display_name=name.title(), description=name))

        # Create StorageSetting pointing to tmp_path
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
            video_bitrate=1200000,
            video_max_width=1280,
            max_image_mb=8,
            max_video_mb=64,
            max_upload_mb=16,
        )
        db.session.add(ss)
        db.session.commit()

        app.config['UPLOAD_FOLDER'] = upload_dir
        app.config['STORAGE_LOCAL_PATH'] = upload_dir

        yield app

        db.session.remove()
        db.drop_all()


def _make_test_image(width=2000, height=2000, fmt='PNG'):
    """Create a test image in memory."""
    img = Image.new('RGB', (width, height), color='red')
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf


def _make_file_storage(buf, filename, content_type='image/png'):
    """Wrap a BytesIO in a Werkzeug FileStorage-like object."""
    from werkzeug.datastructures import FileStorage
    buf.seek(0)
    return FileStorage(stream=buf, filename=filename, content_type=content_type)


# ──────────────────────────────────────────────
# save_image_light: core behaviour
# ──────────────────────────────────────────────
class TestSaveImageLight:
    def test_image_is_resized(self, app):
        """Large image must be resized to fit max dimensions."""
        with app.app_context():
            from app.storage import save_image_light
            buf = _make_test_image(4000, 3000)
            fs = _make_file_storage(buf, 'big.png')
            rel = save_image_light(fs, folder='posts', size=(800, 800))

            upload_dir = app.config['UPLOAD_FOLDER']
            saved = Image.open(os.path.join(upload_dir, rel))
            assert saved.width <= 800
            assert saved.height <= 800

    def test_image_converted_to_preferred_format(self, app):
        """Image should be saved in the preferred format (webp)."""
        with app.app_context():
            from app.storage import save_image_light
            buf = _make_test_image(200, 200)
            fs = _make_file_storage(buf, 'small.png')
            rel = save_image_light(fs, folder='posts', size=(800, 800))
            assert rel.endswith('.webp')

    def test_output_smaller_than_input(self, app):
        """Optimized file must be smaller than the raw input."""
        with app.app_context():
            from app.storage import save_image_light
            buf = _make_test_image(2000, 2000)
            original_size = buf.getbuffer().nbytes
            fs = _make_file_storage(buf, 'large.png')
            rel = save_image_light(fs, folder='posts', size=(800, 800))

            upload_dir = app.config['UPLOAD_FOLDER']
            saved_size = os.path.getsize(os.path.join(upload_dir, rel))
            assert saved_size < original_size

    def test_invalid_file_rejected(self, app):
        """Non-image data must be rejected."""
        with app.app_context():
            from app.storage import save_image_light
            fake = io.BytesIO(b'not an image')
            fs = _make_file_storage(fake, 'bad.png')
            with pytest.raises(ValueError):
                save_image_light(fs, folder='posts')


# ──────────────────────────────────────────────
# social/utils: save_picture delegates to save_image_light
# ──────────────────────────────────────────────
class TestSocialUtils:
    def test_save_picture_optimizes(self, app):
        with app.app_context():
            from app.social.utils import save_picture
            buf = _make_test_image(2000, 2000)
            fs = _make_file_storage(buf, 'post.png')
            rel = save_picture(fs, folder='posts', size=(800, 800))

            upload_dir = app.config['UPLOAD_FOLDER']
            saved = Image.open(os.path.join(upload_dir, rel))
            assert saved.width <= 800
            assert saved.height <= 800

    def test_save_video_delegates(self, app):
        """save_video must call save_video_light."""
        with app.app_context():
            with patch('app.social.utils.save_video_light') as mock_svl:
                mock_svl.return_value = 'posts/video_123.mp4'
                from app.social.utils import save_video
                fake = _make_file_storage(io.BytesIO(b'\x00'), 'clip.mp4', 'video/mp4')
                result = save_video(fake, folder='posts')
                mock_svl.assert_called_once_with(fake, folder='posts')
                assert result == 'posts/video_123.mp4'


# ──────────────────────────────────────────────
# groups: save_group_picture uses save_image_light
# ──────────────────────────────────────────────
class TestGroupsOptimization:
    def test_group_picture_optimizes(self, app):
        with app.app_context():
            from app.groups.routes import save_group_picture
            buf = _make_test_image(3000, 3000)
            fs = _make_file_storage(buf, 'group.png')
            result = save_group_picture(fs, subfolder='groups')
            assert result is not None
            # Must contain the subfolder path
            assert 'groups/' in result

    def test_group_picture_invalid_returns_none(self, app):
        with app.app_context():
            from app.groups.routes import save_group_picture
            result = save_group_picture(None)
            assert result is None


# ──────────────────────────────────────────────
# messages: save_group_avatar uses save_image_light
# ──────────────────────────────────────────────
class TestMessagesOptimization:
    def test_group_avatar_optimizes(self, app):
        with app.app_context():
            from app.messages.routes import save_group_avatar
            buf = _make_test_image(2000, 2000)
            fs = _make_file_storage(buf, 'avatar.png')
            result = save_group_avatar(fs)
            assert result is not None
            assert 'group_avatars/' in result

    def test_group_avatar_invalid_returns_none(self, app):
        with app.app_context():
            from app.messages.routes import save_group_avatar
            result = save_group_avatar(MagicMock(filename=''))
            assert result is None


# ──────────────────────────────────────────────
# marketplace: _save_listing_image uses save_image_light
# ──────────────────────────────────────────────
class TestMarketplaceOptimization:
    def test_listing_image_optimizes(self, app):
        with app.app_context():
            from app.marketplace.routes import _save_listing_image
            buf = _make_test_image(2000, 2000)
            fs = _make_file_storage(buf, 'product.png')
            result = _save_listing_image(fs)
            assert result is not None
            assert 'marketplace/' in result

    def test_listing_image_invalid_returns_none(self, app):
        with app.app_context():
            from app.marketplace.routes import _save_listing_image
            result = _save_listing_image(None)
            assert result is None


# ──────────────────────────────────────────────
# stories: _save_story_file uses save_image_light / save_video_light
# ──────────────────────────────────────────────
class TestStoriesOptimization:
    def test_story_image_optimizes(self, app):
        with app.app_context():
            from app.stories.routes import _save_story_file
            buf = _make_test_image(3000, 3000)
            fs = _make_file_storage(buf, 'story.png')
            result = _save_story_file(fs)
            assert result is not None
            assert 'stories/' in result

    def test_story_video_delegates(self, app):
        with app.app_context():
            with patch('app.stories.routes.save_video_light') as mock_svl:
                mock_svl.return_value = 'stories/clip_123.mp4'
                from app.stories.routes import _save_story_file
                fake = _make_file_storage(io.BytesIO(b'\x00'), 'story.mp4', 'video/mp4')
                result = _save_story_file(fake)
                mock_svl.assert_called_once()
                assert 'stories/' in result

    def test_story_invalid_extension_rejected(self, app):
        with app.app_context():
            from app.stories.routes import _save_story_file
            fake = _make_file_storage(io.BytesIO(b'\x00'), 'story.exe', 'application/exe')
            with pytest.raises(ValueError, match='not allowed'):
                _save_story_file(fake)


# ──────────────────────────────────────────────
# messages/utils: save_attachment optimizes images
# ──────────────────────────────────────────────
class TestMessageAttachmentOptimization:
    def test_image_attachment_optimized(self, app):
        with app.app_context():
            from app.messages.utils import save_attachment
            buf = _make_test_image(2000, 2000)
            fs = _make_file_storage(buf, 'photo.png')
            attachment = save_attachment(fs, message_id=1)
            assert attachment is not None
            assert attachment.filename.endswith('.webp')

    def test_non_image_attachment_saved_normally(self, app):
        """Non-image attachments (e.g. PDF) should be saved without optimization."""
        with app.app_context():
            from app.messages.utils import save_attachment
            fake_pdf = io.BytesIO(b'%PDF-1.4 fake content')
            fs = _make_file_storage(fake_pdf, 'doc.pdf', 'application/pdf')
            # Ensure upload dir exists under configured UPLOAD_FOLDER
            upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'message_attachments')
            os.makedirs(upload_dir, exist_ok=True)
            attachment = save_attachment(fs, message_id=1)
            assert attachment is not None
            assert attachment.original_filename == 'doc.pdf'
