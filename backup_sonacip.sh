#!/bin/bash
# SONACIP Production Backup Script
# Complete backup system for production SONACIP deployment

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
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="sonacip_backup_$DATE"

# Print functions
print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "${CYAN}${BOLD}=== $1 ===${NC}"; }

print_header "SONACIP Production Backup"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root"
    print_status "Use: sudo bash backup_sonacip.sh"
    exit 1
fi

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Create backup subdirectory
CURRENT_BACKUP_DIR="$BACKUP_DIR/$BACKUP_NAME"
mkdir -p "$CURRENT_BACKUP_DIR"

print_status "Starting backup process..."
print_status "Backup directory: $CURRENT_BACKUP_DIR"

# 1. Backup Application Files
print_status "Backing up application files..."
if [[ -d "$INSTALL_DIR" ]]; then
    cp -r "$INSTALL_DIR" "$CURRENT_BACKUP_DIR/application/"
    print_success "Application files backed up"
else
    print_error "Installation directory not found: $INSTALL_DIR"
    exit 1
fi

# 2. Backup Database
print_status "Backing up database..."
if [[ -f "$INSTALL_DIR/sonacip.db" ]]; then
    cp "$INSTALL_DIR/sonacip.db" "$CURRENT_BACKUP_DIR/database/"
    print_success "Database backed up"
else
    print_warning "Database file not found: $INSTALL_DIR/sonacip.db"
fi

# 3. Backup Configuration Files
print_status "Backing up configuration files..."
mkdir -p "$CURRENT_BACKUP_DIR/config"

# Backup systemd service
if [[ -f "/etc/systemd/system/sonacip.service" ]]; then
    cp "/etc/systemd/system/sonacip.service" "$CURRENT_BACKUP_DIR/config/"
    print_success "Systemd service backed up"
fi

# Backup nginx configuration
if [[ -f "/etc/nginx/sites-available/sonacip" ]]; then
    cp "/etc/nginx/sites-available/sonacip" "$CURRENT_BACKUP_DIR/config/"
    print_success "Nginx configuration backed up"
fi

# Backup environment file
if [[ -f "$INSTALL_DIR/.env" ]]; then
    cp "$INSTALL_DIR/.env" "$CURRENT_BACKUP_DIR/config/"
    print_success "Environment configuration backed up"
fi

# 4. Create Backup Metadata
print_status "Creating backup metadata..."
cat > "$CURRENT_BACKUP_DIR/backup_info.txt" << EOF
SONACIP Backup Information
========================
Backup Date: $(date)
Backup Name: $BACKUP_NAME
Installation Directory: $INSTALL_DIR
System: $(uname -a)
Python Version: $(python3 --version 2>&1)
Services Status:
- SONACIP: $(systemctl is-active sonacip 2>/dev/null || echo "inactive")
- Nginx: $(systemctl is-active nginx 2>/dev/null || echo "inactive")
Database Size: $([ -f "$INSTALL_DIR/sonacip.db" ] && du -h "$INSTALL_DIR/sonacip.db" | cut -f1 || echo "N/A")
Application Size: $(du -sh "$INSTALL_DIR" 2>/dev/null | cut -f1 || echo "N/A")
EOF

print_success "Backup metadata created"

# 5. Compress Backup
print_status "Compressing backup..."
cd "$BACKUP_DIR"
tar -czf "$BACKUP_NAME.tar.gz" "$BACKUP_NAME/"

# Verify compression
if [[ -f "$BACKUP_DIR/$BACKUP_NAME.tar.gz" ]]; then
    print_success "Backup compressed successfully"
    
    # Get compressed size
    COMPRESSED_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_NAME.tar.gz" | cut -f1)
    print_status "Compressed backup size: $COMPRESSED_SIZE"
    
    # Remove uncompressed directory
    rm -rf "$CURRENT_BACKUP_DIR"
    
    print_success "Uncompressed backup directory cleaned up"
else
    print_error "Backup compression failed"
    exit 1
fi

# 6. Cleanup Old Backups (keep last 7)
print_status "Cleaning up old backups..."
cd "$BACKUP_DIR"
ls -t *.tar.gz | tail -n +8 | xargs -r rm -f 2>/dev/null || true
print_success "Old backups cleaned up (keeping last 7)"

# 7. Set Permissions
print_status "Setting backup permissions..."
chmod -R 600 "$BACKUP_DIR"/*.tar.gz
chown -R root:root "$BACKUP_DIR"

print_success "Backup permissions set"

# 8. List Available Backups
print_header "Available Backups"
ls -lah "$BACKUP_DIR"/*.tar.gz 2>/dev/null | tail -10 || print_warning "No backups found"

print_header "Backup Complete!"
echo ""
print_success "🎉 SONACIP backup completed successfully!"
echo ""
echo "📋 Backup Details:"
echo "   📁 Backup Name: $BACKUP_NAME"
echo "   📂 Location: $BACKUP_DIR"
echo "   📦 File: $BACKUP_DIR/$BACKUP_NAME.tar.gz"
echo "   📊 Size: $COMPRESSED_SIZE"
echo ""
echo "🛠️  Restore Commands:"
echo "   To restore: sudo bash restore_sonacip.sh $BACKUP_NAME"
echo "   To list: ls -la $BACKUP_DIR"
echo ""
echo "📁 Backup Contents:"
echo "   ✅ Application files"
echo "   ✅ Database"
echo "   ✅ Configuration files"
echo "   ✅ Service configurations"
echo "   ✅ Backup metadata"
echo ""
print_success "Backup process completed successfully!"
