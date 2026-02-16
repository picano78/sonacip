"""
Social utilities
"""
from app.storage import save_image_light, save_video_light


def save_picture(form_picture, folder='avatars', size=(300, 300)):
    """Save picture using lightweight, admin-configured storage."""
    return save_image_light(form_picture, folder=folder, size=size)


def save_video(form_video, folder='posts'):
    """Save video using lightweight, admin-configured storage."""
    return save_video_light(form_video, folder=folder)
