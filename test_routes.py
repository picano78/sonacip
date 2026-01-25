#!/usr/bin/env python
"""
Test script to verify all routes are accessible
"""
import os
from app import create_app
from app.models import User

app = create_app()
# Disable CSRF for testing
app.config['WTF_CSRF_ENABLED'] = False

def test_routes():
    """Test main routes"""
    with app.test_client() as client:
        print('=== TESTING PUBLIC ROUTES ===')
        
        public_routes = [
            ('/', 'Home Page'),
            ('/auth/login', 'Login Page'),
            ('/auth/register', 'Register Page'),
            ('/subscription/plans', 'Plans Page'),
        ]
        
        for url, name in public_routes:
            response = client.get(url)
            status = '✓' if response.status_code in [200, 302] else '✗'
            print(f'{status} {name:25} [{response.status_code}] {url}')
        
        print('\n=== TESTING AUTHENTICATED ROUTES (will redirect) ===')
        
        auth_routes = [
            ('/admin/dashboard', 'Admin Dashboard'),
            ('/social/feed', 'Social Feed'),
            ('/events/', 'Events List'),
            ('/crm/', 'CRM Dashboard'),
            ('/notifications/', 'Notifications'),
        ]
        
        for url, name in auth_routes:
            response = client.get(url)
            # These should redirect to login (302) or forbidden (403)
            status = '✓' if response.status_code in [200, 302, 403] else '✗'
            print(f'{status} {name:25} [{response.status_code}] {url}')
        
        # Test with authenticated user
        print('\n=== TESTING AS AUTHENTICATED SUPER ADMIN ===')
        
        # Simulate login
        admin_password = os.environ.get('SUPERADMIN_PASSWORD')
        if not admin_password:
            print('⚠ SUPERADMIN_PASSWORD not set; skipping authenticated admin route checks')
            return

        response = client.post('/auth/login', data={
            'email': 'admin@sonacip.it',
            'password': admin_password
        }, follow_redirects=False)
        
        if response.status_code == 302:
            admin_routes = [
                ('/admin/dashboard', 'Admin Dashboard'),
                ('/social/feed', 'Social Feed'),
                ('/events/', 'Events List'),
                ('/crm/', 'CRM Dashboard'),
            ]
            
            for url, name in admin_routes:
                response = client.get(url, follow_redirects=True)
                status = '✓' if response.status_code == 200 else '✗'
                print(f'{status} {name:25} [{response.status_code}] {url}')
        else:
            print('✗ Login failed')

if __name__ == '__main__':
    test_routes()
