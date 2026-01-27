# 🏆 SONACIP - Piattaforma SaaS per Gestione Sportiva

Sistema completo di gestione per società sportive, staff, atleti e appassionati.

**✅ PRODUCTION-READY - Piattaforma funzionale e consolidata**  
**📅 Validato:** 2026-01-25  
**🚀 Status:** Pronto per deployment VPS dopo configurazione variabili ambiente obbligatorie

## 🚀 Caratteristiche

- **Gestione Utenti Multi-Ruolo**: Super Admin, Società Sportive, Staff, Atleti, Appassionati
- **Social Network**: Feed, post, like, commenti, sistema follow stile LinkedIn
- **CRM Integrato**: Gestione contatti, lead, opportunità, attività
- **Eventi e Convocazioni**: Creazione eventi, convocazione atleti, gestione risposte accept/reject
- **Notifiche**: Sistema interno + integrazione email (SMTP) + pronto per SMS
- **Backup & Restore**: Backup completo database e file con restore validato
- **Admin Panel**: Dashboard completo con statistiche, gestione utenti, audit logs
- **Sicurezza**: Login protetto, controllo ruoli, CSRF protection, bcrypt passwords

## 📋 Requisiti

- Python 3.11+
- SQLite (default) o PostgreSQL
- Nginx (produzione)
- Gunicorn (produzione)

## ⚡ Quick Start (Locale)

```bash
pip3 install -r requirements.txt
cp .env.example .env
gunicorn -c gunicorn.conf.py run:app
```

**Accedi a:** http://localhost

**Credenziali Admin (auto-seed):**
- Email: admin@example.com
- Password: Admin123!

## 🔧 Installazione Completa (Sviluppo)

```bash
# Clone o estrai il progetto
cd /opt/sonacip

# Crea virtual environment (opzionale ma raccomandato)
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Installa dipendenze
pip install -r requirements.txt

# Crea file .env
cp .env.example .env

# Avvia con Gunicorn
gunicorn -c gunicorn.conf.py run:app
```

## 🚢 Deployment Produzione (Ubuntu 24.04)

### 1. Preparazione Server

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3.12 python3.12-venv python3-pip nginx -y
```

### 2. Deploy Applicazione

```bash
sudo mkdir -p /opt/sonacip
sudo cp -r . /opt/sonacip/
cd /opt/sonacip
sudo chown -R www-data:www-data /opt/sonacip

sudo -u www-data python3.12 -m venv venv
sudo -u www-data venv/bin/pip install -r requirements.txt
sudo -u www-data cp .env.example .env
# Configura .env con SECRET_KEY forte e DATABASE_URL (SQLite assoluto o PostgreSQL)
sudo -u www-data mkdir -p logs backups uploads
```

### 3. Configura Gunicorn + Systemd

```bash
sudo cp deploy/sonacip.service /etc/systemd/system/sonacip.service
sudo systemctl daemon-reload
sudo systemctl start sonacip
sudo systemctl enable sonacip
sudo systemctl status sonacip
```

### 4. Configura Nginx

```bash
sudo cp deploy/nginx_sonacip.conf /etc/nginx/sites-available/sonacip
# Modifica dominio nel file
sudo ln -s /etc/nginx/sites-available/sonacip /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 5. SSL (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
```

## 🎯 Struttura Progetto

```
/opt/sonacip/
├── gunicorn.conf.py      # Configurazione Gunicorn
├── run.py                 # Entry point unico (app factory)
├── config.py              # Configurazione (Dev/Prod)
├── requirements.txt       # Dipendenze Python
├── start.sh              # Script avvio rapido
├── .env.example          # Template variabili ambiente
├── .env                  # Variabili ambiente produzione
├── app/
│   ├── __init__.py       # Application factory
│   ├── models.py         # Database models (11 tabelle)
│   ├── auth/             # Autenticazione e registrazione
│   ├── admin/            # Panel admin completo
│   ├── social/           # Social network (feed, posts, follow)
│   ├── crm/              # CRM (contatti, opportunità, attività)
│   ├── events/           # Eventi e convocazioni
│   ├── scheduler/        # Calendario società
│   ├── notifications/    # Notifiche (interno + email + SMS-ready)
│   ├── backup/           # Backup/Restore completo
│   ├── templates/        # Template Jinja2 (65+ files)
│   └── static/           # CSS, JS, immagini
├── deploy/
│   ├── nginx_sonacip.conf  # Configurazione Nginx
│   └── sonacip.service     # Systemd service
├── backups/             # Directory backup (auto-created)
├── uploads/             # File caricati (auto-created)
├── logs/                # Log applicazione (auto-created)
└── sonacip.db           # Database SQLite (auto-created)
```

## 👥 Ruoli Utente

- **Super Admin**: Gestione completa sistema
- **Società Sportiva**: Gestione eventi, atleti, staff
- **Staff**: Assistenza società, creazione eventi
- **Atleta**: Risposta convocazioni
- **Appassionato**: Navigazione sociale

## 🔐 Configurazione

Genera SECRET_KEY:
```python
python3 -c "import secrets; print(secrets.token_hex(32))"
```

File .env (produzione):
```
APP_ENV=production
FLASK_ENV=production
SECRET_KEY=generated-key
DATABASE_URL=sqlite:////opt/sonacip/sonacip.db
USE_PROXYFIX=true
RATELIMIT_STORAGE_URI=memory://
```

## 📝 Note Importanti

1. Cambia password admin dopo installazione
2. Configura SECRET_KEY forte
3. Abilita HTTPS in produzione
4. Backup regolari via admin panel
5. Monitora log: `sudo journalctl -u sonacip -f`

---

**SONACIP © 2026** - Made with ❤️ for sports