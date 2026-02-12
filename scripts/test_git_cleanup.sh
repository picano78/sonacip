#!/bin/bash
# Test suite per git_cleanup.sh
# Test suite for git_cleanup.sh

set -e

# Colori
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLEANUP_SCRIPT="$SCRIPT_DIR/git_cleanup.sh"
TEST_COUNT=0
PASS_COUNT=0
FAIL_COUNT=0

echo "🧪 Test Suite per Git Cleanup Script"
echo "===================================="
echo ""

# Funzione per eseguire un test
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    TEST_COUNT=$((TEST_COUNT + 1))
    echo -e "${YELLOW}Test $TEST_COUNT: $test_name${NC}"
    
    if eval "$test_command"; then
        echo -e "${GREEN}✅ PASSED${NC}"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo -e "${RED}❌ FAILED${NC}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
    echo ""
}

# Test 1: Script esiste ed è eseguibile
run_test "Script esiste ed è eseguibile" \
    "[ -x '$CLEANUP_SCRIPT' ]"

# Test 2: Script ha shebang corretto
run_test "Script ha shebang bash" \
    "head -n 1 '$CLEANUP_SCRIPT' | grep -q '#!/bin/bash'"

# Test 3: Script fallisce fuori da repository Git
run_test "Script rileva quando non è in repo Git" \
    "cd /tmp && OUTPUT=\$('$CLEANUP_SCRIPT' 2>&1); EXITCODE=\$?; echo \"\$OUTPUT\" | grep -q 'Error.*repository' && [ \$EXITCODE -eq 1 ]"

# Test 4: Script funziona da root del repository
run_test "Script funziona da root repository" \
    "cd '$SCRIPT_DIR/..' && '$CLEANUP_SCRIPT' > /dev/null 2>&1"

# Test 5: Script funziona da sottodirectory
run_test "Script funziona da sottodirectory" \
    "cd '$SCRIPT_DIR' && '$CLEANUP_SCRIPT' > /dev/null 2>&1"

# Test 6: Script ha messaggi bilingue
run_test "Script ha messaggi in italiano e inglese" \
    "grep -q 'Pulizia Repository' '$CLEANUP_SCRIPT' && grep -q 'Repository Cleanup' '$CLEANUP_SCRIPT'"

# Test 7: Script esegue git gc
run_test "Script contiene git gc --prune=now" \
    "grep -q 'git gc --prune=now' '$CLEANUP_SCRIPT'"

# Test 8: Script verifica integrità con fsck
run_test "Script verifica integrità repository" \
    "grep -q 'git fsck --full' '$CLEANUP_SCRIPT'"

# Test 9: Documentazione esiste
run_test "Documentazione GIT_MAINTENANCE.md esiste" \
    "[ -f '$SCRIPT_DIR/../GIT_MAINTENANCE.md' ]"

# Test 10: README menziona manutenzione
run_test "README menziona manutenzione repository" \
    "grep -q 'Manutenzione Repository' '$SCRIPT_DIR/../README.md'"

# Riepilogo
echo "======================================"
echo "Riepilogo Test / Test Summary"
echo "======================================"
echo -e "Totale test: $TEST_COUNT"
echo -e "${GREEN}Passati: $PASS_COUNT${NC}"
if [ $FAIL_COUNT -gt 0 ]; then
    echo -e "${RED}Falliti: $FAIL_COUNT${NC}"
else
    echo -e "Falliti: $FAIL_COUNT"
fi
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}🎉 Tutti i test sono passati!${NC}"
    exit 0
else
    echo -e "${RED}⚠️  Alcuni test sono falliti${NC}"
    exit 1
fi
