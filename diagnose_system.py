#!/usr/bin/env python
"""
System Diagnosis - Senior Backend Engineer
Diagnose and fix SONACIP issues without breaking anything
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_basic_structure():
    """Check basic project structure"""
    print("CHECKING BASIC PROJECT STRUCTURE")
    print("=" * 50)
    
    critical_files = [
        'app/__init__.py',
        'app/models.py',
        'app/auth/routes.py',
        'app/auth/forms.py',
        'run.py',
        '.env'
    ]
    
    all_exist = True
    
    for file_path in critical_files:
        exists = os.path.exists(file_path)
        status = "EXISTS" if exists else "MISSING"
        print(f"  {file_path}: {status}")
        if not exists:
            all_exist = False
    
    return all_exist

def check_database():
    """Check database connectivity"""
    print("\nCHECKING DATABASE")
    print("=" * 50)
    
    try:
        # Try to import without full app initialization
        import sqlite3
        db_path = 'uploads/sonacip.db'
        
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if users table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
            user_table = cursor.fetchone()
            
            if user_table:
                print("  Database: EXISTS")
                print("  User table: EXISTS")
                
                # Count users
                cursor.execute("SELECT COUNT(*) FROM user")
                user_count = cursor.fetchone()[0]
                print(f"  Users in database: {user_count}")
                
                conn.close()
                return True
            else:
                print("  Database: EXISTS")
                print("  User table: MISSING")
                conn.close()
                return False
        else:
            print("  Database: MISSING")
            return False
            
    except Exception as e:
        print(f"  Database check failed: {e}")
        return False

def check_dependencies():
    """Check basic dependencies"""
    print("\nCHECKING DEPENDENCIES")
    print("=" * 50)
    
    critical_deps = [
        ('flask', 'Flask'),
        ('flask_sqlalchemy', 'Flask-SQLAlchemy'),
        ('flask_login', 'Flask-Login'),
        ('flask_wtf', 'Flask-WTF'),
        ('werkzeug', 'Werkzeug'),
        ('wtforms', 'WTForms')
    ]
    
    all_ok = True
    
    for module_name, package_name in critical_deps:
        try:
            __import__(module_name)
            print(f"  {package_name}: OK")
        except ImportError:
            print(f"  {package_name}: MISSING")
            all_ok = False
    
    return all_ok

def check_routes():
    """Check critical routes"""
    print("\nCHECKING CRITICAL ROUTES")
    print("=" * 50)
    
    routes_file = 'app/auth/routes.py'
    
    try:
        with open(routes_file, 'r') as f:
            content = f.read()
        
        critical_routes = [
            ('/login', 'Login route'),
            ('/register', 'User registration'),
            ('/register/society', 'Society registration'),
            ('/register-society', 'Society registration alias')
        ]
        
        all_exist = True
        
        for route, description in critical_routes:
            exists = f"@bp.route('{route}'" in content
            status = "EXISTS" if exists else "MISSING"
            print(f"  {description} ({route}): {status}")
            if not exists:
                all_exist = False
        
        return all_exist
        
    except Exception as e:
        print(f"  Routes check failed: {e}")
        return False

def check_templates():
    """Check templates"""
    print("\nCHECKING TEMPLATES")
    print("=" * 50)
    
    templates = [
        'app/templates/base.html',
        'app/templates/auth/login.html',
        'app/templates/auth/register.html',
        'app/templates/auth/register_society.html'
    ]
    
    all_exist = True
    
    for template in templates:
        exists = os.path.exists(template)
        status = "EXISTS" if exists else "MISSING"
        print(f"  {template}: {status}")
        if not exists:
            all_exist = False
    
    return all_exist

def check_user_model():
    """Check User model structure"""
    print("\nCHECKING USER MODEL")
    print("=" * 50)
    
    try:
        # Try to import models without app context
        sys.path.insert(0, 'app')
        
        # Check if we can at least read the models file
        with open('app/models.py', 'r') as f:
            content = f.read()
        
        critical_methods = [
            'def set_password',
            'def check_password',
            'password_hash',
            'email'
        ]
        
        all_ok = True
        
        for method in critical_methods:
            exists = method in content
            status = "EXISTS" if exists else "MISSING"
            print(f"  {method}: {status}")
            if not exists:
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"  User model check failed: {e}")
        return False

def identify_issues():
    """Identify all issues"""
    print("SYSTEM DIAGNOSIS - SONACIP")
    print("=" * 60)
    
    checks = [
        ("Basic Structure", check_basic_structure),
        ("Database", check_database),
        ("Dependencies", check_dependencies),
        ("Routes", check_routes),
        ("Templates", check_templates),
        ("User Model", check_user_model)
    ]
    
    issues = []
    
    for check_name, check_func in checks:
        try:
            if not check_func():
                issues.append(check_name)
        except Exception as e:
            print(f"  {check_name}: ERROR - {e}")
            issues.append(f"{check_name} (Error)")
    
    print("\n" + "=" * 60)
    if issues:
        print("ISSUES FOUND:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("NO ISSUES FOUND - System is healthy!")
    
    return issues

def fix_missing_dependencies():
    """Fix missing dependencies"""
    print("\nFIXING MISSING DEPENDENCIES")
    print("=" * 50)
    
    missing_deps = []
    
    critical_deps = [
        ('flask', 'Flask'),
        ('flask_sqlalchemy', 'Flask-SQLAlchemy'),
        ('flask_login', 'Flask-Login'),
        ('flask_wtf', 'Flask-WTF'),
        ('werkzeug', 'Werkzeug'),
        ('wtforms', 'WTForms')
    ]
    
    for module_name, package_name in critical_deps:
        try:
            __import__(module_name)
        except ImportError:
            missing_deps.append(package_name)
    
    if missing_deps:
        print(f"Installing missing dependencies: {', '.join(missing_deps)}")
        
        # Create requirements.txt if missing
        requirements = '''Flask==2.3.3
Flask-SQLAlchemy==3.0.5
Flask-Login==0.6.3
Flask-WTF==1.1.1
Werkzeug==2.3.7
WTForms==3.0.1
email-validator==2.0.0
itsdangerous==2.1.2
'''
        
        with open('requirements.txt', 'w') as f:
            f.write(requirements)
        
        print("  Created requirements.txt")
        print("  Install with: pip install -r requirements.txt")
        
        return False
    else:
        print("  All dependencies are installed")
        return True

def fix_missing_templates():
    """Fix missing templates"""
    print("\nFIXING MISSING TEMPLATES")
    print("=" * 50)
    
    # Create directories
    os.makedirs('app/templates/auth', exist_ok=True)
    
    # Create base template if missing
    if not os.path.exists('app/templates/base.html'):
        base_template = '''<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}SONACIP{% endblock %}</title>
    
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    
    {% block extra_head %}{% endblock %}
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('main.index') }}">
                SONACIP
            </a>
            
            <div class="collapse navbar-collapse">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('main.index') }}">Home</a>
                    </li>
                </ul>
                
                <ul class="navbar-nav">
                    {% if current_user.is_authenticated %}
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('auth.logout') }}">Logout</a>
                        </li>
                    {% else %}
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('auth.login') }}">Login</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('auth.register') }}">Registrati</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('auth.register_society') }}">Registra Societa</a>
                        </li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </nav>

    <!-- Flash Messages -->
    <div class="container mt-3">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible fade show" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
    </div>

    <!-- Main Content -->
    <main>
        {% block content %}{% endblock %}
    </main>

    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    
    {% block extra_scripts %}{% endblock %}
</body>
</html>
'''
        
        with open('app/templates/base.html', 'w') as f:
            f.write(base_template)
        print("  Created app/templates/base.html")
    
    # Create login template if missing
    if not os.path.exists('app/templates/auth/login.html'):
        login_template = '''{% extends "base.html" %}

{% block title %}Login - SONACIP{% endblock %}

{% block content %}
<div class="container mt-5">
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header">
                    <h3 class="text-center">Accedi a SONACIP</h3>
                </div>
                <div class="card-body">
                    <form method="POST" action="{{ url_for('auth.login') }}">
                        {{ form.hidden_tag() }}
                        
                        <div class="mb-3">
                            <label for="identifier" class="form-label">Email o Username</label>
                            {{ form.identifier(class="form-control") }}
                            {% if form.identifier.errors %}
                                <div class="text-danger">
                                    {% for error in form.identifier.errors %}
                                        <small>{{ error }}</small>
                                    {% endfor %}
                                </div>
                            {% endif %}
                        </div>
                        
                        <div class="mb-3">
                            <label for="password" class="form-label">Password</label>
                            {{ form.password(class="form-control") }}
                            {% if form.password.errors %}
                                <div class="text-danger">
                                    {% for error in form.password.errors %}
                                        <small>{{ error }}</small>
                                    {% endfor %}
                                </div>
                            {% endif %}
                        </div>
                        
                        <div class="d-grid">
                            <button type="submit" class="btn btn-primary">Accedi</button>
                        </div>
                    </form>
                    
                    <div class="text-center mt-3">
                        <p>Non hai un account? <a href="{{ url_for('auth.register') }}">Registrati</a></p>
                        <p>Sei una societa? <a href="{{ url_for('auth.register_society') }}">Registra la tua societa</a></p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
'''
        
        with open('app/templates/auth/login.html', 'w') as f:
            f.write(login_template)
        print("  Created app/templates/auth/login.html")
    
    return True

def main():
    """Main diagnosis and fix function"""
    print("SONACIP SYSTEM DIAGNOSIS AND FIX")
    print("=" * 60)
    
    # Step 1: Identify issues
    issues = identify_issues()
    
    if not issues:
        print("\nSystem is healthy - No fixes needed!")
        return True
    
    # Step 2: Apply fixes
    print("\nAPPLYING FIXES")
    print("=" * 60)
    
    fixes_applied = []
    
    if "Dependencies" in issues or any("Dependencies" in issue for issue in issues):
        if fix_missing_dependencies():
            fixes_applied.append("Dependencies")
    
    if "Templates" in issues:
        if fix_missing_templates():
            fixes_applied.append("Templates")
    
    # Step 3: Re-check
    print("\nRE-CHECKING SYSTEM")
    print("=" * 60)
    remaining_issues = identify_issues()
    
    print("\n" + "=" * 60)
    if fixes_applied:
        print("FIXES APPLIED:")
        for fix in fixes_applied:
            print(f"  - {fix}")
    
    if remaining_issues:
        print("REMAINING ISSUES:")
        for issue in remaining_issues:
            print(f"  - {issue}")
        print("\nSome issues require manual intervention.")
    else:
        print("ALL ISSUES FIXED - System is now healthy!")
    
    return len(remaining_issues) == 0

if __name__ == '__main__':
    main()
