#!/usr/bin/env python
"""
Test Register Society Fix - Simple test without full app initialization
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_route_fix():
    """Test that the route was added correctly"""
    print("TESTING REGISTER SOCIETY ROUTE FIX")
    print("=" * 50)
    
    routes_file = 'app/auth/routes.py'
    
    try:
        with open(routes_file, 'r') as f:
            content = f.read()
        
        # Check for both routes
        has_register_society = '@bp.route(\'/register-society\'' in content
        has_register_slash_society = '@bp.route(\'/register/society\'' in content
        
        print(f"Route /register-society exists: {has_register_society}")
        print(f"Route /register/society exists: {has_register_slash_society}")
        
        if has_register_society and has_register_slash_society:
            print("SUCCESS: Both routes are present")
            return True
        else:
            print("FAILED: Missing routes")
            return False
            
    except Exception as e:
        print(f"Error testing route fix: {e}")
        return False

def test_templates_created():
    """Test that templates were created"""
    print("\nTESTING TEMPLATES CREATED")
    print("=" * 50)
    
    templates = [
        'app/templates/base.html',
        'app/templates/auth/register_society.html'
    ]
    
    all_exist = True
    
    for template in templates:
        exists = os.path.exists(template)
        print(f"Template {template}: {'EXISTS' if exists else 'MISSING'}")
        if not exists:
            all_exist = False
    
    if all_exist:
        print("SUCCESS: All templates created")
        return True
    else:
        print("FAILED: Some templates missing")
        return False

def main():
    """Run tests"""
    print("TEST REGISTER SOCIETY 404 FIX")
    print("=" * 60)
    
    success = True
    
    # Test 1: Route fix
    if not test_route_fix():
        success = False
    
    # Test 2: Templates created
    if not test_templates_created():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("REGISTER SOCIETY 404 FIX VERIFIED!")
        print("Route /register-society added")
        print("Templates created")
        print("\nThe fix should resolve the 404 error.")
        print("Try accessing: http://localhost:8000/auth/register-society")
    else:
        print("SOME FIXES FAILED")
        print("Check errors above")
    
    return success

if __name__ == '__main__':
    main()
