# SONACIP - Admin Login Credentials

## Default Super Admin Credentials

The SONACIP platform is configured with fixed super admin credentials for development and testing environments.

### Credentials

- **Email**: `Picano78@gmail.com`
- **Password**: `Simone78`

### Usage

1. **Initialize the database** (first time only):
   ```bash
   python3 init_db.py
   ```

2. **Start the application**:
   ```bash
   python3 run.py
   # or
   flask run
   ```

3. **Login**:
   - Navigate to `/auth/login`
   - Use the email and password above
   - You will have full super admin access

### Role-Based Authentication

SONACIP uses a **role-based authentication system**, not boolean flags like `is_superadmin`. 

The super admin user is identified by having the `super_admin` role in the database.

#### Available Roles

- `super_admin` - Full system access (level 100)
- `admin` - Administrative access (level 90)
- `moderator` - Content moderation (level 50)
- `society_admin` - Society administrator (level 45)
- `societa` - Sports society (level 40)
- `staff` - Staff member (level 30)
- `coach` - Coach (level 30)
- `atleta` / `athlete` - Athlete (level 20)
- `appassionato` / `user` - Regular user (level 10)
- `guest` - Guest user (level 1)

### Production Security

⚠️ **IMPORTANT**: In production environments, you **MUST** set custom credentials via environment variables:

```bash
export SUPERADMIN_EMAIL="your-admin@yourdomain.com"
export SUPERADMIN_PASSWORD="your-secure-password"
```

Or in your `.env` file:

```env
SUPERADMIN_EMAIL=your-admin@yourdomain.com
SUPERADMIN_PASSWORD=your-secure-password
```

If you don't set these in production, the system will generate random credentials and log them once at startup. Make sure to copy these credentials as they won't be shown again.

### Troubleshooting

#### "Sessione scaduta" (Session Expired)

The session timeout has been extended to 30 days and CSRF token timeout is disabled to prevent this error. If you still see it:

1. Clear your browser cookies
2. Try logging in again

#### Database Already Exists Warning

If you see a message like "Tables already exist - skipping migration", this is normal. The system detects existing tables and avoids recreating them.

#### Testing the Credentials

You can verify the admin credentials are correct by running:

```bash
python3 << 'EOF'
from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    admin = User.query.filter_by(email='Picano78@gmail.com').first()
    if admin and admin.check_password('Simone78'):
        print("✓ Credentials verified!")
    else:
        print("✗ Credentials verification failed")
EOF
```

### Support

For issues or questions, please refer to the main README.md or open an issue on GitHub.
