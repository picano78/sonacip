#!/usr/bin/env python
"""
SONACIP Production Entry Point
Single entry point for production deployment
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(project_root / '.env')

# Import Flask app
try:
    from app import create_app
    app = create_app()
except ImportError:
    # Fallback to basic Flask app
    from flask import Flask, jsonify
    app = Flask(__name__)
    
    # Auto-generate SECRET_KEY if not present
    if not app.config.get('SECRET_KEY'):
        import secrets
        app.config['SECRET_KEY'] = secrets.token_hex(32)
    
    @app.route('/')
    def index():
        return jsonify({
            "status": "running",
            "app": "SONACIP",
            "message": "Production server is running"
        })
    
    @app.route('/health')
    def health():
        return jsonify({
            "status": "healthy",
            "app": "SONACIP",
            "version": "1.0.0"
        }), 200

# Production configuration
app.config['DEBUG'] = False
app.config['ENV'] = 'production'

if __name__ == '__main__':
    # Production server configuration
    host = '0.0.0.0'
    port = 8000
    
    print(f"Starting SONACIP production server on {host}:{port}")
    print(f"Debug mode: {app.config.get('DEBUG', False)}")
    
    app.run(host=host, port=port, debug=False)
