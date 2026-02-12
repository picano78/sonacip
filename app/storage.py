"""
Storage helpers for pluggable media backends and lightweight assets.
"""
import os
from datetime import datetime, timezone
from typing import Tuple
import shutil
import subprocess
import magic

from flask import current_app
from werkzeug.utils import secure_filename
from PIL import Image

from app import db
from app.models import StorageSetting


# Allowed file extensions and MIME types for security
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'}
ALLOWED_IMAGE_MIMES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp'
}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv'}
ALLOWED_VIDEO_MIMES = {
    'video/mp4', 'video/x-msvideo', 'video/quicktime', 
    'video/x-ms-wmv', 'video/x-flv', 'video/webm', 'video/x-matroska'
}


def validate_file_type(file_stream, allowed_extensions: set, allowed_mimes: set, file_type: str = "file"):
    """
    Validate file type using both extension and MIME type detection.
    Returns True if valid, raises ValueError if invalid.
    """
    # Check file extension
    filename = getattr(file_stream, 'filename', '')
    if not filename:
        raise ValueError(f"Invalid {file_type}: no filename provided")
    
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if ext not in allowed_extensions:
        raise ValueError(f"Invalid {file_type} extension. Allowed: {', '.join(allowed_extensions)}")
    
    # Check MIME type using python-magic
    try:
        file_stream.seek(0)
        mime = magic.from_buffer(file_stream.read(2048), mime=True)
        file_stream.seek(0)
        
        if mime not in allowed_mimes:
            raise ValueError(f"Invalid {file_type} MIME type '{mime}'. File may be disguised.")
    except Exception as e:
        current_app.logger.warning(f"MIME type validation failed: {e}")
        # If magic fails, at least we checked the extension
    
    return True


def get_storage_settings() -> StorageSetting:
    """
    Return persisted storage settings.

    IMPORTANT (no runtime fix policy):
    - This function MUST NOT mutate DB schema (no ALTER TABLE).
    - This function MUST NOT auto-create default rows at runtime.
    Run `python manage.py db upgrade` and `python manage.py seed` during install/deploy.
    """
    settings = StorageSetting.query.first()
    if not settings:
        raise RuntimeError(
            "StorageSetting mancante. Esegui `python manage.py db upgrade` e `python manage.py seed`."
        )
    return settings


def _media_root() -> str:
    settings = get_storage_settings()
    root = settings.base_path or current_app.config.get('STORAGE_LOCAL_PATH') or current_app.config.get('UPLOAD_FOLDER')
    if not root:
        raise RuntimeError("Storage root non configurata. Imposta STORAGE_LOCAL_PATH o UPLOAD_FOLDER.")
    if not os.path.isdir(root):
        raise RuntimeError(
            f"Storage root '{root}' non esiste. Creala durante l'install/deploy (no runtime fixes)."
        )
    if not os.access(root, os.W_OK):
        raise RuntimeError(f"Storage root '{root}' non è scrivibile dal processo.")
    return root


def ensure_subfolder(folder: str) -> str:
    """Return an existing subfolder under the active media root (no auto-create)."""
    root = _media_root()
    target = os.path.join(root, folder)
    if not os.path.isdir(target):
        raise RuntimeError(
            f"Cartella media '{target}' mancante. Creala durante l'install/deploy (no runtime fixes)."
        )
    if not os.access(target, os.W_OK):
        raise RuntimeError(f"Cartella media '{target}' non è scrivibile dal processo.")
    return target


def save_image_light(form_picture, folder: str = 'posts', size: Tuple[int, int] = (1280, 1280)) -> str:
    """Save image as lightweight web/optimized format honoring admin settings."""
    settings = get_storage_settings()
    
    # Validate file type before processing
    validate_file_type(form_picture, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_MIMES, "image")
    
    _enforce_size_limit(form_picture, settings.max_image_mb)
    upload_folder = ensure_subfolder(folder)

    original_name = secure_filename(form_picture.filename or 'image')
    name, _ext = os.path.splitext(original_name)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')

    target_ext = (settings.preferred_image_format or 'webp').lower().replace('.', '')
    filename = f"{name}_{timestamp}.{target_ext}"
    file_path = os.path.join(upload_folder, filename)

    try:
        # Verify image can be opened by Pillow (additional security check)
        img = Image.open(form_picture)
        # Verify it's actually an image by checking format
        if not img.format:
            raise ValueError("File is not a valid image")
        if img.mode in ('RGBA', 'LA'):
            img = img.convert('RGB')
        img.thumbnail(size)
        img.save(file_path, format=target_ext.upper(), quality=settings.image_quality or 75, optimize=True)
    except (IOError, OSError, ValueError) as e:
        # Do not fallback to raw save - reject invalid files
        current_app.logger.error(f"Image validation/processing failed: {e}")
        raise ValueError(f"Invalid image file: {e}")

    return os.path.join(folder, filename)


def save_video_light(form_file, folder: str = 'posts') -> str:
    """Compress video via ffmpeg when available, enforce size limits."""
    settings = get_storage_settings()
    
    # Validate file type before processing
    validate_file_type(form_file, ALLOWED_VIDEO_EXTENSIONS, ALLOWED_VIDEO_MIMES, "video")
    
    _enforce_size_limit(form_file, settings.max_video_mb)
    upload_folder = ensure_subfolder(folder)
    original_name = secure_filename(form_file.filename or 'video')
    name, _ext = os.path.splitext(original_name)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
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
        except (subprocess.CalledProcessError, OSError) as e:
            # Do not fallback - reject invalid videos
            current_app.logger.error(f"Video processing failed: {e}")
            if os.path.exists(tmp_input):
                os.remove(tmp_input)
            raise ValueError(f"Invalid video file: {e}")

    # Fallback when ffmpeg missing - save but still validated
    form_file.save(file_path)
    return os.path.join(folder, filename)


def save_binary(form_file, folder: str = 'posts') -> str:
    """Save non-image binaries without altering content (size checked if possible)."""
    settings = get_storage_settings()
    _enforce_size_limit(form_file, settings.max_video_mb)
    upload_folder = ensure_subfolder(folder)
    original_name = secure_filename(form_file.filename or 'file')
    name, ext = os.path.splitext(original_name)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
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
