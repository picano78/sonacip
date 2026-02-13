#!/bin/bash
# SONACIP Setup Script for Optimized Features
# This script installs and configures all optimization features

set -e  # Exit on error

echo "╔══════════════════════════════════════════════╗"
echo "║   SONACIP Optimization Setup Script         ║"
echo "║   Installing Enhanced Features               ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    print_warning "Running as root. Consider using a regular user with sudo."
fi

# 1. Check Python version
print_status "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.11"

if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"; then
    print_success "Python $PYTHON_VERSION is installed"
else
    print_error "Python $REQUIRED_VERSION+ is required. Current: $PYTHON_VERSION"
    exit 1
fi

# 2. Check Redis
print_status "Checking Redis installation..."
if command -v redis-cli &> /dev/null; then
    print_success "Redis is installed"
    
    # Check if Redis is running
    if redis-cli ping &> /dev/null; then
        print_success "Redis is running"
    else
        print_warning "Redis is installed but not running"
        echo "Starting Redis..."
        if command -v systemctl &> /dev/null; then
            sudo systemctl start redis 2>/dev/null || true
        fi
    fi
else
    print_warning "Redis not found. Installing Redis..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y redis-server
        sudo systemctl enable redis
        sudo systemctl start redis
        print_success "Redis installed and started"
    elif command -v yum &> /dev/null; then
        sudo yum install -y redis
        sudo systemctl enable redis
        sudo systemctl start redis
        print_success "Redis installed and started"
    else
        print_error "Cannot install Redis automatically. Please install manually."
        exit 1
    fi
fi

# 3. Create/activate virtual environment
print_status "Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_success "Virtual environment created"
else
    print_status "Virtual environment already exists"
fi

source venv/bin/activate
print_success "Virtual environment activated"

# 4. Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip &> /dev/null
print_success "Pip upgraded"

# 5. Install requirements
print_status "Installing Python dependencies..."
echo "This may take a few minutes..."
pip install -r requirements.txt
print_success "Dependencies installed"

# 6. Setup environment variables
print_status "Checking environment configuration..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        print_warning ".env file not found. Creating from .env.example..."
        cp .env.example .env
        print_success ".env file created"
        print_warning "⚠️  IMPORTANT: Edit .env and set your configuration!"
        print_warning "Required: SECRET_KEY, DATABASE_URL, MAIL_SERVER, etc."
    else
        print_error ".env.example not found!"
        exit 1
    fi
else
    print_success ".env file exists"
fi

# 7. Generate secret key if needed
if grep -q "CHANGEME" .env 2>/dev/null; then
    print_status "Generating SECRET_KEY..."
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/CHANGEME_GENERATE_WITH_PYTHON_SECRETS/$SECRET_KEY/" .env
    else
        # Linux
        sed -i "s/CHANGEME_GENERATE_WITH_PYTHON_SECRETS/$SECRET_KEY/" .env
    fi
    print_success "SECRET_KEY generated"
fi

# 8. Check Twilio configuration
print_status "Checking Twilio SMS configuration..."
if grep -q "TWILIO_ACCOUNT_SID" .env && ! grep -q "your_account_sid" .env; then
    print_success "Twilio configuration found"
else
    print_warning "Twilio not configured. SMS features will be disabled."
    print_status "To enable SMS, add to .env:"
    echo "  TWILIO_ACCOUNT_SID=your_account_sid"
    echo "  TWILIO_AUTH_TOKEN=your_auth_token"
    echo "  TWILIO_FROM_NUMBER=+15551234567"
fi

# 9. Initialize database
print_status "Initializing database..."
if [ -f "manage.py" ]; then
    python manage.py db upgrade 2>/dev/null || python init_db.py
    print_success "Database initialized"
elif [ -f "init_db.py" ]; then
    python init_db.py
    print_success "Database initialized"
else
    print_warning "No database initialization script found"
fi

# 10. Create systemd services
print_status "Creating systemd service files..."

# Celery Worker Service
cat > /tmp/sonacip-celery.service << EOF
[Unit]
Description=SONACIP Celery Worker
After=network.target redis.target

[Service]
Type=simple
User=$(whoami)
Group=$(whoami)
WorkingDirectory=$(pwd)
Environment="PATH=$(pwd)/venv/bin"
ExecStart=$(pwd)/venv/bin/celery -A celery_app.celery worker --loglevel=info
ExecStop=/bin/kill -TERM \$MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Celery Beat Service
cat > /tmp/sonacip-celery-beat.service << EOF
[Unit]
Description=SONACIP Celery Beat Scheduler
After=network.target redis.target

[Service]
Type=simple
User=$(whoami)
Group=$(whoami)
WorkingDirectory=$(pwd)
Environment="PATH=$(pwd)/venv/bin"
ExecStart=$(pwd)/venv/bin/celery -A celery_app.celery beat --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

print_success "Systemd service files created in /tmp/"
print_status "To install services, run:"
echo "  sudo cp /tmp/sonacip-celery.service /etc/systemd/system/"
echo "  sudo cp /tmp/sonacip-celery-beat.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable sonacip-celery sonacip-celery-beat"
echo "  sudo systemctl start sonacip-celery sonacip-celery-beat"

# 11. Create log directories
print_status "Creating log directories..."
mkdir -p logs backups uploads
print_success "Directories created"

# 12. Test installations
print_status "Running installation tests..."

# Test Redis connection
if python3 -c "import redis; r=redis.Redis(); r.ping()" 2>/dev/null; then
    print_success "✓ Redis connection test passed"
else
    print_error "✗ Redis connection test failed"
fi

# Test Celery
if python3 -c "from celery_app import celery; print('OK')" 2>/dev/null | grep -q "OK"; then
    print_success "✓ Celery import test passed"
else
    print_error "✗ Celery import test failed"
fi

# Test database connection
if python3 -c "from app import create_app, db; app=create_app(); app.app_context().push(); db.session.execute(db.text('SELECT 1'))" 2>/dev/null; then
    print_success "✓ Database connection test passed"
else
    print_warning "✗ Database connection test failed (might need configuration)"
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║         Setup Complete!                      ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
print_success "All optimization features are installed!"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Configure .env file with your settings"
echo "   - Edit: nano .env"
echo "   - Set: DATABASE_URL, MAIL_SERVER, TWILIO credentials"
echo ""
echo "2. Start the services:"
echo "   ./start.sh                  # Flask application"
echo "   ./start_celery.sh          # Background tasks worker"
echo "   ./start_celery_beat.sh     # Scheduled tasks"
echo ""
echo "3. Access the application:"
echo "   - Web: http://localhost:5000"
echo "   - API Docs: http://localhost:5000/api/docs/"
echo "   - Automation Builder: http://localhost:5000/automation/builder"
echo "   - Health Check: http://localhost:5000/health/detailed"
echo ""
echo "4. Monitor tasks (optional):"
echo "   celery -A celery_app.celery flower --port=5555"
echo "   Then visit: http://localhost:5555"
echo ""
echo "📖 For detailed documentation, see:"
echo "   - OPTIMIZATION_GUIDE.md"
echo "   - README.md"
echo ""
print_success "Happy optimizing! 🚀"
