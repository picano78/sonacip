#!/bin/bash
# SONACIP Server Setup Script
# Esegui questo script sul server Ubuntu come root

set -e

echo "=========================================="
echo "SONACIP Server Setup"
echo "=========================================="
echo ""

# 1. Assicurati che la directory esista
mkdir -p /root/sonacip
mkdir -p /root/sonacip/uploads

cd /root/sonacip

# 2. Crea/sovrascrivi il file .env
cat > .env << 'EOF'
SUPERADMIN_EMAIL=picano78@gmail.com
SUPERADMIN_PASSWORD=simone78
DATABASE_URL=sqlite:////root/sonacip/uploads/sonacip.db
SQLALCHEMY_DATABASE_URI=sqlite:////root/sonacip/uploads/sonacip.db
SECRET_KEY=4f8a2b9c1d3e5f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2
FLASK_ENV=production
FLASK_DEBUG=False
PORT=8000
EOF

echo "[OK] .env creato con credenziali"

# 3. Crea il file wsgi.py se non esiste
cat > wsgi.py << 'EOF'
#!/usr/bin/env python
"""WSGI entrypoint for Gunicorn."""
import os
import sys

# Load .env BEFORE importing app
from dotenv import load_dotenv
basedir = os.path.abspath(os.path.dirname(__file__))
env_path = os.path.join(basedir, '.env')

if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
    print(f"[OK] Loaded .env from {env_path}", file=sys.stderr)

from app import create_app
app = create_app()
application = app
EOF

echo "[OK] wsgi.py creato"

# 4. Crea il service systemd
cat > /etc/systemd/system/sonacip.service << 'EOF'
[Unit]
Description=SONACIP Flask Application
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/root/sonacip
Environment=PATH=/root/sonacip/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=/root/sonacip
Environment=HOME=/root
ExecStart=/root/sonacip/venv/bin/gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=30
Restart=on-failure
RestartSec=10
StartLimitInterval=60s
StartLimitBurst=3

[Install]
WantedBy=multi-user.target
EOF

echo "[OK] Service systemd creato"

# 5. Libera porta 8000 se occupata
fuser -k 8000/tcp 2>/dev/null || true
sleep 2

echo "[OK] Porta 8000 liberata"

# 6. Ricarica systemd e avvia
systemctl daemon-reload
systemctl enable sonacip
systemctl restart sonacip

echo ""
echo "=========================================="
echo "Setup completato!"
echo "=========================================="
echo ""

# 7. Controlla lo stato
sleep 3
echo "--- Stato servizio ---"
systemctl status sonacip --no-pager

echo ""
echo "--- Ultimi log ---"
journalctl -u sonacip -n 20 --no-pager

echo ""
echo "Credenziali superadmin:"
echo "  Email: picano78@gmail.com"
echo "  Password: simone78"
echo ""
echo "Se ci sono errori, controlla: journalctl -u sonacip -f"
