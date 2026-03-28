#!/bin/bash

# SONACIP Auto-Repair Script
# Automatically detects and fixes common service issues
# Maintains SONACIP always online

LOG="/var/log/sonacip_auto_fix.log"

echo "=== AUTO FIX $(date) ===" >> $LOG

# Function to log with timestamp
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> $LOG
}

# Controllo servizio SONACIP
if ! systemctl is-active --quiet sonacip; then
    log_message "Service down - restarting sonacip"
    systemctl restart sonacip
    sleep 5
    
    # Verify restart worked
    if systemctl is-active --quiet sonacip; then
        log_message "Service successfully restarted"
    else
        log_message "Service restart failed - checking logs"
        journalctl -u sonacip -n 10 >> $LOG
    fi
fi

# Controllo porta 8000 (app response)
if ! curl -s --max-time 10 http://127.0.0.1:8000 > /dev/null 2>&1; then
    log_message "App not responding on port 8000 - fixing"
    
    # Fix entrypoint automatico
    if [ -f "/opt/sonacip/_truth_app.py" ]; then
        log_message "Found _truth_app.py - updating service entrypoint"
        sed -i 's/app:app/_truth_app:app/g' /etc/systemd/system/sonacip.service
        sed -i 's/wsgi:app/_truth_app:app/g' /etc/systemd/system/sonacip.service
        sed -i 's/run:app/_truth_app:app/g' /etc/systemd/system/sonacip.service
    else
        log_message "_truth_app.py not found - checking alternatives"
        if [ -f "/opt/sonacip/run.py" ]; then
            log_message "Using run.py entrypoint"
            sed -i 's/_truth_app:app/run:app/g' /etc/systemd/system/sonacip.service
            sed -i 's/app:app/run:app/g' /etc/systemd/system/sonacip.service
            sed -i 's/wsgi:app/run:app/g' /etc/systemd/system/sonacip.service
        fi
    fi

    # Check virtual environment
    if [ ! -d "/opt/sonacip/venv" ]; then
        log_message "Virtual environment missing - recreating"
        cd /opt/sonacip
        python3 -m venv venv
        /opt/sonacip/venv/bin/pip install --upgrade pip
        if [ -f "/opt/sonacip/requirements.txt" ]; then
            /opt/sonacip/venv/bin/pip install -r requirements.txt
        fi
    fi

    # Reload and restart service
    systemctl daemon-reload
    systemctl restart sonacip
    sleep 10
    
    # Test again after fix
    if curl -s --max-time 10 http://127.0.0.1:8000 > /dev/null 2>&1; then
        log_message "App successfully fixed and responding"
    else
        log_message "App fix failed - checking service logs"
        journalctl -u sonacip -n 20 >> $LOG
    fi
else
    log_message "App responding correctly on port 8000"
fi

# Controllo nginx
if ! systemctl is-active --quiet nginx; then
    log_message "Nginx down - restarting nginx"
    systemctl restart nginx
    sleep 5
    
    if systemctl is-active --quiet nginx; then
        log_message "Nginx successfully restarted"
    else
        log_message "Nginx restart failed"
    fi
else
    log_message "Nginx running correctly"
fi

# Controllo spazio disco (preventivo)
DISK_USAGE=$(df / | awk 'NR==2{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 90 ]; then
    log_message "WARNING: Disk usage at ${DISK_USAGE}% - cleaning temp files"
    # Pulizia temporanea
    rm -rf /tmp/* 2>/dev/null || true
    rm -rf /opt/sonacip/logs/* 2>/dev/null || true
    journalctl --vacuum-time=7d 2>/dev/null || true
fi

# Controllo memoria (preventivo)
AVAILABLE_MEM=$(free -m | awk 'NR==2{print $7}')
if [ "$AVAILABLE_MEM" -lt 100 ]; then
    log_message "WARNING: Low memory (${AVAILABLE_MEM}MB) - optimizing"
    # Forza garbage collection se possibile
    if [ -d "/opt/sonacip/venv" ]; then
        /opt/sonacip/venv/bin/python -c "
import gc
gc.collect()
print('Memory cleanup performed')
" 2>/dev/null || true
    fi
fi

# Verifica finale completa
SONACIP_STATUS=$(systemctl is-active sonacip)
NGINX_STATUS=$(systemctl is-active nginx)
APP_STATUS=$(curl -s --max-time 5 -o /dev/null -w "%{http_code}" http://127.0.0.1:8000 || echo "000")

log_message "Final status - SONACIP: $SONACIP_STATUS, NGINX: $NGINX_STATUS, APP: $APP_STATUS"

# Se tutto è OK, log di successo
if [ "$SONACIP_STATUS" = "active" ] && [ "$NGINX_STATUS" = "active" ] && [ "$APP_STATUS" = "200" ]; then
    log_message "✅ All systems operational - SONACIP fully online"
else
    log_message "⚠️  Some issues detected - monitoring required"
fi

echo "=== AUTO FIX DONE ===" >> $LOG
echo "" >> $LOG
