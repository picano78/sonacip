#!/usr/bin/env python3
"""
SONACIP Auto-Deploy Script
Esegui: python3 auto_deploy.py
"""

import subprocess
import sys
import os

# Configurazione server
SERVER_HOST = "87.106.1.221"
SERVER_USER = "root"

def run_ssh_command(command):
    """Esegue comando SSH sul server"""
    ssh_cmd = f"ssh {SERVER_USER}@{SERVER_HOST} '{command}'"
    print(f"\n[EXEC] {ssh_cmd}\n")
    result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(f"[STDERR] {result.stderr}")
    return result.returncode == 0

def main():
    print("=" * 60)
    print("SONACIP Auto-Deploy")
    print("=" * 60)
    print(f"Server: {SERVER_HOST}")
    print("")
    
    # Verifica connessione SSH
    print("[1] Verifica connessione SSH...")
    test = subprocess.run(f"ssh -o ConnectTimeout=5 {SERVER_USER}@{SERVER_HOST} 'echo OK'", 
                         shell=True, capture_output=True, text=True)
    if "OK" not in test.stdout:
        print("[ERRORE] Connessione SSH fallita!")
        print("Assicurati di avere:")
        print(f"  1. Accesso SSH a {SERVER_USER}@{SERVER_HOST}")
        print("  2. Chiave SSH configurata o password pronta")
        print("")
        print("Prova manualmente:")
        print(f"  ssh {SERVER_USER}@{SERVER_HOST}")
        sys.exit(1)
    
    print("[OK] Connessione SSH verificata\n")
    
    # Comandi da eseguire sul server
    commands = """
cd /root/sonacip && \
echo 'SUPERADMIN_EMAIL=picano78@gmail.com' > .env && \
echo 'SUPERADMIN_PASSWORD=simone78' >> .env && \
echo 'DATABASE_URL=sqlite:////root/sonacip/uploads/sonacip.db' >> .env && \
echo 'SQLALCHEMY_DATABASE_URI=sqlite:////root/sonacip/uploads/sonacip.db' >> .env && \
mkdir -p uploads && \
fuser -k 8000/tcp 2>/dev/null; sleep 2; \
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
systemctl daemon-reload && \
systemctl stop sonacip 2>/dev/null; pkill -f gunicorn 2>/dev/null; sleep 2; \
systemctl start sonacip && \
sleep 5 && \
echo '=== STATO SERVIZIO ===' && \
systemctl status sonacip --no-pager && \
echo '' && \
echo '=== LOG ===' && \
journalctl -u sonacip -n 30 --no-pager && \
echo '' && \
echo '=== PORTA ===' && \
ss -tlnp | grep 8000 || netstat -tlnp | grep 8000 || echo 'Porta 8000 non trovata'
"""
    
    print("[2] Esecuzione comandi sul server...")
    print("-" * 60)
    
    success = run_ssh_command(commands)
    
    print("-" * 60)
    if success:
        print("\n[SUCCESS] Deploy completato!")
        print(f"URL: http://{SERVER_HOST}:8000")
        print("Login: picano78@gmail.com / simone78")
    else:
        print("\n[WARNING] Completato con possibili errori.")
        print("Controlla i log sopra.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
