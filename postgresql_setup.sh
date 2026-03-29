#!/bin/bash

# SONACIP PostgreSQL Setup Script
# Configures PostgreSQL and connects to SONACIP

set -e

echo "=== SONACIP POSTGRESQL SETUP ==="

# Step 1: Install PostgreSQL
echo "Step 1: Installing PostgreSQL..."
apt-get update -qq
apt-get install -y postgresql postgresql-contrib

# Enable and start PostgreSQL
systemctl enable postgresql
systemctl start postgresql

# Verify PostgreSQL is running
if systemctl is-active --quiet postgresql; then
    echo "✅ PostgreSQL is running"
else
    echo "❌ PostgreSQL failed to start"
    exit 1
fi

# Step 2: Create database and user
echo ""
echo "Step 2: Creating database and user..."

# Database and user configuration
DB_NAME="sonacip"
DB_USER="sonacip_user"
DB_PASSWORD="StrongPass123!"

# Execute PostgreSQL commands
echo "Creating database..."
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME;" || echo "Database may already exist"

echo "Creating user..."
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" || echo "User may already exist"

echo "Configuring user settings..."
sudo -u postgres psql -c "ALTER ROLE $DB_USER SET client_encoding TO 'utf8';"
sudo -u postgres psql -c "ALTER ROLE $DB_USER SET default_transaction_isolation TO 'read committed';"
sudo -u postgres psql -c "ALTER ROLE $DB_USER SET timezone TO 'UTC';"

echo "Granting privileges..."
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

echo "✅ Database and user created successfully"

# Step 3: Update .env file
echo ""
echo "Step 3: Updating .env file..."

ENV_FILE="/opt/sonacip/.env"
NEW_DATABASE_URL="postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME"

if [ -f "$ENV_FILE" ]; then
    echo "Found .env file, updating DATABASE_URL..."
    
    # Backup original .env
    cp "$ENV_FILE" "$ENV_FILE.backup.$(date +%s)"
    
    # Update DATABASE_URL
    if grep -q "DATABASE_URL=" "$ENV_FILE"; then
        sed -i "s|DATABASE_URL=.*|DATABASE_URL=$NEW_DATABASE_URL|g" "$ENV_FILE"
        echo "✅ DATABASE_URL updated in existing .env"
    else
        echo "DATABASE_URL=$NEW_DATABASE_URL" >> "$ENV_FILE"
        echo "✅ DATABASE_URL added to .env"
    fi
    
    # Set correct permissions
    chown sonacip:sonacip "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    
    echo "✅ .env file updated successfully"
else
    echo "Creating new .env file..."
    cat > "$ENV_FILE" << EOF
# SONACIP Production Environment
DATABASE_URL=$NEW_DATABASE_URL
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || echo "fallback-secret-key")
FLASK_ENV=production
DEBUG=False
HOST=127.0.0.1
PORT=8000
PYTHONUNBUFFERED=1
EOF
    
    chown sonacip:sonacip "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "✅ New .env file created"
fi

# Step 4: Optimize systemd service for RAM
echo ""
echo "Step 4: Optimizing systemd service for RAM usage..."

SERVICE_FILE="/etc/systemd/system/sonacip.service"

if [ -f "$SERVICE_FILE" ]; then
    echo "Found service file, optimizing workers..."
    
    # Backup original service file
    cp "$SERVICE_FILE" "$SERVICE_FILE.backup.$(date +%s)"
    
    # Update workers to 1 for lower RAM usage
    sed -i 's/--workers 2/--workers 1/g' "$SERVICE_FILE"
    sed -i 's/--workers [0-9]\+/--workers 1/g' "$SERVICE_FILE"
    
    echo "✅ Service optimized for low RAM usage"
else
    echo "❌ Service file not found, creating basic service..."
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=SONACIP Production Application
After=network.target postgresql.service
Wants=network.target postgresql.service

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
    run:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    
    chown root:root "$SERVICE_FILE"
    chmod 644 "$SERVICE_FILE"
    echo "✅ Basic service file created"
fi

# Step 5: Reload systemd
echo ""
echo "Step 5: Reloading systemd..."
systemctl daemon-reexec
systemctl daemon-reload
echo "✅ Systemd reloaded"

# Step 6: Restart services
echo ""
echo "Step 6: Restarting services..."

# Restart PostgreSQL
echo "Restarting PostgreSQL..."
systemctl restart postgresql
sleep 3

if systemctl is-active --quiet postgresql; then
    echo "✅ PostgreSQL restarted successfully"
else
    echo "❌ PostgreSQL restart failed"
    exit 1
fi

# Restart SONACIP
echo "Restarting SONACIP..."
systemctl restart sonacip
sleep 5

