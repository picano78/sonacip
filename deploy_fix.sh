#!/bin/bash
# SONACIP Complete Deploy Fix
# Esegui come root: bash deploy_fix.sh

set -e

echo "=========================================="
echo "SONACIP Deploy Fix - Avvio..."
echo "=========================================="

# 1. Vai alla directory
cd /root/sonacip || { echo "ERRORE: Directory /root/sonacip non trovata"; exit 1; }

# 2. Crea/correggi .env con valori corretti
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

echo "[OK] .env creato:"
cat .env

# 3. Assicurati che uploads directory esista
mkdir -p /root/sonacip/uploads

# 4. Correggi run.py se necessario
if [ ! -f run.py ]; then
cat > run.py << 'EOF'
#!/usr/bin/env python
"""Production entrypoint for SONACIP."""
import os
import sys

# CRITICAL: Load .env BEFORE importing app
from dotenv import load_dotenv
basedir = os.path.abspath(os.path.dirname(__file__))
env_path = os.path.join(basedir, '.env')

if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
    print(f"[OK] Loaded .env from {env_path}", file=sys.stderr)

from app import create_app
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
EOF
    echo "[OK] run.py creato"
fi

# 5. Libera porta 8000
echo "[INFO] Liberando porta 8000..."
fuser -k 8000/tcp 2>/dev/null || true
sleep 2

# 6. Crea/correggi service systemd
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
ExecStart=/root/sonacip/venv/bin/gunicorn -w 2 -b 0.0.0.0:8000 run:app
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

echo "[OK] sonacip.service creato"

# 7. Ricarica systemd
echo "[INFO] Ricaricando systemd..."
systemctl daemon-reload
systemctl enable sonacip

# 8. Ferma eventuali processi precedenti
systemctl stop sonacip 2>/dev/null || true
pkill -f gunicorn 2>/dev/null || true
sleep 2

# 9. Avvia servizio
echo "[INFO] Avviando sonacip..."
systemctl start sonacip

# 10. Attendi avvio
sleep 5

echo ""
echo "=========================================="
echo "VERIFICA STATO SERVIZIO"
echo "=========================================="

# 11. Mostra stato
systemctl status sonacip --no-pager || true

echo ""
echo "=========================================="
echo "ULTIMI LOG (30 righe)"
echo "=========================================="
journalctl -u sonacip -n 30 --no-pager || true

echo ""
echo "=========================================="
echo "VERIFICA PORTA 8000"
echo "=========================================="
netstat -tlnp | grep 8000 || ss -tlnp | grep 8000 || echo "Porta 8000 non in ascolto"

echo ""
echo "=========================================="
echo "RIEPILOGO"
echo "=========================================="
echo "Superadmin: picano78@gmail.com / simone78"
echo "Database: sqlite:////root/sonacip/uploads/sonacip.db"
echo "URL: http://87.106.1.221:8000"
echo ""

# 12. Verifica finale
if systemctl is-active --quiet sonacip; then
    echo "[SUCCESS] Servizio SONACIP ATTIVO!"
    exit 0
else
    echo "[ERRORE] Servizio NON attivo. Controlla i log sopra."
    exit 1
fi
