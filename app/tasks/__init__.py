"""
Tasks and Projects Blueprint - Advanced Planning Module
Asana/Monday.com/ClickUp level functionality
"""
from flask import Blueprint

bp = Blueprint('tasks', __name__)

from app.tasks import routes
