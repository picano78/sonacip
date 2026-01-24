"""
Social utilities
"""
from app.storage import save_image_light


def save_picture(form_picture, folder='avatars', size=(300, 300)):
    """Save picture using lightweight, admin-configured storage."""
    return save_image_light(form_picture, folder=folder, size=size)
