# SONACIP - Deployment Guide for IONOS VPS

## Quick Start Commands

```bash
# 1. Login to VPS
ssh root@YOUR_VPS_IP

# 2. Install prerequisites
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv postgresql nginx certbot python3-certbot-nginx git

# 3. Create project directory
mkdir -p /root/sonacip
cd /root/sonacip

# 4. Upload project files (from your computer)
# scp -r ./sonacip/* root@YOUR_VPS_IP:/root/sonacip/

# 5. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 6. Install dependencies
pip install -r requirements.txt

# 7. Configure environment
cp .env.example .env
nano .env  # Edit with your settings

# 8. Initialize database
python init_db.py

# 9. Install systemd service
cp sonacip.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable sonacip

# 10. Configure Nginx
cp deploy/sonacip.nginx.conf /etc/nginx/sites-available/sonacip
ln -s /etc/nginx/sites-available/sonacip /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default  # Remove default site
nginx -t

# 11. Start services
systemctl start sonacip
systemctl restart nginx

# 12. Configure firewall
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable

# 13. SSL Certificate (optional but recommended)
certbot --nginx -d yourdomain.com

# 14. Verify installation
systemctl status sonacip
curl http://localhost:8000
```

## Service Management

```bash
# Start
systemctl start sonacip

# Stop
systemctl stop sonacip

# Restart
systemctl restart sonacip

# Status
systemctl status sonacip

# Logs
journalctl -u sonacip -f
```

## Backup & Restore

```bash
# Create backup
./backup.sh

# Restore backup
./restore.sh /root/sonacip/backups/sonacip_backup_YYYYMMDD_HHMMSS.tar.gz
```

## Troubleshooting

### Service won't start
```bash
# Check logs
journalctl -u sonacip -n 50

# Test manually
source venv/bin/activate
cd /root/sonacip
python run.py
```

### Database connection error
```bash
# Check database exists
ls -la /root/sonacip/uploads/sonacip.db

# Recreate if needed
python init_db.py
```

### Nginx 502 Bad Gateway
```bash
# Check gunicorn is running
ps aux | grep gunicorn

# Restart both
systemctl restart sonacip
systemctl restart nginx
```

## File Structure

```
/root/sonacip/
├── app/              # Application code
├── uploads/          # User uploads & database
├── backups/          # Backup archives
├── logs/             # Application logs
├── migrations/       # Database migrations
├── run.py            # Development entrypoint
├── wsgi.py           # Production entrypoint
├── gunicorn.conf.py  # Gunicorn configuration
├── requirements.txt  # Python dependencies
├── .env              # Environment variables
└── sonacip.service   # Systemd service file
```

## Security Checklist

- [ ] Change default passwords in .env
- [ ] Enable HTTPS with Let's Encrypt
- [ ] Configure firewall (ufw)
- [ ] Set proper file permissions
- [ ] Disable DEBUG mode
- [ ] Configure SESSION_COOKIE_SECURE=True
- [ ] Regular backups

## Default Credentials

**Admin Panel:**
- Email: picano78@gmail.com
- Password: Simone78

**Database:**
- SQLite: /root/sonacip/uploads/sonacip.db

**IMPORTANT:** Change these credentials for production!