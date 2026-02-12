# 🏆 SONACIP - Piattaforma SaaS per Gestione Sportiva

⚠️ ENTRYPOINT DI PRODUZIONE: `wsgi:app`. `run.py` è mantenuto solo come alias legacy (compatibilità), ma non è l’entrypoint raccomandato.

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

📖 **Per informazioni complete sulle credenziali del Super Admin, consulta:** [FAQ_CREDENZIALI_ADMIN.md](FAQ_CREDENZIALI_ADMIN.md)

⭐ **CREDENZIALI PREDEFINITE**:
- **Email**: Picano78@gmail.com
- **Password**: Simone78

Queste credenziali sono configurate nel file `.env.example` e verranno utilizzate quando copi il file in `.env`.

### Configurazione Rapida

Al primo avvio, se non specifichi credenziali personalizzate tramite variabili d'ambiente, l'applicazione genererà automaticamente credenziali sicure casuali e le mostrerà nei log.

⚠️ **IMPORTANTE PER LA SICUREZZA**: 
- Imposta sempre credenziali personalizzate PRIMA del primo avvio in produzione
- Le credenziali generate casualmente vengono mostrate UNA SOLA VOLTA nei log
- Copia immediatamente le credenziali generate e conservale in modo sicuro
- Cambia la password dopo il primo accesso

Per personalizzare le credenziali del Super Admin, imposta le variabili d'ambiente PRIMA del primo avvio:

```bash
export SUPERADMIN_EMAIL="tuaemail@esempio.it"
export SUPERADMIN_PASSWORD="TuaPasswordSicura"
```

oppure aggiungile al file `.env`:

```
# Il file .env.example contiene già le credenziali predefinite:
# SUPERADMIN_EMAIL=Picano78@gmail.com
# SUPERADMIN_PASSWORD=Simone78

# Puoi usarle così come sono, o modificarle:
SUPERADMIN_EMAIL=tuaemail@esempio.it
SUPERADMIN_PASSWORD=TuaPasswordSicura
```

### Come recuperare le credenziali generate

Se le credenziali sono state generate automaticamente, cerca nei log di avvio:

```bash
# Con systemd
sudo journalctl -u sonacip -n 100 | grep -A 5 "Generated Super Admin"

# Oppure nei file di log
cat logs/sonacip.log | grep -A 5 "Generated Super Admin"
```

**📚 Per una guida completa con tutte le opzioni e troubleshooting, leggi:** [FAQ_CREDENZIALI_ADMIN.md](FAQ_CREDENZIALI_ADMIN.md)

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

Le variabili ambiente sono documentate nel file .env.example.

## 📝 Note Importanti

1. Cambia password admin dopo installazione
2. Configura SECRET_KEY forte
3. Abilita HTTPS in produzione
4. Backup regolari via admin panel
5. Monitora i log di sistema del servizio

---

**SONACIP © 2026** - Made with ❤️ for sports