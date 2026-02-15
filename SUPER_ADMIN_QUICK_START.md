# SONACIP Super Admin Login - Quick Start Guide

## ✅ The Fix Has Been Applied

This repository now includes improvements to prevent and fix super admin login issues.

## 🚀 Quick Start - First Time Setup

### 1. Initialize the Database

```bash
python3 init_db.py
```

You should see output like:
```
✓ Database connection verified
✓ Database schema created via create_all()
✓ Seed completed
✓ Database initialized
```

### 2. Verify Credentials Work

```bash
python3 fix_admin_credentials.py
```

You should see:
```
✅ DIAGNOSIS: Everything looks good!
```

If you see any errors, run the fix:
```bash
python3 fix_admin_credentials.py --fix
```

### 3. Start the Application

```bash
python3 run.py
```

### 4. Login

Navigate to `http://localhost:5000/auth/login` and use:
- **Email**: (Check your `.env` file or use defaults from config)
- **Password**: (Check your `.env` file or use defaults from config)

**Note**: Default credentials are in `app/core/config.py` if no `.env` file is configured.

## 🔧 Troubleshooting

### Problem: "Credenziali non valide" (Invalid credentials)

**Solution 1** - Use the diagnostic tool:
```bash
# Check what's wrong
python3 fix_admin_credentials.py

# If it finds issues, fix them
python3 fix_admin_credentials.py --fix
```

**Solution 2** - Set custom credentials:
```bash
# Create .env file
cp .env.example .env

# Edit .env and set:
# SUPERADMIN_EMAIL=your-email@example.com
# SUPERADMIN_PASSWORD=YourSecurePassword123!

# Fix credentials
python3 fix_admin_credentials.py --fix --email your-email@example.com --password YourSecurePassword123!
```

**Solution 3** - Reinitialize database (⚠️ WARNING: Deletes all data):
```bash
# Backup first!
cp uploads/sonacip.db uploads/sonacip.db.backup

# Remove and reinitialize
rm uploads/sonacip.db
python3 init_db.py
```

### Problem: Database not initialized

**Symptoms**:
- Error about missing tables
- User not found errors
- Application won't start

**Solution**:
```bash
python3 init_db.py
```

### Problem: Can't remember what credentials were set

**Solution**:
```bash
# The diagnostic tool will show you what's configured
python3 fix_admin_credentials.py

# Look for the "Configuration:" section which shows the email
# (password is masked for security)
```

## 📚 Documentation

- **`SUPER_ADMIN_LOGIN_FIX.md`** - Detailed technical documentation about the fix
- **`ADMIN_LOGIN.md`** - General admin login documentation
- **`FAQ_CREDENZIALI_ADMIN.md`** - FAQ about credentials (Italian)
- **`CREDENZIALI_ADMIN.txt`** - Quick reference guide (Italian)

## 🔐 Security Best Practices

1. **Never use default credentials in production**
   - Always set custom `SUPERADMIN_EMAIL` and `SUPERADMIN_PASSWORD` in `.env`

2. **Change password after first login**
   - Go to your profile and change the password immediately

3. **Use strong passwords**
   - Minimum 12 characters
   - Mix of uppercase, lowercase, numbers, and symbols

4. **Keep .env file secure**
   - Never commit `.env` to version control (it's in `.gitignore`)
   - Restrict file permissions: `chmod 600 .env`

## 🆘 Still Having Issues?

1. Check application logs:
   ```bash
   tail -f logs/sonacip.log
   ```

2. Look for error messages containing:
   - "Login failed"
   - "Password"
   - "Super admin"

3. Run verbose diagnostics:
   ```bash
   python3 fix_admin_credentials.py 2>&1 | tee diagnostic_output.txt
   ```

4. Check the database exists:
   ```bash
   ls -lh uploads/sonacip.db
   ```

5. Verify Flask is installed:
   ```bash
   python3 -c "import flask; print('Flask OK')"
   ```

## ✨ What Was Fixed

This fix addresses:
- Silent password update failures during database seeding
- Lack of diagnostic tools for credential issues
- Insufficient logging for authentication debugging

**Key improvements:**
- ✅ Better error handling with detailed logging
- ✅ Automatic password repair during seeding
- ✅ Diagnostic tool to verify and fix credentials
- ✅ Enhanced security logging
- ✅ Comprehensive documentation

## 📞 Support

For more help, see:
- Main README.md
- RISOLUZIONE_PROBLEMI.md (Italian troubleshooting guide)
- Open an issue on GitHub

---

**Last Updated**: February 2026  
**Version**: 1.0 (Super Admin Login Fix)
