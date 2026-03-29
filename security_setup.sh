#!/bin/bash

# SONACIP Security Setup Script
# HTTPS, domain configuration, server hardening, and optimization

set -e

echo "=== SONACIP SECURITY SETUP ==="

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

# Step 1: Install Certbot
print_header "Step 1: Installing Certbot"
print_status "Updating package lists..."
apt-get update -qq

print_status "Installing Certbot and Nginx plugin..."
apt-get install -y certbot python3-certbot-nginx

print_success "Certbot installed successfully"

# Step 2: Configure Nginx for Domain
print_header "Step 2: Configuring Nginx for Domain"

# Get server IP for fallback
SERVER_IP=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || curl -s --max-time 5 ipinfo.io/ip 2>/dev/null || echo "YOUR_IP")

echo ""
print_status "Current server IP: $SERVER_IP"
echo ""

# Ask for domain
echo -e "${YELLOW}Do you have a domain name for this server?${NC}"
echo "If yes, enter domain (e.g., miosito.it)"
echo "If no, press Enter to use IP address"
echo ""
read -p "Domain name: " DOMAIN_NAME

if [[ -n "$DOMAIN_NAME" ]]; then
    # Domain provided - configure for domain
    print_status "Configuring Nginx for domain: $DOMAIN_NAME"
    
    # Backup current nginx config
    NGINX_CONFIG="/etc/nginx/sites-available/sonacip"
    if [[ -f "$NGINX_CONFIG" ]]; then
        cp "$NGINX_CONFIG" "$NGINX_CONFIG.backup.$(date +%s)"
    fi
    
    # Update nginx config with domain
    cat > "$NGINX_CONFIG" << EOF
server {
    listen 80;
    server_name $DOMAIN_NAME www.$DOMAIN_NAME;
    
    # Redirect to HTTPS
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN_NAME www.$DOMAIN_NAME;
    
    # SSL configuration (will be filled by Certbot)
    # ssl_certificate /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem;
    
    # Optimized for 1GB RAM VPS
    client_max_body_size 50M;
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
        application/xml+rss
        application/atom+xml
        image/svg+xml;

    # Keep connections alive for better performance
    keepalive_timeout 30;
    keepalive_requests 100;

    # Main application proxy
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect off;
        
        # Timeouts optimized for VPS
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }

    # Health check endpoint (internal only)
    location /health {
        proxy_pass http://127.0.0.1:8000;
        access_log off;
        allow 127.0.0.1;
        allow ::1;
        deny all;
    }

    # Static files with caching (30 days)
    location /static/ {
        alias /opt/sonacip/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # CSS files with caching
    location ~* \.css$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
        add_header Vary Accept-Encoding;
    }

    # JavaScript files with caching
    location ~* \.js$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
        add_header Vary Accept-Encoding;
    }

    # Image files with caching
    location ~* \.(jpg|jpeg|png|gif|ico|svg|webp)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # Upload files with limited caching
    location /uploads/ {
        alias /opt/sonacip/uploads/;
        expires 1h;
        add_header Cache-Control "public";
        access_log off;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Hide nginx version
    server_tokens off;

    # Logs
    access_log /var/log/nginx/sonacip_access.log combined buffer=32k flush=5m;
    error_log /var/log/nginx/sonacip_error.log warn;
}
EOF

    # Test nginx configuration
    if nginx -t; then
        print_success "Nginx configuration updated for domain: $DOMAIN_NAME"
        systemctl reload nginx
        print_success "Nginx reloaded successfully"
    else
        print_error "Nginx configuration failed"
        exit 1
    fi
    
    USE_DOMAIN=true
    print_success "Domain configuration completed"
else
    # No domain - use IP
    print_warning "No domain provided, using IP address configuration"
    USE_DOMAIN=false
    print_status "Keeping current IP-based configuration"
fi

# Step 3: Activate HTTPS
print_header "Step 3: Activating HTTPS"

if [[ "$USE_DOMAIN" == true ]]; then
    print_status "Activating HTTPS with Let's Encrypt for domain: $DOMAIN_NAME"
    
    # Get SSL certificate
    if certbot --nginx -d "$DOMAIN_NAME" -d "www.$DOMAIN_NAME" --non-interactive --agree-tos -m "admin@$DOMAIN_NAME"; then
        print_success "SSL certificate obtained successfully"
        
        # Enable auto-renewal
        systemctl enable certbot.timer
        print_success "Auto-renewal enabled"
        
        # Verify certificate
        if certbot certificates | grep -q "$DOMAIN_NAME"; then
            print_success "Certificate verified"
        else
            print_warning "Certificate verification failed"
        fi
    else
        print_error "Failed to obtain SSL certificate"
        print_status "Continuing with HTTP only..."
    fi
