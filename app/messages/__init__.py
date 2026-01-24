"""
Messages blueprint
"""
from flask import Blueprint

bp = Blueprint('messages', __name__)

from app.messages import routes  # noqa: E402,F401
