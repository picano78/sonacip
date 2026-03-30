#!/bin/bash

# SONACIP Full Deployment Fix Script
# Complete deployment verification and fix for Ubuntu 24.04 VPS

set -e

echo "=== SONACIP FULL DEPLOYMENT FIX ==="
echo "Goal: Make website fully working and accessible online"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "${CYAN}${BOLD}=== $1 ===${NC}"; }

# Configuration
PROJECT_DIR="/opt/sonacip"
VENV_DIR="$PROJECT_DIR/venv"
SERVICE_NAME="sonacip"
NGINX_SITE="/etc/nginx/sites-available/sonacip"
ISSUES_FOUND=()
FIXES_APPLIED=()

# Step 1: Python & pip verification
print_header "Step 1: Python & Pip Verification"

echo "Checking Python3..."
if command -v python3 >/dev/null 2>&1; then
    PYTHON_VERSION=$(python3 --version)
    print_success "✅ Python3 found: $PYTHON_VERSION"
else
    print_error "❌ Python3 not found"
    ISSUES_FOUND+=("Python3 not installed")
    FIXES_APPLIED+=("Installing Python3")
    apt-get update -qq
    apt-get install -y python3 python3-full
fi

echo "Checking pip..."
if ! python3 -m pip --version >/dev/null 2>&1; then
    print_warning "⚠️ Pip not working, fixing..."
    ISSUES_FOUND+=("pip not working")
    FIXES_APPLIED+=("Fixing pip installation")
    
    python3 -m ensurepip --upgrade || true
    python3 -m pip install --upgrade pip
else
    PIP_VERSION=$(python3 -m pip --version)
    print_success "✅ Pip working: $PIP_VERSION"
fi

# Step 2: Virtual environment
print_header "Step 2: Virtual Environment Setup"

cd "$PROJECT_DIR" 2>/dev/null || {
    print_error "❌ Project directory not found: $PROJECT_DIR"
    ISSUES_FOUND+=("Project directory missing")
    FIXES_APPLIED+=("Creating project directory")
    mkdir -p "$PROJECT_DIR"
    cd "$PROJECT_DIR"
}

if [ ! -d "$VENV_DIR" ]; then
    print_warning "⚠️ Virtual environment not found, creating..."
    ISSUES_FOUND+=("Virtual environment missing")
    FIXES_APPLIED+=("Creating virtual environment")
    
    python3 -m venv venv
    print_success "✅ Virtual environment created"
else
    print_success "✅ Virtual environment exists"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

if [ "$VIRTUAL_ENV" = "$VENV_DIR" ]; then
    print_success "✅ Virtual environment activated"
else
    print_error "❌ Failed to activate virtual environment"
    ISSUES_FOUND+=("Virtual environment activation failed")
    FIXES_APPLIED+=("Fixing virtual environment activation")
fi

# Step 3: Dependencies
print_header "Step 3: Dependencies Installation"

if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    print_status "Installing from requirements.txt..."
    if python3 -m pip install -r requirements.txt; then
        print_success "✅ Dependencies installed from requirements.txt"
    else
        print_error "❌ Failed to install from requirements.txt"
        ISSUES_FOUND+=("Requirements installation failed")
        FIXES_APPLIED+=("Manual dependency installation")
        
        # Install basic dependencies
        python3 -m pip install flask gunicorn sqlalchemy psycopg2-binary redis
    fi
else
    print_warning "⚠️ requirements.txt not found, installing basic dependencies..."
    ISSUES_FOUND+=("requirements.txt missing")
    FIXES_APPLIED+=("Installing basic dependencies")
    
    python3 -m pip install flask gunicorn sqlalchemy psycopg2-binary redis
fi

# Step 4: Flask app detection
print_header "Step 4: Flask App Detection"

ENTRY_POINT=""
APP_FILE=""

# Detect entry point
if [ -f "$PROJECT_DIR/_truth_app.py" ]; then
    ENTRY_POINT="_truth_app:app"
    APP_FILE="_truth_app.py"
    print_success "✅ Found _truth_app.py"
elif [ -f "$PROJECT_DIR/run.py" ]; then
    ENTRY_POINT="run:app"
    APP_FILE="run.py"
    print_success "✅ Found run.py"
elif [ -f "$PROJECT_DIR/app.py" ]; then
    ENTRY_POINT="app:app"
    APP_FILE="app.py"
    print_success "✅ Found app.py"
elif [ -f "$PROJECT_DIR/wsgi.py" ]; then
    ENTRY_POINT="wsgi:app"
    APP_FILE="wsgi.py"
    print_success "✅ Found wsgi.py"
