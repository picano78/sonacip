#!/bin/bash

# SONACIP Stable Auto-Healing Setup
# Simple, reliable system without server reboot

set -e

echo "=== SONACIP STABLE AUTO-HEALING SETUP ==="

# Step 1: Install stable scripts
echo "Step 1: Installing stable scripts..."
cp health_check_stable.sh /opt/sonacip/health_check.sh
cp auto_fix_stable.sh /opt/sonacip/auto_fix.sh

# Step 2: Set permissions
echo "Step 2: Setting permissions..."
chmod +x /opt/sonacip/health_check.sh
chmod +x /opt/sonacip/auto_fix.sh

# Step 3: Create log file
echo "Step 3: Creating log file..."
touch /var/log/sonacip_health.log
chmod 644 /var/log/sonacip_health.log

# Step 4: Setup cron job (every minute)
echo "Step 4: Setting up cron job..."
(crontab -l 2>/dev/null; echo "* * * * * /opt/sonacip/health_check.sh") | crontab -

echo "✅ Cron job configured (every minute)"

# Step 5: Update systemd service for auto-restart
echo "Step 5: Configuring systemd auto-restart..."
SERVICE_FILE="/etc/systemd/system/sonacip.service"

if [ -f "$SERVICE_FILE" ]; then
    # Backup original
    cp "$SERVICE_FILE" "$SERVICE_FILE.backup.$(date +%s)"
    
    # Ensure restart settings are present
    if ! grep -q "Restart=" "$SERVICE_FILE"; then
        sed -i '/^\[Service\]/a Restart=always' "$SERVICE_FILE"
    fi
    
    if ! grep -q "RestartSec=" "$SERVICE_FILE"; then
        sed -i '/Restart=always/a RestartSec=5' "$SERVICE_FILE"
    fi
    
    echo "✅ Systemd service updated with auto-restart"
else
    echo "❌ Service file not found"
    exit 1
fi

# Reload systemd
systemctl daemon-reload
systemctl restart sonacip

echo "✅ Systemd reloaded and service restarted"

# Step 6: Test the system
echo "Step 6: Testing stable auto-healing..."

# Test health check
echo "Testing health check script..."
/opt/sonacip/health_check.sh

# Verify cron job
echo ""
echo "=== CRON VERIFICATION ==="
if crontab -l | grep -q "health_check.sh"; then
    echo "✅ Cron job active"
    echo "📋 Schedule: Every minute"
    echo "📝 Log: /var/log/sonacip_health.log"
else
    echo "❌ Cron job not found"
fi

# Verify services
echo ""
echo "=== SERVICE STATUS ==="
if systemctl is-active --quiet sonacip; then
    echo "✅ SONACIP: RUNNING"
else
    echo "❌ SONACIP: FAILED"
fi

if systemctl is-active --quiet nginx; then
    echo "✅ Nginx: RUNNING"
else
    echo "❌ Nginx: FAILED"
fi

if systemctl is-active --quiet postgresql; then
    echo "✅ PostgreSQL: RUNNING"
else
    echo "❌ PostgreSQL: FAILED"
fi

# Test application response
echo ""
echo "=== APPLICATION TEST ==="
if curl -s --max-time 5 http://localhost:8000 >/dev/null 2>&1; then
    echo "✅ Application: RESPONDING"
else
    echo "❌ Application: NOT RESPONDING"
fi

# Step 7: Setup monitoring commands
echo ""
echo "Step 7: Setting up monitoring..."

# Create simple status script
cat > /opt/sonacip/check_status.sh << 'EOF'
#!/bin/bash
echo "=== SONACIP STATUS ==="
echo "Time: $(date)"
echo ""
echo "Services:"
systemctl is-active sonacip nginx postgresql 2>/dev/null | sed 's/^/   /'
echo ""
echo "Application:"
if curl -s --max-time 3 http://localhost:8000 >/dev/null 2>&1; then
    echo "   Status: ✅ RESPONDING"
else
    echo "   Status: ❌ DOWN"
fi
echo ""
echo "Recent logs:"
tail -5 /var/log/sonacip_health.log 2>/dev/null | sed 's/^/   /'
EOF

chmod +x /opt/sonacip/check_status.sh

echo "✅ Status script created: /opt/sonacip/check_status.sh"

# Final summary
echo ""
echo "=== STABLE AUTO-HEALING SETUP COMPLETE ==="
echo ""
echo "🤖 Features:"
echo "   ✅ Health monitoring every minute"
echo "   ✅ Automatic service restart"
echo "   ✅ Full stack restart if needed"
echo "   ✅ Clear logging"
echo "   ✅ NO server reboot"
echo "   ✅ Simple and reliable"
echo ""
echo "📋 Commands:"
echo "   📊 Status: /opt/sonacip/check_status.sh"
echo "   🔍 Health: /opt/sonacip/health_check.sh"
echo "   🔧 Fix: /opt/sonacip/auto_fix.sh"
echo "   📝 Logs: tail -f /var/log/sonacip_health.log"
echo ""
echo "⚙️ Configuration:"
echo "   🔄 Check frequency: Every minute"
echo "   📝 Log location: /var/log/sonacip_health.log"
echo "   🔧 Auto-restart: Enabled (5s delay)"
echo "   🚫 Server reboot: DISABLED"
echo ""
echo "🧪 Test:"
echo "   To test: systemctl stop sonacip"
echo "   Wait 1 minute → should auto-restart"
echo "   Check: /opt/sonacip/check_status.sh"
echo ""
echo "🚀 Stable auto-healing system ready!"
