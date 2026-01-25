# SONACIP - Sistema Completo e Funzionante

## ✅ STATO DEL PROGETTO

**SONACIP È COMPLETO, COERENTE E PRONTO PER L'USO**

Tutti i test passano con successo. Il sistema è:
- ✅ Internamente coerente
- ✅ Strutturalmente corretto
- ✅ Eseguibile senza errori
- ✅ Una solida base per espansioni future

---

## 🚀 AVVIO RAPIDO

### 1. Avvio del Server

```bash
# Ambiente di sviluppo
flask --app run run

# Produzione con Gunicorn
gunicorn -c gunicorn_config.py run:app
```

Il server sarà disponibile su:
- `http://localhost:5000`
- `http://0.0.0.0:5000`

### 2. Accesso al Sistema

#### Account di Default

| Ruolo | Email | Password | Descrizione |
|-------|-------|----------|-------------|
| Super Admin | admin@sonacip.it | impostata via SUPERADMIN_PASSWORD oppure generata e riportata nei log | Accesso completo al sistema |
| Società | test@societa.it | test123 | Società sportiva di test |
| Atleta | test@atleta.it | test123 | Atleta associato alla società |
| Appassionato | test@fan.it | test123 | Utente generico |

**⚠️ IMPORTANTE**: Impostare `SUPERADMIN_PASSWORD` prima del primo avvio e ruotare la password dopo il primo accesso.

---

## 📋 ARCHITETTURA

### Modelli Database

Il sistema utilizza **14 tabelle** principali:

1. **user** - Gestione utenti multi-ruolo (super_admin, societa, staff, atleta, appassionato)
2. **post** - Post social stile LinkedIn
3. **comment** - Commenti ai post
4. **event** - Eventi sportivi (allenamenti, partite, tornei)
5. **notification** - Sistema notifiche interno
6. **audit_log** - Log di audit per azioni amministrative
7. **backup** - Tracciamento backup
8. **message** - Messaggi diretti tra utenti
9. **contact** - Contatti CRM
10. **opportunity** - Opportunità CRM
11. **crm_activity** - Attività CRM
12. **followers** - Relazioni social (follower/following)
13. **post_likes** - Like ai post
14. **event_athletes** - Convocazioni eventi

### Blueprint Registrati

Il sistema è organizzato in **8 blueprint**:

1. **main** - Homepage e pagine pubbliche
2. **auth** - Autenticazione (login, registrazione)
3. **admin** - Pannello amministrativo
4. **social** - Feed social, profili, post
5. **events** - Gestione eventi sportivi
6. **notifications** - Sistema notifiche
7. **backup** - Gestione backup
8. **crm** - CRM per società sportive

---

## 🔐 SISTEMA DI RUOLI E PERMESSI

### Ruoli Disponibili

1. **super_admin**
   - Accesso completo al sistema
   - Gestione di tutti gli utenti
   - Accesso al pannello amministrativo
   - Visualizzazione log di audit

2. **societa** (Società Sportiva)
   - Dashboard dedicata
   - Gestione staff e atleti
   - Creazione eventi
   - CRM integrato
   - Pubblicazione post

3. **staff**
   - Associato a una società
   - Gestione atleti della società
   - Creazione eventi
   - Accesso CRM

4. **atleta**
   - Associato a una società
   - Risposta a convocazioni
   - Feed social
   - Visualizzazione eventi

5. **appassionato**
   - Feed social
   - Follow società e atleti
   - Interazione con post

### Decoratori di Accesso

Il sistema fornisce decoratori helper in `app/utils.py`:

```python
from app.utils import (
    admin_required,           # Solo super_admin
    society_required,         # Solo societa
    staff_or_society_required,# Staff o societa
    role_required,            # Ruoli specifici
)

# Esempi d'uso
@bp.route('/admin-only')
@login_required
@admin_required
def admin_view():
    pass

@bp.route('/multi-role')
@login_required
@role_required('super_admin', 'societa', 'staff')
def multi_role_view():
    pass
```

### Funzioni di Permesso

