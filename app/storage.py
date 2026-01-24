"""
Storage helpers for pluggable media backends and lightweight assets.
"""
import os
from datetime import datetime
from typing import Tuple

from flask import current_app
from werkzeug.utils import secure_filename
from PIL import Image

from app import db
from app.models import StorageSetting


def get_storage_settings() -> StorageSetting:
    """Return persisted storage settings or create defaults from config."""
    settings = StorageSetting.query.first()
    if not settings:
        settings = StorageSetting(
            storage_backend=current_app.config.get('STORAGE_BACKEND', 'local'),
            base_path=current_app.config.get('STORAGE_LOCAL_PATH') or current_app.config.get('UPLOAD_FOLDER'),
            preferred_image_format=current_app.config.get('MEDIA_PREFERRED_IMAGE_FORMAT', 'webp'),
            preferred_video_format=current_app.config.get('MEDIA_PREFERRED_VIDEO_FORMAT', 'mp4'),
            image_quality=current_app.config.get('MEDIA_IMAGE_QUALITY', 75),
        )
        db.session.add(settings)
        db.session.commit()
    if not settings.base_path:
        settings.base_path = current_app.config.get('STORAGE_LOCAL_PATH') or current_app.config.get('UPLOAD_FOLDER')
        db.session.commit()
    return settings


def _media_root() -> str:
    settings = get_storage_settings()
    root = settings.base_path or current_app.config.get('UPLOAD_FOLDER')
    os.makedirs(root, exist_ok=True)
    return root


def ensure_subfolder(folder: str) -> str:
    """Ensure a subfolder exists under the active media root."""
    root = _media_root()
    target = os.path.join(root, folder)
    os.makedirs(target, exist_ok=True)
    return target


def save_image_light(form_picture, folder: str = 'posts', size: Tuple[int, int] = (1280, 1280)) -> str:
    """Save image as lightweight web/optimized format honoring admin settings."""
    settings = get_storage_settings()
    upload_folder = ensure_subfolder(folder)

    original_name = secure_filename(form_picture.filename or 'image')
    name, _ext = os.path.splitext(original_name)
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')

    target_ext = (settings.preferred_image_format or 'webp').lower().replace('.', '')
    filename = f"{name}_{timestamp}.{target_ext}"
    file_path = os.path.join(upload_folder, filename)

    try:
        img = Image.open(form_picture)
        if img.mode in ('RGBA', 'LA'):
            img = img.convert('RGB')
        img.thumbnail(size)
        img.save(file_path, format=target_ext.upper(), quality=settings.image_quality or 75, optimize=True)
    except Exception:
        # Fallback to raw save if conversion fails
        form_picture.save(file_path)

    return os.path.join(folder, filename)


def save_binary(form_file, folder: str = 'posts') -> str:
    """Save non-image binaries (e.g., video) without altering content."""
    upload_folder = ensure_subfolder(folder)
    original_name = secure_filename(form_file.filename or 'file')
    name, ext = os.path.splitext(original_name)
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    filename = f"{name}_{timestamp}{ext or ''}"
    file_path = os.path.join(upload_folder, filename)
    form_file.save(file_path)
    return os.path.join(folder, filename)
