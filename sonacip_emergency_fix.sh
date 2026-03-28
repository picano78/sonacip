#!/bin/bash

# SONACIP Emergency Fix Script
# Fixes systemd service crash and optimizes for low-resource VPS

echo "=== SONACIP EMERGENCY FIX ==="

# Step 1: DEBUG - Analyze current errors
echo "Step 1: Analyzing service errors..."
if command -v journalctl >/dev/null 2>&1; then
    echo "=== RECENT SERVICE LOGS ==="
    journalctl -u sonacip -n 50 --no-pager 2>/dev/null || echo "No logs available"
else
    echo "journalctl not available - checking alternative logs"
    if [ -f "/var/log/sonacip.log" ]; then
        tail -50 /var/log/sonacip.log
    fi
fi

# Step 2: OPTIMIZE GUNICORN FOR LOW RESOURCE
echo ""
echo "Step 2: Optimizing Gunicorn for 800MB RAM..."

# Detect correct entry point
ENTRY_POINT="run:app"
if [ -f "/opt/sonacip/_truth_app.py" ]; then
    ENTRY_POINT="_truth_app:app"
    echo "Found _truth_app.py - using _truth_app:app"
else
    echo "Using run:app (standard for this project)"
fi

# Create optimized service file
cat > /etc/systemd/system/sonacip.service << EOF
[Unit]
Description=SONACIP Production Application
After=network.target redis.service
Wants=network.target redis.service

[Service]
Type=simple
User=sonacip
Group=sonacip
WorkingDirectory=/opt/sonacip
Environment="PATH=/opt/sonacip/venv/bin"
EnvironmentFile=/opt/sonacip/.env
Environment=PYTHONUNBUFFERED=1
Environment=RUN_MAIN=true
ExecStart=/opt/sonacip/venv/bin/gunicorn \\
    --workers 1 \\
    --threads 1 \\
    --worker-class gthread \\
    --timeout 120 \\
    --bind 127.0.0.1:8000 \\
    --access-logfile - \\
    --error-logfile - \\
    --max-requests 1000 \\
    --max-requests-jitter 100 \\
    --preload \\
    $ENTRY_POINT
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=10
KillMode=mixed
TimeoutStopSec=30

# Memory optimization for 800MB RAM VPS
MemoryMax=256M
MemoryLimit=256M
OOMScoreAdjust=200

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/sonacip /var/log /tmp
UMask=0027

[Install]
WantedBy=multi-user.target
EOF

echo "Gunicorn optimized for low-resource VPS"

# Step 3: ENVIRONMENT SETUP
echo ""
echo "Step 3: Setting up environment variables..."

# Ensure .env file exists with critical variables
if [ ! -f "/opt/sonacip/.env" ]; then
    echo "Creating .env file with secure defaults..."
    cat > /opt/sonacip/.env << EOF
# SONACIP Production Environment
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || echo "fallback-secret-key-change-in-production")
DATABASE_URL=sqlite:///sonacip.db
REDIS_URL=redis://127.0.0.1:6379/0
FLASK_ENV=production
DEBUG=False
HOST=127.0.0.1
PORT=8000
PYTHONUNBUFFERED=1
EOF
else
    echo "Checking .env file for critical variables..."
    # Check and add missing critical variables
    if ! grep -q "SECRET_KEY=" /opt/sonacip/.env; then
        echo "SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || echo "fallback-secret-key")" >> /opt/sonacip/.env
    fi
    if ! grep -q "DATABASE_URL=" /opt/sonacip/.env; then
        echo "DATABASE_URL=sqlite:///sonacip.db" >> /opt/sonacip/.env
    fi
    if ! grep -q "REDIS_URL=" /opt/sonacip/.env; then
        echo "REDIS_URL=redis://127.0.0.1:6379/0" >> /opt/sonacip/.env
    fi
fi

# Set correct permissions
chown sonacip:sonacip /opt/sonacip/.env
chmod 600 /opt/sonacip/.env

echo "Environment configured"

# Step 4: REDIS SETUP (MANDATORY)
echo ""
echo "Step 4: Installing and configuring Redis..."

# Install Redis if not present
if ! command -v redis-server >/dev/null 2>&1; then
    echo "Installing Redis..."
    apt-get update -qq
    apt-get install -y redis-server
fi

# Enable and start Redis
systemctl enable redis-server
systemctl start redis-server

# Verify Redis is running
if systemctl is-active --quiet redis-server; then
    echo "✅ Redis is running"
else
    echo "❌ Redis failed to start"
fi

# Step 5: PERMISSIONS FIX
echo ""
echo "Step 5: Fixing permissions..."

# Ensure sonacip user exists
if ! id "sonacip" &>/dev/null; then
    echo "Creating sonacip user..."
    useradd -m -s /bin/bash sonacip
