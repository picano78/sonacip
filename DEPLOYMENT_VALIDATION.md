# SONACIP - Quick Deployment Validation Guide
**Fast Reference for Post-Deployment Verification**

---

## 1. Run All Tests (2 minutes)

```bash
cd /opt/sonacip
python -m pytest -v
```

**Expected Result:** `69 passed` with 0 failures

---

## 2. Security Check (30 seconds)

```bash
# Check security headers
curl -I https://your-domain.com

# Should see:
# X-Content-Type-Options: nosniff
# X-Frame-Options: DENY
# Strict-Transport-Security: max-age=63072000
# Content-Security-Policy: ...
```

---

## 3. Test Login (1 minute)

1. Open: `https://your-domain.com/auth/login`
2. Login with super admin credentials
3. Verify redirect to dashboard
4. Logout

**✅ Pass:** Login works, dashboard loads, logout works

---

## 4. Check Admin Panel (1 minute)

1. Login as admin
2. Visit: `/admin/`
3. Check:
   - User list loads
   - Statistics display
   - Audit logs accessible

**✅ Pass:** All admin pages load without errors

---

## 5. Verify File Upload (1 minute)

1. Login as any user
2. Try to upload profile picture
3. Verify only allowed formats work (jpg, png, gif)

**✅ Pass:** Valid files accepted, invalid rejected

---

## 6. Test Social Features (2 minutes)

1. Login as athlete
2. Create a test post
3. Verify post appears in feed
4. Try to like/comment
5. Delete test post

**✅ Pass:** All social features working

---

## 7. Test CRM (2 minutes)

1. Login as society
2. Create test contact
3. Create test opportunity
4. Verify both saved correctly
5. Delete test data

**✅ Pass:** CRM features operational

---

## 8. Test Events (2 minutes)

1. Login as society
2. Create test event
3. Invite athlete
4. Verify athlete receives notification
5. Delete test event

**✅ Pass:** Event system working

---

## 9. Check Notifications (1 minute)

1. Perform action that triggers notification
2. Check notification appears
3. Mark as read
4. Verify counter updates

**✅ Pass:** Notification system working

---

## 10. Verify Backup (2 minutes)

1. Login as admin
2. Go to `/backup/`
3. Create manual backup
4. Verify backup file created

**✅ Pass:** Backup system functional

---

## Quick Health Check Script

Create `health_check.sh`:

```bash
#!/bin/bash

echo "🔍 SONACIP Health Check"
echo "======================="

# Test database
echo -n "Database: "
python -c "from app import create_app, db; app=create_app(); app.app_context().push(); db.session.execute('SELECT 1'); print('✅ OK')"

# Test redis (if used)
if [ -n "$REDIS_URL" ]; then
    echo -n "Redis: "
    redis-cli ping > /dev/null 2>&1 && echo "✅ OK" || echo "❌ FAIL"
fi

# Test HTTP
echo -n "Web Server: "
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ | grep -q 200 && echo "✅ OK" || echo "❌ FAIL"

# Test HTTPS (if configured)
if [ -n "$HTTPS_ENABLED" ]; then
    echo -n "HTTPS: "
    curl -s -o /dev/null -w "%{http_code}" https://localhost/ | grep -q 200 && echo "✅ OK" || echo "❌ FAIL"
fi

# Check logs for errors
echo -n "Recent Errors: "
ERROR_COUNT=$(tail -n 100 logs/sonacip.log | grep -c ERROR)
if [ $ERROR_COUNT -eq 0 ]; then
    echo "✅ None"
else
    echo "⚠️  $ERROR_COUNT errors in last 100 lines"
fi

echo "======================="
echo "Health check complete"
```

Run: `chmod +x health_check.sh && ./health_check.sh`

---

## Critical Paths to Test

### Authentication Flow
```
/auth/login → Dashboard → /auth/logout
```

### Admin Flow
```
/admin/ → /admin/users → /admin/audit-logs → /admin/settings
```

### Social Flow
```
/social/feed → Create Post → Like → Comment → Delete
```

### CRM Flow
```
/crm/contacts → Create → Edit → /crm/opportunities → Create → Link to Contact
```

### Event Flow
```
/events/ → Create Event → Invite Athlete → View RSVPs → Edit → Delete
```

---

## Expected Response Times

- **Home Page:** < 500ms
- **Login:** < 1s
- **Dashboard:** < 1s
- **List Pages:** < 2s
- **Form Submissions:** < 2s
- **File Upload:** < 5s (depends on file size)

---

## Common Issues and Fixes

### Issue: 500 Error on Login
**Fix:** Check DATABASE_URL and SECRET_KEY in .env

### Issue: CSRF Token Errors
**Fix:** Ensure SESSION_COOKIE_SECURE matches HTTPS status

### Issue: File Upload Fails
**Fix:** Check uploads/ directory permissions: `chmod 755 uploads/`

### Issue: Emails Not Sending
**Fix:** Verify SMTP settings in .env

### Issue: Admin Panel Not Accessible
**Fix:** Verify super admin user exists and role is correct

---

## Monitoring Commands

### Check Service Status
```bash
systemctl status sonacip
```

### View Logs (Real-time)
```bash
tail -f logs/sonacip.log
```

### Check Resource Usage
```bash
ps aux | grep gunicorn
free -h
df -h
```

### Database Connections
```bash
# PostgreSQL
psql -c "SELECT count(*) FROM pg_stat_activity;"
```

---

## Emergency Rollback

If issues arise:

```bash
# Stop service
sudo systemctl stop sonacip

# Restore from backup
python manage.py restore backups/latest-backup.sql

# Start service
sudo systemctl start sonacip

# Verify
curl -I http://localhost:8000/
```

---

## Performance Benchmarks

### Database
- User query: < 50ms
- Post feed: < 200ms
- Complex CRM query: < 500ms

### API Endpoints
- GET /api/users: < 100ms
- POST /api/posts: < 300ms
- GET /social/feed: < 500ms

### Load Capacity
- Concurrent users: 100+ (default config)
- Requests/second: 50+ (default config)
- Database connections: 20 (default pool)

---

## Support Checklist

Before contacting support, verify:

- [ ] All tests pass: `pytest`
- [ ] Environment variables set correctly
- [ ] Database accessible
- [ ] Logs checked for errors
- [ ] Disk space available
- [ ] Service running: `systemctl status sonacip`
- [ ] Firewall allows traffic (port 80/443)
- [ ] SSL certificate valid (if HTTPS)

---

## Success Criteria

✅ **Platform is READY when:**

1. All 69 tests pass
2. Security headers present
3. Login/logout works
4. All major features accessible
5. No errors in logs (after startup)
6. File uploads work
7. Notifications deliver
8. Backup system functional
9. Performance within benchmarks
10. Monitoring shows healthy status

---

**Quick Reference Guide** - Keep this handy for deployments!  
**Updated:** February 12, 2026  
**SONACIP Platform**
