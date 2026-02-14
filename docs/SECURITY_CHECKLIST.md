# Security Checklist for Production Deployment

## 🔴 Critical (MUST DO before production)

### Authentication & Authorization

- [ ] **Change default admin credentials**
  - [ ] Set `SUPERADMIN_EMAIL` to a real, monitored email address
  - [ ] Set `SUPERADMIN_PASSWORD` to a strong, unique password (min 12 chars)
  - [ ] Change password immediately after first login
  - [ ] Verify default credentials are NOT in use

- [ ] **Generate strong SECRET_KEY**
  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"
  ```
  - [ ] Set in `.env` file
  - [ ] Verify it's not a placeholder value
  - [ ] Store securely in password manager/vault

- [ ] **Enable HTTPS**
  - [ ] Configure SSL/TLS certificate (Let's Encrypt recommended)
  - [ ] Set `SESSION_COOKIE_SECURE=true` in `.env`
  - [ ] Configure Nginx/Caddy to redirect HTTP to HTTPS
  - [ ] Verify HSTS headers are active
  - [ ] Test SSL configuration: https://www.ssllabs.com/ssltest/

### Database Security

- [ ] **Use PostgreSQL (not SQLite)**
  - [ ] Install and configure PostgreSQL
  - [ ] Set strong database password
  - [ ] Configure `DATABASE_URL` in `.env`
  - [ ] Verify connection works

- [ ] **Restrict database access**
  - [ ] Allow connections only from localhost (or specific IPs)
  - [ ] Use firewall rules to block external database access
  - [ ] Disable remote PostgreSQL access if not needed

- [ ] **Enable database backups**
  - [ ] Configure automated daily backups
  - [ ] Test backup restoration process
  - [ ] Store backups in secure location
  - [ ] Encrypt backup files

### Environment Configuration

- [ ] **Secure .env file**
  - [ ] Verify `.env` is in `.gitignore`
  - [ ] Set file permissions to 600: `chmod 600 .env`
  - [ ] Never commit `.env` to version control
  - [ ] Use environment variables or secrets manager in production

- [ ] **Set production environment**
  - [ ] Set `APP_ENV=production` or `FLASK_ENV=production`
  - [ ] Verify `DEBUG=False` (should be default)
  - [ ] Verify application starts without warnings

### Network Security

- [ ] **Configure firewall (UFW)**
  ```bash
  sudo ufw allow 22/tcp   # SSH
  sudo ufw allow 80/tcp   # HTTP
  sudo ufw allow 443/tcp  # HTTPS
  sudo ufw enable
  ```

- [ ] **Change SSH port (optional but recommended)**
  - [ ] Edit `/etc/ssh/sshd_config`
  - [ ] Set `Port` to non-standard port (e.g., 2222)
  - [ ] Restart SSH: `sudo systemctl restart ssh`

- [ ] **Disable password authentication for SSH**
  - [ ] Set up SSH key authentication
  - [ ] Set `PasswordAuthentication no` in `/etc/ssh/sshd_config`
  - [ ] Restart SSH service

## 🟡 Important (Should do for production)

### Application Security

- [ ] **Configure SMTP for email notifications**
  - [ ] Set `MAIL_SERVER`, `MAIL_USERNAME`, `MAIL_PASSWORD`
  - [ ] Use app-specific password for Gmail
  - [ ] Test email sending

- [ ] **Configure rate limiting**
  - [ ] Verify Redis is running for rate limit storage
  - [ ] Test rate limits are working
  - [ ] Adjust limits if needed

- [ ] **Set up monitoring**
  - [ ] Monitor application logs: `logs/sonacip.log`
  - [ ] Monitor security logs: `logs/security.log`
  - [ ] Set up log rotation (configured automatically)
  - [ ] Consider external monitoring (e.g., Sentry, Datadog)

- [ ] **Configure file uploads**
  - [ ] Verify `MAX_CONTENT_LENGTH` is appropriate (default 50MB)
  - [ ] Verify `ALLOWED_EXTENSIONS` includes only safe types
  - [ ] Test file upload validation

### Server Security

- [ ] **Update system packages**
  ```bash
  sudo apt update
  sudo apt upgrade -y
  ```

- [ ] **Set up automatic security updates**
  ```bash
  sudo apt install unattended-upgrades
  sudo dpkg-reconfigure -plow unattended-upgrades
  ```

- [ ] **Harden SSH configuration**
  - [ ] Disable root login: `PermitRootLogin no`
  - [ ] Use SSH keys instead of passwords
  - [ ] Install fail2ban: `sudo apt install fail2ban`

- [ ] **Configure Nginx security headers**
  - Verify these headers are set (already in `deploy/nginx_sonacip.conf`):
  - [ ] `X-Frame-Options: SAMEORIGIN`
  - [ ] `X-Content-Type-Options: nosniff`
  - [ ] `X-XSS-Protection: 1; mode=block`
  - [ ] `Strict-Transport-Security` (HSTS)

### Backup & Recovery

- [ ] **Set up automated backups**
  - [ ] Database backups (daily)
  - [ ] File uploads backups (daily)
  - [ ] Configuration backups
  - [ ] Store backups off-site

- [ ] **Test restore process**
  - [ ] Practice restoring from backup
  - [ ] Document restoration procedure
  - [ ] Verify backup encryption works

## 🟢 Recommended (Best practices)

### Access Control

- [ ] **Implement IP whitelisting for admin panel** (optional)
  ```nginx
  location /admin {
      allow 1.2.3.4;  # Your IP
      deny all;
      # ... rest of config
  }
  ```

- [ ] **Enable two-factor authentication** (if implemented)

- [ ] **Regular password rotation**
  - [ ] Change admin password every 90 days
  - [ ] Change database password every 90 days
  - [ ] Change SECRET_KEY yearly

### Monitoring & Logging

- [ ] **Set up log aggregation**
  - [ ] Consider ELK stack, Graylog, or cloud solution
  - [ ] Monitor for suspicious activity
  - [ ] Set up alerts for critical errors

- [ ] **Monitor resource usage**
  ```bash
  # Install monitoring tools
  sudo apt install htop iotop
  ```
  - [ ] CPU usage
  - [ ] Memory usage
  - [ ] Disk space
  - [ ] Database connections

- [ ] **Set up uptime monitoring**
  - [ ] Use external service (UptimeRobot, Pingdom, etc.)
  - [ ] Set up alerts for downtime
  - [ ] Monitor SSL certificate expiration

### Code Security

- [ ] **Run security scan**
  ```bash
  python security_scan.py
  ```

- [ ] **Run security tests**
  ```bash
  ./run_security_tests.sh
  ```

- [ ] **Keep dependencies updated**
  ```bash
  pip list --outdated
  # Update carefully, testing after each update
  pip install -U <package-name>
  ```

- [ ] **Regular security audits**
  - [ ] Review user permissions quarterly
  - [ ] Check for unused accounts
  - [ ] Review access logs for anomalies
  - [ ] Update dependencies with security patches

### Database Optimization

- [ ] **Configure database connection pooling**
  - Already configured in `app/core/config.py`
  - [ ] Verify settings are appropriate for your load
  - [ ] Monitor connection pool usage

- [ ] **Enable slow query logging**
  ```sql
  -- In PostgreSQL
  ALTER SYSTEM SET log_min_duration_statement = 1000;  -- 1 second
  ```

- [ ] **Create database indexes** for frequently queried fields

### Compliance

- [ ] **Privacy policy** (if collecting personal data)

- [ ] **Terms of service**

- [ ] **GDPR compliance** (if serving EU users)
  - [ ] Data export functionality
  - [ ] Data deletion functionality
  - [ ] Cookie consent (if using tracking cookies)

## Verification Commands

### Check SECRET_KEY is set
```bash
cd /opt/sonacip
source venv/bin/activate
python -c "from app.core.config import Config; print('✅ OK' if Config.SECRET_KEY and len(Config.SECRET_KEY) > 20 else '❌ WEAK SECRET_KEY')"
```

### Check admin credentials are not default
```bash
python -c "from app.core.config import Config; print('❌ USING DEFAULT CREDENTIALS!' if Config.SUPERADMIN_EMAIL == 'Picano78@gmail.com' else '✅ Custom credentials set')"
```

### Check SSL certificate
```bash
echo | openssl s_client -connect yourdomain.com:443 2>/dev/null | openssl x509 -noout -dates
```

### Check firewall status
```bash
sudo ufw status
```

### Check running services
```bash
sudo systemctl status sonacip
sudo systemctl status postgresql
sudo systemctl status redis-server
sudo systemctl status nginx
```

### Check disk space
```bash
df -h
```

### Check logs for errors
```bash
tail -f /opt/sonacip/logs/sonacip.log
tail -f /opt/sonacip/logs/security.log
sudo journalctl -u sonacip -f
```

## Emergency Response

### If credentials are compromised

1. **Immediately change all passwords**
   ```bash
   python update_admin_credentials.py
   ```

2. **Generate new SECRET_KEY**
   - All sessions will be invalidated (users must re-login)

3. **Review audit logs**
   ```bash
   grep "suspicious" logs/security.log
   ```

4. **Check for unauthorized access**
   - Review user accounts
   - Check for unauthorized admin accounts
   - Review recent database changes

### If system is compromised

1. **Disconnect from network** (if severe)
2. **Review logs** for attack vectors
3. **Restore from clean backup**
4. **Update all credentials**
5. **Patch security vulnerabilities**
6. **Monitor for suspicious activity**

## Regular Maintenance Schedule

### Daily
- [ ] Check logs for errors
- [ ] Verify backups completed successfully
- [ ] Monitor disk space

### Weekly
- [ ] Review security logs
- [ ] Check for suspicious login attempts
- [ ] Monitor resource usage trends

### Monthly
- [ ] Update system packages
- [ ] Review user accounts and permissions
- [ ] Test backup restoration
- [ ] Check SSL certificate expiration

### Quarterly
- [ ] Update application dependencies
- [ ] Security audit
- [ ] Review and rotate credentials
- [ ] Performance review and optimization

### Yearly
- [ ] Change SECRET_KEY (invalidates all sessions)
- [ ] Major dependency updates
- [ ] Full security assessment
- [ ] Disaster recovery drill

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Flask Security Best Practices](https://flask.palletsprojects.com/en/3.0.x/security/)
- [PostgreSQL Security](https://www.postgresql.org/docs/current/security.html)
- [Nginx Security](https://docs.nginx.com/nginx/admin-guide/security-controls/)