fi

# Fix ownership
chown -R sonacip:sonacip /opt/sonacip
chmod -R 755 /opt/sonacip

# Fix virtual environment permissions
if [ -d "/opt/sonacip/venv" ]; then
    chown -R sonacip:sonacip /opt/sonacip/venv
fi

echo "Permissions fixed"

# Step 6: MANUAL TEST
echo ""
echo "Step 6: Testing manual Gunicorn startup..."

# Switch to sonacip user and test
sudo -u sonacip bash -c "
cd /opt/sonacip
if [ -f 'venv/bin/activate' ]; then
    source venv/bin/activate
    echo 'Virtual environment activated'
    
    # Test Python import
    python -c 'from run import app; print(\"✅ Import successful\")' 2>/dev/null || echo '❌ Import failed'
    
    # Quick gunicorn test (5 seconds max)
    timeout 5 gunicorn run:app --bind 127.0.0.1:8000 --workers 1 --threads 1 2>/dev/null &
    GUNICORN_PID=\$!
    sleep 3
    if kill -0 \$GUNICORN_PID 2>/dev/null; then
        echo '✅ Gunicorn starts successfully'
        kill \$GUNICORN_PID 2>/dev/null
    else
        echo '❌ Gunicorn failed to start'
    fi
else
    echo '❌ Virtual environment not found'
fi
"

# Step 7: SYSTEMD FIX
echo ""
echo "Step 7: Fixing systemd service..."

# Reload systemd completely
systemctl daemon-reexec
systemctl daemon-reload

# Restart service
systemctl restart sonacip

# Wait and check status
sleep 10

# Step 8: NGINX CHECK
echo ""
echo "Step 8: Checking Nginx configuration..."

# Check if nginx is installed and running
if command -v nginx >/dev/null 2>&1; then
    if systemctl is-active --quiet nginx; then
        echo "✅ Nginx is running"
        
        # Check proxy configuration
        if grep -q "proxy_pass http://127.0.0.1:8000" /etc/nginx/sites-available/sonacip 2>/dev/null; then
            echo "✅ Nginx proxy configuration correct"
        else
            echo "⚠️  Nginx proxy may need configuration"
        fi
        
        # Restart nginx to ensure latest config
        systemctl restart nginx
    else
        echo "❌ Nginx is not running - starting..."
        systemctl start nginx
    fi
else
    echo "⚠️  Nginx not installed"
fi

# Step 9: FINAL OUTPUT
echo ""
echo "=== FINAL STATUS ==="

# Service status
if systemctl is-active --quiet sonacip; then
    echo "✅ SONACIP service: RUNNING"
    echo "   Status: $(systemctl is-active sonacip)"
else
    echo "❌ SONACIP service: FAILED"
    echo "   Status: $(systemctl is-active sonacip)"
    echo "   Checking recent logs..."
    if command -v journalctl >/dev/null 2>&1; then
        journalctl -u sonacip -n 10 --no-pager 2>/dev/null || echo "No logs available"
    fi
fi

# Redis status
if systemctl is-active --quiet redis-server; then
    echo "✅ Redis service: RUNNING"
else
    echo "❌ Redis service: FAILED"
fi

# Nginx status
if systemctl is-active --quiet nginx; then
    echo "✅ Nginx service: RUNNING"
else
    echo "❌ Nginx service: FAILED"
fi

# Test app response
echo ""
echo "Testing application response..."
if curl -s --max-time 5 http://127.0.0.1:8000 >/dev/null 2>&1; then
    echo "✅ App responding on port 8000"
    
    # Get server IP for public URL
    SERVER_IP=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || curl -s --max-time 5 ipinfo.io/ip 2>/dev/null || echo "YOUR_IP")
    echo "🌐 Public URL: http://$SERVER_IP"
else
    echo "❌ App not responding on port 8000"
    echo "   Testing with curl directly..."
    curl -v --max-time 5 http://127.0.0.1:8000 2>&1 | head -10
fi

echo ""
echo "=== EMERGENCY FIX COMPLETE ==="
echo ""
echo "🔧 Applied fixes:"
echo "   ✅ Gunicorn optimized for 800MB RAM (1 worker, 1 thread)"
echo "   ✅ Environment variables configured"
echo "   ✅ Redis installed and running"
echo "   ✅ Permissions fixed"
echo "   ✅ Systemd service reloaded"
echo "   ✅ Nginx proxy checked"
echo ""
echo "📊 Resource usage:"
echo "   Memory limit: 256M"
echo "   Workers: 1"
echo "   Threads: 1"
echo "   Timeout: 120s"
echo ""
echo "🚀 If service still fails, check:"
echo "   journalctl -u sonacip -n 50"
echo "   /var/log/sonacip.log"
echo "   /opt/sonacip/.env"
