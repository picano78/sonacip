# Guida Installazione SONACIP su VPS

## Requisiti Minimi
- Ubuntu 22.04+ / Debian 12+ (consigliato)
- Python 3.11+
- PostgreSQL 14+ (consigliato) oppure SQLite 3 (per installazioni leggere)
- Nginx (reverse proxy)
- 1 GB RAM, 10 GB disco

## Installazione Automatica (consigliata)

Per un'installazione automatica completa, usa lo script incluso:

```bash
# Copia il progetto sul server e lancia l'installer come root
sudo SONACIP_DOMAIN=tuodominio.it \
     SONACIP_LETSENCRYPT_EMAIL=tuaemail@email.com \
     bash sonacip_install.sh
```

Lo script configura automaticamente: utente di sistema, venv Python, systemd, Nginx con SSL, backup automatici, logrotate e healthcheck.

**Opzioni aggiuntive:**
- `SONACIP_ENABLE_UFW=true` - Configura il firewall UFW
- `SONACIP_ENABLE_REDIS=true` - Installa e configura Redis per il rate limiting

> Se preferisci un'installazione manuale, segui i passaggi sotto.

---

## Installazione Manuale

### 1. Preparazione Server

```bash
# Aggiorna il sistema
sudo apt update && sudo apt upgrade -y

# Installa dipendenze
sudo apt install -y python3.11 python3.11-venv python3.11-dev \
    postgresql postgresql-contrib nginx certbot python3-certbot-nginx \
    git build-essential libpq-dev
```

## 2. Crea Utente e Directory

```bash
# Crea utente dedicato
sudo useradd -r -m -s /bin/bash sonacip

# Crea directory
sudo mkdir -p /var/www/sonacip
sudo chown sonacip:sonacip /var/www/sonacip
```

## 3. Database PostgreSQL

```bash
# Entra come utente postgres
sudo -u postgres psql

# Crea database e utente
CREATE USER sonacip WITH PASSWORD 'tua_password_sicura';
CREATE DATABASE sonacip OWNER sonacip;
GRANT ALL PRIVILEGES ON DATABASE sonacip TO sonacip;
\q
```

## 4. Trasferisci i File

```bash
# Dal tuo computer locale, trasferisci il progetto
scp -r ./* tuouser@tuovps:/var/www/sonacip/

# Oppure con git
sudo -u sonacip git clone <tuo-repo> /var/www/sonacip
```

## 5. Configura l'Ambiente

```bash
# Entra come utente sonacip
sudo -iu sonacip
cd /var/www/sonacip

# Crea ambiente virtuale Python
python3.11 -m venv venv
source venv/bin/activate

# Installa dipendenze
pip install --upgrade pip
pip install -r requirements.txt

# Configura le variabili d'ambiente
cp .env.example .env
nano .env  # Compila tutti i valori necessari

# Crea le cartelle necessarie
mkdir -p uploads backups logs instance
```

## 6. Variabili d'Ambiente Importanti

Apri `.env` e configura almeno:

| Variabile | Descrizione |
|-----------|-------------|
| `SECRET_KEY` | Chiave segreta (genera con `python3 -c "import secrets; print(secrets.token_hex(32))"`) |
| `DATABASE_URL` | `postgresql://sonacip:tua_password@localhost:5432/sonacip` |
| `APP_ENV` | `production` |
| `SUPERADMIN_EMAIL` | Email del super admin |
| `SUPERADMIN_PASSWORD` | Password iniziale del super admin |
| `MAIL_USERNAME` | Email SMTP per invio notifiche |
| `MAIL_PASSWORD` | Password app SMTP |

## 7. Inizializza il Database

```bash
source venv/bin/activate

# Esegui le migrazioni del database
python manage.py db upgrade

# Popola i dati di base (ruoli, impostazioni, super admin)
python manage.py seed

# Nota: al primo avvio, l'app esegue automaticamente le migrazioni
# ma è consigliato farlo manualmente prima di avviare il servizio
```

## 8. Installa il Servizio Systemd

```bash
# Copia il file di servizio
sudo cp deploy/sonacip.service /etc/systemd/system/

# Ricarica systemd
sudo systemctl daemon-reload

# Avvia e abilita il servizio
sudo systemctl enable sonacip
sudo systemctl start sonacip

# Verifica lo stato
sudo systemctl status sonacip
```

## 9. Configura Nginx

```bash
# Copia la configurazione Nginx
sudo cp deploy/sonacip.nginx.conf /etc/nginx/sites-available/sonacip

# Modifica il dominio nel file
sudo nano /etc/nginx/sites-available/sonacip
# Sostituisci "tuodominio.it" con il tuo dominio reale

# Attiva il sito
sudo ln -s /etc/nginx/sites-available/sonacip /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Verifica e riavvia Nginx
sudo nginx -t
sudo systemctl restart nginx
```

## 10. Certificato SSL (Let's Encrypt)

```bash
# Installa certificato SSL gratuito
sudo certbot --nginx -d tuodominio.it -d www.tuodominio.it

# Il rinnovo automatico è già configurato da certbot
```

## 11. Permessi File

```bash
# Imposta i permessi corretti
sudo chown -R sonacip:sonacip /var/www/sonacip
sudo chmod -R 755 /var/www/sonacip
sudo chmod 600 /var/www/sonacip/.env
sudo chmod -R 775 /var/www/sonacip/uploads
sudo chmod -R 775 /var/www/sonacip/backups
sudo chmod -R 775 /var/www/sonacip/logs
```

---

## Comandi Utili

```bash
# Stato del servizio
sudo systemctl status sonacip

# Riavvia l'applicazione
sudo systemctl restart sonacip

# Vedi i log in tempo reale
sudo journalctl -u sonacip -f

# Log di accesso Nginx
sudo tail -f /var/log/nginx/access.log

# Log errori applicazione
tail -f /var/www/sonacip/logs/error.log

# Aggiorna l'applicazione
cd /var/www/sonacip
sudo -u sonacip git pull
sudo -u sonacip venv/bin/pip install -r requirements.txt
sudo systemctl restart sonacip
```

## Backup Automatico (Cron)

```bash
# Aggiungi un backup giornaliero del database
sudo crontab -u sonacip -e

# Aggiungi questa riga:
0 3 * * * pg_dump sonacip > /var/www/sonacip/backups/sonacip_$(date +\%Y\%m\%d).sql 2>/dev/null
```

## Uso con SQLite (alternativa a PostgreSQL)

Se non vuoi installare PostgreSQL, SONACIP funziona anche con SQLite. Basta **non impostare** `DATABASE_URL` nel file `.env` (oppure rimuoverlo):

```bash
# Nel file .env, commenta o rimuovi la riga DATABASE_URL
# DATABASE_URL=postgresql://...

# L'app creerà automaticamente il file sonacip.db nella cartella del progetto
```

SQLite è ideale per:
- Installazioni piccole (< 50 utenti)
- Test e sviluppo locale
- Server con risorse limitate

> **Nota:** Per società con molti membri o accessi simultanei, PostgreSQL è fortemente consigliato.

---

## Risoluzione Problemi

| Problema | Soluzione |
|----------|----------|
| 502 Bad Gateway | `sudo systemctl restart sonacip` e controlla i log |
| Permessi negati | Verifica `chown` e `chmod` su uploads/logs/backups |
| Database non raggiungibile | Verifica `DATABASE_URL` in `.env` e che PostgreSQL sia attivo |
| Email non funzionano | Verifica `MAIL_USERNAME` e `MAIL_PASSWORD` (usa App Password per Gmail) |
| CSS/JS non caricano | Verifica la sezione `location /static/` in Nginx |
