#!/usr/bin/env python
"""
Fix Critical Issues Safely - Senior Backend Engineer
Fix SONACIP issues without breaking anything
"""

import sys
import os
from pathlib import Path
import secrets

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def create_env_file():
    """Create .env file with safe defaults"""
    print("CREATING .env FILE")
    print("=" * 50)
    
    env_file = '.env'
    
    if os.path.exists(env_file):
        print("  .env file already exists - skipping")
        return True
    
    # Generate secure secret key
    secret_key = secrets.token_hex(32)
    
    env_content = f'''# SONACIP Environment Configuration
SECRET_KEY={secret_key}

# Database Configuration
SQLALCHEMY_DATABASE_URI=sqlite:///uploads/sonacip.db
SQLALCHEMY_TRACK_MODIFICATIONS=False

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True

# Security
WTF_CSRF_ENABLED=True
WTF_CSRF_TIME_LIMIT=None

# Email Configuration (optional)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Upload Configuration
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=16777216  # 16MB

# Rate Limiting
RATELIMIT_STORAGE_URL=memory://
'''
    
    try:
        with open(env_file, 'w') as f:
            f.write(env_content)
        print(f"  Created {env_file}")
        print("  Generated secure SECRET_KEY")
        return True
    except Exception as e:
        print(f"  Error creating .env file: {e}")
        return False

def initialize_database():
    """Initialize database safely"""
    print("\nINITIALIZING DATABASE")
    print("=" * 50)
    
    try:
        # Create uploads directory
        os.makedirs('uploads', exist_ok=True)
        
        # Try to create app and initialize database
        from app import create_app, db
        
        print("  Creating Flask app...")
        app = create_app()
        
        with app.app_context():
            print("  Creating database tables...")
            db.create_all()
            print("  Database tables created successfully")
            
            # Check if we need to seed basic data
            from app.models import User, Role
            
            # Create default roles if they don't exist
            role_names = ['super_admin', 'admin', 'societa', 'appassionato']
            
            for role_name in role_names:
                role = Role.query.filter_by(name=role_name).first()
                if not role:
                    role = Role(name=role_name)
                    db.session.add(role)
                    print(f"  Created role: {role_name}")
            
            db.session.commit()
            print("  Default roles created")
            
            # Check user count
            user_count = User.query.count()
            print(f"  Current users in database: {user_count}")
            
            return True
            
    except Exception as e:
        print(f"  Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_simple_run_script():
    """Create a simple run script"""
    print("\nCREATING SIMPLE RUN SCRIPT")
    print("=" * 50)
    
    run_script = '''#!/usr/bin/env python
"""
Simple SONACIP Runner - Safe startup
"""

import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
import sys
sys.path.insert(0, str(project_root))

def main():
    """Run SONACIP application"""
    print("Starting SONACIP...")
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    # Create app
    from app import create_app
    app = create_app()
    
    # Run app
    port = int(os.environ.get('PORT', 8000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"Running on http://localhost:{port}")
    print(f"Debug mode: {debug}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)

if __name__ == '__main__':
    main()
'''
    
    try:
        with open('run_simple.py', 'w') as f:
            f.write(run_script)
        print("  Created run_simple.py")
        return True
    except Exception as e:
        print(f"  Error creating run script: {e}")
        return False

def test_basic_functionality():
    """Test basic functionality"""
    print("\nTESTING BASIC FUNCTIONALITY")
    print("=" * 50)
    
    try:
        from app import create_app
        
        app = create_app()
        
        with app.test_client() as client:
            # Test main page
            response = client.get('/')
            print(f"  Main page (/): {response.status_code}")
            
            # Test login page
            response = client.get('/auth/login')
            print(f"  Login page (/auth/login): {response.status_code}")
            
            # Test register page
            response = client.get('/auth/register')
            print(f"  Register page (/auth/register): {response.status_code}")
            
            # Test register society page
            response = client.get('/auth/register-society')
            print(f"  Register society page (/auth/register-society): {response.status_code}")
            
            print("  Basic functionality tests completed")
            return True
            
    except Exception as e:
        print(f"  Error testing functionality: {e}")
        return False

def main():
    """Main fix function"""
    print("SONACIP CRITICAL ISSUES FIX - SAFE MODE")
    print("=" * 60)
    
    fixes_applied = []
    
    # Fix 1: Create .env file
    if create_env_file():
        fixes_applied.append(".env file")
    
    # Fix 2: Initialize database
    if initialize_database():
        fixes_applied.append("Database initialization")
    
    # Fix 3: Create simple run script
    if create_simple_run_script():
        fixes_applied.append("Simple run script")
    
    # Fix 4: Test functionality
    if test_basic_functionality():
        fixes_applied.append("Functionality test")
    
    print("\n" + "=" * 60)
    print("FIXES APPLIED:")
    for fix in fixes_applied:
        print(f"  - {fix}")
    
    print("\nNEXT STEPS:")
    print("1. Run the application:")
    print("   python run_simple.py")
    print("")
    print("2. Or use the original run.py:")
    print("   python run.py")
    print("")
    print("3. Test the following URLs:")
    print("   http://localhost:8000/")
    print("   http://localhost:8000/auth/login")
    print("   http://localhost:8000/auth/register")
    print("   http://localhost:8000/auth/register-society")
    print("")
    print("4. If you encounter issues, check:")
    print("   - Database: uploads/sonacip.db")
    print("   - Environment: .env file")
    print("   - Logs: Console output")
    
    return len(fixes_applied) == 4

if __name__ == '__main__':
    main()
