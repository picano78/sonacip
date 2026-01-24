#!/usr/bin/env python
"""
SONACIP System Validation Script
Comprehensive test to ensure the system is production-ready
"""
import sys
from app import create_app, db
from app.models import (
    User, Post, Comment, Event, Notification, AuditLog, 
    Backup, Message, Contact, Opportunity, CRMActivity,
    Role, Permission, Plan, Subscription, Payment, Society
)

app = create_app()
app.config['WTF_CSRF_ENABLED'] = False

def print_header(title):
    """Print a formatted header"""
    print('\n' + '=' * 70)
    print(f'  {title}')
    print('=' * 70)

def test_database_models():
    """Test all database models can be queried"""
    print_header('DATABASE MODELS TEST')
    
    models = [
        ('User', User),
        ('Post', Post),
        ('Comment', Comment),
        ('Event', Event),
        ('Notification', Notification),
        ('AuditLog', AuditLog),
        ('Backup', Backup),
        ('Message', Message),
        ('Contact', Contact),
        ('Opportunity', Opportunity),
        ('CRMActivity', CRMActivity),
        ('Role', Role),
        ('Permission', Permission),
        ('Plan', Plan),
        ('Subscription', Subscription),
        ('Payment', Payment),
        ('Society', Society),
    ]
    
    with app.app_context():
        for name, model in models:
            try:
                count = model.query.count()
                print(f'  ✓ {name:20} - {count} records')
            except Exception as e:
                print(f'  ✗ {name:20} - ERROR: {e}')
                return False
    
    return True

def test_database_initialization():
    """Test database initialization data"""
    print_header('DATABASE INITIALIZATION TEST')
    
    with app.app_context():
        # Check roles
        roles = Role.query.count()
        print(f'  Roles: {roles} (expected: 5)')
        if roles != 5:
            print('  ⚠ Warning: Expected 5 roles')
        
        # Check permissions
        permissions = Permission.query.count()
        print(f'  Permissions: {permissions} (expected: 17)')
        if permissions < 10:
            print('  ⚠ Warning: Too few permissions')
        
        # Check plans
        plans = Plan.query.count()
        print(f'  Plans: {plans} (expected: 4)')
        if plans != 4:
            print('  ⚠ Warning: Expected 4 plans')
        
        # Check super admin
        admin = User.query.filter_by(role='super_admin').first()
        if admin:
            print(f'  ✓ Super Admin exists: {admin.email}')
        else:
            print('  ✗ Super Admin NOT found!')
            return False
        
        # Test admin password
        if admin.check_password('admin123'):
            print('  ✓ Admin password is correct')
        else:
            print('  ✗ Admin password check failed!')
            return False
    
    return True

def test_routes():
    """Test all main routes are accessible"""
    print_header('ROUTES TEST')
    
    with app.test_client() as client:
        # Public routes
        public_routes = [
            ('/', 'Home'),
            ('/auth/login', 'Login'),
            ('/auth/register', 'Register'),
            ('/subscription/plans', 'Plans'),
        ]
        
        print('\n  Public Routes:')
        for url, name in public_routes:
            response = client.get(url)
            status = '✓' if response.status_code == 200 else '✗'
            print(f'    {status} {name:15} [{response.status_code}] {url}')
        
        # Login as admin
        print('\n  Logging in as Super Admin...')
        response = client.post('/auth/login', data={
            'email': 'admin@sonacip.it',
            'password': 'admin123'
        }, follow_redirects=False)
        
        if response.status_code != 302:
            print('    ✗ Login failed!')
            return False
        
        print('    ✓ Login successful')
        
        # Authenticated routes
        auth_routes = [
            ('/admin/dashboard', 'Admin Dashboard'),
            ('/admin/users', 'Admin Users'),
            ('/social/feed', 'Social Feed'),
            ('/events/', 'Events'),
            ('/crm/', 'CRM'),
            ('/notifications/', 'Notifications'),
            ('/backup/', 'Backup'),
            ('/subscription/my-subscription', 'My Subscription'),
        ]
        
        print('\n  Authenticated Routes (as Super Admin):')
        for url, name in auth_routes:
            response = client.get(url, follow_redirects=True)
            status = '✓' if response.status_code == 200 else '✗'
            print(f'    {status} {name:20} [{response.status_code}] {url}')
            
            if response.status_code != 200:
                return False
    
    return True

