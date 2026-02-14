#!/usr/bin/env python3
"""
Test payment automation and menu changes
"""
import ast
import os
import sys

def test_python_syntax():
    """Test Python files have correct syntax"""
    print("Testing Python file syntax...")
    files_to_check = [
        'app/payments/routes.py',
        'app/payments/automation.py',
    ]
    
    for file_path in files_to_check:
        try:
            with open(file_path, 'r') as f:
                ast.parse(f.read())
            print(f"  ✓ {file_path} syntax OK")
        except SyntaxError as e:
            print(f"  ✗ {file_path} has syntax error: {e}")
            return False
    
    return True


def test_automation_functions():
    """Test that new automation functions are defined"""
    print("\nTesting automation functions...")
    
    with open('app/payments/automation.py', 'r') as f:
        content = f.read()
    
    required_functions = [
        'auto_approve_small_payments',
        'send_social_payment_notifications',
        'quick_payment_summary_for_admin',
    ]
    
    for func in required_functions:
        if f"def {func}" in content:
            print(f"  ✓ Function '{func}' exists")
        else:
            print(f"  ✗ Function '{func}' NOT FOUND")
            return False
    
    # Check for AUTO_APPROVE_THRESHOLD constant
    if "AUTO_APPROVE_THRESHOLD" in content:
        print(f"  ✓ AUTO_APPROVE_THRESHOLD constant defined")
    else:
        print(f"  ✗ AUTO_APPROVE_THRESHOLD constant NOT FOUND")
        return False
    
    return True


def test_new_routes():
    """Test that new routes are defined"""
    print("\nTesting new payment routes...")
    
    with open('app/payments/routes.py', 'r') as f:
        content = f.read()
    
    required_routes = [
        ('quick_approve', '/quick-approve/<int:payment_id>'),
        ('quick_reject', '/quick-reject/<int:payment_id>'),
        ('bulk_approve', '/bulk-approve'),
        ('automation_settings', '/automation-settings'),
    ]
    
    for func_name, route in required_routes:
        if f"def {func_name}" in content:
            print(f"  ✓ Route '{func_name}' exists")
        else:
            print(f"  ✗ Route '{func_name}' NOT FOUND")
            return False
    
    return True


def test_menu_changes():
    """Test that menu has been updated to show 'Planner Campo'"""
    print("\nTesting menu changes...")
    
    with open('app/templates/components/navbar.html', 'r') as f:
        content = f.read()
    
    # Check for "Planner Campo" text
    if "Planner Campo" in content:
        print("  ✓ 'Planner Campo' text found in navbar")
    else:
        print("  ✗ 'Planner Campo' text NOT FOUND in navbar")
        return False
    
    # Check for field_planner.index route
    if "field_planner.index" in content:
        print("  ✓ 'field_planner.index' route found in navbar")
    else:
        print("  ✗ 'field_planner.index' route NOT FOUND in navbar")
        return False
    
    return True


def test_template_files():
    """Test that template files exist"""
    print("\nTesting template files...")
    
    required_templates = [
        'app/templates/payments/automation_settings.html',
        'app/templates/payments/admin.html',
    ]
    
    for template in required_templates:
        if os.path.exists(template):
            print(f"  ✓ Template '{template}' exists")
        else:
            print(f"  ✗ Template '{template}' NOT FOUND")
            return False
    
    # Check admin.html has quick action buttons
    with open('app/templates/payments/admin.html', 'r') as f:
        content = f.read()
    
    if 'quick-approve-btn' in content:
        print("  ✓ Quick approve button found in admin template")
    else:
        print("  ✗ Quick approve button NOT FOUND in admin template")
        return False
    
    if 'quick-reject-btn' in content:
        print("  ✓ Quick reject button found in admin template")
    else:
        print("  ✗ Quick reject button NOT FOUND in admin template")
        return False
    
    return True


def main():
    """Run all tests"""
    print("="*60)
    print("SONACIP Payment Automation & Menu Changes Tests")
    print("="*60)
    
    tests = [
        test_python_syntax,
        test_automation_functions,
        test_new_routes,
        test_menu_changes,
        test_template_files,
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        return 0
    else:
        print(f"❌ SOME TESTS FAILED ({passed}/{total})")
        return 1


if __name__ == '__main__':
    sys.exit(main())
