"""
Social utilities
"""
import os
from datetime import datetime, timezone

from app import db
from app.storage import save_image_light, save_video_light


def save_picture(form_picture, folder='avatars', size=(300, 300)):
    """Save picture using lightweight, admin-configured storage."""
    return save_image_light(form_picture, folder=folder, size=size)


def save_video(form_video, folder='posts'):
    """Save video using lightweight, admin-configured storage."""
    return save_video_light(form_video, folder=folder)


def cleanup_expired_post_photos():
    """
    Delete expired post photos from disk and clear the image field.
    Called by the Celery periodic task.
    """
    from app.models import Post, StorageSetting

    now = datetime.now(timezone.utc)
    expired_posts = Post.query.filter(
        Post.photo_expires_at.isnot(None),
        Post.photo_expires_at <= now,
        Post.image.isnot(None),
    ).all()

    deleted_count = 0
    for post in expired_posts:
        try:
            ss = StorageSetting.query.first()
            base_path = ss.base_path if ss else 'uploads'
            file_path = os.path.join(base_path, post.image)
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed to delete expired post photo file: %s", e)
        post.image = None
        post.photo_expires_at = None
        deleted_count += 1

    if deleted_count:
        db.session.commit()

    return {'post_photos_deleted': deleted_count}