```python
from app.utils import can_manage_user, can_view_user, get_user_society

# Verifica se current_user può gestire un altro utente
if can_manage_user(target_user):
    # Permetti modifica
    pass

# Verifica se current_user può vedere il profilo
if can_view_user(target_user):
    # Mostra profilo
    pass

# Ottieni la società associata a un utente
society = get_user_society(user)
```

---

## 📁 STRUTTURA DELLE DIRECTORY

```
sonacip/
├── app/                    # Applicazione Flask
│   ├── __init__.py        # Factory pattern
│   ├── models.py          # Modelli SQLAlchemy
│   ├── utils.py           # Utility e decoratori comuni
│   ├── admin/             # Blueprint amministrazione
│   ├── auth/              # Blueprint autenticazione
│   ├── backup/            # Blueprint backup
│   ├── crm/               # Blueprint CRM
│   ├── events/            # Blueprint eventi
│   ├── main/              # Blueprint principale
│   ├── notifications/     # Blueprint notifiche
│   ├── social/            # Blueprint social
│   ├── static/            # File statici (CSS, JS, immagini)
│   └── templates/         # Template Jinja2
├── backups/               # Directory backup
├── logs/                  # Log applicazione
├── uploads/               # File caricati
│   ├── avatars/          # Avatar utenti
│   ├── covers/           # Foto copertina
│   └── posts/            # Immagini post
├── config.py             # Configurazione
├── run.py                # Entrypoint UNICO
├── test_suite.py         # Suite di test automatici
├── gunicorn_config.py    # Configurazione Gunicorn
├── requirements.txt      # Dipendenze Python
├── sonacip.db           # Database SQLite
└── README.md            # Documentazione
```

---

## 🧪 TEST

### Test Automatici

Esegui la suite di test completa:

```bash
python test_suite.py
```

Output atteso:
```
============================================================
SONACIP TEST SUITE
============================================================

Testing application startup...
  ✓ Application starts successfully

Testing imports...
  ✓ All imports successful

Testing database...
  ✓ Database has 14 tables
  ✓ Super admin exists: admin@sonacip.it

Testing blueprints...
  ✓ All 8 blueprints registered

Testing routes...
  ✓ All 7 critical routes exist

Testing user roles...
  ✓ All role methods work correctly

Testing relationships...
  ✓ Relationships working correctly

============================================================
✓ ALL TESTS PASSED (7/7)
============================================================
```

### Test Manuali

1. **Login come Admin**
   - Vai su `http://localhost:5000/auth/login`
   - Email: `admin@sonacip.it`
   - Password: impostata via `SUPERADMIN_PASSWORD` o riportata nei log di avvio
   - Verifica accesso a `/admin/dashboard`

2. **Login come Società**
   - Email: `test@societa.it`
   - Password: `test123`
   - Verifica accesso a `/social/society/dashboard`

3. **Creazione Evento**
   - Login come società
   - Vai su `/events/create`
   - Crea un evento di test

4. **Feed Social**
   - Login con qualsiasi account
   - Vai su `/social/feed`
   - Crea un post

---

## 🔧 CONFIGURAZIONE

### Variabili d'Ambiente

```bash
# Flask
FLASK_ENV=production
SECRET_KEY=your-secret-key-here

# Database
DATABASE_URL=sqlite:///sonacip.db

# Email (opzionale)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-password
MAIL_DEFAULT_SENDER=noreply@sonacip.it

# SMS (opzionale)
SMS_PROVIDER=twilio
SMS_API_KEY=your-api-key
SMS_API_SECRET=your-api-secret
```

### Database

Il sistema usa **SQLite** di default. Per usare PostgreSQL o MySQL:

```python
# In config.py
SQLALCHEMY_DATABASE_URI = 'postgresql://user:pass@localhost/sonacip'
# oppure
SQLALCHEMY_DATABASE_URI = 'mysql://user:pass@localhost/sonacip'
```

---

## 🛡️ SICUREZZA

### Implementazioni di Sicurezza

1. **Password Hashing**
   - Werkzeug security
   - `generate_password_hash()` e `check_password_hash()`

2. **CSRF Protection**
   - Flask-WTF
   - Token automatici in tutti i form

3. **Session Security**
   - Cookie HttpOnly
   - SameSite=Lax
   - Scadenza 7 giorni

