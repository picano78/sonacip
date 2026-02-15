#!/usr/bin/env python3
"""
Integration test for super admin login fix.
This test verifies the complete authentication flow.
"""
import sys
import os
import subprocess
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_command(cmd, description):
    """Run a command and return success status."""
    print(f"\n{'='*70}")
    print(f"Test: {description}")
    print(f"{'='*70}")
    print(f"Running: {cmd}")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ PASSED")
        if result.stdout:
            print("Output:", result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
        return True
    else:
        print("❌ FAILED")
        print("Error:", result.stderr)
        return False

def test_integration():
    """Run integration tests."""
    print("\n" + "="*70)
    print("SONACIP - Super Admin Login Integration Test")
    print("="*70)
    
    # Create a temporary test database
    test_db = tempfile.mktemp(suffix='.db')
    os.environ['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{test_db}'
    
    try:
        tests_passed = 0
        tests_failed = 0
        
        # Test 1: Initialize database
        if run_command('python3 init_db.py', 'Database Initialization'):
            tests_passed += 1
        else:
            tests_failed += 1
            print("\n⚠️  Database initialization failed - cannot continue tests")
            return False
        
        # Test 2: Run diagnostics
        if run_command('python3 fix_admin_credentials.py', 'Credential Diagnostics'):
            tests_passed += 1
        else:
            tests_failed += 1
        
        # Test 3: Fix credentials
        if run_command('python3 fix_admin_credentials.py --fix', 'Credential Fix'):
            tests_passed += 1
        else:
            tests_failed += 1
        
        # Test 4: Verify password works
        verify_code = """
from app import create_app, db
from app.models import User
app = create_app()
with app.app_context():
    email = app.config.get('SUPERADMIN_EMAIL')
    password = app.config.get('SUPERADMIN_PASSWORD')
    admin = User.query.filter_by(email=email).first()
    if admin and admin.check_password(password):
        print('Password verification successful')
        exit(0)
    else:
        print('Password verification failed')
        exit(1)
"""
        verify_file = tempfile.mktemp(suffix='.py')
        with open(verify_file, 'w') as f:
            f.write(verify_code)
        
        if run_command(f'python3 {verify_file}', 'Password Verification'):
            tests_passed += 1
        else:
            tests_failed += 1
        
        os.unlink(verify_file)
        
        # Print summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"Tests Passed: {tests_passed}")
        print(f"Tests Failed: {tests_failed}")
        print()
        
        if tests_failed == 0:
            print("✅ ALL TESTS PASSED!")
            print()
            print("The super admin login fix is working correctly.")
            print("You can now start the application and login.")
            return True
        else:
            print("❌ SOME TESTS FAILED")
            print()
            print("There may be issues with the super admin login.")
            print("Check the error messages above for details.")
            return False
            
    finally:
        # Cleanup
        if os.path.exists(test_db):
            try:
                os.unlink(test_db)
            except:
                pass

if __name__ == "__main__":
    try:
        success = test_integration()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTests cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
