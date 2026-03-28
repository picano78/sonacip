#!/bin/bash

# SONACIP Service Configuration Fix
# Ensures correct entrypoint and restart policies

echo "=== SONACIP SERVICE FIX ==="

# Detect correct entry point
ENTRY_POINT="run:app"  # Default for this project
if [ -f "/opt/sonacip/_truth_app.py" ]; then
    ENTRY_POINT="_truth_app:app"
    echo "Found _truth_app.py - using _truth_app:app"
else
    echo "Using run:app (standard for this project)"
fi

# Create/fix systemd service
cat > /etc/systemd/system/sonacip.service << EOF
[Unit]
Description=SONACIP Production Application
After=network.target
Wants=network.target

[Service]
Type=simple
User=sonacip
Group=sonacip
WorkingDirectory=/opt/sonacip
Environment="PATH=/opt/sonacip/venv/bin"
EnvironmentFile=/opt/sonacip/.env
Environment=PYTHONUNBUFFERED=1
Environment=RUN_MAIN=true
ExecStart=/opt/sonacip/venv/bin/gunicorn \\
    --workers 1 \\
    --threads 1 \\
    --worker-class gthread \\
    --timeout 120 \\
    --bind 127.0.0.1:8000 \\
    --access-logfile - \\
    --error-logfile - \\
    $ENTRY_POINT
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=5
KillMode=mixed
TimeoutStopSec=10

# Memory optimization for 1GB RAM
MemoryMax=512M
MemoryLimit=512M
OOMScoreAdjust=100

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/sonacip /var/log /tmp
UMask=0027

[Install]
WantedBy=multi-user.target
EOF

echo "Service configuration updated with entrypoint: $ENTRY_POINT"

# Reload and restart
systemctl daemon-reload
systemctl enable sonacip
systemctl restart sonacip

echo "Service restarted with auto-restart enabled"

# Verify
sleep 5
if systemctl is-active --quiet sonacip; then
    echo "✅ SONACIP service is running"
else
    echo "❌ Service failed - checking logs"
    journalctl -u sonacip -n 20
fi

echo "=== SERVICE FIX DONE ==="
