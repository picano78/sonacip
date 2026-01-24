#!/bin/bash
#
# SONACIP VPS Deployment Script
# Run this script on a fresh Ubuntu/Debian VPS
#

set -e

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                   SONACIP VPS DEPLOYMENT                           ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

echo "📦 Step 1: Installing system dependencies..."
apt-get update
apt-get install -y python3 python3-pip python3-venv nginx postgresql postgresql-contrib git

echo "✅ System dependencies installed"
echo ""

echo "📦 Step 2: Creating application user..."
if ! id "sonacip" &>/dev/null; then
    useradd -m -s /bin/bash sonacip
    echo "✅ User 'sonacip' created"
else
    echo "ℹ️  User 'sonacip' already exists"
fi
echo ""

echo "📦 Step 3: Setting up PostgreSQL database..."
sudo -u postgres psql -c "CREATE DATABASE sonacip;" 2>/dev/null || echo "ℹ️  Database already exists"
sudo -u postgres psql -c "CREATE USER sonacip WITH PASSWORD 'sonacip_secure_password';" 2>/dev/null || echo "ℹ️  User already exists"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE sonacip TO sonacip;"
echo "✅ Database configured"
echo ""

echo "📦 Step 4: Setting up application directory..."
APP_DIR="/opt/sonacip"
mkdir -p $APP_DIR
cd $APP_DIR

# If this is a git repository, pull latest
if [ -d ".git" ]; then
    echo "ℹ️  Git repository found, pulling latest changes..."
    git pull
else
    echo "ℹ️  Copy your application files to $APP_DIR"
fi

echo "✅ Application directory ready"
echo ""

echo "📦 Step 5: Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Virtual environment created and dependencies installed"
echo ""

echo "📦 Step 6: Creating environment configuration..."
cat > .env << 'EOF'
FLASK_ENV=production
SECRET_KEY=CHANGE_THIS_TO_A_RANDOM_SECRET_KEY
DATABASE_URL=postgresql://sonacip:sonacip_secure_password@localhost/sonacip
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=noreply@sonacip.it
EOF

echo "⚠️  IMPORTANT: Edit .env file and update:"
echo "   - SECRET_KEY (generate a random key)"
echo "   - Database password"
echo "   - Email settings"
echo ""

echo "📦 Step 7: Creating required directories..."
mkdir -p logs backups uploads/avatars uploads/covers uploads/posts
chown -R sonacip:sonacip $APP_DIR
echo "✅ Directories created"
echo ""

echo "📦 Step 8: Initializing database..."
sudo -u sonacip bash << 'DBINIT'
source /opt/sonacip/venv/bin/activate
cd /opt/sonacip
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all(); print('Database initialized')"
DBINIT
echo "✅ Database initialized"
echo ""

echo "📦 Step 9: Installing systemd service..."
cat > /etc/systemd/system/sonacip.service << 'EOF'
[Unit]
Description=SONACIP SaaS Platform
After=network.target

[Service]
Type=notify
User=sonacip
Group=sonacip
WorkingDirectory=/opt/sonacip
Environment="PATH=/opt/sonacip/venv/bin"
ExecStart=/opt/sonacip/venv/bin/gunicorn -c /opt/sonacip/gunicorn_config.py run:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable sonacip
echo "✅ Systemd service installed"
echo ""

echo "📦 Step 10: Configuring Nginx..."
cat > /etc/nginx/sites-available/sonacip << 'EOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    location /static {
        alias /opt/sonacip/app/static;
        expires 30d;
    }

    location /uploads {
        alias /opt/sonacip/uploads;
        expires 7d;
    }
}
EOF

ln -sf /etc/nginx/sites-available/sonacip /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx
echo "✅ Nginx configured"
echo ""

echo "📦 Step 11: Starting SONACIP..."
systemctl start sonacip
sleep 3
systemctl status sonacip --no-pager
echo ""

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                    DEPLOYMENT COMPLETE! 🎉                         ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
echo "✅ SONACIP is now running!"
echo ""
echo "📝 Next Steps:"
echo ""
echo "1. Edit configuration:"
echo "   nano /opt/sonacip/.env"
echo ""
echo "2. Restart service:"
echo "   systemctl restart sonacip"
echo ""
echo "3. View logs:"
echo "   journalctl -u sonacip -f"
echo "   tail -f /opt/sonacip/logs/sonacip.log"
echo ""
echo "4. Check status:"
echo "   systemctl status sonacip"
echo ""
echo "5. Access the application:"
echo "   http://your-server-ip/"
echo ""
echo "🔐 Default Admin Credentials:"
echo "   Email: admin@sonacip.it"
echo "   Password: admin123"
echo ""
echo "⚠️  SECURITY WARNINGS:"
echo "   - Change admin password immediately!"
echo "   - Update SECRET_KEY in .env"
echo "   - Configure firewall (ufw)"
echo "   - Set up SSL certificate (certbot)"
echo "   - Update database password"
echo ""
echo "📚 Documentation: /opt/sonacip/PRODUCTION_READY.md"
echo ""
echo "════════════════════════════════════════════════════════════════════"