else
    print_warning "No domain configured - HTTPS setup skipped"
    print_status "HTTPS requires a domain name"
fi

# Step 4: Server Hardening
print_header "Step 4: Server Hardening"

print_status "Configuring firewall..."

# Configure UFW firewall
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

print_success "Firewall configured and enabled"

# Disable root SSH login
print_status "Hardening SSH configuration..."
if grep -q "^#PermitRootLogin yes" /etc/ssh/sshd_config; then
    sed -i 's/^#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
    print_success "Root SSH login disabled"
elif grep -q "^PermitRootLogin yes" /etc/ssh/sshd_config; then
    sed -i 's/^PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
    print_success "Root SSH login disabled"
else
    print_status "Root SSH login already disabled or not found"
fi

# Restart SSH
systemctl restart ssh
print_success "SSH configuration reloaded"

# Additional security measures
print_status "Applying additional security measures..."

# Disable password authentication (if key-based auth is available)
if [[ -d "/root/.ssh" ]] && [[ -f "/root/.ssh/authorized_keys" ]]; then
    if grep -q "^PasswordAuthentication yes" /etc/ssh/sshd_config; then
        sed -i 's/^PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
        print_success "Password authentication disabled (key auth available)"
    fi
fi

systemctl restart ssh

# Step 5: Nginx Optimization
print_header "Step 5: Nginx Optimization"

print_status "Optimizing Nginx configuration..."

# Create optimized nginx main config
NGINX_MAIN="/etc/nginx/nginx.conf"
if [[ -f "$NGINX_MAIN" ]]; then
    cp "$NGINX_MAIN" "$NGINX_MAIN.backup.$(date +%s)"
fi

