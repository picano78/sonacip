"""
Social utilities
"""
import os
from werkzeug.utils import secure_filename
from flask import current_app
from PIL import Image


def save_picture(form_picture, folder='avatars', size=(300, 300)):
    """
    Save and resize uploaded picture
    Returns filename
    """
    # Generate secure filename
    filename = secure_filename(form_picture.filename)
    
    # Add timestamp to avoid conflicts
    from datetime import datetime
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    name, ext = os.path.splitext(filename)
    filename = f"{name}_{timestamp}{ext}"
    
    # Full path
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], folder)
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, filename)
    
    # Resize and save
    try:
        img = Image.open(form_picture)
        img.thumbnail(size)
        img.save(file_path)
    except Exception as e:
        # If resize fails, save original
        form_picture.save(file_path)
    
    # Return relative path
    return os.path.join(folder, filename)
