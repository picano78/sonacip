"""
Notifications Blueprint
Internal notification system + email integration
"""
from flask import Blueprint

bp = Blueprint('notifications', __name__)

from app.notifications import routes
