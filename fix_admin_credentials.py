#!/usr/bin/env python3
"""
Script to diagnose and fix super admin credentials.
This script will:
1. Check if the super admin user exists
2. Verify if the password is correct
3. Optionally reset the password to default or custom values
4. Provide detailed diagnostic information

Usage:
  python3 fix_admin_credentials.py                    # Diagnose only
  python3 fix_admin_credentials.py --fix              # Fix using default credentials
  python3 fix_admin_credentials.py --fix --email admin@example.com --password SecurePass123
"""

import sys
import os
import argparse

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User, Role


def diagnose_admin():
    """Diagnose the current state of super admin credentials."""
    app = create_app()
    
    with app.app_context():
        print("\n" + "="*70)
        print("SONACIP - Super Admin Diagnostic Tool")
        print("="*70 + "\n")
        
        # Get configured credentials
        config_email = app.config.get("SUPERADMIN_EMAIL")
        config_password = app.config.get("SUPERADMIN_PASSWORD")
        
        print("📋 Configuration:")
        print(f"   SUPERADMIN_EMAIL: {config_email}")
        print(f"   SUPERADMIN_PASSWORD: {'*' * len(config_password) if config_password else 'NOT SET'}")
        print()
        
        # Check if super_admin role exists
        print("🔍 Checking roles...")
        super_admin_role = Role.query.filter_by(name='super_admin').first()
        if not super_admin_role:
            print("   ❌ Super admin role NOT found in database!")
            print("   💡 Run 'python3 init_db.py' to initialize the database")
            return None, None, None
        print(f"   ✅ Super admin role exists (ID: {super_admin_role.id}, Level: {super_admin_role.level})")
        print()
        
        # Check for users with super_admin role
        print("🔍 Checking super admin users...")
        super_admins = User.query.filter_by(role_id=super_admin_role.id).all()
        
        if not super_admins:
            print("   ❌ NO super admin users found!")
            print("   💡 Run 'python3 init_db.py' to create the super admin user")
            return None, None, None
        
        print(f"   Found {len(super_admins)} super admin user(s):")
        for admin in super_admins:
            print(f"   - ID: {admin.id}, Email: {admin.email}, Username: {admin.username}")
            print(f"     Active: {admin.is_active}, Verified: {admin.is_verified}, Email Confirmed: {getattr(admin, 'email_confirmed', False)}")
        print()
        
        # Find the admin matching configured email
        print("🔍 Looking for configured admin...")
        admin = User.query.filter_by(email=config_email).first()
        
        if not admin:
            print(f"   ❌ User with email '{config_email}' NOT found!")
            if super_admins:
                print(f"   💡 But found {len(super_admins)} other super admin(s)")
                print("   💡 You might need to use a different email or create the user")
            return None, config_email, config_password
        
        print(f"   ✅ Found user: {admin.email} (ID: {admin.id})")
        print()
        
        # Check password
        print("🔍 Testing password...")
        try:
            password_valid = admin.check_password(config_password)
            if password_valid:
                print("   ✅ Password is CORRECT!")
                print()
                print("="*70)
                print("✅ DIAGNOSIS: Everything looks good!")
                print("="*70)
                print("\nIf you're still having login issues, check:")
                print("  1. Browser cookies (clear them and try again)")
                print("  2. CSRF token issues (check browser console for errors)")
                print("  3. Session configuration (check SECRET_KEY is set)")
                print("  4. Application is running and accessible")
                print()
                return admin, config_email, config_password
            else:
                print("   ❌ Password is INCORRECT!")
                print()
                print("="*70)
                print("⚠️  DIAGNOSIS: Password mismatch detected!")
                print("="*70)
                print("\nThe super admin user exists but the password doesn't match.")
                print("Run with --fix to reset the password.")
                print()
                return admin, config_email, config_password
        except Exception as e:
            print(f"   ❌ Error checking password: {e}")
            print()
            print("="*70)
            print("⚠️  DIAGNOSIS: Password verification failed!")
            print("="*70)
            print("\nThere may be a database corruption or password hash issue.")
            print("Run with --fix to reset the password.")
            print()
            return admin, config_email, config_password