4. **Audit Log**
   - Tracking azioni amministrative
   - IP address logging
   - Timestamp di tutte le operazioni

### Best Practices

1. **Produzione**
   ```bash
   # Cambia SECRET_KEY
   export SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
   
   # Cambia password admin
   # Via interfaccia o script Python
   ```

2. **HTTPS**
   - Usa reverse proxy (nginx) con SSL
   - File di configurazione: `deployment/nginx.conf`

3. **Backup Regolari**
   - Interfaccia backup disponibile su `/backup/`
   - Backup automatici configurabili

---

## 🚢 DEPLOYMENT IN PRODUZIONE

### Con Gunicorn

```bash
# Install
pip install gunicorn

# Run
gunicorn -c gunicorn_config.py run:app
```

### Con Systemd (Linux)

```bash
# Copia service file
sudo cp deployment/sonacip.service /etc/systemd/system/

# Abilita e avvia
sudo systemctl enable sonacip
sudo systemctl start sonacip
sudo systemctl status sonacip
```

### Con Nginx (Reverse Proxy)

```bash
# Copia configurazione
sudo cp deployment/nginx.conf /etc/nginx/sites-available/sonacip

# Abilita sito
sudo ln -s /etc/nginx/sites-available/sonacip /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 📊 STATISTICHE PROGETTO

- **Linee di codice**: ~5000+
- **Modelli database**: 14
- **Blueprint**: 8
- **Route**: 50+
- **Template**: 38
- **Test copertura**: Core functionality

---

## 🎯 PROSSIMI PASSI SUGGERITI

Anche se il sistema è completo, questi sono miglioramenti opzionali:

1. **Frontend Enhancement**
   - Migliorare UI/UX con JavaScript moderno
   - Implementare real-time updates con WebSockets

2. **Feature Expansion**
   - Sistema di pagamenti (Stripe/PayPal)
   - Integrazione calendario (Google Calendar)
   - App mobile (React Native / Flutter)

3. **Performance**
   - Cache con Redis
   - Background tasks con Celery
   - Database query optimization

4. **Analytics**
   - Dashboard statistiche avanzate
   - Export dati in Excel/PDF
   - Grafici interattivi

5. **Testing**
   - Unit tests completi
   - Integration tests
   - E2E testing con Selenium

---

## 📝 NOTE TECNICHE

### Gestione Utenti Multi-Ruolo

Il sistema usa un **singolo modello User** con campo `role` invece di modelli separati.
Questo semplifica:
- Query e join
- Gestione permessi
- Migrazione dati

### No Migration System

Il sistema usa `db.create_all()` invece di Alembic migrations.
Vantaggi per questo progetto:
- Semplicità
- Nessuna migration history da gestire
- Ideale per prototipo/MVP

Per produzione con migration:
```bash
pip install flask-migrate
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### Datetime Deprecation

Il sistema usa `datetime.utcnow()` che è deprecated in Python 3.12+.
Per il futuro, migrare a:
```python
from datetime import datetime, timezone
datetime.now(timezone.utc)
```

---

## 🆘 TROUBLESHOOTING

### Port Already in Use
```bash
# Trova processo
lsof -ti:5000

# Kill processo
kill -9 $(lsof -ti:5000)
```

### Database Locked
```bash
# Verifica processi
ps aux | grep python

# Restart applicazione
```

### Import Errors
```bash
# Reinstalla dipendenze
pip install -r requirements.txt

# Verifica Python version
python --version  # Deve essere 3.8+
```

---

## 📞 SUPPORTO

Per problemi o domande:
1. Verifica la documentazione
2. Esegui `python test_suite.py`
3. Controlla i log in `logs/`
4. Verifica configurazione in `config.py`

---

## ✅ CHECKLIST PRE-PRODUZIONE

- [ ] Cambiata SECRET_KEY
- [ ] Cambiata password admin
- [ ] Configurato database produzione (non SQLite)
- [ ] Configurato HTTPS
- [ ] Configurato backup automatici
- [ ] Testato tutti i flussi critici
- [ ] Configurato monitoring/logging
- [ ] Configurato email server
- [ ] Documentato procedure operative

---

**SONACIP è pronto per l'uso. Buon lavoro! 🚀**
