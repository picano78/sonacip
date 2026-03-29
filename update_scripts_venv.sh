#!/bin/bash

# SONACIP Scripts Update for Virtual Environment
# Updates all scripts to use venv consistently

set -e

echo "=== UPDATING SCRIPTS FOR VENV USAGE ==="

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

# Function to update script for venv usage
update_script_for_venv() {
    local script_path="$1"
    local script_name=$(basename "$script_path")
    
    if [ -f "$script_path" ]; then
        print_status "Updating $script_name for venv usage..."
        
        # Backup original
        cp "$script_path" "$script_path.backup.$(date +%s)"
        
        # Add venv activation at the beginning of the script
        if ! grep -q "source venv/bin/activate" "$script_path"; then
            # Find the first non-comment, non-shebang line and add venv activation
            sed -i '/^#!/!b; /^#/!b; a\
cd /opt/sonacip\
source venv/bin/activate\
export PYTHONPATH="/opt/sonacip:$PYTHONPATH"
' "$script_path"
        fi
        
        # Replace pip calls with python -m pip
        sed -i 's|/opt/sonacip/venv/bin/pip|python -m pip|g' "$script_path"
        sed -i 's|pip install|python -m pip install|g' "$script_path"
        sed -i 's|pip list|python -m pip list|g' "$script_path"
        sed -i 's|pip show|python -m pip show|g' "$script_path"
        sed -i 's|pip uninstall|python -m pip uninstall|g' "$script_path"
        sed -i 's|/usr/bin/pip3|python -m pip|g' "$script_path"
        sed -i 's|/usr/local/bin/pip|python -m pip|g' "$script_path"
        
        # Remove dangerous flags
        sed -i 's|--break-system-packages||g' "$script_path"
        sed -i 's|--force-reinstall||g' "$script_path"
        
        # Replace python calls with python3 if needed
        sed -i 's|python3 |python3 -m |g' "$script_path"
        
        # Add venv check
        if ! grep -q "check_venv" "$script_path"; then
            sed -i '/^#!/a\
\
# Check virtual environment\
check_venv() {\
    if [ ! -d "/opt/sonacip/venv" ]; then\
        echo "ERROR: Virtual environment not found. Please run fix_pip_environment.sh first."\
        exit 1\
    fi\
    if [ "$VIRTUAL_ENV" != "/opt/sonacip/venv" ]; then\
        cd /opt/sonacip\
        source venv/bin/activate\
    fi\
}\
' "$script_path"
        fi
        
        print_success "Updated: $script_name"
    else
        print_error "Script not found: $script_path"
    fi
}

# Update all shell scripts
print_status "Scanning for shell scripts to update..."

# Find all .sh files in the project
find "$PROJECT_DIR" -name "*.sh" -type f | while read -r script; do
    # Skip the update script itself
    if [[ "$script" != *"update_scripts_venv.sh" ]]; then
        update_script_for_venv "$script"
    fi
done

# Create a master venv activation function
print_status "Creating master venv activation function..."

cat > "$PROJECT_DIR/venv_manager.sh" << 'EOF'
#!/bin/bash

# SONACIP Virtual Environment Manager
# Master script for venv management

PROJECT_DIR="/opt/sonacip"
VENV_DIR="$PROJECT_DIR/venv"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${YELLOW}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "${BLUE}=== $1 ===${NC}"; }

# Function to activate venv
activate_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        print_error "Virtual environment not found at $VENV_DIR"
        print_status "Please run: /opt/sonacip/fix_pip_environment.sh"
        return 1
    fi
    
    cd "$PROJECT_DIR"
    source venv/bin/activate
    
    if [ "$VIRTUAL_ENV" = "$VENV_DIR" ]; then
        print_success "Virtual environment activated: $VIRTUAL_ENV"
        export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
        return 0
    else
        print_error "Failed to activate virtual environment"
        return 1
    fi
}

# Function to check venv status
check_venv_status() {
    print_header "Virtual Environment Status"
    
    if [ -d "$VENV_DIR" ]; then
        echo "✅ Virtual environment exists: $VENV_DIR"
        
        if [ "$VIRTUAL_ENV" = "$VENV_DIR" ]; then
            echo "✅ Virtual environment is active"
            echo "📦 Python: $(which python)"
            echo "📦 Pip: $(which pip)"
            echo "📦 Pip version: $(pip --version)"
        else
            echo "⚠️  Virtual environment is not active"
            echo "🔄 Current VIRTUAL_ENV: $VIRTUAL_ENV"
        fi
    else
        echo "❌ Virtual environment not found"
    fi
}

# Function to run command in venv
run_in_venv() {
    local cmd="$1"
    print_status "Running command in virtual environment: $cmd"
    
    if activate_venv; then
        eval "$cmd"
    else
        print_error "Failed to activate virtual environment"
        return 1
    fi
}

