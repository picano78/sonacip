# 🔐 Come Accedere come Super Admin

Questa guida ti spiega in modo semplice e rapido come accedere a SONACIP come super amministratore.

## 🚀 Accesso Rapido (Prima Installazione)

### Passaggio 1: Crea il file di configurazione

```bash
# Copia il file di esempio con le credenziali predefinite
cp .env.example .env
```

Questo file `.env` contiene già le credenziali predefinite per lo sviluppo:
- **Email**: `Picano78@gmail.com`
- **Password**: `Simone78`

### Passaggio 2: Inizializza il database

```bash
python3 init_db.py
```

Vedrai un output simile a:
```
✓ Database connection verified
✓ Database schema created
✓ Seed completed
✓ Database initialized
```

### Passaggio 3: Avvia l'applicazione

```bash
python3 run.py
```

L'applicazione si avvierà sulla porta 5000.

### Passaggio 4: Accedi

1. Apri il browser e vai a: **http://localhost:5000/auth/login**
2. Inserisci le credenziali:
   - **Email**: `Picano78@gmail.com`
   - **Password**: `Simone78`
3. Clicca su "Accedi"

✅ **Fatto!** Ora sei loggato come super amministratore.

---

## 🔧 Risoluzione Problemi

### ❌ Problema: "Credenziali non valide"

**Soluzione 1** - Usa lo strumento di diagnosi:
```bash
python3 fix_admin_credentials.py
```

Se trova problemi, esegui:
```bash
python3 fix_admin_credentials.py --fix
```

**Soluzione 2** - Verifica il file .env:
```bash
# Assicurati che il file .env esista
ls -la .env

# Verifica il contenuto
cat .env | grep SUPERADMIN
```

Se il file `.env` non esiste o è vuoto, ricrea lo:
```bash
cp .env.example .env
```

### ❌ Problema: "Database non trovato" o errori di tabelle mancanti

**Soluzione**:
```bash
python3 init_db.py
```

### ❌ Problema: Ho dimenticato le credenziali

Se hai modificato le credenziali e le hai dimenticate:

**Opzione A** - Ripristina le credenziali predefinite:
```bash
# Ricopia il file di esempio
cp .env.example .env

# Aggiorna le credenziali nel database
python3 fix_admin_credentials.py --fix
```

**Opzione B** - Imposta nuove credenziali personalizzate:
```bash
# Modifica il file .env con le tue nuove credenziali
nano .env  # o usa il tuo editor preferito

# Aggiorna nel database
python3 fix_admin_credentials.py --fix --email tuaemail@esempio.it --password TuaNuovaPassword123
```

### ❌ Problema: Le credenziali erano generate automaticamente

Se all'avvio hai visto un messaggio del tipo:
```
NO SUPERADMIN CREDENTIALS PROVIDED!
Generated Super Admin credentials:
  Email: admin@sonacip.local
  Password: aB3#xY9$...
```

Puoi recuperarle con:
```bash
# Usa lo script automatico
python3 recupera_credenziali.py

# Oppure cerca nei log
cat logs/sonacip.log | grep -A 5 "Generated Super Admin"
```

---

## ⚙️ Configurazione Avanzata

### Personalizzare le Credenziali

Per usare credenziali personalizzate invece di quelle predefinite:

1. Modifica il file `.env`:
   ```bash
   nano .env
   ```

2. Cambia le seguenti righe:
   ```env
   SUPERADMIN_EMAIL=tuaemail@tuodominio.it
   SUPERADMIN_PASSWORD=TuaPasswordSicura123!
   ```

3. Se il database esiste già, aggiorna le credenziali:
   ```bash
   python3 fix_admin_credentials.py --fix --email tuaemail@tuodominio.it --password TuaPasswordSicura123!
   ```

4. Riavvia l'applicazione:
   ```bash
   # Ferma (Ctrl+C se in esecuzione)
   # Poi riavvia
   python3 run.py
   ```

### Verifica dello Stato

Per verificare che tutto sia configurato correttamente:
```bash
# Verifica le credenziali nel database
python3 fix_admin_credentials.py

# Output atteso:
# ✅ DIAGNOSIS: Everything looks good!
```

---

## 🔒 Sicurezza - IMPORTANTE

### ⚠️ Solo per Sviluppo

Le credenziali predefinite (`Picano78@gmail.com` / `Simone78`) sono:
- **SOLO PER SVILUPPO LOCALE**
- **MAI DA USARE IN PRODUZIONE**
- Facilmente indovinabili e pubblicamente documentate

### ✅ Per Produzione

Se stai installando SONACIP su un server di produzione:

1. **PRIMA di inizializzare il database**, modifica il file `.env` con credenziali sicure:
   ```env
   SUPERADMIN_EMAIL=admin@ilmiodominio.it
   SUPERADMIN_PASSWORD=UnaPasswordMoltoSicura123!@#
   ```

2. Usa una password forte:
   - Minimo 12 caratteri
   - Lettere maiuscole e minuscole
   - Numeri
   - Caratteri speciali

3. **Cambia immediatamente la password** dopo il primo accesso:
   - Accedi come super admin
   - Vai su "Profilo" → "Impostazioni" → "Cambia Password"

4. Proteggi il file `.env`:
   ```bash
   chmod 600 .env
   ```

---

## 📚 Documentazione Aggiuntiva

Per maggiori informazioni, consulta:

- **FAQ_CREDENZIALI_ADMIN.md** - FAQ complete sulle credenziali
- **SUPER_ADMIN_LOGIN_FIX.md** - Dettagli tecnici sulla correzione del login
- **ADMIN_LOGIN.md** - Documentazione generale sul login admin (inglese)
- **README.md** - Documentazione principale del progetto

---

## 🆘 Hai Ancora Problemi?

Se hai seguito tutti i passaggi e ancora non riesci ad accedere:

1. **Verifica i log dell'applicazione**:
   ```bash
   tail -f logs/sonacip.log
   ```

2. **Esegui una diagnosi completa**:
   ```bash
   python3 fix_admin_credentials.py 2>&1 | tee diagnostica.txt
   ```

3. **Controlla lo stato del database**:
   ```bash
   ls -lh sonacip.db
   # oppure
   ls -lh uploads/sonacip.db
   ```

4. **Verifica che Flask sia installato**:
   ```bash
   python3 -c "import flask; print('Flask OK')"
   ```

5. **Reinstalla le dipendenze** se necessario:
   ```bash
   pip3 install -r requirements.txt
   ```

---

## ✨ Riepilogo Comandi Rapidi

```bash
# Setup iniziale completo
cp .env.example .env
python3 init_db.py
python3 run.py

# Accedi a: http://localhost:5000/auth/login
# Email: Picano78@gmail.com
# Password: Simone78

# Se hai problemi
python3 fix_admin_credentials.py --fix

# Per recuperare credenziali generate
python3 recupera_credenziali.py
```

---

**Ultima modifica**: Febbraio 2026  
**Versione SONACIP**: 2.0
