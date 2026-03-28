#!/bin/bash
# SONACIP Production Restore Script
# Complete restore system for production SONACIP deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Configuration
BACKUP_DIR="/opt/backups/sonacip"
INSTALL_DIR="/opt/sonacip"

# Print functions
print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "${CYAN}${BOLD}=== $1 ===${NC}"; }

# Function to show usage
show_usage() {
    echo "Usage: sudo bash restore_sonacip.sh [backup_name]"
    echo ""
    echo "Available backups:"
    if [[ -d "$BACKUP_DIR" ]]; then
        ls -1 "$BACKUP_DIR"/*.tar.gz 2>/dev/null | sed 's/\.tar\.gz$//' | sed 's/.*\///'
    else
        echo "No backups found in $BACKUP_DIR"
    fi
    echo ""
    echo "Example: sudo bash restore_sonacip.sh sonacip_backup_20240328_143022"
}

print_header "SONACIP Production Restore"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root"
    print_status "Use: sudo bash restore_sonacip.sh [backup_name]"
    exit 1
fi

# Check arguments
if [[ $# -eq 0 ]]; then
    print_error "No backup name specified"
    show_usage
    exit 1
fi

BACKUP_NAME="$1"
BACKUP_FILE="$BACKUP_DIR/$BACKUP_NAME.tar.gz"

# Check if backup exists
if [[ ! -f "$BACKUP_FILE" ]]; then
    print_error "Backup file not found: $BACKUP_FILE"
    echo ""
    show_usage
    exit 1
fi

# Show backup info
if [[ -f "$BACKUP_DIR/$BACKUP_NAME/backup_info.txt" ]]; then
    print_header "Backup Information"
    cat "$BACKUP_DIR/$BACKUP_NAME/backup_info.txt"
    echo ""
else
    print_warning "Backup metadata not found"
fi

# Confirmation
print_warning "This will REPLACE the current SONACIP installation!"
print_warning "All current data will be LOST unless you have a backup!"
echo ""
read -p "Are you sure you want to restore from $BACKUP_NAME? (type 'yes' to confirm): " confirm
if [[ "$confirm" != "yes" ]]; then
    print_status "Restore cancelled by user"
    exit 0
fi

print_status "Starting restore process..."

# 1. Stop Services
print_status "Stopping SONACIP services..."
systemctl stop sonacip 2>/dev/null || true
systemctl stop nginx 2>/dev/null || true
print_success "Services stopped"

# 2. Backup Current Installation (if exists)
if [[ -d "$INSTALL_DIR" ]]; then
    print_status "Backing up current installation..."
    CURRENT_BACKUP="$INSTALL_DIR.backup.$(date +%s)"
    mv "$INSTALL_DIR" "$CURRENT_BACKUP"
    print_success "Current installation backed up to: $CURRENT_BACKUP"
fi

# 3. Extract Backup
print_status "Extracting backup..."
cd "/opt"
if ! tar -xzf "$BACKUP_FILE"; then
    print_error "Failed to extract backup file"
    exit 1
fi
print_success "Backup extracted successfully"

# 4. Restore Application Files
print_status "Restoring application files..."
if [[ -d "/opt/$BACKUP_NAME/application" ]]; then
    mv "/opt/$BACKUP_NAME/application" "$INSTALL_DIR"
    print_success "Application files restored"
else
    print_error "Application files not found in backup"
    exit 1
fi

# 5. Restore Database
print_status "Restoring database..."
if [[ -f "/opt/$BACKUP_NAME/database/sonacip.db" ]]; then
    cp "/opt/$BACKUP_NAME/database/sonacip.db" "$INSTALL_DIR/"
    chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/sonacip.db" 2>/dev/null || true
    print_success "Database restored"
else
    print_warning "Database not found in backup"
fi

# 6. Restore Configuration Files
print_status "Restoring configuration files..."

# Restore systemd service
if [[ -f "/opt/$BACKUP_NAME/config/sonacip.service" ]]; then
    cp "/opt/$BACKUP_NAME/config/sonacip.service" "/etc/systemd/system/"
    systemctl daemon-reload
    print_success "Systemd service restored"
else
    print_warning "Systemd service not found in backup"
fi

# Restore nginx configuration
if [[ -f "/opt/$BACKUP_NAME/config/sonacip" ]]; then
    cp "/opt/$BACKUP_NAME/config/sonacip" "/etc/nginx/sites-available/"
    print_success "Nginx configuration restored"
else
    print_warning "Nginx configuration not found in backup"
fi

# Restore environment file
if [[ -f "/opt/$BACKUP_NAME/config/.env" ]]; then
    cp "/opt/$BACKUP_NAME/config/.env" "$INSTALL_DIR/"
    chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/.env" 2>/dev/null || true
    chmod 600 "$INSTALL_DIR/.env"
    print_success "Environment configuration restored"
else
    print_warning "Environment configuration not found in backup"
fi

# 7. Set Permissions
print_status "Setting correct permissions..."
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"

# Create necessary directories
mkdir -p "$INSTALL_DIR/logs" "$INSTALL_DIR/uploads" "$INSTALL_DIR/static" "$INSTALL_DIR/backups"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/logs" "$INSTALL_DIR/uploads" "$INSTALL_DIR/static" "$INSTALL_DIR/backups"

print_success "Permissions set"

# 8. Restart Services
print_status "Starting services..."
systemctl start sonacip
systemctl start nginx

# Wait for services to start
sleep 5

# 9. Verify Services
print_status "Verifying services..."
if systemctl is-active --quiet sonacip; then
    print_success "✅ SONACIP service is running"
else
    print_error "❌ SONACIP service failed to start"
    systemctl status sonacip --no-pager
fi

if systemctl is-active --quiet nginx; then
    print_success "✅ Nginx is running"
else
    print_error "❌ Nginx failed to start"
    systemctl status nginx --no-pager
fi

# 10. Test Application
print_status "Testing application..."
HEALTH_CHECK_COUNT=0
MAX_HEALTH_CHECKS=6

while [[ $HEALTH_CHECK_COUNT -lt $MAX_HEALTH_CHECKS ]]; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 | grep -q "200\|302"; then
        print_success "✅ Application health check passed"
        break
    else
        HEALTH_CHECK_COUNT=$((HEALTH_CHECK_COUNT + 1))
        print_status "Health check attempt $HEALTH_CHECK_COUNT/$MAX_HEALTH_CHECKS..."
        sleep 5
    fi
done

if [[ $HEALTH_CHECK_COUNT -eq $MAX_HEALTH_CHECKS ]]; then
    print_warning "⚠️  Application health check failed after $MAX_HEALTH_CHECKS attempts"
    print_status "Checking service logs..."
    journalctl -u sonacip -n 20 --no-pager
fi

# 11. Cleanup
print_status "Cleaning up temporary files..."
rm -rf "/opt/$BACKUP_NAME"
print_success "Temporary files cleaned up"

# Get server IP
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s ipinfo.io/ip 2>/dev/null || echo "YOUR_IP")

print_header "Restore Complete!"
echo ""
print_success "🎉 SONACIP has been successfully restored!"
echo ""
echo "📋 Restore Details:"
echo "   📁 Backup Used: $BACKUP_NAME"
echo "   📂 Installation: $INSTALL_DIR"
echo "   🌐 Server IP: $SERVER_IP"
echo "   🔗 URL: http://$SERVER_IP"
echo ""
echo "🛠️  Management Commands:"
echo "   📊 Status: systemctl status sonacip"
echo "   📋 Logs: journalctl -u sonacip -f"
echo "   🔄 Restart: systemctl restart sonacip"
echo ""
echo "📁 Restored Components:"
echo "   ✅ Application files"
echo "   ✅ Database"
echo "   ✅ Configuration files"
echo "   ✅ Service configurations"
echo "   ✅ Environment settings"
echo ""
print_success "Restore process completed successfully!"
echo ""
print_status "Application is now running at: http://$SERVER_IP"
