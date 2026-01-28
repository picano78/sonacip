#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Questo installer è deprecato. Uso sonacip_install.sh..."
exec "$SCRIPT_DIR/sonacip_install.sh" "$@"
