#!/usr/bin/env bash
set -euo pipefail

APP_USER="sonacip"
APP_DIR="/opt/sonacip"
ENV_FILE="/etc/sonacip.env"
SERVICE_FILE="/etc/systemd/system/sonacip.service"

if [[ $EUID -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

echo "[1/7] Installing system packages..."
apt-get update -y
apt-get install -y --no-install-recommends \
  python3 \
  python3-venv \
  python3-pip \
  python3-dev \
  build-essential \
  libpq-dev \
  rsync

echo "[2/7] Creating service user and app directory..."
if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd --system --create-home --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
fi
mkdir -p "$APP_DIR"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

echo "[3/7] Copying project files..."
rsync -a --delete \
  --exclude '.git' \
  --exclude 'venv' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'logs' \
  --exclude 'uploads' \
  ./ "$APP_DIR"/

mkdir -p "$APP_DIR/logs" "$APP_DIR/uploads"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

echo "[4/7] Creating virtual environment and installing dependencies..."
sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "[5/7] Writing environment file..."
if [[ ! -f "$ENV_FILE" ]]; then
  SECRET_KEY=$(python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
  )
  cat > "$ENV_FILE" <<EOF
APP_ENV=production
FLASK_ENV=production
SECRET_KEY=$SECRET_KEY
EOF
  chmod 600 "$ENV_FILE"
fi


echo "[6/7] Creating systemd service..."
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=SONACIP Flask Application
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$APP_DIR/venv/bin/gunicorn wsgi:app -b 0.0.0.0:8000 --workers 3 --threads 2 --access-logfile - --error-logfile -
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable sonacip.service


echo "[7/7] Starting service..."
systemctl restart sonacip.service
systemctl status sonacip.service --no-pager

echo "Install complete. App should be available on port 8000."