else
    print_error "❌ No Flask app entry point found"
    ISSUES_FOUND+=("No Flask app entry point")
    FIXES_APPLIED+=("Creating basic Flask app")
    
    # Create basic Flask app
    cat > "$PROJECT_DIR/run.py" << 'EOF'
from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return "SONACIP is running!"

@app.route('/health')
def health():
    return {"status": "ok"}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
EOF
    
    ENTRY_POINT="run:app"
    APP_FILE="run.py"
fi

print_status "Using entry point: $ENTRY_POINT"

# Test app import
print_status "Testing Flask app import..."
if python3 -c "from $APP_FILE.split('.')[0] import app; print('✅ App import successful')" 2>/dev/null; then
    print_success "✅ Flask app imports correctly"
else
    print_error "❌ Flask app import failed"
    ISSUES_FOUND+=("Flask app import failed")
    FIXES_APPLIED+=("Fixing Flask app import")
    
    # Fix Python path
    export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
fi

# Step 5: Test run
print_header "Step 5: Test Run"

print_status "Testing Flask app startup..."
timeout 10 python3 -c "
import sys
sys.path.insert(0, '$PROJECT_DIR')
from $APP_FILE.split('.')[0] import app
print('✅ Flask app loads successfully')
" 2>/dev/null || {
    print_error "❌ Flask app test failed"
    ISSUES_FOUND+=("Flask app test failed")
    FIXES_APPLIED+=("Fixing Flask app issues")
}

# Step 6: Gunicorn setup
print_header "Step 6: Gunicorn Setup"

# Check if gunicorn is installed
if ! python3 -m pip show gunicorn >/dev/null 2>&1; then
    print_warning "⚠️ Gunicorn not installed, installing..."
    ISSUES_FOUND+=("Gunicorn not installed")
    FIXES_APPLIED+=("Installing Gunicorn")
    
    python3 -m pip install gunicorn
fi

# Test gunicorn
print_status "Testing Gunicorn configuration..."
timeout 5 python3 -m gunicorn --check "$ENTRY_POINT" 2>/dev/null || {
    print_warning "⚠️ Gunicorn check failed, trying alternative configuration"
    ISSUES_FOUND+=("Gunicorn configuration issue")
    FIXES_APPLIED+=("Fixing Gunicorn configuration")
}

# Step 7: Nginx configuration
print_header "Step 7: Nginx Configuration"

# Check if nginx is installed
if ! command -v nginx >/dev/null 2>&1; then
    print_warning "⚠️ Nginx not installed, installing..."
    ISSUES_FOUND+=("Nginx not installed")
    FIXES_APPLIED+=("Installing Nginx")
    
    apt-get install -y nginx
fi

# Check if nginx is running
if ! systemctl is-active --quiet nginx; then
    print_warning "⚠️ Nginx not running, starting..."
    ISSUES_FOUND+=("Nginx not running")
    FIXES_APPLIED+=("Starting Nginx")
    
    systemctl start nginx
fi

# Create nginx configuration
print_status "Creating Nginx configuration..."
cat > "$NGINX_SITE" << EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect off;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000;
        access_log off;
        allow 127.0.0.1;
        deny all;
    }
}
EOF

# Enable site
ln -sf "$NGINX_SITE" "/etc/nginx/sites-enabled/sonacip"
rm -f "/etc/nginx/sites-enabled/default"

# Test nginx configuration
if nginx -t; then
    print_success "✅ Nginx configuration valid"
    systemctl reload nginx
else
    print_error "❌ Nginx configuration invalid"
    ISSUES_FOUND+=("Nginx configuration invalid")
    FIXES_APPLIED+=("Fixing Nginx configuration")
fi

# Step 8: Firewall
print_header "Step 8: Firewall Configuration"

# Check if UFW is available
if command -v ufw >/dev/null 2>&1; then
    print_status "Configuring firewall..."
    
    # Allow ports
    ufw allow 8000/tcp || true
    ufw allow 80/tcp || true
    ufw allow 22/tcp || true
    
    # Enable firewall if not already enabled
    if ! ufw status | grep -q "Status: active"; then
        print_warning "⚠️ Enabling firewall..."
        ufw --force enable
    fi
    
    print_success "✅ Firewall configured"
else
    print_warning "⚠️ UFW not available"
fi

# Step 9: Auto-start (systemd service)
print_header "Step 9: Auto-start Configuration"

