#!/usr/bin/env bash
set -euo pipefail

APP_USER="sonacip"
APP_DIR="/opt/sonacip"
ENV_FILE="/opt/sonacip/.env"
SERVICE_FILE="/etc/systemd/system/sonacip.service"
NGINX_SITE_AVAILABLE="/etc/nginx/sites-available/sonacip"
NGINX_SITE_ENABLED="/etc/nginx/sites-enabled/sonacip"
LE_WEBROOT="/var/www/letsencrypt"
SONACIP_DOMAIN="${SONACIP_DOMAIN:-}"
SONACIP_LETSENCRYPT_EMAIL="${SONACIP_LETSENCRYPT_EMAIL:-}"
SONACIP_ENABLE_UFW="${SONACIP_ENABLE_UFW:-false}"
SONACIP_ENABLE_REDIS="${SONACIP_ENABLE_REDIS:-false}"
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
  certbot \
  python3-certbot \
  python3-certbot-nginx \
  openssl \
  logrotate \
  rsync \
  curl

if [[ "$SONACIP_ENABLE_REDIS" == "true" || "$SONACIP_ENABLE_REDIS" == "on" || "$SONACIP_ENABLE_REDIS" == "1" ]]; then
  apt-get install -y --no-install-recommends redis-server
  systemctl enable --now redis-server
fi

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
    printf '%s\n' "SESSION_COOKIE_SECURE=true"
    printf '%s\n' "SUPERADMIN_EMAIL=admin@example.com"
    printf '%s\n' "SUPERADMIN_PASSWORD=$ADMIN_PASSWORD"
  } >> "$ENV_FILE"
  chown "$APP_USER":"$APP_USER" "$ENV_FILE"
  echo "Credenziali iniziali admin:"
  echo "  email: admin@example.com"
  echo "  password: $ADMIN_PASSWORD"
fi

# Ensure Redis config is present if enabled
if [[ "$SONACIP_ENABLE_REDIS" == "true" || "$SONACIP_ENABLE_REDIS" == "on" || "$SONACIP_ENABLE_REDIS" == "1" ]]; then
  if ! grep -qE '^REDIS_URL=' "$ENV_FILE"; then
    printf '%s\n' "REDIS_URL=redis://localhost:6379/0" >> "$ENV_FILE"
  fi
  if ! grep -qE '^RATELIMIT_STORAGE_URI=' "$ENV_FILE"; then
    printf '%s\n' "RATELIMIT_STORAGE_URI=redis://localhost:6379/1" >> "$ENV_FILE"
  fi
  chown "$APP_USER":"$APP_USER" "$ENV_FILE"
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
install -m 0644 "$APP_DIR/deploy/sonacip-backup.service" /etc/systemd/system/sonacip-backup.service
install -m 0644 "$APP_DIR/deploy/sonacip-backup.timer" /etc/systemd/system/sonacip-backup.timer
install -m 0644 "$APP_DIR/deploy/sonacip-healthcheck.service" /etc/systemd/system/sonacip-healthcheck.service
install -m 0644 "$APP_DIR/deploy/sonacip-healthcheck.timer" /etc/systemd/system/sonacip-healthcheck.timer
install -m 0644 "$APP_DIR/deploy/logrotate_sonacip" /etc/logrotate.d/sonacip

systemctl daemon-reload
systemctl enable sonacip.service
systemctl enable --now sonacip-backup.timer
systemctl enable --now sonacip-healthcheck.timer


echo "[8/10] Configurazione Nginx (HTTP)..."
mkdir -p "$LE_WEBROOT/.well-known/acme-challenge"
chown -R root:root "$LE_WEBROOT"
chmod -R 0755 "$LE_WEBROOT"

# SSL strategy:
# - If SONACIP_DOMAIN + SONACIP_LETSENCRYPT_EMAIL are provided -> Let's Encrypt
# - else -> self-signed cert (still HTTPS, so cookies work)
SERVER_NAME="_"
if [[ -n "$SONACIP_DOMAIN" ]]; then
  SERVER_NAME="$SONACIP_DOMAIN"
fi

SSL_CERT="/etc/ssl/sonacip/fullchain.pem"
SSL_KEY="/etc/ssl/sonacip/privkey.pem"

if [[ -n "$SONACIP_DOMAIN" && -n "$SONACIP_LETSENCRYPT_EMAIL" ]]; then
  echo "Richiesta certificato Let's Encrypt per: $SONACIP_DOMAIN"
  SSL_CERT="/etc/letsencrypt/live/$SONACIP_DOMAIN/fullchain.pem"
  SSL_KEY="/etc/letsencrypt/live/$SONACIP_DOMAIN/privkey.pem"
  certbot certonly --webroot -w "$LE_WEBROOT" \
    -d "$SONACIP_DOMAIN" \
    --agree-tos --non-interactive --email "$SONACIP_LETSENCRYPT_EMAIL" \
    --keep-until-expiring
  systemctl enable certbot.timer || true
else
  echo "SSL: uso certificato self-signed (imposta SONACIP_DOMAIN + SONACIP_LETSENCRYPT_EMAIL per Let's Encrypt)."
  install -d -m 0755 /etc/ssl/sonacip
  if [[ ! -f "$SSL_CERT" || ! -f "$SSL_KEY" ]]; then
    CN="${SONACIP_DOMAIN:-localhost}"
    openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
      -subj "/CN=$CN" \
      -keyout "$SSL_KEY" -out "$SSL_CERT"
    chmod 0600 "$SSL_KEY"
  fi
fi

python3 "$APP_DIR/scripts/render_nginx_conf.py" \
  --template "$APP_DIR/deployment/nginx_site.conf.template" \
  --out "$NGINX_SITE_AVAILABLE" \
  --server-name "$SERVER_NAME" \
  --ssl-cert "$SSL_CERT" \
  --ssl-key "$SSL_KEY"

ln -sf "$NGINX_SITE_AVAILABLE" "$NGINX_SITE_ENABLED"
if [[ -e /etc/nginx/sites-enabled/default ]]; then
  rm -f /etc/nginx/sites-enabled/default
fi
nginx -t
systemctl enable nginx
systemctl restart nginx

if [[ "$SONACIP_ENABLE_UFW" == "true" || "$SONACIP_ENABLE_UFW" == "on" || "$SONACIP_ENABLE_UFW" == "1" ]]; then
  echo "Configurazione firewall UFW..."
  apt-get install -y --no-install-recommends ufw
  ufw allow OpenSSH
  ufw allow 'Nginx Full'
  ufw --force enable
fi


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
