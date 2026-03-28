#!/bin/bash

# Execute SONACIP Emergency Fix
# This script runs the emergency fix on the server

echo "=== EXECUTING SONACIP EMERGENCY FIX ==="

# Copy and execute emergency fix
sudo bash /opt/sonacip/sonacip_emergency_fix.sh
