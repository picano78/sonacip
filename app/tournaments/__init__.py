"""Tournament blueprint (enterprise-grade tournaments)"""
from flask import Blueprint

bp = Blueprint('tournaments', __name__)

from app.tournaments import routes  # noqa: E402,F401
