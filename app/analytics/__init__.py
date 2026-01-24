"""
Analytics Blueprint - Advanced BI and Insights
Power BI/Tableau level functionality
"""
from flask import Blueprint

bp = Blueprint('analytics', __name__)

from app.analytics import routes