def test_user_methods():
    """Test user model methods"""
    print_header('USER MODEL METHODS TEST')
    
    with app.app_context():
        admin = User.query.filter_by(role='super_admin').first()
        
        tests = [
            ('is_admin()', admin.is_admin(), True),
            ('is_society()', admin.is_society(), False),
            ('is_staff()', admin.is_staff(), False),
            ('is_athlete()', admin.is_athlete(), False),
            ('get_full_name()', admin.get_full_name(), 'Super Admin'),
        ]
        
        for name, result, expected in tests:
            if result == expected:
                print(f'  ✓ {name:25} = {result}')
            else:
                print(f'  ✗ {name:25} = {result} (expected {expected})')
                return False
        
        # Test permissions
        print('\n  Permission checks:')
        perm_tests = [
            ('users', 'view_all'),
            ('admin', 'access'),
            ('events', 'create'),
        ]
        
        for resource, action in perm_tests:
            has_perm = admin.has_permission(resource, action)
            status = '✓' if has_perm else '✗'
            print(f'    {status} {resource}:{action}')
    
    return True

def test_plan_features():
    """Test plan features"""
    print_header('SUBSCRIPTION PLANS TEST')
    
    with app.app_context():
        plans = Plan.query.order_by(Plan.display_order).all()
        
        for plan in plans:
            print(f'\n  {plan.name} (€{plan.price_monthly}/month):')
            print(f'    - Max Athletes: {plan.max_athletes or "Unlimited"}')
            print(f'    - CRM: {"Yes" if plan.has_crm else "No"}')
            print(f'    - Advanced Stats: {"Yes" if plan.has_advanced_stats else "No"}')
            print(f'    - API Access: {"Yes" if plan.has_api_access else "No"}')
    
    return True

def test_blueprints():
    """Test all blueprints are registered"""
    print_header('BLUEPRINTS TEST')
    
    expected_blueprints = [
        'main', 'auth', 'admin', 'social', 'events',
        'notifications', 'backup', 'crm', 'subscription'
    ]
    
    registered = list(app.blueprints.keys())
    
    print(f'  Expected: {len(expected_blueprints)} blueprints')
    print(f'  Registered: {len(registered)} blueprints')
    
    for bp in expected_blueprints:
        if bp in registered:
            print(f'    ✓ {bp}')
        else:
            print(f'    ✗ {bp} NOT REGISTERED')
            return False
    
    return True

def main():
    """Run all tests"""
    print('\n')
    print('╔' + '═' * 68 + '╗')
    print('║' + ' ' * 20 + 'SONACIP VALIDATION SUITE' + ' ' * 24 + '║')
    print('╚' + '═' * 68 + '╝')
    
    tests = [
        ('Database Models', test_database_models),
        ('Database Initialization', test_database_initialization),
        ('Blueprints', test_blueprints),
        ('User Model Methods', test_user_methods),
        ('Subscription Plans', test_plan_features),
        ('Routes', test_routes),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f'\n  ⚠ {name} test had issues')
        except Exception as e:
            failed += 1
            print(f'\n  ✗ {name} test failed with exception: {e}')
            import traceback
            traceback.print_exc()
    
    # Final summary
    print_header('VALIDATION SUMMARY')
    print(f'  Total Tests: {len(tests)}')
    print(f'  ✓ Passed: {passed}')
    print(f'  ✗ Failed: {failed}')
    
    if failed == 0:
        print('\n  🎉 ALL TESTS PASSED! SONACIP IS PRODUCTION READY!')
        print('\n  Credentials:')
        print('    Email: admin@sonacip.it')
        print('    Password: admin123')
        print('\n  Start with: python run.py')
        print('=' * 70)
        return 0
    else:
        print('\n  ⚠ SOME TESTS FAILED - REVIEW ISSUES ABOVE')
        print('=' * 70)
        return 1

if __name__ == '__main__':
    sys.exit(main())
