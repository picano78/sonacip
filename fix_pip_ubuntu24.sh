#!/bin/bash

# SONACIP Pip Fix for Ubuntu 24.04
# Fixes pip3 command not found issue

set -e

echo "=== PIP FIX FOR UBUNTU 24.04 ==="

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

# Step 1: Check Python3 installation
print_header "Step 1: Checking Python3 Installation"

if command -v python3 >/dev/null 2>&1; then
    PYTHON_VERSION=$(python3 --version)
    print_success "Python3 found: $PYTHON_VERSION"
else
    print_error "Python3 not found. Installing..."
    apt-get update -qq
    apt-get install -y python3 python3-full
    print_success "Python3 installed"
fi

# Step 2: Check current pip status
print_header "Step 2: Checking Current Pip Status"

echo "Checking pip3 command..."
if command -v pip3 >/dev/null 2>&1; then
    PIP3_VERSION=$(pip3 --version 2>/dev/null || echo "Failed to get version")
    print_success "pip3 found: $PIP3_VERSION"
else
    print_warning "pip3 command not found"
fi

echo "Checking python3 -m pip..."
if python3 -m pip --version >/dev/null 2>&1; then
    PIP_MODULE_VERSION=$(python3 -m pip --version)
    print_success "python3 -m pip working: $PIP_MODULE_VERSION"
else
    print_warning "python3 -m pip not working"
fi

# Step 3: Ensure pip is installed correctly
print_header "Step 3: Ensuring Pip Installation"

print_status "Running python3 -m ensurepip --upgrade..."
if python3 -m ensurepip --upgrade; then
    print_success "ensurepip completed successfully"
else
    print_warning "ensurepip failed, continuing with alternative method..."
fi

# Step 4: Upgrade pip
print_header "Step 4: Upgrading Pip"

print_status "Upgrading pip using python3 -m pip..."
if python3 -m pip install --upgrade pip; then
    NEW_PIP_VERSION=$(python3 -m pip --version)
    print_success "Pip upgraded: $NEW_PIP_VERSION"
else
    print_error "Failed to upgrade pip"
fi

# Step 5: Create symlinks if pip3 is missing
print_header "Step 5: Creating Symlinks"

# Check if pip3 exists in standard locations
PIP3_LOCATIONS=(
    "/usr/bin/pip3"
    "/usr/local/bin/pip3"
    "/bin/pip3"
    "/usr/bin/pip"
    "/usr/local/bin/pip"
)

PIP3_FOUND=false
for location in "${PIP3_LOCATIONS[@]}"; do
    if [ -f "$location" ]; then
        print_status "Found pip at: $location"
        PIP3_FOUND=true
        break
    fi
done

if [ "$PIP3_FOUND" = true ]; then
    # Create symlinks to /usr/local/bin if needed
    if [ ! -f "/usr/local/bin/pip3" ] && [ -f "/usr/bin/pip3" ]; then
        print_status "Creating symlink for pip3..."
        ln -sf /usr/bin/pip3 /usr/local/bin/pip3 || true
        print_success "pip3 symlink created"
    fi
    
    if [ ! -f "/usr/local/bin/pip" ] && [ -f "/usr/bin/pip" ]; then
        print_status "Creating symlink for pip..."
        ln -sf /usr/bin/pip /usr/local/bin/pip || true
        print_success "pip symlink created"
    fi
else
    print_warning "No pip installation found, will reinstall"
fi

# Step 6: Verify installation
print_header "Step 6: Verifying Installation"

echo "Testing python3 -m pip..."
if python3 -m pip --version >/dev/null 2>&1; then
    FINAL_PIP_VERSION=$(python3 -m pip --version)
    print_success "✅ python3 -m pip: $FINAL_PIP_VERSION"
else
    print_error "❌ python3 -m pip still not working"
fi

echo "Testing pip3 command..."
if command -v pip3 >/dev/null 2>&1; then
    PIP3_FINAL_VERSION=$(pip3 --version 2>/dev/null || echo "Command exists but failed to execute")
    print_success "✅ pip3 command: $PIP3_FINAL_VERSION"
else
    print_error "❌ pip3 command still not found"
fi

echo "Testing pip command..."
if command -v pip >/dev/null 2>&1; then
    PIP_FINAL_VERSION=$(pip --version 2>/dev/null || echo "Command exists but failed to execute")
    print_success "✅ pip command: $PIP_FINAL_VERSION"
else
    print_error "❌ pip command not found"
fi

# Step 7: Complete reinstall if still not working
print_header "Step 7: Complete Reinstall (if needed)"

if ! command -v pip3 >/dev/null 2>&1 || ! python3 -m pip --version >/dev/null 2>&1; then
    print_warning "Pip still not working, performing complete reinstall..."
    
    print_status "Removing existing pip packages..."
    apt-get remove -y python3-pip python3-pip-whl python3-pip-whl 2>/dev/null || true
    
    print_status "Cleaning pip cache..."
    rm -rf ~/.cache/pip 2>/dev/null || true
    rm -rf /root/.cache/pip 2>/dev/null || true
    
    print_status "Reinstalling python3-pip..."
    apt-get install -y python3-pip
    
    print_status "Running ensurepip again..."
    python3 -m ensurepip --upgrade
    
    print_status "Upgrading pip..."
    python3 -m pip install --upgrade pip
    
    print_status "Creating symlinks again..."
    ln -sf /usr/bin/pip3 /usr/local/bin/pip3 2>/dev/null || true
    ln -sf /usr/bin/pip /usr/local/bin/pip 2>/dev/null || true
    
    print_success "Complete reinstall finished"
else
    print_success "Pip is working correctly, no reinstall needed"
fi

# Step 8: Final verification and PATH update
print_header "Step 8: Final Verification"

