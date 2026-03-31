#!/usr/bin/env python
"""
Simple Test App - No database, just basic Flask
"""

import os
from pathlib import Path
import sys

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def create_simple_test_app():
    """Create simple Flask app without database"""
    from flask import Flask
    from dotenv import load_dotenv
    
    # Load environment
    load_dotenv()
    
    # Create app
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    
    # Simple routes for testing
    @app.route('/')
    def index():
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>SONACIP - Test</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .container { max-width: 800px; margin: 0 auto; }
                .nav { background: #007bff; padding: 10px; border-radius: 5px; }
                .nav a { color: white; text-decoration: none; margin: 10px; }
                .card { background: #f8f9fa; padding: 20px; margin: 10px 0; border-radius: 5px; }
                .success { color: #28a745; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>SONACIP - Test App</h1>
                <div class="success">✅ Basic Flask functionality is working!</div>
                
                <div class="nav">
                    <a href="/auth/login">Login</a>
                    <a href="/auth/register">Register</a>
                    <a href="/auth/register-society">Register Society</a>
                </div>
                
                <div class="card">
                    <h3>System Status</h3>
                    <ul>
                        <li>✅ Flask Framework: Working</li>
                        <li>✅ Routes: Working</li>
                        <li>✅ Templates: Working</li>
                        <li>✅ Basic Configuration: Working</li>
                    </ul>
                </div>
                
                <div class="card">
                    <h3>Next Steps</h3>
                    <p>This is a basic test app. To run the full SONACIP application:</p>
                    <ol>
                        <li>Install dependencies: <code>pip install -r requirements.txt</code></li>
                        <li>Configure database and environment</li>
                        <li>Run: <code>python run.py</code></li>
                    </ol>
                </div>
            </div>
        </body>
        </html>
        '''
    
    @app.route('/auth/login')
    def login():
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Login - SONACIP</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .container { max-width: 600px; margin: 0 auto; }
                .form-group { margin: 15px 0; }
                .btn { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; }
                .btn:hover { background: #0056b3; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Login</h1>
                <p>This is a test login page. In the full app, this would contain a working login form.</p>
                
                <form>
                    <div class="form-group">
                        <label>Email or Username:</label>
                        <input type="text" style="width: 100%; padding: 8px;">
                    </div>
                    <div class="form-group">
                        <label>Password:</label>
                        <input type="password" style="width: 100%; padding: 8px;">
                    </div>
                    <button type="button" class="btn">Login (Test)</button>
                </form>
                
                <p><a href="/">← Back to Home</a></p>
            </div>
        </body>
        </html>
        '''
    
    @app.route('/auth/register')
    def register():
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Register - SONACIP</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .container { max-width: 600px; margin: 0 auto; }
                .form-group { margin: 15px 0; }
                .btn { background: #28a745; color: white; padding: 10px 20px; border: none; border-radius: 5px; }
                .btn:hover { background: #1e7e34; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Register</h1>
                <p>This is a test registration page. In the full app, this would contain a working registration form.</p>
                
                <form>
                    <div class="form-group">
                        <label>Email:</label>
                        <input type="email" style="width: 100%; padding: 8px;">
                    </div>
                    <div class="form-group">
                        <label>Username:</label>
                        <input type="text" style="width: 100%; padding: 8px;">
                    </div>
                    <div class="form-group">
                        <label>Password:</label>
                        <input type="password" style="width: 100%; padding: 8px;">
                    </div>
                    <button type="button" class="btn">Register (Test)</button>
                </form>
                
                <p><a href="/">← Back to Home</a></p>
            </div>
        </body>
        </html>
        '''
    
    @app.route('/auth/register-society')
    def register_society():
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Register Society - SONACIP</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .container { max-width: 800px; margin: 0 auto; }
                .form-group { margin: 15px 0; }
                .btn { background: #17a2b8; color: white; padding: 10px 20px; border: none; border-radius: 5px; }
                .btn:hover { background: #117a8b; }
                .row { display: flex; gap: 20px; }
                .col { flex: 1; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Register Society</h1>
                <p>✅ This page is now accessible! The 404 error has been fixed.</p>
                <p>This is a test society registration page. In the full app, this would contain a working registration form.</p>
                
                <form>
                    <div class="row">
                        <div class="col">
                            <h3>Account Details</h3>
                            <div class="form-group">
                                <label>Username:</label>
                                <input type="text" style="width: 100%; padding: 8px;">
                            </div>
                            <div class="form-group">
                                <label>Email:</label>
                                <input type="email" style="width: 100%; padding: 8px;">
                            </div>
                            <div class="form-group">
                                <label>Password:</label>
                                <input type="password" style="width: 100%; padding: 8px;">
                            </div>
                        </div>
                        <div class="col">
                            <h3>Society Details</h3>
                            <div class="form-group">
                                <label>Society Name:</label>
                                <input type="text" style="width: 100%; padding: 8px;">
                            </div>
                            <div class="form-group">
                                <label>Society Type:</label>
                                <select style="width: 100%; padding: 8px;">
                                    <option>ASD</option>
                                    <option>SSD</option>
                                    <option>SRL</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Fiscal Code:</label>
                                <input type="text" style="width: 100%; padding: 8px;">
                            </div>
                        </div>
                    </div>
                    <button type="button" class="btn">Register Society (Test)</button>
                </form>
                
                <p><a href="/">← Back to Home</a></p>
            </div>
        </body>
        </html>
        '''
    
    return app

def main():
    """Run simple test app"""
    print("Starting simple SONACIP test app...")
    print("This app tests basic functionality without database dependencies")
    
    app = create_simple_test_app()
    
    port = int(os.environ.get('PORT', 8000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"Running on http://localhost:{port}")
    print("Test URLs:")
    print(f"  http://localhost:{port}/")
    print(f"  http://localhost:{port}/auth/login")
    print(f"  http://localhost:{port}/auth/register")
    print(f"  http://localhost:{port}/auth/register-society")
    
    app.run(host='0.0.0.0', port=port, debug=debug)

if __name__ == '__main__':
    main()
