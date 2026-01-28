"""
Storage helpers for pluggable media backends and lightweight assets.
"""
import os
from datetime import datetime
from typing import Tuple
import shutil
import subprocess

from flask import current_app
from werkzeug.utils import secure_filename
from PIL import Image

from app.core.extensions import db
from app.models import StorageSetting


def get_storage_settings() -> StorageSetting:
    """Return persisted storage settings or create defaults from config."""
    _ensure_storage_schema()
    settings = StorageSetting.query.first()
    if not settings:
        settings = StorageSetting(
            storage_backend=current_app.config.get('STORAGE_BACKEND', 'local'),
            base_path=current_app.config.get('STORAGE_LOCAL_PATH') or current_app.config.get('UPLOAD_FOLDER'),
            preferred_image_format=current_app.config.get('MEDIA_PREFERRED_IMAGE_FORMAT', 'webp'),
            preferred_video_format=current_app.config.get('MEDIA_PREFERRED_VIDEO_FORMAT', 'mp4'),
            image_quality=current_app.config.get('MEDIA_IMAGE_QUALITY', 75),
            video_bitrate=current_app.config.get('MEDIA_VIDEO_MAX_BITRATE', 1200000),
            video_max_width=current_app.config.get('MEDIA_VIDEO_MAX_WIDTH', 1280),
            max_image_mb=current_app.config.get('MEDIA_MAX_IMAGE_MB', 8),
            max_video_mb=current_app.config.get('MEDIA_MAX_VIDEO_MB', 64),
        )
        db.session.add(settings)
        db.session.commit()
    if not settings.base_path:
        settings.base_path = current_app.config.get('STORAGE_LOCAL_PATH') or current_app.config.get('UPLOAD_FOLDER')
        db.session.commit()
    return settings


def _ensure_storage_schema():
    """Ensure new columns exist for storage settings (works on SQLite)."""
    engine = db.get_engine()
    insp = db.inspect(engine)
    columns = {col['name'] for col in insp.get_columns('storage_setting')} if insp.has_table('storage_setting') else set()
    required = {
        'video_bitrate': 'INTEGER',
        'video_max_width': 'INTEGER',
        'max_image_mb': 'INTEGER',
        'max_video_mb': 'INTEGER'
    }
    if not insp.has_table('storage_setting'):
        return
    for col, coltype in required.items():
        if col not in columns:
            try:
                with engine.begin() as conn:
                    conn.execute(f"ALTER TABLE storage_setting ADD COLUMN {col} {coltype}")
            except Exception as exc:
                current_app.logger.warning(f"Non riesco ad aggiungere colonna {col} a storage_setting: {exc}")


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
    _enforce_size_limit(form_picture, settings.max_image_mb)
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


def save_video_light(form_file, folder: str = 'posts') -> str:
    """Compress video via ffmpeg when available, enforce size limits."""
    settings = get_storage_settings()
    _enforce_size_limit(form_file, settings.max_video_mb)
    upload_folder = ensure_subfolder(folder)
    original_name = secure_filename(form_file.filename or 'video')
    name, _ext = os.path.splitext(original_name)
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    filename = f"{name}_{timestamp}.{settings.preferred_video_format or 'mp4'}"
    file_path = os.path.join(upload_folder, filename)

    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        try:
            tmp_input = os.path.join(upload_folder, f"{name}_{timestamp}_src")
            form_file.save(tmp_input)
            cmd = [
                ffmpeg_path,
                '-i', tmp_input,
                '-y',
                '-vf', f"scale='min({settings.video_max_width},iw)':-2",
                '-b:v', str(settings.video_bitrate),
                '-maxrate', str(settings.video_bitrate),
                '-bufsize', str(settings.video_bitrate * 2),
                '-c:v', 'libx264',
                '-preset', 'veryfast',
                '-c:a', 'aac',
                file_path
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.remove(tmp_input)
            return os.path.join(folder, filename)
        except Exception:
            # fallback to raw save
            pass

    # Fallback when ffmpeg missing or fails
    form_file.save(file_path)
    return os.path.join(folder, filename)


def save_binary(form_file, folder: str = 'posts') -> str:
    """Save non-image binaries without altering content (size checked if possible)."""
    settings = get_storage_settings()
    _enforce_size_limit(form_file, settings.max_video_mb)
    upload_folder = ensure_subfolder(folder)
    original_name = secure_filename(form_file.filename or 'file')
    name, ext = os.path.splitext(original_name)
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    filename = f"{name}_{timestamp}{ext or ''}"
    file_path = os.path.join(upload_folder, filename)
    form_file.save(file_path)
    return os.path.join(folder, filename)


def _enforce_size_limit(file_storage, max_mb: int):
    if not max_mb:
        return
    try:
        file_storage.seek(0, os.SEEK_END)
        size_bytes = file_storage.tell()
        file_storage.seek(0)
    except Exception:
        return
    if size_bytes > max_mb * 1024 * 1024:
        raise ValueError(f'File troppo grande: limite {max_mb}MB')
