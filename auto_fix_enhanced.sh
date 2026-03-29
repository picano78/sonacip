#!/bin/bash

# SONACIP Enhanced Auto-Fix Script
# Comprehensive auto-repair system with server restart capability

LOG_FILE="/var/log/sonacip_health.log"

# Function to log with timestamp
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] AUTO-FIX: $1" >> "$LOG_FILE"
}

# Function to restart service
restart_service() {
    local service_name="$1"
    log_message "Restarting $service_name..."
    
    if systemctl restart "$service_name"; then
        sleep 5
        if systemctl is-active --quiet "$service_name"; then
            log_message "✅ $service_name restarted successfully"
            return 0
        else
            log_message "❌ $service_name restart failed"
            return 1
        fi
    else
        log_message "❌ Failed to restart $service_name"
        return 1
    fi
}

# Function to clear RAM cache
clear_ram_cache() {
    log_message "Clearing RAM cache..."
    sync
    echo 3 > /proc/sys/vm/drop_caches
    log_message "✅ RAM cache cleared"
}

# Function to check disk space
check_disk_space() {
    local usage=$(df / | awk 'NR==2{print $5}' | sed 's/%//')
    if [ "$usage" -gt 90 ]; then
        log_message "⚠️ Disk usage high: ${usage}% - Cleaning up"
        # Clean temp files
        rm -rf /tmp/* 2>/dev/null || true
        # Clean logs if needed
        find /var/log -name "*.log" -type f -mtime +7 -delete 2>/dev/null || true
        # Clean package cache
        apt-get clean 2>/dev/null || true
        log_message "✅ Disk cleanup completed"
    fi
}

# Function to check memory usage
check_memory_usage() {
    local available=$(free -m | awk 'NR==2{print $7}')
    if [ "$available" -lt 100 ]; then
        log_message "⚠️ Low memory: ${available}MB available - Clearing cache"
        clear_ram_cache
    fi
}

# Function to fix database issues
fix_database() {
    log_message "Checking database connectivity..."
    
    # Test database connection
    if sudo -u sonacip python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('/opt/sonacip/.env')
db_url = os.environ.get('DATABASE_URL', '')
try:
    if 'postgresql' in db_url:
        import psycopg2
        conn = psycopg2.connect(db_url)
        conn.close()
        print('✅ PostgreSQL connection OK')
    else:
        print('Using non-PostgreSQL database')
except Exception as e:
    print(f'❌ Database error: {e}')
    exit(1)
" 2>/dev/null; then
        log_message "✅ Database connection OK"
    else
        log_message "❌ Database connection failed - restarting PostgreSQL"
        restart_service "postgresql"
    fi
}

# Function to fix application issues
fix_application() {
    log_message "Checking application..."
    
    # Check virtual environment
    if [ ! -d "/opt/sonacip/venv" ]; then
        log_message "❌ Virtual environment missing - recreating"
        cd /opt/sonacip
        python3 -m venv venv
        /opt/sonacip/venv/bin/pip install --upgrade pip
        if [ -f "/opt/sonacip/requirements.txt" ]; then
            /opt/sonacip/venv/bin/pip install -r requirements.txt
        fi
        log_message "✅ Virtual environment recreated"
    fi
    
    # Check .env file
    if [ ! -f "/opt/sonacip/.env" ]; then
        log_message "❌ .env file missing - creating default"
        cat > /opt/sonacip/.env << EOF
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || echo "fallback-secret")
DATABASE_URL=postgresql://sonacip_user:StrongPass123!@localhost/sonacip
FLASK_ENV=production
DEBUG=False
HOST=127.0.0.1
PORT=8000
PYTHONUNBUFFERED=1
EOF
        chown sonacip:sonacip /opt/sonacip/.env
        chmod 600 /opt/sonacip/.env
        log_message "✅ .env file created"
    fi
}

# Function to restart server (last resort)
restart_server() {
    log_message "🚨 CRITICAL: Attempting server restart (last resort)"
    
    # Log the restart reason
    log_message "Server restart triggered due to persistent service failures"
    
    # Wait a moment before restart
    sleep 5
    
    # Restart the server
    if reboot; then
        log_message "✅ Server restart initiated"
    else
        log_message "❌ Failed to restart server - manual intervention required"
    fi
}

# Main auto-fix logic
log_message "=== AUTO-FIX STARTED ==="

# Track fixes applied
FIXES_APPLIED=0

# Check and fix system resources
check_disk_space
check_memory_usage

# Fix database issues
if ! fix_database; then
    ((FIXES_APPLIED++))
fi

# Fix application issues
if ! fix_application; then
    ((FIXES_APPLIED++))
fi

# Restart services if needed
SERVICES_RESTARTED=false

if ! systemctl is-active --quiet sonacip; then
    log_message "🔧 SONACIP service down - restarting"
    if restart_service "sonacip"; then
        ((FIXES_APPLIED++))
        SERVICES_RESTARTED=true
    fi
fi

if ! systemctl is-active --quiet nginx; then
    log_message "🔧 Nginx service down - restarting"
    if restart_service "nginx"; then
        ((FIXES_APPLIED++))
        SERVICES_RESTARTED=true
    fi
fi

if ! systemctl is-active --quiet postgresql; then
    log_message "🔧 PostgreSQL service down - restarting"
    if restart_service "postgresql"; then
        ((FIXES_APPLIED++))
        SERVICES_RESTARTED=true
    fi
fi

# Clear RAM cache if services were restarted
if [ "$SERVICES_RESTARTED" = true ]; then
    clear_ram_cache
fi

# Wait for services to stabilize
if [ "$SERVICES_RESTARTED" = true ]; then
    sleep 10
fi

# Final verification
FINAL_STATUS=true

if ! systemctl is-active --quiet sonacip; then
    log_message "❌ SONACIP still down after fix"
    FINAL_STATUS=false
fi

if ! systemctl is-active --quiet nginx; then
    log_message "❌ Nginx still down after fix"
    FINAL_STATUS=false
fi

if ! systemctl is-active --quiet postgresql; then
    log_message "❌ PostgreSQL still down after fix"
    FINAL_STATUS=false
fi

if ! curl -s --max-time 10 http://localhost:8000 >/dev/null 2>&1; then
    log_message "❌ Application still not responding after fix"
    FINAL_STATUS=false
fi

# If still failing, consider server restart
if [ "$FINAL_STATUS" = false ]; then
    log_message "🚨 CRITICAL: Multiple services still failing after auto-repair"
    
    # Check if we've already tried server restart recently
    RESTART_MARKER="/tmp/sonacip_server_restart"
    if [ -f "$RESTART_MARKER" ]; then
        RESTART_TIME=$(cat "$RESTART_MARKER")
        CURRENT_TIME=$(date +%s)
        TIME_DIFF=$((CURRENT_TIME - RESTART_TIME))
        
        # Only restart if last restart was more than 30 minutes ago
        if [ "$TIME_DIFF" -gt 1800 ]; then
            log_message "🚨 Initiating server restart (last restart was $((TIME_DIFF/60)) minutes ago)"
            echo "$(date +%s)" > "$RESTART_MARKER"
            restart_server
        else
            log_message "⚠️ Server restart attempted recently ($((TIME_DIFF/60)) minutes ago) - skipping"
            log_message "❌ Manual intervention required"
        fi
    else
        log_message "🚨 First critical failure - initiating server restart"
        echo "$(date +%s)" > "$RESTART_MARKER"
        restart_server
    fi
else
    log_message "✅ ALL SYSTEMS OPERATIONAL after auto-repair"
    # Remove restart marker if systems are healthy
    rm -f "$RESTART_MARKER"
fi

log_message "=== AUTO-FIX COMPLETED (Fixes applied: $FIXES_APPLIED) ==="
echo "" >> "$LOG_FILE"
