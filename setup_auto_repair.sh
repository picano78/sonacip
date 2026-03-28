#!/bin/bash

# SONACIP Auto-Repair Setup Script
# Configures automatic monitoring and repair

echo "=== SONACIP AUTO-REPAIR SETUP ==="

# Step 1: Make scripts executable
chmod +x /opt/sonacip/auto_fix.sh
chmod +x /opt/sonacip/sonacip_service_fix.sh

# Step 2: Fix service configuration
echo "Applying service fixes..."
/opt/sonacip/sonacip_service_fix.sh

# Step 3: Setup cron job for auto-repair
echo "Setting up auto-repair cron job..."

# Get current crontab
crontab -l > /tmp/mycron 2>/dev/null || touch /tmp/mycron

# Remove existing auto-fix entry if exists
sed -i '/auto_fix.sh/d' /tmp/mycron

# Add new auto-fix entry (every minute)
echo "* * * * * /opt/sonacip/auto_fix.sh" >> /tmp/mycron

# Install new crontab
crontab /tmp/mycron
rm /tmp/mycron

echo "Auto-repair cron job configured (runs every minute)"

# Step 4: Test auto-repair script
echo "Testing auto-repair script..."
/opt/sonacip/auto_fix.sh

# Step 5: Verify setup
echo ""
echo "=== SETUP VERIFICATION ==="

# Check cron
if crontab -l | grep -q "auto_fix.sh"; then
    echo "✅ Auto-repair cron job active"
else
    echo "❌ Auto-repair cron job not found"
fi

# Check service
if systemctl is-active --quiet sonacip; then
    echo "✅ SONACIP service running"
else
    echo "❌ SONACIP service not running"
fi

# Check nginx
if systemctl is-active --quiet nginx; then
    echo "✅ Nginx service running"
else
    echo "❌ Nginx service not running"
fi

# Test app response
if curl -s --max-time 5 http://127.0.0.1:8000 > /dev/null 2>&1; then
    echo "✅ App responding on port 8000"
else
    echo "❌ App not responding on port 8000"
fi

echo ""
echo "=== AUTO-REPAIR SYSTEM ACTIVE ==="
echo "📋 Monitoring features:"
echo "   ✅ Service restart on failure"
echo "   ✅ App response monitoring"
echo "   ✅ Entry point auto-detection"
echo "   ✅ Virtual environment check"
echo "   ✅ Nginx monitoring"
echo "   ✅ Disk space monitoring"
echo "   ✅ Memory monitoring"
echo ""
echo "📝 Logs location: /var/log/sonacip_auto_fix.log"
echo "🔄 Check frequency: Every minute"
echo "🛠️  Manual repair: /opt/sonacip/auto_fix.sh"
echo ""
echo "🚀 SONACIP is now self-healing!"
