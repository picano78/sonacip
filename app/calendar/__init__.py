"""Society Calendar blueprint (director-level calendar, separate from field planner)"""
from flask import Blueprint

bp = Blueprint('calendar', __name__)

from app.calendar import routes  # noqa: E402,F401