def fix_admin_credentials(email=None, password=None):
    """Fix super admin credentials."""
    app = create_app()
    
    with app.app_context():
        # Get default credentials if not provided
        if not email:
            email = app.config.get("SUPERADMIN_EMAIL")
        if not password:
            password = app.config.get("SUPERADMIN_PASSWORD")
        
        print("\n" + "="*70)
        print("SONACIP - Fixing Super Admin Credentials")
        print("="*70 + "\n")
        
        print(f"Target Email: {email}")
        print(f"Target Password: {'*' * len(password)}")
        print()
        
        # Check if super_admin role exists
        super_admin_role = Role.query.filter_by(name='super_admin').first()
        if not super_admin_role:
            print("❌ Super admin role not found!")
            print("   Run 'python3 init_db.py' first to initialize the database")
            return False
        
        # Find or create the admin user
        admin = User.query.filter_by(email=email).first()
        
        if not admin:
            print(f"Creating new super admin user with email: {email}")
            admin = User(
                email=email,
                username=email,
                first_name="Admin",  # Generic name - change after first login
                last_name="",
                is_active=True,
                is_verified=True,
                email_confirmed=True,
                role_obj=super_admin_role,
                role_legacy=super_admin_role.name,
            )
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()
            print(f"✅ Super admin user created successfully!")
        else:
            print(f"Updating existing user: {email} (ID: {admin.id})")
            
            # Ensure all flags are correct
            changed = False
            if admin.role_id != super_admin_role.id:
                admin.role_obj = super_admin_role
                admin.role_legacy = super_admin_role.name
                changed = True
                print("   - Updated role to super_admin")
            
            if not admin.is_active:
                admin.is_active = True
                changed = True
                print("   - Activated account")
            
            if not admin.is_verified:
                admin.is_verified = True
                changed = True
                print("   - Marked as verified")
            
            if not getattr(admin, 'email_confirmed', False):
                admin.email_confirmed = True
                changed = True
                print("   - Confirmed email")
            
            # Always update password
            admin.set_password(password)
            changed = True
            print("   - Updated password")
            
            if changed:
                db.session.commit()
                print(f"✅ Super admin user updated successfully!")
            else:
                print("   No changes needed (already correct)")
        
        # Verify the fix
        print("\n🔍 Verifying fix...")
        admin = User.query.filter_by(email=email).first()
        if admin and admin.check_password(password):
            print("   ✅ Password verification successful!")
            print()
            print("="*70)
            print("✅ SUCCESS! Super admin credentials are now working!")
            print("="*70)
            print()
            print("🔑 Login Credentials:")
            print(f"   Email:    {email}")
            print(f"   Password: {'*' * len(password)}")
            print()
            print("⚠️  IMPORTANT: Change this password after your first login!")
            print()
            return True
        else:
            print("   ❌ Verification failed!")
            print()
            print("="*70)
            print("❌ FAILED: Something went wrong!")
            print("="*70)
            print()
            print("Please check the database and try again.")
            print("If the problem persists, there may be a deeper issue.")
            print()
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Diagnose and fix SONACIP super admin credentials",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Just diagnose (no changes):
  python3 fix_admin_credentials.py
  
  # Fix using default credentials from config:
  python3 fix_admin_credentials.py --fix
  
  # Fix with custom credentials:
  python3 fix_admin_credentials.py --fix --email admin@example.com --password MySecurePass123
        """
    )
    parser.add_argument('--fix', action='store_true', 
                       help='Fix the credentials (default: diagnose only)')
    parser.add_argument('--email', type=str, 
                       help='Email for super admin (default: from config)')
    parser.add_argument('--password', type=str,
                       help='Password for super admin (default: from config)')
    
    args = parser.parse_args()
    
    if args.fix:
        success = fix_admin_credentials(email=args.email, password=args.password)
        sys.exit(0 if success else 1)
    else:
        admin, email, password = diagnose_admin()
        if admin and email and password:
            # Password is correct, all good
            sys.exit(0)
        else:
            # Something is wrong
            print("Run with --fix to attempt automatic repair.")
            sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