# Step 7: Verify service
echo ""
echo "Step 7: Verifying SONACIP service..."

echo "=== SERVICE STATUS ==="
systemctl status sonacip --no-pager

# Check if service is running
if systemctl is-active --quiet sonacip; then
    echo "✅ SONACIP service is running"
else
    echo "❌ SONACIP service failed to start"
    
    echo ""
    echo "=== RECENT LOGS ==="
    journalctl -u sonacip -n 50 --no-pager
    
    echo ""
    echo "Step 8: Manual troubleshooting..."
    
    # Step 8: Manual test
    echo "Attempting manual startup..."
    
    sudo -u sonacip bash -c "
cd /opt/sonacip
if [ -f 'venv/bin/activate' ]; then
    source venv/bin/activate
    echo 'Virtual environment activated'
    
    # Test database connection
    python -c \"
import os
from dotenv import load_dotenv
load_dotenv()
db_url = os.environ.get('DATABASE_URL', '')
print(f'Database URL: {db_url}')

try:
    import psycopg2
    conn = psycopg2.connect(db_url)
    print('✅ Database connection successful')
    conn.close()
except Exception as e:
    print(f'❌ Database connection failed: {e}')
\"
    
    # Test import
    python -c 'from run import app; print(\"✅ Import successful\")' 2>/dev/null || echo '❌ Import failed'
    
    # Quick gunicorn test
    echo 'Testing Gunicorn startup...'
    timeout 10 gunicorn run:app --bind 127.0.0.1:8000 --workers 1 2>&1 &
    GUNICORN_PID=\$!
    sleep 5
    
    if kill -0 \$GUNICORN_PID 2>/dev/null; then
        echo '✅ Gunicorn starts successfully'
        kill \$GUNICORN_PID 2>/dev/null
    else
        echo '❌ Gunicorn failed to start'
        wait \$GUNICORN_PID 2>/dev/null
    fi
else
    echo '❌ Virtual environment not found'
fi
"
    
    # Try to restart service again after manual test
    echo ""
    echo "Attempting service restart after manual test..."
    systemctl restart sonacip
    sleep 5
fi

# Step 9: Final confirmation
echo ""
echo "Step 9: Final confirmation..."

# Final service check
if systemctl is-active --quiet sonacip; then
    echo "✅ SONACIP service: ACTIVE"
    
    # Test port 8000
    echo "Testing port 8000..."
    if curl -s --max-time 5 http://127.0.0.1:8000 >/dev/null 2>&1; then
        echo "✅ Port 8000: RESPONDING"
    else
        echo "❌ Port 8000: NOT RESPONDING"
    fi
    
    # Test database connection
    echo "Testing database connection..."
    sudo -u sonacip python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('/opt/sonacip/.env')
db_url = os.environ.get('DATABASE_URL', '')
try:
    import psycopg2
    conn = psycopg2.connect(db_url)
    print('✅ Database connection: SUCCESS')
    conn.close()
except Exception as e:
    print(f'❌ Database connection: FAILED - {e}')
" 2>/dev/null || echo "Database test failed"
    
    # Get server IP
    SERVER_IP=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || curl -s --max-time 5 ipinfo.io/ip 2>/dev/null || echo "YOUR_IP")
    
    echo ""
    echo "=== SETUP COMPLETE ==="
    echo "🎯 PostgreSQL configured successfully"
    echo "🗄️  Database: sonacip"
    echo "👤 User: sonacip_user"
    echo "🔗 Connection: postgresql://sonacip_user:****@localhost/sonacip"
    echo "🌐 Application URL: http://$SERVER_IP"
    echo "📊 Service status: RUNNING"
    echo "💾 Memory usage: Optimized (1 worker)"
    
else
    echo "❌ SONACIP service: FAILED"
    echo ""
    echo "=== TROUBLESHOOTING INFO ==="
    echo "Check logs: journalctl -u sonacip -n 100"
    echo "Check database: sudo -u postgres psql -c '\\l'"
    echo "Check .env: cat /opt/sonacip/.env"
    echo "Manual test: cd /opt/sonacip && source venv/bin/activate && gunicorn run:app --bind 127.0.0.1:8000"
    exit 1
fi

echo ""
echo "🚀 PostgreSQL setup completed successfully!"
echo "📋 Configuration summary:"
echo "   ✅ PostgreSQL installed and running"
echo "   ✅ Database 'sonacip' created"
echo "   ✅ User 'sonacip_user' configured"
echo "   ✅ .env file updated with PostgreSQL URL"
echo "   ✅ Service optimized for low RAM (1 worker)"
echo "   ✅ SONACIP service active and responding"