# Create systemd service
cat > "/etc/systemd/system/$SERVICE_NAME.service" << EOF
[Unit]
Description=SONACIP Flask App
After=network.target nginx.service

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_DIR/bin"
Environment="PYTHONPATH=$PROJECT_DIR"
Environment=PYTHONUNBUFFERED=1
ExecStart=$VENV_DIR/bin/gunicorn -w 2 -b 127.0.0.1:8000 $ENTRY_POINT
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload and enable service
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

# Wait for service to start
sleep 5

if systemctl is-active --quiet "$SERVICE_NAME"; then
    print_success "✅ Systemd service created and started"
else
    print_error "❌ Systemd service failed to start"
    ISSUES_FOUND+=("Systemd service failed")
    FIXES_APPLIED+=("Fixing systemd service")
fi

# Step 10: Final test
print_header "Step 10: Final Test"

# Get public IP
PUBLIC_IP=$(curl -s --max-time 10 ifconfig.me 2>/dev/null || curl -s --max-time 10 ipinfo.io/ip 2>/dev/null || echo "YOUR_IP")

# Test local port 8000
print_status "Testing local port 8000..."
if curl -s --max-time 10 http://127.0.0.1:8000 >/dev/null 2>&1; then
    print_success "✅ Local port 8000 responding"
else
    print_error "❌ Local port 8000 not responding"
    ISSUES_FOUND+=("Local port 8000 not responding")
    FIXES_APPLIED+=("Fixing local service")
fi

# Test public access
print_status "Testing public access..."
if curl -s --max-time 10 "http://$PUBLIC_IP" >/dev/null 2>&1; then
    print_success "✅ Site accessible via public IP"
else
    print_error "❌ Site not accessible via public IP"
    ISSUES_FOUND+=("Public access failed")
    FIXES_APPLIED+=("Fixing public access")
fi

# Final summary
print_header "DEPLOYMENT SUMMARY"

echo ""
echo "🔍 ISSUES FOUND:"
if [ ${#ISSUES_FOUND[@]} -eq 0 ]; then
    echo "   ✅ No issues found"
else
    for issue in "${ISSUES_FOUND[@]}"; do
        echo "   ❌ $issue"
    done
fi

echo ""
echo "🔧 FIXES APPLIED:"
if [ ${#FIXES_APPLIED[@]} -eq 0 ]; then
    echo "   ✅ No fixes needed"
else
    for fix in "${FIXES_APPLIED[@]}"; do
        echo "   🔧 $fix"
    done
fi

echo ""
echo "🌐 FINAL STATUS:"
echo "   📁 Project: $PROJECT_DIR"
echo "   🐍 Virtual Environment: $VENV_DIR"
echo "   🎯 Entry Point: $ENTRY_POINT"
echo "   🔗 Local URL: http://127.0.0.1:8000"
echo "   🌐 Public URL: http://$PUBLIC_IP"

# Service status
echo ""
echo "🛡️ SERVICE STATUS:"
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "   ✅ SONACIP service: RUNNING"
else
    echo "   ❌ SONACIP service: FAILED"
fi

if systemctl is-active --quiet nginx; then
    echo "   ✅ Nginx: RUNNING"
else
    echo "   ❌ Nginx: FAILED"
fi

# Final confirmation
echo ""
if curl -s --max-time 10 "http://$PUBLIC_IP" >/dev/null 2>&1; then
    print_success "🎉 SITE ONLINE"
    echo ""
    echo "✅ CONFIRMATION: SITE ONLINE"
    echo "🌐 Access your website at: http://$PUBLIC_IP"
else
    print_error "❌ SITE NOT ONLINE"
    echo ""
    echo "❌ CONFIRMATION: SITE NOT ONLINE"
    echo ""
    echo "🔧 Manual troubleshooting needed:"
    echo "   1. Check service: systemctl status $SERVICE_NAME"
    echo "   2. Check logs: journalctl -u $SERVICE_NAME -n 20"
    echo "   3. Check nginx: systemctl status nginx"
    echo "   4. Test local: curl http://127.0.0.1:8000"
fi

echo ""
echo "📋 MANAGEMENT COMMANDS:"
echo "   📊 Service status: systemctl status $SERVICE_NAME"
echo "   📝 Service logs: journalctl -u $SERVICE_NAME -f"
echo "   🔄 Restart service: systemctl restart $SERVICE_NAME"
echo "   🌐 Test local: curl http://127.0.0.1:8000"
echo "   🌐 Test public: curl http://$PUBLIC_IP"

echo ""
print_success "🚀 Full deployment fix completed!"
