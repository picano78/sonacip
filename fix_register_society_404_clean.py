#!/usr/bin/env python
"""
Fix Register Society 404 Error - Senior Backend Engineer
Add missing /register-society route alias and create missing templates
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def fix_register_society_route():
    """Add missing /register-society route alias"""
    print("FIXING REGISTER SOCIETY 404 ERROR")
    print("=" * 50)
    
    routes_file = 'app/auth/routes.py'
    
    try:
        with open(routes_file, 'r') as f:
            content = f.read()
        
        # Check if register-society route already exists
        if '@bp.route(\'/register-society\'' in content:
            print("✅ /register-society route already exists")
            return True
        
        # Find the society registration route
        society_route_pos = content.find('@bp.route(\'/register/society\'')
        if society_route_pos == -1:
            print("❌ Society registration route not found")
            return False
        
        print("📝 Adding /register-society alias route...")
        
        # Find the end of the register_society function
        function_start = content.find('def register_society():', society_route_pos)
        if function_start == -1:
            print("❌ register_society function not found")
            return False
        
        # Find the next route definition to determine function end
        next_route_pos = content.find('\n@bp.route(', function_start)
        if next_route_pos == -1:
            next_route_pos = len(content)
        
        # Add the alias route after the function
        alias_route = '''

@bp.route('/register-society', methods=['GET', 'POST'])
@limiter.limit("2 per hour", methods=["POST"])
def register_society_alias():
    """Alias route for society registration."""
    return register_society()
'''
        
        # Insert the alias route
        new_content = content[:next_route_pos] + alias_route + content[next_route_pos:]
        
        with open(routes_file, 'w') as f:
            f.write(new_content)
        
        print("✅ /register-society alias route added successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing register society route: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_missing_templates():
    """Create missing authentication templates"""
    print("\nCREATING MISSING TEMPLATES")
    print("=" * 50)
    
    # Create templates directory structure
    templates_dir = 'app/templates/auth'
    os.makedirs(templates_dir, exist_ok=True)
    
    # Create register_society.html template
    register_society_template = '''{% extends "base.html" %}

{% block title %}Registra Società - SONACIP{% endblock %}

{% block content %}
<div class="container mt-5">
    <div class="row justify-content-center">
        <div class="col-md-10">
            <div class="card">
                <div class="card-header">
                    <h3 class="text-center">Registra Società Sportiva</h3>
                </div>
                <div class="card-body">
                    <form method="POST" action="{{ url_for('auth.register_society') }}">
                        {{ form.hidden_tag() }}
                        
                        <div class="row">
                            <div class="col-md-6">
                                <h5>Dati Account</h5>
                                
                                <div class="mb-3">
                                    <label for="username" class="form-label">Username *</label>
                                    {{ form.username(class="form-control") }}
                                    {% if form.username.errors %}
                                        <div class="text-danger">
                                            {% for error in form.username.errors %}
                                                <small>{{ error }}</small>
                                            {% endfor %}
                                        </div>
                                    {% endif %}
                                </div>
                                
                                <div class="mb-3">
                                    <label for="email" class="form-label">Email *</label>
                                    {{ form.email(class="form-control") }}
                                    {% if form.email.errors %}
                                        <div class="text-danger">
                                            {% for error in form.email.errors %}
                                                <small>{{ error }}</small>
                                            {% endfor %}
                                        </div>
                                    {% endif %}
                                </div>
                                
                                <div class="mb-3">
                                    <label for="password" class="form-label">Password *</label>
                                    {{ form.password(class="form-control") }}
                                    {% if form.password.errors %}
                                        <div class="text-danger">
                                            {% for error in form.password.errors %}
                                                <small>{{ error }}</small>
                                            {% endfor %}
                                        </div>
                                    {% endif %}
                                </div>
                                
                                <div class="mb-3">
                                    <label for="password2" class="form-label">Conferma Password *</label>
                                    {{ form.password2(class="form-control") }}
                                    {% if form.password2.errors %}
                                        <div class="text-danger">
                                            {% for error in form.password2.errors %}
                                                <small>{{ error }}</small>
                                            {% endfor %}
                                        </div>
                                    {% endif %}
                                </div>
                            </div>
                            
                            <div class="col-md-6">
                                <h5>Dati Società</h5>
                                
                                <div class="mb-3">
                                    <label for="company_name" class="form-label">Nome Società *</label>
                                    {{ form.company_name(class="form-control") }}
                                    {% if form.company_name.errors %}
                                        <div class="text-danger">
                                            {% for error in form.company_name.errors %}
                                                <small>{{ error }}</small>
                                            {% endfor %}
                                        </div>
                                    {% endif %}
                                </div>
                                
                                <div class="mb-3">
                                    <label for="company_type" class="form-label">Tipo Società *</label>
                                    {{ form.company_type(class="form-control") }}
                                </div>
                                
                                <div class="mb-3">
                                    <label for="fiscal_code" class="form-label">Codice Fiscale *</label>
                                    {{ form.fiscal_code(class="form-control") }}
                                    {% if form.fiscal_code.errors %}
                                        <div class="text-danger">
                                            {% for error in form.fiscal_code.errors %}
                                                <small>{{ error }}</small>
                                            {% endfor %}
                                        </div>
                                    {% endif %}
                                </div>
                                
                                <div class="mb-3">
                                    <label for="vat_number" class="form-label">Partita IVA</label>
                                    {{ form.vat_number(class="form-control") }}
                                </div>
                                
                                <div class="mb-3">
                                    <label for="phone" class="form-label">Telefono *</label>
                                    {{ form.phone(class="form-control") }}
                                    {% if form.phone.errors %}
                                        <div class="text-danger">
                                            {% for error in form.phone.errors %}
                                                <small>{{ error }}</small>
                                            {% endfor %}
                                        </div>
                                    {% endif %}
                                </div>
                            </div>
                        </div>
                        
                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="address" class="form-label">Indirizzo *</label>
                                    {{ form.address(class="form-control") }}
                                    {% if form.address.errors %}
                                        <div class="text-danger">
                                            {% for error in form.address.errors %}
                                                <small>{{ error }}</small>
                                            {% endfor %}
                                        </div>
                                    {% endif %}
                                </div>
                            </div>
                            
                            <div class="col-md-3">
                                <div class="mb-3">
                                    <label for="city" class="form-label">Città *</label>
                                    {{ form.city(class="form-control") }}
                                    {% if form.city.errors %}
                                        <div class="text-danger">
                                            {% for error in form.city.errors %}
                                                <small>{{ error }}</small>
                                            {% endfor %}
                                        </div>
                                    {% endif %}
                                </div>
                            </div>
                            
                            <div class="col-md-3">
                                <div class="mb-3">
                                    <label for="postal_code" class="form-label">CAP</label>
                                    {{ form.postal_code(class="form-control") }}
                                </div>
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label for="province" class="form-label">Provincia *</label>
                            {{ form.province(class="form-control") }}
                        </div>
                        
                        <div class="d-grid">
                            <button type="submit" class="btn btn-primary btn-lg">Registra Società</button>
                        </div>
                    </form>
                    
                    <div class="text-center mt-3">
                        <p>Hai già un account? <a href="{{ url_for('auth.login') }}">Accedi</a></p>
                        <p>Sei una persona fisica? <a href="{{ url_for('auth.register') }}">Registrati come utente</a></p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
'''
    
    try:
        template_file = f'{templates_dir}/register_society.html'
        with open(template_file, 'w') as f:
            f.write(register_society_template)
        print(f"✅ Created {template_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating templates: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_base_template():
    """Create base template if missing"""
    print("\nCREATING BASE TEMPLATE")
    print("=" * 50)
    
    base_template = '''<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}SONACIP{% endblock %}</title>
    
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Font Awesome -->
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    
    {% block extra_head %}{% endblock %}
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('main.index') }}">
                <i class="fas fa-futbol"></i> SONACIP
            </a>
            
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('main.index') }}">Home</a>
                    </li>
                    {% if current_user.is_authenticated %}
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('main.dashboard') }}">Dashboard</a>
                        </li>
                    {% endif %}
                </ul>
                
                <ul class="navbar-nav">
                    {% if current_user.is_authenticated %}
                        <li class="nav-item dropdown">
                            <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                                <i class="fas fa-user"></i> {{ current_user.username }}
                            </a>
                            <ul class="dropdown-menu">
                                <li><a class="dropdown-item" href="{{ url_for('auth.profile') }}">Profilo</a></li>
                                <li><hr class="dropdown-divider"></li>
                                <li><a class="dropdown-item" href="{{ url_for('auth.logout') }}">Logout</a></li>
                            </ul>
                        </li>
                    {% else %}
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('auth.login') }}">Login</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('auth.register') }}">Registrati</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('auth.register_society') }}">Registra Società</a>
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
    
    try:
        base_file = 'app/templates/base.html'
        os.makedirs('app/templates', exist_ok=True)
        
        with open(base_file, 'w') as f:
            f.write(base_template)
        print(f"✅ Created {base_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating base template: {e}")
        return False

def test_fix():
    """Test the fix"""
    print("\nTESTING THE FIX")
    print("=" * 50)
    
    try:
        from app import create_app
        app = create_app()
        
        with app.test_client() as client:
            # Test both URLs
            urls_to_test = [
                ('/auth/register-society', 'register-society URL'),
                ('/auth/register/society', 'register/society URL')
            ]
            
            all_passed = True
            
            for url, description in urls_to_test:
                print(f"Testing {description}...")
                response = client.get(url)
                
                if response.status_code == 200:
                    print(f"   ✅ {description}: OK")
                else:
                    print(f"   ❌ {description}: FAILED ({response.status_code})")
                    all_passed = False
            
            if all_passed:
                print("\n✅ Both URLs working correctly!")
                return True
            else:
                print("\n❌ Some URLs still failing")
                return False
                
    except Exception as e:
        print(f"❌ Error testing fix: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all fixes"""
    print("FIX REGISTER SOCIETY 404 ERROR")
    print("=" * 60)
    
    success = True
    
    # Fix 1: Add missing route
    if not fix_register_society_route():
        success = False
    
    # Fix 2: Create missing templates
    if not create_missing_templates():
        success = False
    
    # Fix 3: Create base template
    if not create_base_template():
        success = False
    
    # Fix 4: Test the solution
    if not test_fix():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("REGISTER SOCIETY 404 ERROR FIXED!")
        print("/auth/register-society route added")
        print("Templates created")
        print("Both URLs working")
        print("\nTry accessing:")
        print("  • http://localhost:8000/auth/register-society")
        print("  • http://localhost:8000/auth/register/society")
    else:
        print("SOME FIXES FAILED")
        print("Check errors above")
    
    return success

if __name__ == '__main__':
    main()
