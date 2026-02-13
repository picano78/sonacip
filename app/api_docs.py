"""
API Documentation Configuration using Flasgger (Swagger)
"""
from flasgger import Swagger


def init_swagger(app):
    """Initialize Swagger API documentation"""
    
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": 'apispec',
                "route": '/apispec.json',
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/api/docs/"
    }
    
    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "SONACIP API",
            "description": "Complete API documentation for SONACIP - Social CRM Platform for Sports Organizations",
            "contact": {
                "email": "support@sonacip.it",
                "name": "SONACIP Support"
            },
            "version": "1.0.0"
        },
        "host": app.config.get('SERVER_NAME', 'localhost:5000'),
        "basePath": "/api/v1",
        "schemes": [
            "https" if app.config.get('SESSION_COOKIE_SECURE') else "http"
        ],
        "securityDefinitions": {
            "Bearer": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": "JWT Authorization header using the Bearer scheme. Example: 'Authorization: Bearer {token}'"
            },
            "SessionAuth": {
                "type": "apiKey",
                "name": "session",
                "in": "cookie",
                "description": "Session-based authentication using Flask-Login"
            }
        },
        "tags": [
            {
                "name": "Authentication",
                "description": "User authentication and registration"
            },
            {
                "name": "Users",
                "description": "User management and profiles"
            },
            {
                "name": "Social",
                "description": "Social feed, posts, comments, and follows"
            },
            {
                "name": "CRM",
                "description": "Contact management and opportunities"
            },
            {
                "name": "Events",
                "description": "Event management and athlete convocations"
            },
            {
                "name": "Notifications",
                "description": "Notification management"
            },
            {
                "name": "Automation",
                "description": "Automation rules and workflows"
            },
            {
                "name": "Payments",
                "description": "Payment processing and subscriptions"
            },
            {
                "name": "Tournaments",
                "description": "Tournament and match management"
            },
            {
                "name": "Analytics",
                "description": "Analytics and reporting"
            }
        ]
    }
    
    swagger = Swagger(app, config=swagger_config, template=swagger_template)
    
    return swagger
