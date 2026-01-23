#!/usr/bin/env python3
"""
SONACIP - Production Entry Point
Single source of truth for running the application
"""
import os
from app import create_app

# Create the Flask application using the factory pattern
app = create_app()

if __name__ == '__main__':
    # Development server - NOT for production
    # Use gunicorn in production: gunicorn -c gunicorn_config.py run:app
    app.run(host='0.0.0.0', port=5000, debug=False)