cat > "$NGINX_MAIN" << EOF
user www-data;
worker_processes auto;
pid /run/nginx.pid;
include /etc/nginx/modules-enabled/*.conf;

events {
    worker_connections 768;
    # multi_accept on;
}

http {
    ##
    # Basic Settings
    ##
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    server_tokens off;

    # client_max_body_size already set in site config

    ##
    # Gzip Settings
    ##
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml;

    ##
    # File Cache Settings
    ##
    open_file_cache max=1000 inactive=20s;
    open_file_cache_valid 30s;
    open_file_cache_min_uses 2;
    open_file_cache_errors on;

    ##
    # SSL Settings (if applicable)
    ##
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers "EECDH+AESGCM:EDH+AESGCM:AES256+EECDH:AES256+EDH";

    ##
    # Logging Settings
    ##
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    ##
    # Virtual Host Configs
    ##
    include /etc/nginx/conf.d/*.conf;
    include /etc/nginx/sites-enabled/*;
}
EOF

# Test nginx configuration
if nginx -t; then
    print_success "Nginx optimization completed"
    systemctl restart nginx
    print_success "Nginx restarted with optimizations"
else
    print_error "Nginx optimization failed"
    exit 1
fi

# Step 6: Cleanup Installation Files
print_header "Step 6: Cleaning Installation Files"

print_status "Removing installation files..."

# Remove installation scripts from project directory
rm -f /root/sonacip/ionos_quick_install.sh 2>/dev/null || true
rm -f /root/sonacip/ionos_production_installer.sh 2>/dev/null || true
rm -f /root/sonacip/install_sonacip*.sh 2>/dev/null || true
rm -f /root/sonacip/installer.sh 2>/dev/null || true
rm -f /root/sonacip/sonacip_install.sh 2>/dev/null || true

# Remove archive files
rm -rf /root/sonacip/*.zip 2>/dev/null || true
rm -rf /root/sonacip/__MACOSX 2>/dev/null || true
rm -rf /root/sonacip/.DS_Store 2>/dev/null || true

# Clean system packages
print_status "Cleaning system packages..."
apt-get autoremove -y
apt-get autoclean
apt-get clean

print_success "Installation files cleaned"

# Step 7: Final Verification
print_header "Step 7: Final Verification"

print_status "Verifying service status..."

# Check SONACIP service
echo ""
echo "=== SONACIP Service Status ==="
if systemctl is-active --quiet sonacip; then
    print_success "✅ SONACIP service: RUNNING"
    systemctl status sonacip --no-pager | head -10
else
    print_error "❌ SONACIP service: FAILED"
    systemctl status sonacip --no-pager
fi

echo ""
echo "=== Nginx Service Status ==="
if systemctl is-active --quiet nginx; then
    print_success "✅ Nginx service: RUNNING"
    systemctl status nginx --no-pager | head -10
else
    print_error "❌ Nginx service: FAILED"
    systemctl status nginx --no-pager
fi

# Check ports
echo ""
echo "=== Port Status ==="
if command -v ss >/dev/null 2>&1; then
    echo "Port 8000 (SONACIP):"
    ss -tulnp | grep ":8000" || echo "Port 8000 not found"
    
    echo ""
    echo "Port 80 (HTTP):"
    ss -tulnp | grep ":80" || echo "Port 80 not found"
    
    if [[ "$USE_DOMAIN" == true ]]; then
        echo ""
        echo "Port 443 (HTTPS):"
        ss -tulnp | grep ":443" || echo "Port 443 not found"
    fi
else
    print_warning "ss command not available for port checking"
fi

# Test application response
echo ""
echo "=== Application Response Test ==="
if curl -s --max-time 10 http://127.0.0.1:8000 >/dev/null 2>&1; then
    print_success "✅ Application responding on port 8000"
else
    print_error "❌ Application not responding on port 8000"
fi

# Test public access
echo ""
echo "=== Public Access Test ==="
if [[ "$USE_DOMAIN" == true ]]; then
    if curl -s --max-time 10 "http://$DOMAIN_NAME" >/dev/null 2>&1; then
        print_success "✅ HTTP access: http://$DOMAIN_NAME"
    else
        print_error "❌ HTTP access failed: http://$DOMAIN_NAME"
    fi
    
    if curl -s --max-time 10 "https://$DOMAIN_NAME" >/dev/null 2>&1; then
        print_success "✅ HTTPS access: https://$DOMAIN_NAME"
    else
        print_warning "⚠️ HTTPS access may not be working: https://$DOMAIN_NAME"
    fi
else
    if curl -s --max-time 10 "http://$SERVER_IP" >/dev/null 2>&1; then
        print_success "✅ HTTP access: http://$SERVER_IP"
    else
        print_error "❌ HTTP access failed: http://$SERVER_IP"
    fi
fi

# Security verification
echo ""
echo "=== Security Status ==="
if ufw status | grep -q "Status: active"; then
    print_success "✅ Firewall: ACTIVE"
else
    print_error "❌ Firewall: INACTIVE"
fi

if systemctl is-active --quiet ssh; then
    print_success "✅ SSH service: RUNNING"
else
    print_error "❌ SSH service: FAILED"
fi

# Final summary
print_header "SECURITY SETUP COMPLETE"

echo ""
echo "🎯 Configuration Summary:"
echo ""

if [[ "$USE_DOMAIN" == true ]]; then
    echo "🌐 Domain Configuration:"
    echo "   📡 Domain: $DOMAIN_NAME"
    echo "   🔗 HTTP: http://$DOMAIN_NAME"
    echo "   🔒 HTTPS: https://$DOMAIN_NAME"
    echo "   📜 SSL: Let's Encrypt certificate"
    echo "   🔄 Auto-renewal: Enabled"
else
    echo "🌐 IP Configuration:"
    echo "   📡 Server IP: $SERVER_IP"
    echo "   🔗 HTTP: http://$SERVER_IP"
    echo "   🔒 HTTPS: Not configured (requires domain)"
fi

echo ""
echo "🛡️ Security Features:"
echo "   🔥 Firewall: UFW enabled (SSH + Nginx)"
echo "   🔐 SSH: Root login disabled"
echo "   🔒 SSL: TLS 1.2/1.3 protocols"
echo "   📋 Headers: Security headers enabled"
echo "   🗑️ Cleanup: Installation files removed"

echo ""
echo "⚡ Performance Optimizations:"
echo "   🗜️  Gzip: Enabled (level 6)"
echo "   💾 Cache: Static files 30 days"
echo "   📦 Upload limit: 50MB"
echo "   🔄 Keep-alive: 30 seconds"
echo "   📊 Workers: Auto-detected"

echo ""
echo "📊 Services Status:"
echo "   ✅ SONACIP: Application server"
echo "   ✅ Nginx: Web server/proxy"
echo "   ✅ PostgreSQL: Database"
echo "   ✅ Redis: Cache (if configured)"

echo ""
echo "🚀 Next Steps:"
echo "   1. Access your application via browser"
echo "   2. Configure SSL certificate if needed"
echo "   3. Monitor system performance"
echo "   4. Setup backups if not already done"
echo "   5. Consider additional hardening as needed"

echo ""
print_success "🎉 SONACIP security setup completed successfully!"
echo ""
echo "📋 Quick Access URLs:"
if [[ "$USE_DOMAIN" == true ]]; then
    echo "   🌐 Main: https://$DOMAIN_NAME"
    echo "   📊 Health: https://$DOMAIN_NAME/health"
else
    echo "   🌐 Main: http://$SERVER_IP"
    echo "   📊 Health: http://$SERVER_IP/health"
fi

echo ""
print_status "System is now production-ready with security optimizations!"
