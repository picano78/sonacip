#!/bin/bash

LOG="/var/log/sonacip_health.log"
DATE=$(date "+%Y-%m-%d %H:%M:%S")

echo "[$DATE] Running auto-fix..." >> $LOG

systemctl restart sonacip
sleep 5

if systemctl is-active --quiet sonacip; then
    echo "[$DATE] FIXED: SONACIP restarted" >> $LOG
    exit 0
fi

echo "[$DATE] Trying full stack restart..." >> $LOG

systemctl restart nginx
systemctl restart postgresql
systemctl restart sonacip

sleep 5

if systemctl is-active --quiet sonacip; then
    echo "[$DATE] FIXED after full restart" >> $LOG
    exit 0
fi

echo "[$DATE] CRITICAL: manual intervention needed" >> $LOG
