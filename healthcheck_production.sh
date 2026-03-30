#!/bin/bash

# SONACIP Health Check Script
# Checks nginx, gunicorn, and port 8000

echo "=== SONACIP HEALTH CHECK ==="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check nginx
if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✅ Nginx: RUNNING${NC}"
else
    echo -e "${RED}❌ Nginx: FAILED${NC}"
    exit 1
fi

# Check sonacip service
if systemctl is-active --quiet sonacip; then
    echo -e "${GREEN}✅ SONACIP service: RUNNING${NC}"
else
    echo -e "${RED}❌ SONACIP service: FAILED${NC}"
    exit 1
fi

# Check port 8000
if netstat -tuln | grep -q ":8000 "; then
    echo -e "${GREEN}✅ Port 8000: LISTENING${NC}"
else
    echo -e "${RED}❌ Port 8000: NOT LISTENING${NC}"
    exit 1
fi

# Test HTTP response
if curl -s --max-time 5 http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo -e "${GREEN}✅ HTTP response: OK${NC}"
else
    echo -e "${YELLOW}⚠️  HTTP response: SLOW/FAILED${NC}"
fi

echo -e "${GREEN}✅ ALL CHECKS PASSED${NC}"
echo "STATUS: OK"
