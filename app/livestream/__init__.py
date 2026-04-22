"""
Live Streaming Module
WebRTC-based live streaming with no server-side video storage
"""
from flask import Blueprint

bp = Blueprint('livestream', __name__, url_prefix='/livestream')

from app.livestream import routes
