# Guida di Migrazione - Rimozione Credenziali Hardcoded

## Panoramica

Questa guida descrive le modifiche apportate per rimuovere le credenziali hardcoded dal codice sorgente di SONACIP e come aggiornare i deployment esistenti.

## Modifiche Implementate

### 1. Credenziali Super Admin

**Prima:** Le credenziali di default erano hardcoded nel codice:
```python
# app/core/config.py
_default_admin_email = 'Picano78@gmail.com'
_default_admin_password = 'Simone78'
```

**Dopo:** Le credenziali DEVONO essere configurate tramite variabili ambiente:
```python
# app/core/config.py
SUPERADMIN_EMAIL = os.environ.get('SUPERADMIN_EMAIL')
SUPERADMIN_PASSWORD = os.environ.get('SUPERADMIN_PASSWORD')
```

### 2. Validazione in Produzione

**Prima:** L'applicazione mostrava solo un warning se venivano usate credenziali di default in produzione.

**Dopo:** L'applicazione **non si avvia** in modalità produzione se le credenziali non sono configurate, prevenendo deployment insicuri.

## Azioni Richieste per Deployment Esistenti

### Sviluppo Locale

1. Copia `.env.example` in `.env` se non l'hai già fatto:
   ```bash
   cp .env.example .env
   ```

2. Modifica `.env` e imposta le tue credenziali di sviluppo:
   ```bash
   SUPERADMIN_EMAIL=admin@localhost
   SUPERADMIN_PASSWORD=DevPassword123!
   ```

3. Riavvia l'applicazione.

### Produzione

⚠️ **ATTENZIONE:** Queste modifiche richiedono azione immediata per i deployment in produzione!

1. **Prima di aggiornare il codice**, assicurati di avere credenziali sicure pronte:
   ```bash
   # Genera una password sicura
   python3 -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits + string.punctuation) for _ in range(20)))"
   ```

2. Imposta le variabili ambiente nel tuo sistema di deployment:

   **Opzione A - File .env (sconsigliato per produzione):**
   ```bash
   # .env (NON committare questo file!)
   SUPERADMIN_EMAIL=admin@tuodominio.it
   SUPERADMIN_PASSWORD=Una!Password1Molto2Sicura3E4Lunga
   ```

   **Opzione B - Variabili ambiente di sistema (consigliato):**
   ```bash
   export SUPERADMIN_EMAIL='admin@tuodominio.it'
   export SUPERADMIN_PASSWORD='Una!Password1Molto2Sicura3E4Lunga'
   ```

   **Opzione C - Systemd service file:**
   ```ini
   [Service]
   Environment="SUPERADMIN_EMAIL=admin@tuodominio.it"
   Environment="SUPERADMIN_PASSWORD=Una!Password1Molto2Sicura3E4Lunga"
   ```

   **Opzione D - Docker/Container:**
   ```bash
   docker run -e SUPERADMIN_EMAIL='admin@tuodominio.it' \
              -e SUPERADMIN_PASSWORD='Una!Password1Molto2Sicura3E4Lunga' \
              ...
   ```

3. Verifica che le variabili siano impostate:
   ```bash
   echo $SUPERADMIN_EMAIL
   echo $SUPERADMIN_PASSWORD
   ```

4. Aggiorna il codice:
   ```bash
   git pull origin main  # o il tuo branch di produzione
   ```

5. Riavvia l'applicazione:
   ```bash
   sudo systemctl restart sonacip  # o il tuo metodo di riavvio
   ```

6. Verifica che l'applicazione si sia avviata correttamente:
   ```bash
   sudo systemctl status sonacip
   tail -f /path/to/logs/sonacip.log
   ```

## Comportamento in Caso di Credenziali Mancanti

### In Sviluppo (APP_ENV=development o FLASK_ENV=development)

Se le variabili `SUPERADMIN_EMAIL` e `SUPERADMIN_PASSWORD` non sono impostate:
- L'applicazione genererà credenziali casuali sicure
- Le credenziali generate verranno mostrate nei log **una sola volta**
- Dovrai copiare queste credenziali immediatamente per accedere

### In Produzione (APP_ENV=production o FLASK_ENV=production)

Se le variabili `SUPERADMIN_EMAIL` e `SUPERADMIN_PASSWORD` non sono impostate:
- L'applicazione **terminerà con un errore** e non si avvierà
- Verrà mostrato un messaggio di errore chiaro con istruzioni
- Questo previene deployment insicuri

## Backward Compatibility

Queste modifiche **NON sono** completamente backward compatible:

- ✅ **Deployment con .env configurato:** Continueranno a funzionare senza modifiche
- ❌ **Deployment che usavano credenziali hardcoded:** Richiederanno configurazione delle variabili ambiente
- ❌ **Deployment in produzione senza .env:** Non si avvieranno fino alla configurazione

## Checklist Pre-Deployment

Prima di aggiornare la produzione, verifica:

- [ ] Hai credenziali sicure pronte (email e password forte)
- [ ] Sai come impostare le variabili ambiente nel tuo sistema
- [ ] Hai testato la configurazione in un ambiente di staging/test
- [ ] Hai un piano di rollback in caso di problemi
- [ ] Hai accesso ai log per verificare l'avvio corretto
- [ ] Hai documentato le nuove credenziali in modo sicuro (password manager)

## Domande Frequenti

### Q: Posso usare le vecchie credenziali di default?
**A:** No, le credenziali hardcoded sono state rimosse per motivi di sicurezza. Devi impostare le tue credenziali tramite variabili ambiente.

### Q: Cosa succede se dimentico di impostare le variabili?
**A:** 
- In sviluppo: Verranno generate credenziali casuali mostrate nei log
- In produzione: L'applicazione non si avvierà

### Q: Come cambio le credenziali dopo il primo avvio?
**A:**
1. Accedi con le credenziali attuali
2. Vai al pannello admin > Profilo utente
3. Cambia la password dall'interfaccia
4. Aggiorna la variabile `SUPERADMIN_PASSWORD` nel tuo sistema

### Q: Le credenziali esistenti nel database saranno invalidate?
**A:** No, le modifiche riguardano solo la configurazione iniziale. Gli utenti e le password esistenti nel database rimarranno invariati.

### Q: Devo rigenerare il database?
**A:** No, non è necessario. Il database esistente continuerà a funzionare normalmente.

## Supporto

Per problemi o domande:
1. Controlla i log dell'applicazione
2. Verifica che le variabili ambiente siano impostate correttamente
3. Consulta la documentazione in README.md
4. Apri un issue su GitHub se il problema persiste

## Cronologia Modifiche

- **2026-02-15**: Rimozione credenziali hardcoded da config.py e seed.py
- **2026-02-15**: Aggiunta validazione obbligatoria in produzione
- **2026-02-15**: Aggiornamento .env.example con placeholder sicuri
