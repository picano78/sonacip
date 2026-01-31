# 🏆 SONACIP - Piattaforma SaaS per Gestione Sportiva

⚠️ ENTRYPOINT UNICO: wsgi:app. run.py non è usato in produzione.

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

## ▶️ Avvio

```bash
gunicorn wsgi:app
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