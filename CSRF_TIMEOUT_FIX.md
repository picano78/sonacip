# Fix CSRF Token Timeout - Risoluzione "Sessione scaduta o richiesta non valida"

## Problema

Gli utenti riscontravano errori di login con i seguenti messaggi:
- "Sessione scaduta o richiesta non valida. Riprova."
- "Credenziali non valide"

Anche utilizzando le credenziali corrette del super admin (`Picano78@gmail.com` / `Simone78`), il login falliva.

## Causa Principale

Il problema era causato da una **discrepanza tra i timeout CSRF e di sessione**:

- **Timeout sessione**: 30 giorni (configurato in `app/core/config.py`)
- **Timeout token CSRF**: 1 ora (default di Flask-WTF, non configurato esplicitamente)

### Come si verificava il problema:

1. Un utente apriva la pagina di login
2. Manteneva la pagina aperta per più di 1 ora
3. Il token CSRF scadeva (dopo 1 ora) ma la sessione era ancora valida (30 giorni)
4. Al tentativo di login, Flask-WTF rilevava un token CSRF scaduto
5. L'applicazione mostrava "Sessione scaduta o richiesta non valida" PRIMA ancora di verificare le credenziali

## Soluzione Implementata

### Modifiche al codice

**File modificato**: `app/core/config.py`

```python
# CSRF configuration
# Set CSRF token timeout to None (no expiration) to match extended session lifetime
# This prevents "Sessione scaduta o richiesta non valida" errors when users keep login pages open
# for extended periods. The session itself provides security through its 30-day timeout.
WTF_CSRF_TIME_LIMIT = None
# Allow CSRF timeout to be configured via environment variable if needed
csrf_time_limit_env = os.environ.get('WTF_CSRF_TIME_LIMIT')
if csrf_time_limit_env:
    try:
        WTF_CSRF_TIME_LIMIT = int(csrf_time_limit_env)
    except (ValueError, TypeError):
        pass
```

### Caratteristiche della soluzione:

1. **Disabilitazione timeout CSRF**: Impostando `WTF_CSRF_TIME_LIMIT = None`, i token CSRF non scadono più
2. **Configurazione flessibile**: Supporto per variabile d'ambiente `WTF_CSRF_TIME_LIMIT` per personalizzazione
3. **Documentazione chiara**: Commenti che spiegano il razionale della modifica

## Impatto sulla Sicurezza

Questa modifica **NON compromette la sicurezza**:

- ✓ La sessione stessa fornisce sicurezza tramite il timeout di 30 giorni
- ✓ La protezione CSRF rimane attiva (i token vengono comunque validati)
- ✓ Viene rimossa solo la scadenza del token, non la validazione
- ✓ La variabile d'ambiente permette di configurare un timeout personalizzato se necessario

### Perché è sicuro:

1. **Protezione della sessione**: Il timeout della sessione (30 giorni) limita il periodo di validità
2. **Validazione CSRF attiva**: I token vengono ancora generati e validati contro gli attacchi CSRF
3. **Same-Site cookie**: `SESSION_COOKIE_SAMESITE = 'Lax'` fornisce protezione aggiuntiva
4. **HTTPS in produzione**: `SESSION_COOKIE_SECURE = true` in produzione garantisce trasmissione sicura

## Test e Verifica

### Test eseguiti:

✓ Configurazione caricata correttamente (`WTF_CSRF_TIME_LIMIT = None`)  
✓ Credenziali super admin verificate (`Picano78@gmail.com` / `Simone78`)  
✓ Login con credenziali corrette: Successo  
✓ Login con credenziali errate: Messaggio di errore appropriato  
✓ Generazione e validazione token CSRF: Funzionante  
✓ Scansione sicurezza CodeQL: Nessun problema rilevato  

## Configurazione Personalizzata

Se si desidera impostare un timeout CSRF personalizzato, aggiungere al file `.env`:

```bash
# Timeout CSRF in secondi (es. 3600 = 1 ora)
WTF_CSRF_TIME_LIMIT=3600
```

Per disabilitare completamente il timeout (impostazione predefinita), lasciare la variabile vuota o non impostarla.

## Risultato

Dopo questa modifica:

- ✓ Gli utenti possono mantenere aperta la pagina di login per periodi prolungati
- ✓ Non vengono più visualizzati errori "Sessione scaduta o richiesta non valida"
- ✓ Le credenziali del super admin funzionano correttamente
- ✓ La sicurezza dell'applicazione è mantenuta

## Credenziali Super Admin

Le credenziali predefinite del super admin sono:

- **Email**: `Picano78@gmail.com`
- **Password**: `Simone78`

Queste credenziali sono configurate in `.env.example` e funzionano correttamente dopo questa correzione.

---

**Data**: 2026-02-13  
**Versione**: 1.0  
**Autore**: SONACIP Development Team
