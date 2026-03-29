#!/bin/bash

LOG="/var/log/sonacip_health.log"
DATE=$(date "+%Y-%m-%d %H:%M:%S")

echo "[$DATE] Checking system..." >> $LOG

# Check HTTP
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000)

if [ "$HTTP_STATUS" != "200" ]; then
    echo "[$DATE] ERROR: HTTP not responding (status $HTTP_STATUS)" >> $LOG
    /opt/sonacip/auto_fix.sh
    exit 1
fi

# Check SONACIP service
if ! systemctl is-active --quiet sonacip; then
    echo "[$DATE] ERROR: SONACIP down" >> $LOG
    /opt/sonacip/auto_fix.sh
    exit 1
fi

# Check NGINX
if ! systemctl is-active --quiet nginx; then
    echo "[$DATE] ERROR: NGINX down" >> $LOG
    systemctl restart nginx
fi

echo "[$DATE] OK" >> $LOG
