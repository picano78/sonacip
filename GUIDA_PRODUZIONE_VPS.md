# SONACIP - Guida Completa per Deployment in Produzione

## 📋 Indice

1. [Panoramica](#panoramica)
2. [Prerequisiti](#prerequisiti)
3. [Architettura dell'Applicazione](#architettura-dellapplicazione)
4. [Installazione Step-by-Step](#installazione-step-by-step)
5. [Configurazione Nginx](#configurazione-nginx)
6. [Configurazione Systemd](#configurazione-systemd)
7. [Comandi di Gestione](#comandi-di-gestione)
8. [Troubleshooting](#troubleshooting)

---

## 🎯 Panoramica

SONACIP è una piattaforma Flask completa per la gestione di società sportive. Questa guida copre il deployment completo su Ubuntu VPS con:

- **Flask 3.1.0** - Framework web Python
- **Gunicorn 23.0.0** - WSGI application server
- **Nginx** - Reverse proxy e web server
- **PostgreSQL** - Database di produzione (raccomandato)
- **Systemd** - Process manager

---

## ✅ Prerequisiti

### Server Requirements

- **OS**: Ubuntu 20.04/22.04/24.04 LTS
- **RAM**: Minimo 2GB (raccomandato 4GB+)
- **Storage**: Minimo 10GB
- **Python**: 3.10+ (preinstallato su Ubuntu 22.04+)

### Pacchetti di Sistema

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv python3-dev
sudo apt install -y nginx postgresql postgresql-contrib
sudo apt install -y build-essential libpq-dev
sudo apt install -y redis-server  # Opzionale, per caching e Celery
sudo apt install -y certbot python3-certbot-nginx  # Per SSL/HTTPS
```

---

## 🏗️ Architettura dell'Applicazione

### Struttura Entrypoints

L'applicazione SONACIP utilizza una struttura chiara e ben definita:

```
sonacip/
├── app/                    # Package principale applicazione
│   ├── __init__.py         # Application factory (create_app)
│   ├── core/              # Configurazione core
│   │   └── config.py      # Config classes (Development/Production)
│   ├── auth/              # Modulo autenticazione
│   ├── admin/             # Pannello amministrazione
│   └── [altri moduli...]
├── run.py                 # Legacy entrypoint (compatibilità)
├── wsgi.py                # ✅ PRODUCTION ENTRYPOINT
├── gunicorn.conf.py       # ✅ Configurazione Gunicorn (SINGLE SOURCE OF TRUTH)
├── gunicorn_config.py     # Wrapper compatibilità (importa da gunicorn.conf.py)
├── requirements.txt       # ✅ Dipendenze Python
├── .env.example           # Template variabili ambiente
└── deploy/                # File di deployment
    ├── sonacip.service    # ✅ Systemd service file
    └── sonacip.nginx.conf # ✅ Nginx configuration
```

### ⚠️ IMPORTANTE: NON ESISTE _truth_app.py

**L'applicazione NON ha un file `_truth_app.py`**. Gli entrypoints ufficiali sono:

1. **`wsgi:application`** - ✅ **PRODUCTION (RACCOMANDATO)**
2. **`wsgi:app`** - ✅ Compatibilità alternativa
3. **`run:app`** - ⚠️ Legacy, mantenuto per retrocompatibilità

### Comando Gunicorn CORRETTO

```bash
# ✅ PRODUCTION - COMANDO UFFICIALE
gunicorn --config gunicorn.conf.py wsgi:application

# ✅ Alternative valide
gunicorn --config gunicorn.conf.py wsgi:app
gunicorn --config gunicorn.conf.py run:app
```

---

## 🚀 Installazione Step-by-Step

### 1. Preparazione Ambiente

```bash
# Creare utente dedicato
sudo useradd -m -s /bin/bash sonacip
sudo usermod -aG www-data sonacip

# Creare directory applicazione
sudo mkdir -p /opt/sonacip
sudo chown sonacip:sonacip /opt/sonacip
```

### 2. Deploy del Codice

```bash
# Cambiare utente
sudo su - sonacip

# Clonare repository
cd /opt/sonacip
git clone https://github.com/picano78/sonacip.git .

# O caricare codice via SCP/SFTP
# scp -r /local/sonacip/* sonacip@your-vps:/opt/sonacip/
```

### 3. Configurazione Virtual Environment

```bash
# Creare virtual environment
cd /opt/sonacip
python3 -m venv venv

# Attivare virtual environment
source venv/bin/activate

# Aggiornare pip
pip install --upgrade pip setuptools wheel

# Installare dipendenze
pip install -r requirements.txt
```

### 4. Configurazione Database PostgreSQL

```bash
# Tornare a utente root
exit

# Configurare PostgreSQL
sudo -u postgres psql

-- In PostgreSQL shell:
CREATE DATABASE sonacip;
CREATE USER sonacip_user WITH PASSWORD 'your_secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE sonacip TO sonacip_user;
\q
```

### 5. Configurazione Variabili Ambiente

```bash
# Tornare a utente sonacip
sudo su - sonacip
cd /opt/sonacip

# Copiare template .env
cp .env.example .env

# Generare chiave segreta
python3 -c "import secrets; print(f'SECRET_KEY={secrets.token_hex(32)}')" >> .env.temp

# Editare .env con le configurazioni corrette
nano .env
```

**Esempio `.env` per produzione:**

```bash
# Ambiente
APP_ENV=production

# Chiave segreta (GENERARE CON: python3 -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=your_generated_secret_key_here_64_chars_minimum

# Database PostgreSQL
DATABASE_URL=postgresql://sonacip_user:your_secure_password_here@localhost:5432/sonacip

# Email SMTP
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=noreply@yourdomain.com

# Super Admin (CAMBIARE IMMEDIATAMENTE DOPO PRIMO ACCESSO!)
SUPERADMIN_EMAIL=admin@yourdomain.com
SUPERADMIN_PASSWORD=your_very_strong_password_here

# Dominio
APP_DOMAIN=yourdomain.com

# Proxy (Nginx)
USE_PROXYFIX=true
SESSION_COOKIE_SECURE=true

# Redis (opzionale ma raccomandato)
REDIS_URL=redis://localhost:6379/0
RATELIMIT_STORAGE_URI=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Sicurezza
SECURITY_HEADERS_ENABLED=true
HSTS_ENABLED=true
CSP_ENABLED=true
```

### 6. Inizializzazione Database

```bash
# Assicurarsi che virtual environment sia attivo
source /opt/sonacip/venv/bin/activate

# Inizializzare database
cd /opt/sonacip
python3 init_db.py

# Verificare che il super admin sia stato creato
# Dovresti vedere un messaggio di conferma con le credenziali
```

### 7. Test Locale

```bash
# Test rapido con Gunicorn
cd /opt/sonacip
source venv/bin/activate
gunicorn --config gunicorn.conf.py wsgi:application --bind 127.0.0.1:8000

# In un altro terminale, testare
curl http://127.0.0.1:8000/
# Dovresti ricevere una risposta HTML
```

---

## 🌐 Configurazione Nginx

### 1. Creare Configurazione Nginx

```bash
# Tornare a root
exit

# Copiare template nginx
sudo cp /opt/sonacip/deploy/sonacip.nginx.conf /etc/nginx/sites-available/sonacip

# Editare configurazione
sudo nano /etc/nginx/sites-available/sonacip
```

**Modificare le seguenti variabili:**
- Sostituire `tuodominio.it` con il tuo dominio reale
- Verificare i percorsi SSL (verranno creati da certbot)

### 2. Abilitare Sito

```bash
# Creare symlink
sudo ln -s /etc/nginx/sites-available/sonacip /etc/nginx/sites-enabled/

# Rimuovere default se presente
sudo rm /etc/nginx/sites-enabled/default

# Testare configurazione
sudo nginx -t

# Riavviare Nginx
sudo systemctl restart nginx
```

### 3. Configurare SSL con Let's Encrypt

```bash
# Ottenere certificato SSL (sostituire con il tuo dominio)
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Certbot modificherà automaticamente la configurazione Nginx
# Seguire le istruzioni interattive

# Verificare rinnovo automatico
sudo certbot renew --dry-run
```

---

## ⚙️ Configurazione Systemd

### 1. Installare Service File

```bash
# Copiare service file
sudo cp /opt/sonacip/deploy/sonacip.service /etc/systemd/system/

# Verificare che il file sia corretto
sudo cat /etc/systemd/system/sonacip.service
```

**Il file deve contenere:**

```ini
[Unit]
Description=SONACIP - Piattaforma Gestione Società Sportive
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=sonacip
Group=sonacip
WorkingDirectory=/opt/sonacip
EnvironmentFile=/opt/sonacip/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/sonacip/venv/bin/gunicorn \
    --config /opt/sonacip/gunicorn.conf.py \
    --capture-output \
    wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=5
KillMode=mixed
TimeoutStopSec=10

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/opt/sonacip
UMask=0027

[Install]
WantedBy=multi-user.target
```

### 2. Abilitare e Avviare Servizio

```bash
# Ricaricare systemd
sudo systemctl daemon-reload

# Abilitare avvio automatico
sudo systemctl enable sonacip

# Avviare servizio
sudo systemctl start sonacip

# Verificare stato
sudo systemctl status sonacip
```

---

## 🎮 Comandi di Gestione

### Gestione Servizio

```bash
# Avviare applicazione
sudo systemctl start sonacip

# Fermare applicazione
sudo systemctl stop sonacip

# Riavviare applicazione
sudo systemctl restart sonacip

# Ricaricare configurazione (senza downtime)
sudo systemctl reload sonacip

# Verificare stato
sudo systemctl status sonacip

# Vedere logs in tempo reale
sudo journalctl -u sonacip -f

# Vedere ultimi 100 log entries
sudo journalctl -u sonacip -n 100
```

### Gestione Nginx

```bash
# Testare configurazione
sudo nginx -t

# Ricaricare configurazione
sudo systemctl reload nginx

# Riavviare Nginx
sudo systemctl restart nginx

# Verificare stato
sudo systemctl status nginx
```

### Gestione Database

```bash
# Backup database
sudo -u postgres pg_dump sonacip > /opt/sonacip/backups/sonacip_$(date +%Y%m%d_%H%M%S).sql

# Restore database
sudo -u postgres psql sonacip < /opt/sonacip/backups/sonacip_backup.sql
```

### Aggiornamento Applicazione

```bash
# Cambiare a utente sonacip
sudo su - sonacip

# Andare alla directory applicazione
cd /opt/sonacip

# Backup prima dell'aggiornamento
pg_dump postgresql://sonacip_user:password@localhost:5432/sonacip > backup_pre_update.sql

# Pull nuove modifiche
git pull origin main

# Attivare virtual environment
source venv/bin/activate

# Aggiornare dipendenze
pip install -r requirements.txt --upgrade

# Eseguire migrazioni database (se necessarie)
flask db upgrade

# Tornare a root e riavviare servizio
exit
sudo systemctl restart sonacip
```

---

## 🔍 Troubleshooting

### 1. Applicazione Non Si Avvia

```bash
# Verificare logs systemd
sudo journalctl -u sonacip -n 50

# Verificare logs Gunicorn
tail -f /opt/sonacip/logs/gunicorn_error.log

# Testare manualmente
sudo su - sonacip
cd /opt/sonacip
source venv/bin/activate
gunicorn --config gunicorn.conf.py wsgi:application --bind 127.0.0.1:8000
```

**Possibili cause:**
- Virtual environment non attivato
- Variabili ambiente (.env) non configurate correttamente
- Database non accessibile
- Permessi file incorretti

### 2. Errore 502 Bad Gateway

```bash
# Verificare che Gunicorn sia in esecuzione
sudo systemctl status sonacip

# Verificare configurazione Nginx
sudo nginx -t

# Verificare connessione Nginx -> Gunicorn
curl http://127.0.0.1:8000/
```

**Possibili cause:**
- Gunicorn non in esecuzione
- Porta 8000 non in ascolto
- Timeout troppo breve (aumentare in nginx.conf)

### 3. Errore Database

```bash
# Verificare PostgreSQL
sudo systemctl status postgresql

# Testare connessione
sudo -u postgres psql -d sonacip -c "SELECT version();"

# Verificare DATABASE_URL in .env
grep DATABASE_URL /opt/sonacip/.env
```

### 4. Problemi di Permessi

```bash
# Impostare proprietà corrette
sudo chown -R sonacip:sonacip /opt/sonacip
sudo chmod -R 755 /opt/sonacip

# Impostare permessi per upload/logs
sudo chmod -R 775 /opt/sonacip/uploads
sudo chmod -R 775 /opt/sonacip/logs
sudo chmod -R 775 /opt/sonacip/backups
```

### 5. SSL/HTTPS Non Funziona

```bash
# Verificare certificati
sudo certbot certificates

# Rinnovare certificati
sudo certbot renew

# Verificare configurazione Nginx SSL
sudo nginx -t
```

---

## 📊 Monitoring e Manutenzione

### Monitoring Logs

```bash
# Application logs
tail -f /opt/sonacip/logs/gunicorn_error.log
tail -f /opt/sonacip/logs/gunicorn_access.log

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# Systemd logs
sudo journalctl -u sonacip -f
```

### Backup Automatico

Il sistema include timer systemd per backup automatici:

```bash
# Abilitare backup automatico
sudo systemctl enable sonacip-backup.timer
sudo systemctl start sonacip-backup.timer

# Verificare timer attivi
sudo systemctl list-timers
```

### Manutenzione Regolare

```bash
# Pulire vecchi logs (mantiene ultimi 30 giorni)
find /opt/sonacip/logs -name "*.log" -mtime +30 -delete

# Vacuum database PostgreSQL
sudo -u postgres vacuumdb --all --analyze

# Aggiornare sistema
sudo apt update && sudo apt upgrade -y
```

---

## ✅ Checklist Finale Pre-Produzione

- [ ] Ubuntu aggiornato all'ultima versione
- [ ] PostgreSQL installato e configurato
- [ ] Nginx installato e configurato
- [ ] Redis installato (opzionale ma raccomandato)
- [ ] Codice applicazione in `/opt/sonacip`
- [ ] Virtual environment creato e dipendenze installate
- [ ] File `.env` configurato con credenziali sicure
- [ ] `SECRET_KEY` generato casualmente (64+ caratteri)
- [ ] Database inizializzato con `init_db.py`
- [ ] Super admin creato e credenziali salvate
- [ ] SSL configurato con Let's Encrypt
- [ ] Systemd service abilitato e funzionante
- [ ] Firewall configurato (porta 80, 443)
- [ ] Backup automatico configurato
- [ ] Monitoring logs attivo
- [ ] Test completo dell'applicazione via HTTPS

---

## 🎯 Comandi Rapidi

### Avvio Completo

```bash
# Da eseguire dopo reboot del server
sudo systemctl start postgresql
sudo systemctl start redis-server  # se usato
sudo systemctl start sonacip
sudo systemctl start nginx
```

### Verifica Status

```bash
# Verificare tutti i servizi
sudo systemctl status postgresql nginx redis-server sonacip
```

### Restart Completo

```bash
# Restart sicuro di tutti i componenti
sudo systemctl restart postgresql
sudo systemctl restart redis-server
sudo systemctl restart sonacip
sudo systemctl reload nginx
```

---

## 📞 Supporto

Per problemi o domande:

1. Verificare questa guida
2. Controllare logs applicazione
3. Consultare documentazione Flask/Gunicorn/Nginx
4. Aprire issue su GitHub: https://github.com/picano78/sonacip/issues

---

## 📝 Note Finali

- **CAMBIARE** le credenziali di default dopo il primo accesso
- **BACKUP** regolare del database
- **MONITORARE** i logs per anomalie
- **AGGIORNARE** regolarmente sistema e dipendenze
- **TESTARE** sempre gli aggiornamenti in ambiente staging prima di produzione

---

**Data creazione guida:** 2026-02-15
**Versione applicazione:** SONACIP Latest
**Testato su:** Ubuntu 22.04 LTS, Ubuntu 24.04 LTS
