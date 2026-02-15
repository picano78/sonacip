# SONACIP - Quick Reference Card (Produzione)

## 🎯 COMANDI ESSENZIALI

### Gestione Servizio
```bash
# Avviare
sudo systemctl start sonacip

# Fermare
sudo systemctl stop sonacip

# Riavviare
sudo systemctl restart sonacip

# Status
sudo systemctl status sonacip

# Logs live
sudo journalctl -u sonacip -f
```

### Gunicorn Diretto (Test)
```bash
cd /opt/sonacip
source venv/bin/activate
gunicorn --config gunicorn.conf.py wsgi:application
```

### Database
```bash
# Backup
sudo -u postgres pg_dump sonacip > backup_$(date +%Y%m%d).sql

# Restore
sudo -u postgres psql sonacip < backup.sql

# Inizializzazione
python3 init_db.py
```

### Nginx
```bash
# Test config
sudo nginx -t

# Reload
sudo systemctl reload nginx

# Restart
sudo systemctl restart nginx
```

---

## 📁 FILE IMPORTANTI

### Entrypoint
- **Production:** `wsgi:application` ✅
- Alternative: `wsgi:app`, `run:app`

### Configurazione
- `.env` - Variabili ambiente (NON committare!)
- `gunicorn.conf.py` - Config Gunicorn
- `deploy/sonacip.service` - Systemd service
- `deploy/sonacip.nginx.conf` - Nginx config

### Scripts
- `verify_production.py` - Verifica setup
- `init_db.py` - Inizializza database

---

## 🔑 VARIABILI .ENV CRITICHE

```bash
# OBBLIGATORIE
SECRET_KEY=<generare con: python3 -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=postgresql://user:pass@localhost:5432/sonacip
SUPERADMIN_EMAIL=admin@domain.com
SUPERADMIN_PASSWORD=<password forte>

# NGINX
USE_PROXYFIX=true
SESSION_COOKIE_SECURE=true
APP_DOMAIN=yourdomain.com

# OPZIONALI MA RACCOMANDATI
REDIS_URL=redis://localhost:6379/0
MAIL_SERVER=smtp.gmail.com
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

---

## 🚀 SETUP RAPIDO VPS

```bash
# 1. Preparazione
sudo apt update && sudo apt install -y python3-venv nginx postgresql redis-server certbot python3-certbot-nginx

# 2. Codice
sudo mkdir -p /opt/sonacip
sudo chown $USER:$USER /opt/sonacip
cd /opt/sonacip
git clone https://github.com/picano78/sonacip.git .

# 3. Virtual Environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Database PostgreSQL
sudo -u postgres psql
CREATE DATABASE sonacip;
CREATE USER sonacip_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE sonacip TO sonacip_user;
\q

# 5. Configurazione
cp .env.example .env
nano .env  # Configurare tutte le variabili
python3 init_db.py

# 6. Systemd
sudo cp deploy/sonacip.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sonacip
sudo systemctl start sonacip

# 7. Nginx + SSL
sudo cp deploy/sonacip.nginx.conf /etc/nginx/sites-available/sonacip
sudo nano /etc/nginx/sites-available/sonacip  # Sostituire dominio
sudo ln -s /etc/nginx/sites-available/sonacip /etc/nginx/sites-enabled/
sudo certbot --nginx -d yourdomain.com
sudo systemctl restart nginx

# 8. Verifica
sudo systemctl status sonacip
curl https://yourdomain.com
```

---

## 🔍 TROUBLESHOOTING RAPIDO

### Applicazione non si avvia
```bash
# Check logs
sudo journalctl -u sonacip -n 50

# Test manuale
cd /opt/sonacip
source venv/bin/activate
python3 -c "from run import app; print('OK')"
```

### 502 Bad Gateway
```bash
# Verifica Gunicorn
sudo systemctl status sonacip
curl http://127.0.0.1:8000/

# Verifica Nginx
sudo nginx -t
sudo systemctl status nginx
```

### Database error
```bash
# Verifica PostgreSQL
sudo systemctl status postgresql
sudo -u postgres psql -d sonacip -c "SELECT version();"

# Verifica connessione
grep DATABASE_URL /opt/sonacip/.env
```

### Permessi
```bash
sudo chown -R sonacip:sonacip /opt/sonacip
sudo chmod -R 755 /opt/sonacip
sudo chmod -R 775 /opt/sonacip/{uploads,logs,backups}
```

---

## 📊 VERIFICA STATUS

```bash
# Tutti i servizi
sudo systemctl status postgresql nginx redis-server sonacip

# Verifica completa
cd /opt/sonacip
python3 verify_production.py

# Logs applicazione
tail -f /opt/sonacip/logs/gunicorn_error.log

# Logs Nginx
tail -f /var/log/nginx/error.log
```

---

## ⚠️ SICUREZZA

### Checklist
- [ ] SECRET_KEY generato casualmente (64+ char)
- [ ] SUPERADMIN_PASSWORD cambiato dopo primo accesso
- [ ] PostgreSQL in produzione (no SQLite)
- [ ] Firewall abilitato (ufw) - porte 80, 443, 22
- [ ] SSL/HTTPS attivo (Let's Encrypt)
- [ ] .env NON committato in git
- [ ] Backup database regolare
- [ ] Sistema aggiornato

### Firewall (UFW)
```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## 📞 RIFERIMENTI

- **Guida completa:** `GUIDA_PRODUZIONE_VPS.md`
- **Analisi:** `ANALISI_PRODUZIONE.md`
- **Verifica:** `python3 verify_production.py`
- **Repository:** https://github.com/picano78/sonacip

---

**Creato:** 2026-02-15
