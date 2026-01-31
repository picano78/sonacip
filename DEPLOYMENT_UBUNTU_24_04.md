## Deployment SONACIP — Ubuntu 24.04 (VPS)

Obiettivo: **clone → install → `gunicorn wsgi:app`** con deployment statico (**systemd + nginx**) e senza “auto-fix” a runtime.

### Prerequisiti di sistema

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx
```

### Installazione applicazione

Scegli una directory (es. `/opt/sonacip`) e un utente dedicato:

```bash
sudo useradd --system --create-home --home-dir /opt/sonacip --shell /usr/sbin/nologin sonacip || true
sudo mkdir -p /opt/sonacip
sudo chown -R sonacip:sonacip /opt/sonacip
```

Copia il repository in `/opt/sonacip` (es. via `git clone` oppure unzip) e crea il venv:

```bash
cd /opt/sonacip
sudo -u sonacip python3 -m venv venv
sudo -u sonacip ./venv/bin/pip install --upgrade pip
sudo -u sonacip ./venv/bin/pip install -r requirements.txt
```

### Configurazione ambiente (OBBLIGATORIA)

Crea `/opt/sonacip/.env` (deve contenere almeno `SECRET_KEY`).

```bash
sudo -u sonacip cp -n .env.example .env
sudo -u sonacip nano .env
```

Note:
- **`SECRET_KEY` è obbligatoria** (l’app non avvia senza).
- `DATABASE_URL` è opzionale: se non impostata, si usa SQLite locale (`./sonacip.db`).

### Inizializzazione database (una sola volta)

```bash
cd /opt/sonacip
sudo -u sonacip ./venv/bin/python init_db.py
```

### Systemd (Gunicorn)

Installa l’unit:

```bash
sudo cp deploy/sonacip.service /etc/systemd/system/sonacip.service
sudo systemctl daemon-reload
sudo systemctl enable --now sonacip.service
sudo systemctl status sonacip.service --no-pager
```

Verifica che l’entrypoint sia **solo**:

```bash
ExecStart=/opt/sonacip/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:8000 wsgi:app
```

### Nginx (reverse proxy)

Copia la configurazione e abilitala:

```bash
sudo cp deployment/nginx.conf /etc/nginx/sites-available/sonacip
sudo ln -sf /etc/nginx/sites-available/sonacip /etc/nginx/sites-enabled/sonacip
sudo nginx -t
sudo systemctl reload nginx
```

Aggiorna `server_name` in `deployment/nginx.conf` con il tuo dominio.

### Smoke test (manuale)

```bash
cd /opt/sonacip
sudo -u sonacip ./venv/bin/python -c "import wsgi; print('wsgi import ok')"
sudo -u sonacip ./venv/bin/gunicorn --version
```

