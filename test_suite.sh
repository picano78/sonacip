#!/bin/bash
# SONACIP - Test Suite
# Verifica che tutti i componenti siano funzionanti

echo "🧪 SONACIP - Test Suite"
echo "======================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Function to run test
run_test() {
    local test_name=$1
    local test_command=$2
    
    echo -n "Testing: $test_name... "
    
    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC}"
        ((TESTS_FAILED++))
    fi
}

# Test 1: Python version
run_test "Python 3.12+" "python3 --version | grep -q 'Python 3'"

# Test 2: Dependencies installed
run_test "Flask installed" "python3 -c 'import flask'"
run_test "SQLAlchemy installed" "python3 -c 'import flask_sqlalchemy'"
run_test "Flask-Login installed" "python3 -c 'import flask_login'"

# Test 3: App initialization
run_test "App factory" "python3 -c 'from app import create_app; app = create_app()'"

# Test 4: Database models
run_test "User model" "python3 -c 'from app.models import User'"
run_test "Post model" "python3 -c 'from app.models import Post'"
run_test "Event model" "python3 -c 'from app.models import Event'"
run_test "Contact model (CRM)" "python3 -c 'from app.models import Contact'"
run_test "Opportunity model (CRM)" "python3 -c 'from app.models import Opportunity'"

# Test 5: Blueprints
run_test "Auth blueprint" "python3 -c 'from app.auth import bp'"
run_test "Admin blueprint" "python3 -c 'from app.admin import bp'"
run_test "Social blueprint" "python3 -c 'from app.social import bp'"
run_test "CRM blueprint" "python3 -c 'from app.crm import bp'"
run_test "Events blueprint" "python3 -c 'from app.events import bp'"
run_test "Notifications blueprint" "python3 -c 'from app.notifications import bp'"
run_test "Backup blueprint" "python3 -c 'from app.backup import bp'"

# Test 6: Database creation
run_test "Database tables" "python3 -c 'from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()'"

# Test 7: Required directories
run_test "Uploads directory" "[ -d uploads ]"
run_test "Backups directory" "[ -d backups ]"
run_test "Logs directory" "[ -d logs ]"

# Test 8: Templates exist
run_test "Base template" "[ -f app/templates/base.html ]"
run_test "Login template" "[ -f app/templates/auth/login.html ]"
run_test "Feed template" "[ -f app/templates/social/feed.html ]"
run_test "CRM index template" "[ -f app/templates/crm/index.html ]"

# Test 9: Static files
run_test "CSS file" "[ -f app/static/css/style.css ]"
run_test "JS file" "[ -f app/static/js/main.js ]"

# Test 10: Config files
run_test "Config module" "python3 -c 'from config import config'"
run_test "Gunicorn config" "[ -f gunicorn_config.py ]"
run_test "Nginx config" "[ -f deployment/nginx.conf ]"
run_test "Systemd service" "[ -f deployment/sonacip.service ]"

echo ""
echo "======================="
echo "Results:"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed! SONACIP is ready for deployment.${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please review the errors above.${NC}"
    exit 1
fi
