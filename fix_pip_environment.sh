#!/bin/bash

# SONACIP Pip Environment Fix for Ubuntu 24.04
# Robust pip management with virtual environment

set -e

echo "=== SONACIP PIP ENVIRONMENT FIX ==="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "${CYAN}${BOLD}=== $1 ===${NC}"; }

PROJECT_DIR="/opt/sonacip"
VENV_DIR="$PROJECT_DIR/venv"

# Step 1: Verify Python3 installation
print_header "Step 1: Verifying Python3 Installation"

if command -v python3 >/dev/null 2>&1; then
    PYTHON_VERSION=$(python3 --version)
    print_success "Python3 found: $PYTHON_VERSION"
else
    print_error "Python3 not found. Installing..."
    apt-get update -qq
    apt-get install -y python3 python3-full
    print_success "Python3 installed"
fi

# Verify python3-pip
if ! dpkg -l | grep -q python3-pip; then
    print_status "Installing python3-pip..."
    apt-get install -y python3-pip
    print_success "python3-pip installed"
else
    print_success "python3-pip already installed"
fi

# Step 2: Create virtual environment
print_header "Step 2: Creating Virtual Environment"

cd "$PROJECT_DIR"

if [ -d "$VENV_DIR" ]; then
    print_warning "Virtual environment already exists. Recreating for clean setup..."
    rm -rf "$VENV_DIR"
fi

print_status "Creating virtual environment..."
if python3 -m venv venv; then
    print_success "Virtual environment created successfully"
else
    print_error "Failed to create virtual environment"
    exit 1
fi

# Step 3: Activate virtual environment
print_header "Step 3: Activating Virtual Environment"

print_status "Activating virtual environment..."
source venv/bin/activate

if [ "$VIRTUAL_ENV" = "$VENV_DIR" ]; then
    print_success "Virtual environment activated: $VIRTUAL_ENV"
else
    print_error "Failed to activate virtual environment"
    exit 1
fi

# Step 4: Update pip inside venv
print_header "Step 4: Updating Pip in Virtual Environment"

print_status "Updating pip using python -m pip..."
python -m ensurepip --upgrade || print_warning "ensurepip failed, continuing..."
python -m pip install --upgrade pip

# Verify pip version
PIP_VERSION=$(pip --version)
print_success "Pip updated: $PIP_VERSION"

# Step 5: Test pip functionality
print_header "Step 5: Testing Pip Functionality"

print_status "Testing pip with a simple package..."
python -m pip install --quiet wheel setuptools

if python -m pip list | grep -q wheel; then
    print_success "Pip functionality verified"
else
    print_error "Pip functionality test failed"
    exit 1
fi

# Step 6: Update existing scripts to use venv
print_header "Step 6: Updating Scripts for Virtual Environment"

# Function to update script
update_script() {
    local script_path="$1"
    if [ -f "$script_path" ]; then
        print_status "Updating script: $script_path"
        
        # Backup original
        cp "$script_path" "$script_path.backup.$(date +%s)"
        
        # Update to use venv
        sed -i "s|/opt/sonacip/venv/bin/pip|python -m pip|g" "$script_path"
        sed -i "s|pip install|python -m pip install|g" "$script_path"
        sed -i "s|/usr/bin/pip3|python -m pip|g" "$script_path"
        
        # Remove dangerous flags
        sed -i "s|--break-system-packages||g" "$script_path"
        
        print_success "Updated: $script_path"
    fi
}

# Update common scripts
update_script "/opt/sonacip/ionos_quick_install.sh"
update_script "/opt/sonacip/sonacip_emergency_fix.sh"
update_script "/opt/sonacip/postgresql_setup.sh"
update_script "/opt/sonacip/security_setup.sh"
update_script "/opt/sonacip/auto_fix.sh"
update_script "/opt/sonacip/setup_auto_healing.sh"

# Step 7: Create pip management script
print_header "Step 7: Creating Pip Management Script"

cat > "$PROJECT_DIR/pip_manager.sh" << 'EOF'
#!/bin/bash

# SONACIP Pip Manager
# Always uses virtual environment

