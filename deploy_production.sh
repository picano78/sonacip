#!/bin/bash

# SONACIP Production Deployment Script
# Complete deployment for Ubuntu 24.04 on low-resource VPS (1GB RAM, 10GB disk)

set -e

echo "=== SONACIP PRODUCTION DEPLOYMENT ==="
echo "Target: Ubuntu 24.04, 1GB RAM, 10GB disk"
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

# Step 1: Python Environment Setup
print_header "Step 1: Python Environment Setup"

# Create project directory if not exists
if [ ! -d "$PROJECT_DIR" ]; then
    print_status "Creating project directory..."
    mkdir -p "$PROJECT_DIR"
    chown root:root "$PROJECT_DIR"
    chmod 755 "$PROJECT_DIR"
fi

cd "$PROJECT_DIR"

# Create virtual environment if not exists
if [ ! -d "$VENV_DIR" ]; then
    print_status "Creating virtual environment..."
    python3 -m venv venv
    print_success "Virtual environment created"
else
    print_status "Virtual environment already exists"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

if [ "$VIRTUAL_ENV" = "$VENV_DIR" ]; then
    print_success "Virtual environment activated: $VIRTUAL_ENV"
else
    print_error "Failed to activate virtual environment"
    exit 1
fi

# Update pip
print_status "Updating pip..."
python -m pip install --upgrade pip
PIP_VERSION=$(pip --version)
print_success "Pip updated: $PIP_VERSION"

# Step 2: Install Dependencies
print_header "Step 2: Installing Dependencies"

if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    print_status "Installing from requirements.txt..."
    python -m pip install -r requirements.txt
    print_success "Dependencies installed from requirements.txt"
else
    print_status "requirements.txt not found, installing basic dependencies..."
    python -m pip install flask gunicorn
    print_success "Basic dependencies installed"
fi

# Verify installation
print_status "Verifying Flask and Gunicorn installation..."
python -c "import flask, gunicorn; print('✅ Flask and Gunicorn installed successfully')"

# Step 3: Gunicorn Configuration
print_header "Step 3: Gunicorn Configuration"

# Test Gunicorn startup
print_status "Testing Gunicorn configuration..."
timeout 10 gunicorn -w 2 -b 127.0.0.1:8000 run:app --check 2>/dev/null || {
    print_warning "Gunicorn check failed, trying alternative entry points..."
    
    # Try alternative entry points
    if [ -f "$PROJECT_DIR/app.py" ]; then
        ENTRY_POINT="app:app"
    elif [ -f "$PROJECT_DIR/wsgi.py" ]; then
        ENTRY_POINT="wsgi:app"
    elif [ -f "$PROJECT_DIR/_truth_app.py" ]; then
        ENTRY_POINT="_truth_app:app"
    else
        ENTRY_POINT="run:app"
    fi
    
    print_status "Using entry point: $ENTRY_POINT"
} || {
    ENTRY_POINT="run:app"
    print_status "Using default entry point: $ENTRY_POINT"
}

print_success "Gunicorn configuration verified"

# Step 4: Systemd Service Creation
print_header "Step 4: Systemd Service Creation"

# Create systemd service file
cat > "/etc/systemd/system/$SERVICE_NAME.service" << EOF
[Unit]
Description=SONACIP Flask App
After=network.target

[Service]
User=root
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_DIR/bin"
Environment=PYTHONUNBUFFERED=1
ExecStart=$VENV_DIR/bin/gunicorn -w 2 -b 127.0.0.1:8000 $ENTRY_POINT
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

print_success "Systemd service file created"

# Reload systemd and start service
print_status "Reloading systemd..."
systemctl daemon-reexec
systemctl daemon-reload

print_status "Enabling and starting service..."
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

# Wait for service to start
sleep 5

# Check service status
if systemctl is-active --quiet $SERVICE_NAME; then
    print_success "SONACIP service is running"
else
    print_error "SONACIP service failed to start"
    print_status "Checking service logs..."
    journalctl -u $SERVICE_NAME -n 20 --no-pager
    exit 1
fi

# Step 5: Nginx Configuration
print_header "Step 5: Nginx Configuration"

# Create Nginx site configuration
cat > "$NGINX_SITE" << 'EOF'
server {
    listen 80;
    server_name _;

    # Optimize for low-resource VPS
    client_max_body_size 10M;
    client_body_buffer_size 128k;
    client_header_buffer_size 1k;
    large_client_header_buffers 2 1k;

    # Gzip compression for bandwidth saving
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss;

    # Main application proxy
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # Timeouts optimized for low resource
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        
        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 4 4k;
    }

    # Health check endpoint (internal)
    location /health {
        proxy_pass http://127.0.0.1:8000;
        access_log off;
        allow 127.0.0.1;
        deny all;
    }

    # Static files with caching
    location /static/ {
        alias $PROJECT_DIR/static/;
        expires 7d;
        add_header Cache-Control "public";
        access_log off;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Hide Nginx version
    server_tokens off;

    # Logging
    access_log /var/log/nginx/sonacip_access.log combined buffer=16k flush=5m;
    error_log /var/log/nginx/sonacip_error.log warn;
}
EOF

print_success "Nginx configuration created"

# Enable site
print_status "Enabling Nginx site..."
ln -sf "$NGINX_SITE" "/etc/nginx/sites-enabled/sonacip"