# Main menu
case "$1" in
    "activate")
        activate_venv
        ;;
    "status")
        check_venv_status
        ;;
    "run")
        if [ -z "$2" ]; then
            print_error "Please provide a command to run"
            echo "Usage: $0 run '<command>'"
            exit 1
        fi
        run_in_venv "${@:2}"
        ;;
    "pip")
        if [ -z "$2" ]; then
            print_error "Please provide pip command"
            echo "Usage: $0 pip <pip-command>"
            exit 1
        fi
        run_in_venv "python -m pip ${@:2}"
        ;;
    "python")
        if [ -z "$2" ]; then
            print_error "Please provide python command"
            echo "Usage: $0 python <python-command>"
            exit 1
        fi
        run_in_venv "python ${@:2}"
        ;;
    *)
        echo "SONACIP Virtual Environment Manager"
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  activate    - Activate virtual environment"
        echo "  status      - Show venv status"
        echo "  run         - Run command in venv"
        echo "  pip         - Run pip command in venv"
        echo "  python      - Run python command in venv"
        echo ""
        echo "Examples:"
        echo "  $0 activate"
        echo "  $0 status"
        echo "  $0 pip install flask"
        echo "  $0 pip list"
        echo "  $0 python --version"
        echo "  $0 run 'python app.py'"
        exit 0
        ;;
esac
EOF

chmod +x "$PROJECT_DIR/venv_manager.sh"
print_success "Venv manager created: /opt/sonacip/venv_manager.sh"

# Create a wrapper for common operations
print_status "Creating operation wrappers..."

cat > "$PROJECT_DIR/sonacip_ops.sh" << 'EOF'
#!/bin/bash

# SONACIP Operations Wrapper
# Common operations with venv support

PROJECT_DIR="/opt/sonacip"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${YELLOW}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "${BLUE}=== $1 ===${NC}"; }

# Ensure venv is active
ensure_venv() {
    if [ ! -d "/opt/sonacip/venv" ]; then
        print_error "Virtual environment not found"
        print_status "Please run: /opt/sonacip/fix_pip_environment.sh"
        exit 1
    fi
    
    if [ "$VIRTUAL_ENV" != "/opt/sonacip/venv" ]; then
        cd /opt/sonacip
        source venv/bin/activate
        export PYTHONPATH="/opt/sonacip:$PYTHONPATH"
    fi
}

# Main operations
case "$1" in
    "install")
        print_header "Installing Dependencies"
        ensure_venv
        if [ -f "requirements.txt" ]; then
            python -m pip install -r requirements.txt
        else
            print_error "requirements.txt not found"
        fi
        ;;
    "update")
        print_header "Updating Dependencies"
        ensure_venv
        python -m pip install --upgrade pip
        if [ -f "requirements.txt" ]; then
            python -m pip install -r requirements.txt --upgrade
        fi
        ;;
    "check")
        print_header "Checking Dependencies"
        ensure_venv
        python -m pip list
        ;;
    "test")
        print_header "Testing Application"
        ensure_venv
        python -c "from run import app; print('✅ Application import successful')"
        ;;
    "shell")
        print_header "Activating Shell"
        ensure_venv
        print_success "Virtual environment activated. Type 'exit' to deactivate."
        bash
        ;;
    *)
        echo "SONACIP Operations Wrapper"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  install  - Install dependencies from requirements.txt"
        echo "  update   - Update dependencies"
        echo "  check    - Check installed dependencies"
        echo "  test     - Test application import"
        echo "  shell    - Activate shell with venv"
        echo ""
        echo "Examples:"
        echo "  $0 install"
        echo "  $0 update"
        echo "  $0 check"
        echo "  $0 test"
        exit 0
        ;;
esac
EOF

chmod +x "$PROJECT_DIR/sonacip_ops.sh"
print_success "Operations wrapper created: /opt/sonacip/sonacip_ops.sh"

# Summary
print_header "SCRIPTS UPDATE SUMMARY"

echo ""
echo "✅ Scripts updated to use virtual environment"
echo "✅ Dangerous flags removed (--break-system-packages)"
echo "✅ All pip calls converted to 'python -m pip'"
echo "✅ Venv activation added to all scripts"
echo "✅ Management tools created"
echo ""

echo "📋 New Management Tools:"
echo "   🐍 Venv Manager: /opt/sonacip/venv_manager.sh"
echo "   🔧 Operations: /opt/sonacip/sonacip_ops.sh"
echo "   📦 Pip Manager: /opt/sonacip/pip_manager.sh"
echo "   📋 Requirements: /opt/sonacip/install_requirements.sh"
echo ""

echo "🛡️ Safe Usage Examples:"
echo "   Activate venv: /opt/sonacip/venv_manager.sh activate"
echo "   Install package: /opt/sonacip/venv_manager.sh pip install flask"
echo "   Install requirements: /opt/sonacip/sonacip_ops.sh install"
echo "   Check status: /opt/sonacip/venv_manager.sh status"
echo "   Test app: /opt/sonacip/sonacip_ops.sh test"
echo ""

print_success "🚀 All scripts updated for virtual environment usage!"
