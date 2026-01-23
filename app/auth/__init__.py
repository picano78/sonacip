"""
Authentication Blueprint
Handles login, registration, logout
"""
from flask import Blueprint

bp = Blueprint('auth', __name__)

from app.auth import routes
