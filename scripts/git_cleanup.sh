#!/bin/bash
# Script per la pulizia del repository Git da rami sospesi e oggetti non raggiungibili
# Script for cleaning up Git repository from dangling branches and unreachable objects

set -e

echo "🧹 Pulizia Repository Git / Git Repository Cleanup"
echo "=================================================="
echo ""

# Colori per l'output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Verifica che siamo in un repository Git e vai alla root
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}❌ Errore: Non siamo in un repository Git${NC}"
    echo -e "${RED}❌ Error: Not in a Git repository${NC}"
    exit 1
fi

# Vai alla root del repository
GIT_ROOT=$(git rev-parse --show-toplevel)
cd "$GIT_ROOT" || exit 1

echo -e "${YELLOW}📊 Controllo dello stato del repository...${NC}"
echo ""

# Mostra i rami locali
echo "🌿 Rami locali / Local branches:"
git branch -v
echo ""

# Mostra i rami remoti
echo "🌐 Rami remoti / Remote branches:"
git branch -r
echo ""

# Verifica rami merged che possono essere eliminati (escluso main/master)
echo -e "${YELLOW}🔍 Controllo rami già merged (escluso main/master)...${NC}"
MERGED_BRANCHES=$(git branch --merged | grep -v '\*' | grep -v 'main' | grep -v 'master' | grep -v 'copilot/' || true)
if [ -z "$MERGED_BRANCHES" ]; then
    echo -e "${GREEN}✅ Nessun ramo merged da pulire${NC}"
else
    echo -e "${YELLOW}Rami merged trovati:${NC}"
    echo "$MERGED_BRANCHES"
fi
echo ""

# Controlla oggetti dangling
echo -e "${YELLOW}🔍 Controllo oggetti sospesi / Checking for dangling objects...${NC}"
DANGLING=$(git fsck --dangling 2>&1 || true)
if [ -z "$DANGLING" ]; then
    echo -e "${GREEN}✅ Nessun oggetto sospeso trovato${NC}"
else
    echo -e "${YELLOW}Oggetti sospesi trovati:${NC}"
    echo "$DANGLING" | head -20
    if [ $(echo "$DANGLING" | wc -l) -gt 20 ]; then
        echo "... (e altri)"
    fi
fi
echo ""

# Esegui garbage collection
echo -e "${YELLOW}🗑️  Esecuzione garbage collection...${NC}"
git gc --prune=now
echo -e "${GREEN}✅ Garbage collection completata${NC}"
echo ""

# Verifica integrità finale
echo -e "${YELLOW}🔒 Verifica integrità del repository...${NC}"
if git fsck --full > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Repository integro e pulito${NC}"
else
    echo -e "${RED}⚠️  Attenzione: Problemi di integrità rilevati${NC}"
    git fsck --full
fi
echo ""

# Statistiche finali
echo "📊 Statistiche repository / Repository statistics:"
git count-objects -v
echo ""

echo -e "${GREEN}✅ Pulizia completata!${NC}"
echo ""
echo "Suggerimenti:"
echo "  - Usa 'git remote prune origin' per rimuovere riferimenti a rami remoti eliminati"
echo "  - Usa 'git branch -d <nome-ramo>' per eliminare rami locali non più necessari"
