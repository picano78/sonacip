#!/bin/bash

# SONACIP Auto-Healing Setup Script
# Configures complete self-healing system

set -e

echo "=== SONACIP AUTO-HEALING SETUP ==="

# Step 1: Copy scripts to /opt/sonacip
echo "Step 1: Installing scripts..."
cp health_check.sh /opt/sonacip/
cp auto_fix_enhanced.sh /opt/sonacip/

# Step 2: Set permissions
echo "Step 2: Setting permissions..."
chmod +x /opt/sonacip/health_check.sh
chmod +x /opt/sonacip/auto_fix_enhanced.sh
chmod +x /opt/sonacip/*.sh

# Step 3: Update auto_fix.sh to use enhanced version
echo "Step 3: Updating auto-fix script..."
if [ -f "/opt/sonacip/auto_fix.sh" ]; then
    cp /opt/sonacip/auto_fix.sh /opt/sonacip/auto_fix_original.sh.backup
    cp /opt/sonacip/auto_fix_enhanced.sh /opt/sonacip/auto_fix.sh
fi

# Step 4: Setup cron job
echo "Step 4: Setting up automatic monitoring..."
crontab -l > /tmp/mycron 2>/dev/null || touch /tmp/mycron

# Remove existing health check entries
sed -i '/health_check.sh/d' /tmp/mycron

# Add new health check cron job
echo "* * * * * /opt/sonacip/health_check.sh >> /var/log/sonacip_health.log 2>&1" >> /tmp/mycron

# Install new crontab
crontab /tmp/mycron
rm /tmp/mycron

echo "✅ Cron job configured (runs every minute)"

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

# Step 6: Create log file
echo "Step 6: Setting up logging..."
touch /var/log/sonacip_health.log
chmod 644 /var/log/sonacip_health.log

echo "✅ Log file created: /var/log/sonacip_health.log"

# Step 7: Test the system
echo "Step 7: Testing auto-healing system..."

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

# Step 8: Setup monitoring
echo ""
echo "Step 8: Setting up monitoring commands..."

# Create monitoring script
cat > /opt/sonacip/monitor_status.sh << 'EOF'
#!/bin/bash
echo "=== SONACIP SYSTEM STATUS ==="
echo "Time: $(date)"
echo ""
echo "🔥 Services:"
systemctl is-active sonacip nginx postgresql | sed 's/^/   /'
echo ""
echo "📊 Resources:"
echo "   Memory: $(free -h | awk 'NR==2{printf "%.1f/%.1fGB (%.0f%%)", $3/1024, $2/1024, $3*100/$2}')"
echo "   Disk: $(df -h / | awk 'NR==2{printf "%s/%s (%s)", $3, $2, $5}')"
echo "   Load: $(uptime | awk -F'load average:' '{print $2}')"
echo ""
echo "🌐 Application:"
if curl -s --max-time 5 http://localhost:8000 >/dev/null 2>&1; then
    echo "   Status: ✅ RESPONDING"
else
    echo "   Status: ❌ DOWN"
fi
echo ""
echo "📋 Recent Health Checks:"
tail -5 /var/log/sonacip_health.log 2>/dev/null | grep "HEALTH\|SYSTEMS" | sed 's/^/   /'
EOF

chmod +x /opt/sonacip/monitor_status.sh

echo "✅ Monitoring script created: /opt/sonacip/monitor_status.sh"

# Final summary
echo ""
echo "=== AUTO-HEALING SETUP COMPLETE ==="
echo ""
echo "🤖 Auto-Healing Features:"
echo "   ✅ Health monitoring every minute"
echo "   ✅ Automatic service restart"
echo "   ✅ Database connection repair"
echo "   ✅ Virtual environment recovery"
echo "   ✅ RAM cache clearing"
echo "   ✅ Disk space management"
echo "   ✅ Server restart (last resort)"
echo "   ✅ Comprehensive logging"
echo ""
echo "📋 Management Commands:"
echo "   📊 Status: /opt/sonacip/monitor_status.sh"
echo "   🔍 Health: /opt/sonacip/health_check.sh"
echo "   🔧 Repair: /opt/sonacip/auto_fix.sh"
echo "   📝 Logs: tail -f /var/log/sonacip_health.log"
echo ""
echo "⚙️ Configuration:"
echo "   🔄 Check frequency: Every minute"
echo "   📝 Log location: /var/log/sonacip_health.log"
echo "   🔧 Auto-restart: Enabled (5s delay)"
echo "   🚨 Server restart: Last resort (30min cooldown)"
echo ""
echo "🧪 Test Simulation:"
echo "   To test: systemctl stop sonacip"
echo "   Wait 1 minute → should auto-restart"
echo ""
echo "🚀 SONACIP is now self-healing and highly available!"