# Update PATH to include /usr/local/bin
if [[ ":$PATH:" != *":/usr/local/bin:"* ]]; then
    export PATH="/usr/local/bin:$PATH"
    echo 'export PATH="/usr/local/bin:$PATH"' >> /etc/bash.bashrc
    echo 'export PATH="/usr/local/bin:$PATH"' >> /root/.bashrc
    print_status "PATH updated to include /usr/local/bin"
fi

# Final tests
echo "Final verification tests:"
echo ""

print_status "Testing python3 -m pip..."
if python3 -m pip --version >/dev/null 2>&1; then
    FINAL_MODULE_VERSION=$(python3 -m pip --version)
    print_success "✅ python3 -m pip: $FINAL_MODULE_VERSION"
else
    print_error "❌ python3 -m pip: FAILED"
fi

print_status "Testing pip3 command..."
if command -v pip3 >/dev/null 2>&1; then
    FINAL_PIP3_VERSION=$(pip3 --version 2>/dev/null || echo "Command found but execution failed")
    if [[ "$FINAL_PIP3_VERSION" != *"Command found but execution failed"* ]]; then
        print_success "✅ pip3: $FINAL_PIP3_VERSION"
    else
        print_error "❌ pip3: $FINAL_PIP3_VERSION"
    fi
else
    print_error "❌ pip3: NOT FOUND"
fi

print_status "Testing pip command..."
if command -v pip >/dev/null 2>&1; then
    FINAL_PIP_VERSION=$(pip --version 2>/dev/null || echo "Command found but execution failed")
    if [[ "$FINAL_PIP_VERSION" != *"Command found but execution failed"* ]]; then
        print_success "✅ pip: $FINAL_PIP_VERSION"
    else
        print_error "❌ pip: $FINAL_PIP_VERSION"
    fi
else
    print_error "❌ pip: NOT FOUND"
fi

# Step 9: Create pip management script
print_header "Step 9: Creating Pip Management Script"

cat > /usr/local/bin/pip_manager << 'EOF'
#!/bin/bash

# Pip Manager for Ubuntu 24.04
# Always uses python3 -m pip

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_status() { echo -e "${YELLOW}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Show current pip version
print_status "Current pip version:"
python3 -m pip --version

echo ""
print_status "Usage examples:"
echo "  Install package: python3 -m pip install package_name"
echo "  Install from requirements: python3 -m pip install -r requirements.txt"
echo "  Upgrade pip: python3 -m pip install --upgrade pip"
echo "  List packages: python3 -m pip list"
echo "  Show package info: python3 -m pip show package_name"
echo ""
print_status "Alternative commands:"
echo "  pip3 install package_name (if pip3 works)"
echo "  pip install package_name (if pip works)"
echo ""
print_success "Always prefer: python3 -m pip"
EOF

chmod +x /usr/local/bin/pip_manager
print_success "Pip manager created: /usr/local/bin/pip_manager"

# Step 10: Summary and recommendations
print_header "Step 10: Summary and Recommendations"

echo ""
echo "=== PIP FIX SUMMARY ==="
echo ""

# Show final status
if python3 -m pip --version >/dev/null 2>&1; then
    print_success "✅ python3 -m pip is working (RECOMMENDED)"
else
    print_error "❌ python3 -m pip is not working"
fi

if command -v pip3 >/dev/null 2>&1; then
    if pip3 --version >/dev/null 2>&1; then
        print_success "✅ pip3 command is working"
    else
        print_warning "⚠️  pip3 command exists but doesn't work properly"
    fi
else
    print_warning "⚠️  pip3 command not found"
fi

if command -v pip >/dev/null 2>&1; then
    if pip --version >/dev/null 2>&1; then
        print_success "✅ pip command is working"
    else
        print_warning "⚠️  pip command exists but doesn't work properly"
    fi
else
    print_warning "⚠️  pip command not found"
fi

echo ""
echo "📋 RECOMMENDATIONS:"
echo "1. Always use 'python3 -m pip' instead of 'pip' or 'pip3'"
echo "2. Use virtual environments: python3 -m venv venv"
echo "3. Activate venv: source venv/bin/activate"
echo "4. Install packages: python3 -m pip install package_name"
echo "5. Use pip manager: /usr/local/bin/pip_manager"
echo ""

echo "🔧 TROUBLESHOOTING:"
echo "- If pip still doesn't work, try: python3 -m ensurepip --upgrade"
echo "- Check PATH: echo \$PATH"
echo "- Check permissions: ls -la /usr/bin/pip*"
echo "- Reinstall: apt remove python3-pip && apt install python3-pip"
echo ""

echo "📊 CURRENT STATUS:"
echo "- Python3: $(python3 --version)"
echo "- python3 -m pip: $(python3 -m pip --version 2>/dev/null || echo 'NOT WORKING')"
echo "- pip3: $(command -v pip3 >/dev/null 2>&1 && pip3 --version 2>/dev/null || echo 'NOT FOUND')"
echo "- pip: $(command -v pip >/dev/null 2>&1 && pip --version 2>/dev/null || echo 'NOT FOUND')"
echo ""

if python3 -m pip --version >/dev/null 2>&1; then
    print_success "🎉 Pip fix completed successfully!"
    echo ""
    echo "✅ You can now use: python3 -m pip install package_name"
else
    print_error "❌ Pip fix failed. Manual intervention required."
    echo ""
    echo "Please check:"
    echo "1. Python3 installation: python3 --version"
    echo "2. Package installation: dpkg -l | grep python3-pip"
    echo "3. System PATH: echo \$PATH"
    echo "4. File permissions: ls -la /usr/bin/pip*"
fi

echo ""
print_success "Pip fix script completed!"
