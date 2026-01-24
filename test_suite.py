#!/usr/bin/env python3
"""
SONACIP Test Suite
Comprehensive tests to verify system integrity
"""
import sys
from app import create_app, db
from app.models import User, Post, Event, Contact, Opportunity, Notification, AuditLog
from datetime import datetime, timedelta

def test_imports():
    """Test that all critical imports work"""
    print("Testing imports...")
    try:
        from app.utils import admin_required, society_required, role_required
        from app.admin.utils import admin_required as admin_req_alias
        from app.models import (User, Post, Comment, Event, Notification,
                                AuditLog, Backup, Message, Contact,
                                Opportunity, CRMActivity)
        print("  ✓ All imports successful")
        return True
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return False


def test_database():
    """Test database structure and basic operations"""
    print("Testing database...")
    app = create_app()
    
    with app.app_context():
        # Check tables exist
        tables = list(db.metadata.tables.keys())
        expected_tables = ['user', 'post', 'comment', 'event', 'notification',
                          'audit_log', 'backup', 'message', 'contact',
                          'opportunity', 'crm_activity']
        
        missing_tables = [t for t in expected_tables if t not in tables]
        if missing_tables:
            print(f"  ✗ Missing tables: {missing_tables}")
            return False
        
        # Check we have a super admin
        admin = User.query.filter_by(role='super_admin').first()
        if not admin:
            print("  ✗ No super admin found")
            return False
        
        print(f"  ✓ Database has {len(tables)} tables")
        print(f"  ✓ Super admin exists: {admin.email}")
        return True


def test_user_roles():
    """Test user role methods"""
    print("Testing user roles...")
    app = create_app()
    
    with app.app_context():
        # Get users of each type
        admin = User.query.filter_by(role='super_admin').first()
        society = User.query.filter_by(role='societa').first()
        athlete = User.query.filter_by(role='atleta').first()
        fan = User.query.filter_by(role='appassionato').first()
        
        if not admin or not society or not athlete or not fan:
            print("  ✗ Missing required test users")
            return False
        
        # Test methods
        if not admin.is_admin():
            print("  ✗ Admin.is_admin() failed")
            return False
        
        if not society.is_society():
            print("  ✗ Society.is_society() failed")
            return False
        
        if not athlete.is_athlete():
            print("  ✗ Athlete.is_athlete() failed")
            return False
        
        print("  ✓ All role methods work correctly")
        return True


def test_relationships():
    """Test database relationships"""
    print("Testing relationships...")
    app = create_app()
    
    with app.app_context():
        society = User.query.filter_by(role='societa').first()
        athlete = User.query.filter_by(role='atleta').first()
        
        if not society or not athlete:
            print("  ✗ Missing test users")
            return False
        
        # Check athlete-society relationship
        if athlete.athlete_society_id != society.id:
            print("  ✗ Athlete-society relationship broken")
            return False
        
        # Check posts relationship
        post_count = Post.query.filter_by(user_id=society.id).count()
        if post_count == 0:
            print("  ! No posts found (expected at least one)")
        
        print("  ✓ Relationships working correctly")
        return True


def test_blueprints():
    """Test all blueprints are registered"""
    print("Testing blueprints...")
    app = create_app()
    
    expected_blueprints = ['main', 'auth', 'admin', 'social', 'events',
                          'notifications', 'backup', 'crm']
    
    registered = list(app.blueprints.keys())
    missing = [bp for bp in expected_blueprints if bp not in registered]
    
    if missing:
        print(f"  ✗ Missing blueprints: {missing}")
        return False
    
    print(f"  ✓ All {len(expected_blueprints)} blueprints registered")
    return True


def test_routes():
    """Test critical routes exist"""
    print("Testing routes...")
    app = create_app()
    
    critical_endpoints = [
        'main.index',
        'auth.login',
        'auth.register',
        'admin.dashboard',
        'social.feed',
        'events.index',
        'crm.index',
    ]
    
    # Check routes are registered in the app
    registered_endpoints = [rule.endpoint for rule in app.url_map.iter_rules()]
    
    missing = [ep for ep in critical_endpoints if ep not in registered_endpoints]
    if missing:
        print(f"  ✗ Missing endpoints: {missing}")
        return False
    
    print(f"  ✓ All {len(critical_endpoints)} critical routes exist")
    return True


def test_startup():
    """Test that the application starts without errors"""
    print("Testing application startup...")
    try:
        app = create_app()
        with app.app_context():
            # Trigger all initialization
            pass
        print("  ✓ Application starts successfully")
        return True
    except Exception as e:
        print(f"  ✗ Startup failed: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("SONACIP TEST SUITE")
    print("=" * 60)
    print()
    
    tests = [
        test_startup,
        test_imports,
        test_database,
        test_blueprints,
        test_routes,
        test_user_roles,
        test_relationships,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
            results.append(False)
        print()
    
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✓ ALL TESTS PASSED ({passed}/{total})")
        print("=" * 60)
        print("\nSONACIP is ready to run!")
        print("\nQuick Start:")
        print("  1. Start the server: python run.py")
        print("  2. Open browser: http://localhost:5000")
        print("  3. Login with: admin@sonacip.it / admin123")
        print("\nTest Accounts:")
        print("  Admin:   admin@sonacip.it / admin123")
        print("  Society: test@societa.it / test123")
        print("  Athlete: test@atleta.it / test123")
        print("  Fan:     test@fan.it / test123")
        return 0
    else:
        print(f"✗ SOME TESTS FAILED ({passed}/{total} passed)")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
