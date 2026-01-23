"""
CRM Blueprint
Customer/Contact Relationship Management
Gestione contatti, lead, opportunità per società sportive
"""
from flask import Blueprint

bp = Blueprint('crm', __name__)

from app.crm import routes
