# SONACIP - Guida Rapida in Italiano

Benvenuto in **SONACIP**, la piattaforma completa per la gestione sportiva.

## 🚀 Installazione e Primo Avvio

### 1. Installazione Dipendenze
```bash
pip3 install -r requirements.txt
```

### 2. Configurazione
```bash
# Copia il file di configurazione con credenziali predefinite
cp .env.example .env
```

### 3. Inizializzazione Database
```bash
python3 init_db.py
```

### 4. Avvio Applicazione
```bash
python3 run.py
```

L'applicazione sarà disponibile su: **http://localhost:5000**

## 🔐 Accesso Super Admin

### Credenziali Predefinite (Sviluppo)

- **Email**: `Picano78@gmail.com`
- **Password**: `Simone78`
- **URL Login**: http://localhost:5000/auth/login

⚠️ **IMPORTANTE**: Queste credenziali sono solo per sviluppo. In produzione, usa credenziali personalizzate nel file `.env`.

### Risoluzione Problemi di Accesso

Se non riesci ad accedere:
```bash
# Diagnosi e correzione automatica
python3 fix_admin_credentials.py --fix
```

**Per una guida completa**, leggi: **[ACCESSO_SUPER_ADMIN.md](./ACCESSO_SUPER_ADMIN.md)**

## 📖 Funzionalità Principali

- **Social Feed** - Condivisione contenuti e interazioni sociali
- **Gestione Eventi** - Organizzazione e gestione eventi sportivi
- **Tornei** - Sistema completo di gestione tornei
- **Calendario Società** - Pianificazione attività delle società
- **CRM** - Gestione relazioni con atleti e membri
- **Planner Campo** - Prenotazione e gestione campi sportivi
- **Fatturazione** - Sistema di fatturazione integrato
- **Live Streaming** - Eventi in diretta
- **Analytics** - Statistiche e report avanzati
- **Abbonamenti** - Gestione piani e pagamenti

## 🛠️ Comandi Utili

### Gestione Database
```bash
# Inizializza/Aggiorna database
python3 init_db.py

# Crea migrazione
python3 create_migration.py "descrizione_modifica"

# Backup database
cp sonacip.db sonacip.db.backup_$(date +%Y%m%d)
```

### Test
```bash
# Esegui tutti i test
python3 -m pytest

# Test specifici
python3 -m pytest tests/test_auth.py
```

### Strumenti Admin
```bash
# Verifica credenziali super admin
python3 fix_admin_credentials.py

# Recupera credenziali generate
python3 recupera_credenziali.py

# Aggiorna credenziali
python3 update_admin_credentials.py
```

## 📚 Documentazione

### Guide in Italiano
- **[ACCESSO_SUPER_ADMIN.md](./ACCESSO_SUPER_ADMIN.md)** - Come accedere come super amministratore
- **[FAQ_CREDENZIALI_ADMIN.md](./FAQ_CREDENZIALI_ADMIN.md)** - FAQ sulle credenziali
- **[RIEPILOGO_CREDENZIALI.md](./RIEPILOGO_CREDENZIALI.md)** - Riepilogo gestione credenziali
- **[RISOLUZIONE_PROBLEMI.md](./RISOLUZIONE_PROBLEMI.md)** - Risoluzione problemi comuni
- **[RAPPORTO_FINALE_IT.md](./RAPPORTO_FINALE_IT.md)** - Report finale implementazione

### Guide Tecniche (Inglese)
- **[README.md](./README.md)** - Documentazione principale
- **[ADMIN_LOGIN.md](./ADMIN_LOGIN.md)** - Login amministratore
- **[DEPLOYMENT_UBUNTU_24_04.md](./DEPLOYMENT_UBUNTU_24_04.md)** - Deploy su Ubuntu
- **[INVOICE_SYSTEM_DOCUMENTATION.md](./INVOICE_SYSTEM_DOCUMENTATION.md)** - Sistema fatturazione

## 🔒 Sicurezza

### Ambiente di Sviluppo
- Usa le credenziali predefinite fornite
- Il file `.env` è già ignorato da Git

### Ambiente di Produzione

**PRIMA** di mettere in produzione:

1. **Genera credenziali sicure**:
   ```bash
   # Genera SECRET_KEY
   python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"
   ```

2. **Modifica `.env`** con:
   - `SECRET_KEY` generato sopra
   - `SUPERADMIN_EMAIL` con la tua email aziendale
   - `SUPERADMIN_PASSWORD` con una password forte (min 12 caratteri)
   - `APP_ENV=production`
   - `DATABASE_URL` con il database PostgreSQL

3. **Proteggi il file**:
   ```bash
   chmod 600 .env
   ```

4. **Dopo il primo accesso**, cambia immediatamente la password dal profilo utente

## 🌐 Deploy in Produzione

### Con Docker (Consigliato)
```bash
# TODO: Docker compose disponibile prossimamente
```

### Su VPS Ubuntu 24.04
Segui la guida: **[DEPLOYMENT_UBUNTU_24_04.md](./DEPLOYMENT_UBUNTU_24_04.md)**

### Con Gunicorn
```bash
# Installa Gunicorn
pip3 install gunicorn

# Avvia con 4 worker
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
```

## 🐛 Problemi Comuni

### "Credenziali non valide"
```bash
python3 fix_admin_credentials.py --fix
```

### "Database non trovato"
```bash
python3 init_db.py
```

### "Sessione scaduta"
- Cancella i cookie del browser
- Riprova il login

### "Errore 502 Bad Gateway"
Consulta: **[FIX_502_REGISTRAZIONE.md](./FIX_502_REGISTRAZIONE.md)**

## 🤝 Supporto

- **Documentazione**: Consulta i file `.md` nella root del progetto
- **Issues**: Apri una issue su GitHub
- **Email**: Contatta il team di sviluppo

## 📄 Licenza

[Specifica la licenza del progetto]

---

**SONACIP** © 2026 - Gestione Sportiva Professionale
