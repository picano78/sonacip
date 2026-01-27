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

echo "📦 Step 2: Using www-data user for service..."
echo "✅ User 'www-data' will run the service"
echo ""

echo "📦 Step 3: Skipping PostgreSQL setup (SQLite default)"
echo "✅ Database configured (SQLite)"
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
APP_ENV=production
FLASK_ENV=production
SECRET_KEY=REPLACE_ME
DATABASE_URL=sqlite:////opt/sonacip/sonacip.db
USE_PROXYFIX=true
RATELIMIT_STORAGE_URI=memory://
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=noreply@sonacip.it
EOF

# Generate random SECRET_KEY
SECRET_KEY=$(python3 - << 'PY'
import secrets
print(secrets.token_hex(32))
PY
)
sed -i "s|SECRET_KEY=REPLACE_ME|SECRET_KEY=${SECRET_KEY}|" .env

echo "⚠️  IMPORTANT: Edit .env file and update:"
echo "   - Email settings"
echo ""

echo "📦 Step 7: Creating required directories..."
mkdir -p logs backups uploads/avatars uploads/covers uploads/posts
chown -R www-data:www-data $APP_DIR
echo "✅ Directories created"
echo ""

echo "📦 Step 8: Installing systemd service..."
cp /opt/sonacip/deploy/sonacip.service /etc/systemd/system/sonacip.service
systemctl daemon-reload
systemctl enable sonacip
echo "✅ Systemd service installed"
echo ""

echo "📦 Step 9: Configuring Nginx..."
cp /opt/sonacip/deploy/nginx_sonacip.conf /etc/nginx/sites-available/sonacip

ln -sf /etc/nginx/sites-available/sonacip /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx
echo "✅ Nginx configured"
echo ""

echo "📦 Step 10: Starting SONACIP..."
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
echo "   Email: admin@example.com"
echo "   Password: Admin123!"
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
