#!/bin/bash

# SONACIP Health Check Script
# Monitors service health and triggers auto-repair

LOG_FILE="/var/log/sonacip_health.log"

# Function to log with timestamp
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Function to check service status
check_service() {
    local service_name="$1"
    if systemctl is-active --quiet "$service_name"; then
        log_message "✅ $service_name is running"
        return 0
    else
        log_message "❌ $service_name is down"
        return 1
    fi
}

# Function to check application response
check_app_response() {
    if curl -s --max-time 10 http://localhost:8000 >/dev/null 2>&1; then
        log_message "✅ Application responding on port 8000"
        return 0
    else
        log_message "❌ Application not responding on port 8000"
        return 1
    fi
}

# Function to trigger auto-fix
trigger_auto_fix() {
    log_message "🚨 TRIGGERING AUTO-FIX"
    log_message "Executing: /opt/sonacip/auto_fix.sh"
    
    if /opt/sonacip/auto_fix.sh >> "$LOG_FILE" 2>&1; then
        log_message "✅ Auto-fix completed successfully"
    else
        log_message "❌ Auto-fix failed"
        return 1
    fi
}

# Main health check
log_message "=== HEALTH CHECK STARTED ==="

# Track if any issues found
ISSUES_FOUND=false

# Check SONACIP service
if ! check_service "sonacip"; then
    ISSUES_FOUND=true
fi

# Check Nginx service
if ! check_service "nginx"; then
    ISSUES_FOUND=true
fi

# Check PostgreSQL service
if ! check_service "postgresql"; then
    ISSUES_FOUND=true
fi

# Check application response
if ! check_app_response; then
    ISSUES_FOUND=true
fi

# If any issues found, trigger auto-fix
if [ "$ISSUES_FOUND" = true ]; then
    log_message "⚠️ ISSUES DETECTED - Starting auto-repair"
    trigger_auto_fix
    
    # Wait for fixes to apply
    sleep 10
    
    # Re-check after fix
    log_message "=== POST-FIX VERIFICATION ==="
    
    if check_service "sonacip" && check_service "nginx" && check_service "postgresql" && check_app_response; then
        log_message "✅ ALL SYSTEMS OPERATIONAL AFTER REPAIR"
    else
        log_message "❌ SOME SYSTEMS STILL DOWN - Manual intervention may be required"
    fi
else
    log_message "✅ ALL SYSTEMS OPERATIONAL"
fi

log_message "=== HEALTH CHECK COMPLETED ==="
echo "" >> "$LOG_FILE"