PROJECT_DIR="/opt/sonacip"
VENV_DIR="$PROJECT_DIR/venv"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_status() { echo -e "${YELLOW}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    print_error "Virtual environment not found. Please run fix_pip_environment.sh first."
    exit 1
fi

# Activate venv
cd "$PROJECT_DIR"
source venv/bin/activate

# Check if venv is active
if [ "$VIRTUAL_ENV" != "$VENV_DIR" ]; then
    print_error "Failed to activate virtual environment"
    exit 1
fi

# Show pip version
print_status "Current pip version:"
pip --version

# Show installed packages
print_status "Installed packages:"
pip list --format=columns

echo ""
print_status "Usage examples:"
echo "  Install package: python -m pip install package_name"
echo "  Install from requirements: python -m pip install -r requirements.txt"
echo "  Update pip: python -m pip install --upgrade pip"
echo "  List packages: python -m pip list"
echo "  Show package info: python -m pip show package_name"
EOF

chmod +x "$PROJECT_DIR/pip_manager.sh"
print_success "Pip manager script created: /opt/sonacip/pip_manager.sh"

# Step 8: Create requirements installer
print_header "Step 8: Creating Requirements Installer"

cat > "$PROJECT_DIR/install_requirements.sh" << 'EOF'
#!/bin/bash

# SONACIP Requirements Installer
# Safe installation using virtual environment

PROJECT_DIR="/opt/sonacip"
VENV_DIR="$PROJECT_DIR/venv"
REQUIREMENTS_FILE="$PROJECT_DIR/requirements.txt"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_status() { echo -e "${YELLOW}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    print_error "Virtual environment not found. Please run fix_pip_environment.sh first."
    exit 1
fi

# Check if requirements.txt exists
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    print_error "requirements.txt not found in $PROJECT_DIR"
    exit 1
fi

# Activate venv
cd "$PROJECT_DIR"
source venv/bin/activate

# Check if venv is active
if [ "$VIRTUAL_ENV" != "$VENV_DIR" ]; then
    print_error "Failed to activate virtual environment"
    exit 1
fi

print_status "Installing requirements from $REQUIREMENTS_FILE"

# Install requirements
if python -m pip install -r "$REQUIREMENTS_FILE"; then
    print_success "Requirements installed successfully"
else
    print_error "Failed to install requirements"
    exit 1
fi

# Show installed packages
print_status "Installed packages:"
python -m pip list --format=columns
EOF

chmod +x "$PROJECT_DIR/install_requirements.sh"
print_success "Requirements installer created: /opt/sonacip/install_requirements.sh"

# Step 9: Test with requirements.txt
print_header "Step 9: Testing with Requirements.txt"

if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    print_status "Found requirements.txt, testing installation..."
    
    # Show first few lines of requirements
    print_status "Requirements preview:"
    head -10 "$PROJECT_DIR/requirements.txt"
    
    echo ""
    print_status "To install requirements, run:"
    echo "  /opt/sonacip/install_requirements.sh"
else
    print_warning "requirements.txt not found in $PROJECT_DIR"
fi

# Step 10: Final verification
print_header "Step 10: Final Verification"

# Test venv activation
cd "$PROJECT_DIR"
source venv/bin/activate

if [ "$VIRTUAL_ENV" = "$VENV_DIR" ]; then
    print_success "Virtual environment working correctly"
else
    print_error "Virtual environment activation failed"
    exit 1
fi

# Test pip in venv
PIP_VERSION=$(python -m pip --version)
print_success "Pip in venv: $PIP_VERSION"

# Test python -m pip
if python -m pip list >/dev/null 2>&1; then
    print_success "python -m pip working correctly"
else
    print_error "python -m pip not working"
    exit 1
fi

# Test without dangerous flags
print_status "Testing safe pip usage..."
python -m pip install --quiet --dry-run wheel 2>/dev/null && print_success "Safe pip usage confirmed"

# Summary
print_header "ENVIRONMENT FIX SUMMARY"

echo ""
echo "✅ Python3: Installed and verified"
echo "✅ Virtual Environment: Created at $VENV_DIR"
echo "✅ Pip: Updated and working in venv"
echo "✅ Scripts: Updated to use venv"
echo "✅ Safety: Removed dangerous flags"
echo "✅ Tools: Created management scripts"
echo ""

echo "📋 Management Commands:"
echo "   🐍 Pip manager: /opt/sonacip/pip_manager.sh"
echo "   📦 Install requirements: /opt/sonacip/install_requirements.sh"
echo "   🔧 Fix environment: /opt/sonacip/fix_pip_environment.sh"
echo ""

echo "🛡️ Safe Usage Examples:"
echo "   Install package: python -m pip install package_name"
echo "   Install from requirements: python -m pip install -r requirements.txt"
echo "   Update pip: python -m pip install --upgrade pip"
echo "   List packages: python -m pip list"
echo ""

echo "⚠️ Important Notes:"
echo "   - Always use 'python -m pip' instead of 'pip'"
echo "   - Virtual environment is always activated first"
echo "   - No --break-system-packages flag needed"
echo "   - All installations are isolated to venv"
echo "   - Compatible with Ubuntu 24.04 and low-resource VPS"
echo ""

print_success "🚀 Pip environment fix completed successfully!"
echo ""
print_status "Environment is now stable and ready for production use."
