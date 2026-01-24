"""
Subscription blueprint
Manage plans, subscriptions, and payments
"""
from flask import Blueprint

bp = Blueprint('subscription', __name__)

from app.subscription import routes
