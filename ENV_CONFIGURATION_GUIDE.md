# SONACIP Environment Configuration Guide

## Quick Start

Before starting SONACIP, you must configure the required environment variables. Follow these steps:

### 1. Check Your Environment

Run the environment check script:

```bash
python3 check_env.py
```

This script will:
- Create `.env` file from `.env.example` if it doesn't exist
- Validate all required environment variables
- Identify placeholder values that need to be changed
- Provide clear instructions on how to fix issues

### 2. Configure Required Variables

Edit the `.env` file and set the following required variables:

#### For Production (`APP_ENV=production`):

```bash
# Required in production
SECRET_KEY=your-secret-key-here  # Generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
SUPERADMIN_EMAIL=your-email@yourdomain.com
SUPERADMIN_PASSWORD=YourSecurePassword123!

# Recommended for production
DATABASE_URL=postgresql://user:password@localhost:5432/sonacip
MAIL_SERVER=smtp.gmail.com
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

#### For Development (`APP_ENV=development`):

```bash
# Required in development
SECRET_KEY=dev-secret-key  # Can be any string in development

# Optional in development (auto-generated if not set)
SUPERADMIN_EMAIL=admin@localhost
SUPERADMIN_PASSWORD=DevPassword123!
```

### 3. Start the Application

Once your environment is configured:

```bash
# For production
./start.sh

# For development
python3 run.py
```

The start script will automatically run the environment check before starting the server.

## Common Issues

### Issue: "SUPERADMIN_EMAIL and SUPERADMIN_PASSWORD must be set in production!"

**Solution:**
1. Ensure `APP_ENV=production` or `FLASK_ENV=production` is set in your `.env` file
2. Set both `SUPERADMIN_EMAIL` and `SUPERADMIN_PASSWORD` in the `.env` file
3. Make sure the values are not the default placeholders (`Picano78@gmail.com` or `Simone78`)
4. Run `python3 check_env.py` to verify your configuration

### Issue: "SECRET_KEY must be set in production environment!"

**Solution:**
1. Generate a secure secret key:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```
2. Add it to your `.env` file:
   ```bash
   SECRET_KEY=<generated-key>
   ```

### Issue: Missing `.env` file

**Solution:**
The `check_env.py` script will automatically create a `.env` file from `.env.example` if it doesn't exist. However, you must edit this file and replace placeholder values with your actual credentials.

## Security Best Practices

1. **Never commit `.env` file to version control**
   - The `.env` file is already in `.gitignore`
   - Always use environment variables or secure secret management in production

2. **Use strong passwords**
   - Minimum 12 characters
   - Mix of uppercase, lowercase, numbers, and special characters
   - Never use default or example passwords in production

3. **Change credentials after first login**
   - Always change the super admin password immediately after first login
   - Consider enabling two-factor authentication

4. **Rotate secrets regularly**
   - Change `SECRET_KEY` and `SUPERADMIN_PASSWORD` periodically
   - Update the database with new credentials using `update_admin_credentials.py`

## Environment Variables Reference

### Required Variables

| Variable | Description | Required In | Example |
|----------|-------------|-------------|---------|
| `SECRET_KEY` | Secret key for sessions and CSRF | Production | `a1b2c3d4...` |
| `SUPERADMIN_EMAIL` | Super admin email address | Production | `admin@company.com` |
| `SUPERADMIN_PASSWORD` | Super admin password | Production | `SecurePass123!` |

### Recommended Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `APP_ENV` | Application environment | `development` | `production` |
| `DATABASE_URL` | Database connection URL | SQLite | `postgresql://...` |
| `MAIL_SERVER` | SMTP server | - | `smtp.gmail.com` |
| `MAIL_USERNAME` | SMTP username | - | `user@gmail.com` |
| `MAIL_PASSWORD` | SMTP password | - | `app-password` |

For a complete list of available environment variables, see `.env.example`.

## Troubleshooting

If you encounter issues:

1. Run the environment check:
   ```bash
   python3 check_env.py
   ```

2. Check the application logs:
   ```bash
   tail -f logs/sonacip.log
   ```

3. Verify database connectivity:
   ```bash
   python3 check_postgresql.py
   ```

4. For additional help, see:
   - `README.md` - Main documentation
   - `MIGRATION_GUIDE.md` - Migration and upgrade guide
   - `RISOLUZIONE_PROBLEMI.md` - Troubleshooting guide (Italian)
