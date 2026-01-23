"""
Social Blueprint
Profiles, feed, posts, follows, likes, comments
"""
from flask import Blueprint

bp = Blueprint('social', __name__)

from app.social import routes
