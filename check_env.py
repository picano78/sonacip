#!/usr/bin/env python3
"""
Pre-flight environment check for SONACIP
Validates that all required environment variables are properly configured
before attempting to start the application.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def check_environment():
    """Check if all required environment variables are properly configured."""
    
    # Colors for terminal output
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    print(f"\n{BLUE}{BOLD}🔍 SONACIP Environment Check{RESET}")
    print("=" * 70)
    
    # Check if .env file exists
    env_file = Path('.env')
    env_example = Path('.env.example')
    
    if not env_file.exists():
        print(f"\n{YELLOW}⚠️  .env file not found{RESET}")
        if env_example.exists():
            print(f"{YELLOW}   Creating .env from .env.example...{RESET}")
            # Copy .env.example to .env
            env_file.write_text(env_example.read_text())
            print(f"{GREEN}   ✓ .env file created{RESET}")
            print(f"\n{YELLOW}{BOLD}⚠️  IMPORTANT:{RESET}")
            print(f"{YELLOW}   Please edit .env and set your credentials before starting!{RESET}")
        else:
            print(f"{RED}   ✗ .env.example not found - cannot create .env{RESET}")
            return False
    
    # Load environment variables from .env
    load_dotenv()
    
    # Detect environment mode
    app_env = os.getenv('APP_ENV', '').lower()
    flask_env = os.getenv('FLASK_ENV', '').lower()
    is_production = app_env == 'production' or flask_env == 'production'
    
    print(f"\n{BOLD}Environment:{RESET} {app_env or flask_env or 'development'}")
    print()
    
    # Required variables in all environments
    required_vars = {
        'SECRET_KEY': 'Secret key for session management and CSRF protection',
    }
    
    # Additional required variables in production
    if is_production:
        required_vars.update({
            'SUPERADMIN_EMAIL': 'Super admin email address',
            'SUPERADMIN_PASSWORD': 'Super admin password',
        })
    
    # Optional but recommended variables
    recommended_vars = {
        'DATABASE_URL': 'Database connection URL (PostgreSQL recommended for production)',
        'MAIL_SERVER': 'SMTP server for sending emails',
        'MAIL_USERNAME': 'SMTP username',
        'MAIL_PASSWORD': 'SMTP password',
    }
    
    # Development-only recommended variables
    if not is_production:
        recommended_vars.update({
            'SUPERADMIN_EMAIL': 'Super admin email (optional in dev, auto-generated if missing)',
            'SUPERADMIN_PASSWORD': 'Super admin password (optional in dev, auto-generated if missing)',
        })
    
    # Placeholders that should be changed in production
    invalid_placeholders = {
        'SECRET_KEY': ['CHANGEME_GENERATE_WITH_PYTHON_SECRETS', 'your-secret-key-here', ''],
        'SUPERADMIN_EMAIL': ['Picano78@gmail.com', ''],  # Only the default example email
        'SUPERADMIN_PASSWORD': ['Simone78', ''],  # Only the default example password
    }
    
    errors = []
    warnings = []
    
    # Check required variables
    print(f"{BOLD}Required Variables:{RESET}")
    for var, description in required_vars.items():
        value = os.getenv(var, '')
        
        # Check if variable is set
        if not value:
            errors.append(f"{var} is not set")
            print(f"  {RED}✗{RESET} {var:<25} - {RED}NOT SET{RESET}")
            print(f"    {description}")
        # Check if variable has an invalid placeholder value
        elif var in invalid_placeholders and value in invalid_placeholders[var]:
            errors.append(f"{var} has placeholder value")
            print(f"  {RED}✗{RESET} {var:<25} - {RED}PLACEHOLDER VALUE{RESET}")
            print(f"    {description}")
            print(f"    Current value: {value}")
        else:
            # Mask sensitive values
            if 'PASSWORD' in var or 'SECRET' in var or 'KEY' in var:
                display_value = '***' + value[-4:] if len(value) > 4 else '****'
            else:
                display_value = value
            print(f"  {GREEN}✓{RESET} {var:<25} - {GREEN}OK{RESET} ({display_value})")
    
    # Check recommended variables
    if recommended_vars:
        print(f"\n{BOLD}Recommended Variables:{RESET}")
        for var, description in recommended_vars.items():
            value = os.getenv(var, '')
            
            if not value:
                warnings.append(f"{var} is not set (optional)")
                print(f"  {YELLOW}⚠{RESET}  {var:<25} - {YELLOW}NOT SET{RESET}")
                print(f"    {description}")
            elif var in invalid_placeholders and value in invalid_placeholders[var]:
                warnings.append(f"{var} has placeholder value")
                print(f"  {YELLOW}⚠{RESET}  {var:<25} - {YELLOW}PLACEHOLDER{RESET}")
                print(f"    {description}")
            else:
                # Mask sensitive values
                if 'PASSWORD' in var or 'SECRET' in var or 'KEY' in var:
                    display_value = '***' + value[-4:] if len(value) > 4 else '****'
                else:
                    display_value = value
                print(f"  {GREEN}✓{RESET} {var:<25} - OK ({display_value})")
    
    # Print summary
    print("\n" + "=" * 70)
    
    if errors:
        print(f"\n{RED}{BOLD}❌ Environment Check Failed{RESET}")
        print(f"\n{RED}Errors found:{RESET}")
        for error in errors:
            print(f"  • {error}")
        
        print(f"\n{BOLD}How to fix:{RESET}")
        print(f"1. Edit the .env file:")
        print(f"   nano .env")
        print(f"2. Set the required variables:")
        
        if 'SUPERADMIN_EMAIL' in ' '.join(errors):
            print(f"   SUPERADMIN_EMAIL=your-email@example.com")
        if 'SUPERADMIN_PASSWORD' in ' '.join(errors):
            print(f"   SUPERADMIN_PASSWORD=YourSecurePassword123!")
        if 'SECRET_KEY' in ' '.join(errors):
            print(f"   SECRET_KEY=$(python3 -c \"import secrets; print(secrets.token_hex(32))\")")
        
        print(f"3. Run this check again:")
        print(f"   python3 check_env.py")
        print()
        
        return False
    
    if warnings:
        print(f"\n{YELLOW}{BOLD}⚠️  Warnings:{RESET}")
        for warning in warnings:
            print(f"  • {warning}")
        print(f"\n{YELLOW}These are optional but recommended for production use.{RESET}")
    
    print(f"\n{GREEN}{BOLD}✅ Environment Check Passed{RESET}")
    
    if is_production:
        print(f"\n{BOLD}Production Mode Detected{RESET}")
        print(f"{YELLOW}Please ensure:{RESET}")
        print(f"  • Credentials are strong and unique")
        print(f"  • Change the super admin password after first login")
        print(f"  • Never commit .env file to version control")
    else:
        print(f"\n{BOLD}Development Mode{RESET}")
        if not os.getenv('SUPERADMIN_EMAIL') or not os.getenv('SUPERADMIN_PASSWORD'):
            print(f"{YELLOW}Note: Super admin credentials not set.{RESET}")
            print(f"{YELLOW}Random credentials will be generated on first startup.{RESET}")
            print(f"{YELLOW}Check the logs for the generated credentials.{RESET}")
    
    print()
    return True


if __name__ == '__main__':
    success = check_environment()
    sys.exit(0 if success else 1)
