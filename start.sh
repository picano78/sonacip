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

# Initialize database
echo "🗄️  Initializing database..."
python3 -c "
from app import create_app, db
app = create_app()
with app.app_context():
    db.create_all()
    print('✓ Database created')
"

if [ $? -ne 0 ]; then
    echo "❌ Failed to initialize database"
    exit 1
fi

# Start server
echo ""
echo "🌟 Starting SONACIP server..."
echo ""
echo "📍 Access the application at: http://localhost:5000"
echo "👤 Default admin login:"
echo "   Email: admin@sonacip.it"
echo "   Password: admin123"
echo ""
echo "Press CTRL+C to stop the server"
echo ""

python3 run.py
