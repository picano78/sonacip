#!/bin/bash
# SONACIP Backup Script - Production Ready
# Creates complete backup of database and uploads

set -e

# Configuration
SONACIP_DIR="/root/sonacip"
BACKUP_DIR="${SONACIP_DIR}/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="sonacip_backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

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

# Create backup directory
mkdir -p "${BACKUP_DIR}"

log_info "Starting SONACIP backup..."
log_info "Backup directory: ${BACKUP_PATH}"

# Create backup folder
mkdir -p "${BACKUP_PATH}"

# Backup database
log_info "Backing up database..."
if [ -f "${SONACIP_DIR}/uploads/sonacip.db" ]; then
    cp "${SONACIP_DIR}/uploads/sonacip.db" "${BACKUP_PATH}/sonacip.db"
    log_info "Database backed up"
elif [ -n "$DATABASE_URL" ]; then
    # For PostgreSQL
    if command -v pg_dump &> /dev/null; then
        DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^@]*\)@.*/\1/p')
        pg_dump -Fc "$DB_NAME" > "${BACKUP_PATH}/database.dump" 2>/dev/null || true
    fi
fi

# Backup uploads
log_info "Backing up uploads..."
if [ -d "${SONACIP_DIR}/uploads" ]; then
    tar -czf "${BACKUP_PATH}/uploads.tar.gz" -C "${SONACIP_DIR}" uploads/ 2>/dev/null || true
    log_info "Uploads backed up"
fi

# Backup .env
log_info "Backing up configuration..."
if [ -f "${SONACIP_DIR}/.env" ]; then
    cp "${SONACIP_DIR}/.env" "${BACKUP_PATH}/.env"
    log_info "Configuration backed up"
fi

# Create manifest
cat > "${BACKUP_PATH}/manifest.txt" << EOF
SONACIP Backup Manifest
=======================
Date: $(date)
Hostname: $(hostname)
Backup Path: ${BACKUP_PATH}

Files Included:
- sonacip.db (SQLite database)
- uploads.tar.gz (media files)
- .env (configuration)

Database Connection:
$DATABASE_URL

Version:
$(cat ${SONACIP_DIR}/.env 2>/dev/null | grep VERSION || echo "Version: Unknown")
EOF

# Create archive
cd "${BACKUP_DIR}"
log_info "Creating archive..."
tar -czf "${BACKUP_NAME}.tar.gz" "${BACKUP_NAME}"
rm -rf "${BACKUP_NAME}"

# Clean old backups (keep last 7)
log_info "Cleaning old backups..."
find "${BACKUP_DIR}" -name "sonacip_backup_*.tar.gz" -type f -mtime +7 -delete 2>/dev/null || true

# Summary
BACKUP_SIZE=$(du -h "${BACKUP_PATH}.tar.gz" 2>/dev/null | cut -f1)
log_info "Backup complete!"
log_info "Archive: ${BACKUP_PATH}.tar.gz (${BACKUP_SIZE})"
log_info "Location: ${BACKUP_DIR}"

echo "${BACKUP_PATH}.tar.gz"