#!/usr/bin/env bash
set -euo pipefail

APP_USER="sonacip"
APP_DIR="/opt/sonacip"
ENV_FILE="/etc/sonacip.env"
SERVICE_FILE="/etc/systemd/system/sonacip.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "Eseguire come root." >&2
  exit 1
fi

if [[ -r /etc/os-release ]]; then
  . /etc/os-release
  if [[ "${ID:-}" != "ubuntu" ]]; then
    echo "OS non supportato: ${ID:-unknown}." >&2
    exit 1
  fi
fi

echo "[1/8] Installazione pacchetti di sistema..."
apt-get update -y
apt-get install -y --no-install-recommends \
  python3 \
  python3-venv \
  python3-pip \
  python3-dev \
  build-essential \
  libpq-dev \
  rsync \
  curl

echo "[2/8] Creazione utente e directory applicativa..."
if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd --system --create-home --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
fi
mkdir -p "$APP_DIR"


echo "[3/8] Copia file progetto in ${APP_DIR}..."
rsync -a --delete \
  --exclude '.git' \
  --exclude 'venv' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'logs' \
  --exclude 'uploads' \
  --exclude 'backups' \
  --exclude 'instance' \
  "$SCRIPT_DIR/" "$APP_DIR/"

mkdir -p "$APP_DIR/logs" "$APP_DIR/uploads" "$APP_DIR/backups"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"


echo "[4/8] Creazione venv e installazione dipendenze..."
if [[ ! -d "$APP_DIR/venv" ]]; then
  sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
fi
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"


echo "[5/8] Scrittura environment file..."
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


echo "[6/8] Installazione servizio systemd..."
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
ExecStart=$APP_DIR/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:8000 wsgi:app
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable sonacip.service


echo "[7/8] Installazione CLI di backup/restore..."
install -m 0755 "$APP_DIR/sonacip" /usr/local/bin/sonacip


echo "[8/8] Validazione sistema..."
if ! "$APP_DIR/venv/bin/python" "$APP_DIR/system_validation.py"; then
  echo "Validazione fallita. Installazione interrotta." >&2
  exit 1
fi

echo "Avvio servizio..."
systemctl restart sonacip.service
systemctl status sonacip.service --no-pager

echo "Installazione completata."
