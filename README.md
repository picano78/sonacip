# 🏆 SONACIP - Piattaforma SaaS per Gestione Sportiva

🇮🇹 **[Leggi questa guida in Italiano](README_IT.md)** | 🔐 **[Come accedere come Super Admin](ACCESSO_SUPER_ADMIN.md)**


⚠️ ENTRYPOINT DI PRODUZIONE: `wsgi:app`. `run.py` è mantenuto solo come alias legacy (compatibilità), ma non è l’entrypoint raccomandato.

Sistema completo di gestione per società sportive, staff, atleti e appassionati.

**✅ PRODUCTION-READY - Piattaforma funzionale e consolidata**  
**📅 Validato:** 2026-01-25  
**🚀 Status:** Pronto per deployment VPS dopo configurazione variabili ambiente obbligatorie

## 🚀 Caratteristiche

- **Gestione Utenti Multi-Ruolo**: Super Admin, Società Sportive, Staff, Atleti, Appassionati
- **Social Network**: Feed, post, like, commenti, sistema follow stile LinkedIn
- **Live Streaming**: Dirette video senza archiviazione server, registrazione opzionale sul dispositivo, visualizzazione full-screen
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

## ✅ Verifica PostgreSQL

Per verificare che PostgreSQL sia installato e configurato correttamente:

```bash
python check_postgresql.py
```

Lo script controlla:
- ✓ Installazione PostgreSQL client e server
- ✓ Servizio PostgreSQL attivo
- ✓ Configurazione DATABASE_URL in `.env`
- ✓ Connessione al database
- ✓ Tabelle create correttamente

## ▶️ Avvio

```bash
export SECRET_KEY="change-me"  # oppure usa un file .env (vedi .env.example)
gunicorn wsgi:app
```

## 🔑 Credenziali Super Admin

🇮🇹 **[Guida completa in italiano: Come accedere come Super Admin](ACCESSO_SUPER_ADMIN.md)**

📖 **Documentazione completa:** 
- [ACCESSO_SUPER_ADMIN.md](ACCESSO_SUPER_ADMIN.md) - **Guida rapida in italiano**
- [FAQ_CREDENZIALI_ADMIN.md](FAQ_CREDENZIALI_ADMIN.md) - FAQ complete
- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - Guida di migrazione per deployment esistenti

### ⚡ Avvio Rapido (Sviluppo)

**Credenziali predefinite per sviluppo locale:**
- **Email**: `Picano78@gmail.com`
- **Password**: `Simone78`

**Setup in 3 comandi:**
```bash
# 1. Copia le credenziali predefinite
cp .env.example .env

# 2. Inizializza il database
python3 init_db.py

# 3. Avvia l'applicazione
python3 run.py
```

Poi accedi su: **http://localhost:5000/auth/login**

⚠️ **IMPORTANTE**: Le credenziali predefinite sono **SOLO per sviluppo**. In produzione, modifica il file `.env` con credenziali sicure prima di eseguire `init_db.py`.

### Configurazione Produzione

Per ambienti di produzione, modifica il file `.env` **PRIMA** di inizializzare il database:
   ```bash
   # Modifica .env con credenziali FORTI e UNICHE
   SUPERADMIN_EMAIL=admin@tuodominio.it
   SUPERADMIN_PASSWORD=Una!Password1Molto2Sicura3E4Lunga
   
   # Poi inizializza
   python3 init_db.py
   ```

3. Avvia l'applicazione:
   ```bash
   python run.py
   # oppure
   sudo systemctl start sonacip
   ```

### 🔧 Risoluzione Problemi di Login

**Se riscontri problemi di accesso come super admin** (errore "Credenziali non valide"), usa il nostro strumento diagnostico:

```bash
# Verifica lo stato delle credenziali
python3 fix_admin_credentials.py

# Se trova problemi, correggili automaticamente
python3 fix_admin_credentials.py --fix
```

📖 **Guida dettagliata:** [SUPER_ADMIN_QUICK_START.md](SUPER_ADMIN_QUICK_START.md)  
📖 **Documentazione tecnica del fix:** [SUPER_ADMIN_LOGIN_FIX.md](SUPER_ADMIN_LOGIN_FIX.md)

### Credenziali Generate Automaticamente (Solo Sviluppo)

Al primo avvio in **sviluppo**, se non specifichi credenziali tramite variabili d'ambiente, 
l'applicazione genererà automaticamente credenziali sicure casuali e le mostrerà nei log.

⚠️ **ATTENZIONE**: In **produzione** l'app NON si avvia senza credenziali configurate!

⚠️ **IMPORTANTE PER LA SICUREZZA**: 
- Imposta sempre credenziali personalizzate PRIMA del primo avvio in produzione
- Le credenziali generate casualmente vengono mostrate UNA SOLA VOLTA nei log
- Copia immediatamente le credenziali generate e conservale in modo sicuro
- Cambia la password dopo il primo accesso

### Come recuperare le credenziali generate

Se le credenziali sono state generate automaticamente (solo in sviluppo), cerca nei log di avvio:

```bash
# Con systemd
sudo journalctl -u sonacip -n 100 | grep -A 5 "Generated Super Admin"

# Oppure nei file di log
cat logs/sonacip.log | grep -A 5 "Generated Super Admin"
```

**📚 Per una guida completa con tutte le opzioni e troubleshooting, leggi:** [FAQ_CREDENZIALI_ADMIN.md](FAQ_CREDENZIALI_ADMIN.md)

### Script di Aggiornamento Credenziali

Se hai già avviato il sistema e vuoi cambiare le credenziali del super admin, usa lo script dedicato:

```bash
cd /opt/sonacip
source venv/bin/activate
python update_admin_credentials.py
```

Lo script aggiornerà le credenziali del super admin alle nuove credenziali che hai configurato
nel file `.env` (variabili SUPERADMIN_EMAIL e SUPERADMIN_PASSWORD).

## 🚀 Deploy VPS (Ubuntu 24.04)

Vedi guida completa: `DEPLOYMENT_UBUNTU_24_04.md`.

Per installazione **automatica** su VPS:

```bash
sudo ./sonacip_install.sh
```

Opzioni:

```bash
export SONACIP_DOMAIN="tuodominio.it"
export SONACIP_LETSENCRYPT_EMAIL="tuamail@tuodominio.it"
export SONACIP_ENABLE_UFW="true"
export SONACIP_ENABLE_REDIS="true"
sudo ./sonacip_install.sh
```

## 🎯 Struttura Progetto

```
/opt/sonacip/
├── gunicorn.conf.py      # Configurazione Gunicorn
├── wsgi.py                # Entry point WSGI per Gunicorn
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
│   ├── livestream/       # Live streaming (dirette senza archiviazione server)
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

## 🔒 Security Features

### Event Logging
- Tracciamento automatico eventi sospetti
- Log file: `logs/security.log`
- Eventi monitorati: tentativi di login falliti, upload sospetti, violazioni CSRF, accessi non autorizzati

### Log Rotation
- Automatica ogni 10MB
- Mantiene 10 backup compressi
- Cleanup automatico dopo 30 giorni

### Backup Encryption
- Tutti i backup cifrati con Fernet (symmetric encryption)
- Chiave salvata in `instance/backup_key.key` (protezione 600)
- Decriptazione automatica durante restore

### Rate Limiting
- Login: 5 tentativi/minuto
- API write: 30 richieste/minuto
- API read: 100 richieste/minuto
- File upload: 10 upload/minuto

### CSP Reporting
- Report violazioni CSP: `/security/csp-report`
- Monitoring automatico tentativi XSS

### Security Scan
Esegui scan di sicurezza automatico:
```bash
python security_scan.py
```

### Security Tests
Esegui la suite completa di test di sicurezza:
```bash
./run_security_tests.sh
```

## 🔐 Configurazione

Le variabili ambiente sono documentate nel file .env.example.

### ⚠️ Security Best Practices for Production

**CRITICAL - Prima del deployment in produzione:**

1. **Credenziali Admin Univoche**
   - ⚠️ Le credenziali hardcoded sono state rimosse - devi configurarle!
   - ✅ Imposta `SUPERADMIN_EMAIL` e `SUPERADMIN_PASSWORD` con valori univoci e sicuri
   - ✅ Usa una password forte (min. 12 caratteri, mix maiuscole/minuscole/numeri/simboli)
   - ✅ Cambia la password immediatamente dopo il primo accesso
   - ⛔ L'app NON si avvia in produzione senza credenziali configurate

2. **SECRET_KEY Sicura**
   - ⛔ NON usare valori di default o placeholder
   - ✅ Genera con: `python3 -c "import secrets; print(secrets.token_hex(32))"`
   - ✅ Conserva in modo sicuro (gestore password, vault)
   - ✅ NON committare mai nel repository

3. **HTTPS Obbligatorio**
   - ✅ Usa sempre HTTPS in produzione (tramite Nginx/Caddy con Let's Encrypt)
   - ✅ Imposta `SESSION_COOKIE_SECURE=true` nel file `.env`
   - ✅ Verifica che HSTS sia abilitato (default: attivo)

4. **Database PostgreSQL**
   - ✅ Usa PostgreSQL in produzione (non SQLite)
   - ✅ Imposta password forte per l'utente database
   - ✅ Limita accesso al database solo da localhost o IP trusted

5. **Monitoraggio e Backup**
   - ✅ Configura backup automatici giornalieri
   - ✅ Monitora i log di sicurezza: `logs/security.log`
   - ✅ Configura alert per tentativi di accesso sospetti

6. **Variabili Ambiente**
   - ✅ NON committare mai il file `.env` nel repository (verificare `.gitignore`)
   - ✅ Usa variabili ambiente o secret manager per valori sensibili
   - ✅ Valida che tutte le variabili obbligatorie siano impostate

Per maggiori dettagli, consulta:
- 📋 [Security Checklist completa](docs/SECURITY_CHECKLIST.md) - Checklist dettagliata per deployment sicuro
- 🔒 [Security Features](#security-features) - Funzionalità di sicurezza integrate
- ⚙️ File `.env.example` - Template configurazione

## 📚 Documentazione Sviluppatori

- [Code Quality Guidelines](docs/CODE_QUALITY_GUIDELINES.md) - Best practices per codice di qualità
- [Performance Best Practices](docs/PERFORMANCE_BEST_PRACTICES.md) - Ottimizzazione performance
- [Security Checklist](docs/SECURITY_CHECKLIST.md) - Checklist sicurezza produzione

## 🧹 Manutenzione Repository

Per mantenere il repository Git pulito e ottimizzato:

```bash
./scripts/git_cleanup.sh
```

Per informazioni dettagliate sulla manutenzione del repository, consulta: [GIT_MAINTENANCE.md](GIT_MAINTENANCE.md)

## 📝 Note Importanti

1. Cambia password admin dopo installazione
2. Configura SECRET_KEY forte
3. Abilita HTTPS in produzione
4. Backup regolari via admin panel
5. Monitora i log di sistema del servizio

---

**SONACIP © 2026** - Made with ❤️ for sports