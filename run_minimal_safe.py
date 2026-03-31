#!/usr/bin/env python
"""
Minimal SONACIP App - Safe testing without optional dependencies
"""

import os
from pathlib import Path
import sys

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def create_minimal_app():
    """Create minimal Flask app with only essential features"""
    from flask import Flask
    from flask_sqlalchemy import SQLAlchemy
    from flask_login import LoginManager
    from flask_wtf.csrf import CSRFProtect
    from dotenv import load_dotenv
    
    # Load environment
    load_dotenv()
    
    # Create app
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///uploads/sonacip.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions
    db = SQLAlchemy(app)
    login_manager = LoginManager(app)
    csrf = CSRFProtect(app)
    
    # Simple User model for testing
    class User(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        email = db.Column(db.String(120), unique=True, nullable=False)
        username = db.Column(db.String(80), unique=True, nullable=False)
        password_hash = db.Column(db.String(255), nullable=False)
        
        def set_password(self, password):
            from werkzeug.security import generate_password_hash
            self.password_hash = generate_password_hash(password)
        
        def check_password(self, password):
            from werkzeug.security import check_password_hash
            return check_password_hash(self.password_hash, password)
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    # Simple routes for testing
    @app.route('/')
    def index():
        return '<h1>SONACIP - Minimal Test App</h1><p>Basic functionality is working!</p><a href="/auth/login">Login</a> | <a href="/auth/register">Register</a> | <a href="/auth/register-society">Register Society</a>'
    
    @app.route('/auth/login')
    def login():
        return '<h2>Login Page</h2><p>Login form would go here</p><a href="/">Back to Home</a>'
    
    @app.route('/auth/register')
    def register():
        return '<h2>Register Page</h2><p>Registration form would go here</p><a href="/">Back to Home</a>'
    
    @app.route('/auth/register-society')
    def register_society():
        return '<h2>Register Society Page</h2><p>Society registration form would go here</p><a href="/">Back to Home</a>'
    
    return app

def main():
    """Run minimal app"""
    print("Starting minimal SONACIP app...")
    
    app = create_minimal_app()
    
    port = int(os.environ.get('PORT', 8000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"Running on http://localhost:{port}")
    print("This is a minimal test app - basic functionality only")
    
    app.run(host='0.0.0.0', port=port, debug=debug)

if __name__ == '__main__':
    main()
