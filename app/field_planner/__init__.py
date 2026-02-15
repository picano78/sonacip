"""Field Planner Module - Field/Facility occupancy management"""
from flask import Blueprint

bp = Blueprint('field_planner', __name__, url_prefix='/field_planner')

from app.field_planner import routes
