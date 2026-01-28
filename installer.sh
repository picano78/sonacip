#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${INSTALL_DIR:-/opt/sonacip}"

echo "[+] Installing system dependencies..."
sudo apt-get update -y
sudo apt-get install -y \
  python3 \
  python3-venv \
  python3-dev \
  build-essential \
  libpq-dev \
  rsync \
  curl

echo "[+] Copying application files to ${INSTALL_DIR}..."
sudo mkdir -p "$INSTALL_DIR"
sudo rsync -a --delete \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'venv' \
  --exclude 'logs' \
  --exclude 'instance' \
  --exclude 'uploads' \
  --exclude 'backups' \
  "$SCRIPT_DIR/" "$INSTALL_DIR/"

echo "[+] Creating virtual environment..."
sudo python3 -m venv "$INSTALL_DIR/venv"

echo "[+] Installing Python dependencies..."
sudo "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
sudo "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

echo "[+] Testing Gunicorn boot..."
sudo mkdir -p "$INSTALL_DIR/logs"
SECRET_KEY_VALUE="${SECRET_KEY:-$("$INSTALL_DIR/venv/bin/python" - <<'PY'
import os
print(os.urandom(32).hex())
PY
)}"

GUNICORN_LOG="$INSTALL_DIR/logs/installer_gunicorn.log"
GUNICORN_PID_FILE="$INSTALL_DIR/.gunicorn.pid"

sudo bash -c "cd '$INSTALL_DIR' && \
  export SECRET_KEY='$SECRET_KEY_VALUE' && \
  export APP_ENV='production' && \
  export FLASK_ENV='production' && \
  '$INSTALL_DIR/venv/bin/gunicorn' --bind 127.0.0.1:8000 wsgi:app \
    --workers 1 --timeout 30 --log-level info \
    --access-logfile '$GUNICORN_LOG' --error-logfile '$GUNICORN_LOG' & \
  echo \$! > '$GUNICORN_PID_FILE'"

sleep 4

if ! sudo kill -0 "$(cat "$INSTALL_DIR/.gunicorn.pid")" 2>/dev/null; then
  echo "[!] Gunicorn failed to start. Output:" >&2
  sudo cat "$GUNICORN_LOG" >&2 || true
  exit 1
fi

echo "[+] Gunicorn started successfully. Shutting down test process..."
sudo kill "$(cat "$INSTALL_DIR/.gunicorn.pid")"
sleep 1

echo "[+] Installer completed successfully."
