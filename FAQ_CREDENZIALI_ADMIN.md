# ❓ FAQ - Credenziali Super Admin

## 🔑 Quali sono le credenziali del Super Admin?

Le credenziali del Super Admin di SONACIP dipendono da come hai configurato l'applicazione:

### Opzione 1: Credenziali Personalizzate (RACCOMANDATA per Produzione)

Se hai impostato le variabili d'ambiente `SUPERADMIN_EMAIL` e `SUPERADMIN_PASSWORD` **prima del primo avvio**, le credenziali saranno quelle che hai configurato.

**Come configurarle:**

1. **Tramite file `.env`** (metodo raccomandato):
   ```bash
   # Copia il file esempio
   cp .env.example .env
   
   # Modifica il file .env e imposta:
   SUPERADMIN_EMAIL=tuaemail@tuodominio.it
   SUPERADMIN_PASSWORD=TuaPasswordSicura123!
   ```

2. **Tramite variabili d'ambiente**:
   ```bash
   export SUPERADMIN_EMAIL="tuaemail@tuodominio.it"
   export SUPERADMIN_PASSWORD="TuaPasswordSicura123!"
   ```

### Opzione 2: Credenziali Generate Automaticamente

Se **NON** hai impostato le variabili d'ambiente prima del primo avvio, l'applicazione genera automaticamente credenziali casuali sicure.

**Dove trovarle:**

Le credenziali generate vengono mostrate **UNA SOLA VOLTA** nei log di avvio dell'applicazione. Cerca nel log un blocco simile a questo:

```
======================================================================
NO SUPERADMIN CREDENTIALS PROVIDED IN ENV!
Generated Super Admin credentials:
  Email: admin@sonacip.local
  Password: aB3#xY9$mK2@pL5!
COPY THESE CREDENTIALS NOW - They will not be shown again!
Set SUPERADMIN_EMAIL and SUPERADMIN_PASSWORD in .env to customize.
======================================================================
```

**Come visualizzare i log:**

- **METODO FACILE: Usa lo script automatico** (raccomandato):
  ```bash
  python recupera_credenziali.py
  ```
  Questo script cerca automaticamente le credenziali in tutti i possibili file di log.

- **Se stai usando systemd** (installazione VPS):
  ```bash
  sudo journalctl -u sonacip -n 100 | grep -A 5 "Generated Super Admin"
  ```

- **Se stai usando Gunicorn direttamente**:
  ```bash
  # Controlla il file di log
  cat logs/sonacip.log | grep -A 5 "Generated Super Admin"
  ```

- **Se stai usando il file di output**:
  ```bash
  # Se hai rediretto l'output durante l'avvio
  cat /var/log/sonacip/startup.log | grep -A 5 "Generated Super Admin"
  ```

## 🆘 Ho perso le credenziali generate, cosa faccio?

Se hai perso le credenziali generate automaticamente e non riesci più ad accedere, hai due opzioni:

### Opzione A: Reimpostare le credenziali tramite variabili d'ambiente

1. Ferma l'applicazione:
   ```bash
   sudo systemctl stop sonacip  # se usi systemd
   # oppure
   pkill -f gunicorn  # se usi gunicorn direttamente
   ```

2. Aggiungi le credenziali desiderate nel file `.env`:
   ```bash
   SUPERADMIN_EMAIL=tuanuovaemail@esempio.it
   SUPERADMIN_PASSWORD=NuovaPasswordSicura123!
   ```

3. Riavvia l'applicazione:
   ```bash
   sudo systemctl start sonacip  # se usi systemd
   # oppure
   gunicorn wsgi:app  # se usi gunicorn direttamente
   ```

L'applicazione aggiornerà automaticamente la password del Super Admin esistente con quella specificata in `.env`.

### Opzione B: Reimpostare il database (ATTENZIONE: cancella tutti i dati)

**⚠️ ATTENZIONE: Questa operazione cancellerà TUTTI i dati!**

```bash
# Backup del database esistente (raccomandato)
cp sonacip.db sonacip.db.backup

# Rimuovi il database
rm sonacip.db

# Imposta le nuove credenziali
export SUPERADMIN_EMAIL="tuaemail@esempio.it"
export SUPERADMIN_PASSWORD="TuaPasswordSicura123!"

# Reinizializza il database
python init_db.py

# Riavvia l'applicazione
sudo systemctl restart sonacip
```

## 🔒 Best Practices per la Sicurezza

1. **Imposta sempre credenziali personalizzate in produzione**
   - Non affidarti mai alle credenziali generate automaticamente in produzione
   - Usa password forti (minimo 12 caratteri, miste maiuscole/minuscole/numeri/simboli)

2. **Cambia la password dopo il primo accesso**
   - Accedi con le credenziali iniziali
   - Vai in "Profilo" → "Cambia Password"
   - Imposta una nuova password sicura

3. **Non condividere le credenziali**
   - Le credenziali del Super Admin sono estremamente sensibili
   - Non condividerle via email, chat, o altri canali non sicuri
   - Usa un password manager per conservarle in modo sicuro

4. **Abilita l'autenticazione a due fattori (se disponibile)**
   - Controlla se l'applicazione supporta 2FA
   - Abilitalo per il tuo account Super Admin

5. **Monitora gli accessi**
   - Controlla regolarmente i log di accesso nel pannello admin
   - Verifica che non ci siano accessi sospetti

## 📋 Credenziali di Default per Ambiente di Test

**⚠️ SOLO PER AMBIENTI DI SVILUPPO/TEST - MAI IN PRODUZIONE!**

Se stai testando in locale e vuoi usare credenziali semplici:

```bash
# Nel file .env o come variabili d'ambiente
SUPERADMIN_EMAIL=admin@test.local
SUPERADMIN_PASSWORD=test123
```

**Ricorda:** Queste credenziali sono insicure e devono essere usate SOLO in ambienti di sviluppo isolati.

## 📞 Supporto

Se hai ancora problemi ad accedere:

1. Controlla i log dell'applicazione per errori
2. Verifica che il file `.env` sia nella directory corretta
3. Assicurati che le variabili d'ambiente siano caricate correttamente
4. Consulta la documentazione completa in `README.md`

---

**SONACIP © 2026** - Gestione Sportiva Sicura e Professionale
