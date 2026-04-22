#!/bin/bash
# SONACIP Restore Script - Production Ready
# Restores database and uploads from backup

set -e

# Configuration
SONACIP_DIR="/root/sonacip"
BACKUP_DIR="${SONACIP_DIR}/backups"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_warn "Running as non-root, some features may not work"
fi

# Show available backups
show_backups() {
    log_info "Available backups:"
    ls -lh "${BACKUP_DIR}"/sonacip_backup_*.tar.gz 2>/dev/null || log_warn "No backups found"
}

# Main restore function
restore_backup() {
    BACKUP_FILE="$1"
    
    if [ ! -f "$BACKUP_FILE" ]; then
        log_error "Backup file not found: $BACKUP_FILE"
        show_backups
        exit 1
    fi
    
    log_info "Starting restore from: $BACKUP_FILE"
    
    # Stop service if running
    if systemctl is-active sonacip &>/dev/null; then
        log_info "Stopping SONACIP service..."
        systemctl stop sonacip || true
    fi
    
    # Create temp directory
    TEMP_DIR=$(mktemp -d)
    
    # Extract backup
    log_info "Extracting backup..."
    tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"
    
    BACKUP_NAME=$(basename "$BACKUP_FILE" .tar.gz)
    EXTRACTED_DIR="${TEMP_DIR}/${BACKUP_NAME}"
    
    # Restore database
    if [ -f "${EXTRACTED_DIR}/sonacip.db" ]; then
        log_info "Restoring database..."
        # Backup current database first
        if [ -f "${SONACIP_DIR}/uploads/sonacip.db" ]; then
            cp "${SONACIP_DIR}/uploads/sonacip.db" "${SONACIP_DIR}/uploads/sonacip.db.bak.$(date +%s)"
        fi
        cp "${EXTRACTED_DIR}/sonacip.db" "${SONACIP_DIR}/uploads/sonacip.db"
        log_info "Database restored"
    fi
    
    # Restore uploads
    if [ -f "${EXTRACTED_DIR}/uploads.tar.gz" ]; then
        log_info "Restoring uploads..."
        # Backup current uploads first
        if [ -d "${SONACIP_DIR}/uploads" ]; then
            rm -rf "${SONACIP_DIR}/uploads.bak.$(date +%s)" 2>/dev/null || true
        fi
        tar -xzf "${EXTRACTED_DIR}/uploads.tar.gz" -C "${SONACIP_DIR}" || true
        log_info "Uploads restored"
    fi
    
    # Restore configuration
    if [ -f "${EXTRACTED_DIR}/.env" ]; then
        log_warn "Configuration file found. Restore? (y/n)"
        read -r response
        if [ "$response" = "y" ]; then
            cp "${EXTRACTED_DIR}/.env" "${SONACIP_DIR}/.env"
            log_info "Configuration restored"
        fi
    fi
    
    # Cleanup
    rm -rf "$TEMP_DIR"
    
    # Start service
    log_info "Starting SONACIP service..."
    systemctl start sonacip || log_warn "Could not start service (run manually: systemctl start sonacip)"
    
    log_info "Restore complete!"
}

# Show usage
show_usage() {
    echo "Usage: $0 <backup_file>"
    echo ""
    echo "Available backups:"
    show_backups
    echo ""
    echo "Examples:"
    echo "  $0 ${BACKUP_DIR}/sonacip_backup_20260422_120000.tar.gz"
    echo "  $0 \$(ls -t ${BACKUP_DIR}/sonacip_backup_*.tar.gz | head -1)  # Restore latest"
}

# Main
if [ $# -eq 0 ]; then
    show_usage
    exit 1
fi

restore_backup "$1"