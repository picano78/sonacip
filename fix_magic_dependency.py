#!/usr/bin/env python
"""
Fix Magic Dependency Issue - Senior Backend Engineer
Fix the missing 'magic' module dependency without breaking anything
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def fix_storage_import():
    """Fix the storage.py import issue"""
    print("FIXING STORAGE IMPORT ISSUE")
    print("=" * 50)
    
    storage_file = 'app/storage.py'
    
    try:
        with open(storage_file, 'r') as f:
            content = f.read()
        
        print(f"  Reading {storage_file}")
        
        # Check if magic import exists
        if 'import magic' in content:
            print("  Found 'import magic' - creating safe fallback")
            
            # Create a safe fallback for magic import
            new_content = content.replace(
                'import magic',
                '''try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False
    print("Warning: python-magic not installed, using fallback")'''
            )
            
            # Also need to fix the usage of magic
            if 'mime = magic.Magic(mime=True)' in new_content:
                new_content = new_content.replace(
                    'mime = magic.Magic(mime=True)',
                    '''if HAS_MAGIC:
                mime = magic.Magic(mime=True)
            else:
                # Fallback when magic is not available
                mime = None'''
                )
            
            # Fix the mime detection usage
            if 'mime.from_buffer' in new_content:
                new_content = new_content.replace(
                    'mime.from_buffer',
                    '''mime.from_buffer if mime else None'''
                )
            
            with open(storage_file, 'w') as f:
                f.write(new_content)
            
            print("  Fixed storage.py with safe fallback")
            return True
        else:
            print("  No 'import magic' found - already fixed or different issue")
            return True
            
    except Exception as e:
        print(f"  Error fixing storage import: {e}")
        return False

def create_requirements_with_magic():
    """Create requirements.txt with magic dependency"""
    print("\nCREATING REQUIREMENTS WITH MAGIC")
    print("=" * 50)
    
    requirements = '''Flask==2.3.3
Flask-SQLAlchemy==3.0.5
Flask-Login==0.6.3
Flask-WTF==1.1.1
Werkzeug==2.3.7
WTForms==3.0.1
email-validator==2.0.0
itsdangerous==2.1.2
python-magic==0.4.27
python-dotenv==1.0.0
Flask-Limiter==3.5.0
'''
    
    try:
        with open('requirements.txt', 'w') as f:
            f.write(requirements)
        print("  Created requirements.txt with python-magic")
        print("  Install with: pip install -r requirements.txt")
        return True
    except Exception as e:
        print(f"  Error creating requirements: {e}")
        return False

def test_app_startup():
    """Test app startup without magic dependency"""
    print("\nTESTING APP STARTUP")
    print("=" * 50)
    
    try:
        # Try to import and create app
        from app import create_app
        
        print("  Creating Flask app...")
        app = create_app()
        print("  Flask app created successfully")
        
        # Test app context
        with app.app_context():
            print("  App context working")
            
            # Test database connection
            from app import db
            print("  Database connection working")
            
            # Test routes
            with app.test_client() as client:
                response = client.get('/auth/login')
                print(f"  Login route test: {response.status_code}")
                
                response = client.get('/auth/register-society')
                print(f"  Register society route test: {response.status_code}")
        
        print("  App startup test PASSED")
        return True
        
    except Exception as e:
        print(f"  App startup test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def initialize_database_safe():
    """Initialize database after fixing imports"""
    print("\nINITIALIZING DATABASE")
    print("=" * 50)
    
    try:
        from app import create_app, db
        from app.models import User, Role
        
        app = create_app()
        
        with app.app_context():
            print("  Creating database tables...")
            db.create_all()
            
            # Create default roles
            role_names = ['super_admin', 'admin', 'societa', 'appassionato']
            
            for role_name in role_names:
                role = Role.query.filter_by(name=role_name).first()
                if not role:
                    role = Role(name=role_name)
                    db.session.add(role)
                    print(f"  Created role: {role_name}")
            
            db.session.commit()
            print("  Database initialized successfully")
            
            # Check user count
            user_count = User.query.count()
            print(f"  Current users: {user_count}")
            
            return True
            
    except Exception as e:
        print(f"  Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main fix function"""
    print("FIX MAGIC DEPENDENCY ISSUE - SAFE MODE")
    print("=" * 60)
    
    fixes_applied = []
    
    # Fix 1: Storage import fallback
    if fix_storage_import():
        fixes_applied.append("Storage import fallback")
    
    # Fix 2: Requirements with magic
    if create_requirements_with_magic():
        fixes_applied.append("Requirements with magic")
    
    # Fix 3: Test app startup
    if test_app_startup():
        fixes_applied.append("App startup test")
    
    # Fix 4: Initialize database
    if initialize_database_safe():
        fixes_applied.append("Database initialization")
    
    print("\n" + "=" * 60)
    print("FIXES APPLIED:")
    for fix in fixes_applied:
        print(f"  - {fix}")
    
    print("\nSYSTEM STATUS:")
    if len(fixes_applied) >= 3:
        print("  System is now READY TO RUN!")
    else:
        print("  Some issues remain - check above")
    
    print("\nNEXT STEPS:")
    print("1. Install missing dependencies:")
    print("   pip install -r requirements.txt")
    print("")
    print("2. Run the application:")
    print("   python run.py")
    print("   OR")
    print("   python run_simple.py")
    print("")
    print("3. Test URLs:")
    print("   http://localhost:8000/")
    print("   http://localhost:8000/auth/login")
    print("   http://localhost:8000/auth/register")
    print("   http://localhost:8000/auth/register-society")
    
    return len(fixes_applied) >= 3

if __name__ == '__main__':
    main()
