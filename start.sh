#!/bin/bash
# Quick start script for SONACIP development

echo "🚀 SONACIP - Quick Start"
echo "========================"
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -q -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi

echo "✓ Dependencies installed"

# Start server
echo ""
echo "🌟 Starting SONACIP server..."
echo ""
echo "📍 Access the application at: http://localhost"
echo "👤 Default admin login:"
echo "   Email: admin@example.com"
echo "   Password: Admin123!"
echo ""
echo "Press CTRL+C to stop the server"
echo ""

gunicorn -c gunicorn.conf.py run:app
