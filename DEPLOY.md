# SONACIP - Deployment Guide for IONOS VPS

## Quick Start Commands (Copy-Paste)

```bash
# 1. Login to VPS
ssh root@YOUR_VPS_IP

# 2. Create directory and upload files
mkdir -p /root/sonacip
# Upload from your computer: scp -r ./sonacip/* root@YOUR_VPS_IP:/root/sonacip/

# 3. Install dependencies
cd /root/sonacip
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
nano .env  # Edit SECRET_KEY, DATABASE_URL

# 5. Install systemd service
cp sonacip.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable sonacip

# 6. Configure Nginx
cp nginx.conf /etc/nginx/sites-available/sonacip
ln -sf /etc/nginx/sites-available/sonacip /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default 2>/dev/null
nginx -t && systemctl restart nginx

# 7. Start
systemctl start sonacip

# 8. Check
systemctl status sonacip
curl http://localhost:8000
```

## Service Commands

```bash
systemctl start sonacip    # Start
systemctl stop sonacip     # Stop
systemctl restart sonacip   # Restart
systemctl status sonacip    # Status
journalctl -u sonacip -f  # Logs
```

## Backup & Restore

```bash
./backup.sh                           # Create backup
./restore.sh backups/sonacip_backup_*.tar.gz  # Restore
```

## File Structure

```
/root/sonacip/
├── run.py              # Development: python run.py
├── wsgi.py            # Production: gunicorn run:app
├── app/               # Application code
├── uploads/           # Database + uploads
├── requirements.txt   # Dependencies
├── sonacip.service   # Systemd service
└── nginx.conf        # Nginx config
```

## Default Credentials

- **Admin**: picano78@gmail.com / Simone78
- **Database**: SQLite at /root/sonacip/uploads/sonacip.db

## IMPORTANT

1. Change `SECRET_KEY` in `.env`
2. Set `FLASK_ENV=production`
3. Set `FLASK_DEBUG=False`
4. Configure firewall: `ufw allow 80/tcp 443/tcp`