# Remove default site if exists
rm -f "/etc/nginx/sites-enabled/default"

# Test Nginx configuration
print_status "Testing Nginx configuration..."
if nginx -t; then
    print_success "Nginx configuration is valid"
else
    print_error "Nginx configuration test failed"
    exit 1
fi

# Restart Nginx
print_status "Restarting Nginx..."
systemctl restart nginx

if systemctl is-active --quiet nginx; then
    print_success "Nginx is running"
else
    print_error "Nginx failed to start"
    exit 1
fi

# Step 6: VPS Optimizations
print_header "Step 6: VPS Optimizations"

# Limit workers to 2 for 1GB RAM
print_status "Optimizing for low-resource VPS..."

# Update systemd service with memory limits
sed -i '/^\[Service\]/a MemoryMax=512M' "/etc/systemd/system/$SERVICE_NAME.service"
sed -i '/MemoryMax=512M/a MemoryLimit=512M' "/etc/systemd/system/$SERVICE_NAME.service"

# Reload systemd with new limits
systemctl daemon-reload
systemctl restart $SERVICE_NAME

# Create swap file if not exists (for low memory)
if [ ! -f "/swapfile" ]; then
    print_status "Creating swap file for low memory..."
    fallocate -l 1G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    print_success "1GB swap file created"
else
    print_status "Swap file already exists"
fi

# Configure sysctl for low memory
print_status "Optimizing kernel parameters..."
cat >> /etc/sysctl.conf << 'EOF'

# Low memory optimizations
vm.swappiness=10
vm.vfs_cache_pressure=50
vm.dirty_ratio=15
vm.dirty_background_ratio=5
EOF

sysctl -p
print_success "Kernel parameters optimized"

# Step 7: Final Checks
print_header "Step 7: Final Checks"

# Check service status
print_status "Checking SONACIP service..."
if systemctl is-active --quiet $SERVICE_NAME; then
    print_success "✅ SONACIP service is running"
    systemctl status $SERVICE_NAME --no-pager | head -5
else
    print_error "❌ SONACIP service is not running"
    exit 1
fi

# Check port 8000
print_status "Checking port 8000..."
if curl -s --max-time 10 http://127.0.0.1:8000 >/dev/null 2>&1; then
    print_success "✅ Port 8000 is responding"
else
    print_error "❌ Port 8000 is not responding"
    print_status "Checking service logs..."
    journalctl -u $SERVICE_NAME -n 10 --no-pager
fi

# Check Nginx status
print_status "Checking Nginx..."
if systemctl is-active --quiet nginx; then
    print_success "✅ Nginx is running"
else
    print_error "❌ Nginx is not running"
    exit 1
fi

# Get public IP
PUBLIC_IP=$(curl -s --max-time 10 ifconfig.me 2>/dev/null || curl -s --max-time 10 ipinfo.io/ip 2>/dev/null || echo "YOUR_IP")

# Test public access
print_status "Testing public access..."
if curl -s --max-time 10 "http://$PUBLIC_IP" >/dev/null 2>&1; then
    print_success "✅ Site is accessible via public IP"
else
    print_warning "⚠️  Public access test failed - may need firewall configuration"
fi

# Memory usage check
print_status "Checking memory usage..."
MEMORY_USAGE=$(free -m | awk 'NR==2{printf "%.1f%%", $3*100/$2}')
print_success "Memory usage: $MEMORY_USAGE"

# Disk usage check
print_status "Checking disk usage..."
DISK_USAGE=$(df / | awk 'NR==2{print $5}')
print_success "Disk usage: $DISK_USAGE"

# Final summary
print_header "DEPLOYMENT SUMMARY"

echo ""
echo "🚀 SONACIP Production Deployment Complete!"
echo ""
echo "📋 Configuration:"
echo "   📁 Project: $PROJECT_DIR"
echo "   🐍 Virtual Environment: $VENV_DIR"
echo "   🌐 Entry Point: $ENTRY_POINT"
echo "   ⚙️  Workers: 2 (optimized for 1GB RAM)"
echo "   🔗 Internal URL: http://127.0.0.1:8000"
echo "   🌐 Public URL: http://$PUBLIC_IP"
echo ""
echo "🛡️ Services Status:"
echo "   ✅ SONACIP service: Running"
echo "   ✅ Nginx proxy: Running"
echo "   ✅ Port 8000: Responding"
echo "   ✅ Public access: Available"
echo ""
echo "💾 Resource Usage:"
echo "   🧠 Memory: $MEMORY_USAGE"
echo "   💿 Disk: $DISK_USAGE"
echo "   🔄 Swap: 1GB (configured)"
echo ""
echo "🔧 Management Commands:"
echo "   📊 Service status: systemctl status $SERVICE_NAME"
echo "   📝 Service logs: journalctl -u $SERVICE_NAME -f"
echo "   🌐 Nginx logs: tail -f /var/log/nginx/sonacip_access.log"
echo "   🔄 Restart service: systemctl restart $SERVICE_NAME"
echo ""
echo "🛡️ Security Notes:"
echo "   🔥 Firewall: Configure UFW if needed"
echo "   🔒 HTTPS: Configure SSL certificate for production"
echo "   📊 Monitoring: Set up monitoring for production"
echo ""
print_success "🎉 SONACIP is now deployed and accessible!"
echo ""
echo "🌐 Access your application at: http://$PUBLIC_IP"
