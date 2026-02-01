#!/usr/bin/env bash
set -euo pipefail

APP_USER="sonacip"
APP_DIR="/opt/sonacip"
ENV_FILE="/opt/sonacip/.env"
SERVICE_FILE="/etc/systemd/system/sonacip.service"
NGINX_SITE_AVAILABLE="/etc/nginx/sites-available/sonacip"
NGINX_SITE_ENABLED="/etc/nginx/sites-enabled/sonacip"
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
  nginx \
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
  SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  ADMIN_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(16))')"
  install -m 0600 /dev/null "$ENV_FILE"
  {
    printf '%s\n' "APP_ENV=production"
    printf '%s\n' "FLASK_ENV=production"
    printf '%s\n' "SECRET_KEY=$SECRET_KEY"
    printf '%s\n' "USE_PROXYFIX=true"
    printf '%s\n' "SUPERADMIN_EMAIL=admin@example.com"
    printf '%s\n' "SUPERADMIN_PASSWORD=$ADMIN_PASSWORD"
  } >> "$ENV_FILE"
  chown "$APP_USER":"$APP_USER" "$ENV_FILE"
  echo "Credenziali iniziali admin:"
  echo "  email: admin@example.com"
  echo "  password: $ADMIN_PASSWORD"
fi


echo "[6/10] Migrazioni DB + seed iniziale..."
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a
sudo -u "$APP_USER" "$APP_DIR/venv/bin/python" "$APP_DIR/manage.py" db upgrade
sudo -u "$APP_USER" "$APP_DIR/venv/bin/python" "$APP_DIR/manage.py" seed


echo "[7/10] Installazione servizio systemd..."
install -m 0644 "$APP_DIR/deploy/sonacip.service" "$SERVICE_FILE"

systemctl daemon-reload
systemctl enable sonacip.service


echo "[8/10] Configurazione Nginx (HTTP)..."
install -m 0644 "$APP_DIR/deployment/nginx.conf" "$NGINX_SITE_AVAILABLE"
ln -sf "$NGINX_SITE_AVAILABLE" "$NGINX_SITE_ENABLED"
if [[ -e /etc/nginx/sites-enabled/default ]]; then
  rm -f /etc/nginx/sites-enabled/default
fi
nginx -t
systemctl enable nginx
systemctl restart nginx


echo "[9/10] Installazione CLI di backup/restore..."
install -m 0755 "$APP_DIR/sonacip" /usr/local/bin/sonacip


echo "[10/10] Validazione sistema..."
if ! "$APP_DIR/venv/bin/python" "$APP_DIR/system_validation.py"; then
  echo "Validazione fallita. Installazione interrotta." >&2
  exit 1
fi

echo "Avvio servizio..."
systemctl restart sonacip.service
systemctl status sonacip.service --no-pager

echo "Installazione completata."
