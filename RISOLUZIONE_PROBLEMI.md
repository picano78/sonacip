# RISOLUZIONE PROBLEMI SONACIP - Riepilogo

## Problemi Risolti ✅

### PROBLEMA 1 — DuplicateTable

**Errore originale:**
```
psycopg2.errors.DuplicateTable: relation "permission" already exists
```

**Causa:** 
Le tabelle venivano create con `db.create_all()` durante l'avvio dell'app, e poi Alembic provava a ricrearle con `flask db upgrade`.

**Soluzione implementata:**
1. Modificato `init_db.py` per verificare se le tabelle esistono già prima di eseguire le migrazioni
2. Aggiunto supporto specifico per SQLite (usa `create_all()`) e PostgreSQL (usa Alembic)
3. Aggiunta variabile d'ambiente `SKIP_AUTO_SEED` per evitare seeding duplicato
4. Messaggi informativi chiari sullo stato del database

**Risultato:**
- ✅ Nessun errore DuplicateTable
- ✅ Inizializzazione pulita per database nuovi
- ✅ Gestione corretta di database esistenti
- ✅ Guida per aggiornamenti schema: `flask db upgrade`

### PROBLEMA 2 — is_superadmin non esiste

**Errore menzionato:**
```
AttributeError: type object 'User' has no attribute 'is_superadmin'
```

**Analisi:**
- ✅ Il modello User NON ha (e non dovrebbe avere) `is_superadmin`
- ✅ SONACIP usa correttamente un sistema basato sui ruoli
- ✅ Il super admin è identificato dal ruolo `super_admin`, non da un boolean

**Credenziali fisse configurate:**
- **Email:** `Picano78@gmail.com`
- **Password:** `Simone78`

**Verifica:**
```python
# Il super admin viene creato automaticamente con:
admin.email = "Picano78@gmail.com"
admin.role = "super_admin"  # NON is_superadmin=True
admin.is_admin() == True    # Metodo basato sul ruolo
```

## File Modificati

1. **`init_db.py`**
   - Aggiunta logica intelligente per rilevare stato database
   - Gestione differenziata SQLite/PostgreSQL
   - Prevenzione errori DuplicateTable

2. **`app/__init__.py`**
   - Supporto per `SKIP_AUTO_SEED` environment variable
   - Migliore coordinazione tra auto-seed e init_db

3. **`tests/test_admin_login.py`** (nuovo)
   - 7 test completi per autenticazione
   - Verifica credenziali fisse
   - Verifica sistema basato su ruoli
   - Tutti i test passano ✅

4. **`ADMIN_LOGIN.md`** (nuovo)
   - Documentazione completa credenziali admin
   - Guida utilizzo e troubleshooting
   - Avvertenze sicurezza per produzione

## Test di Verifica

Tutti i test passano con successo:

```bash
✓ 7 tests passed
✓ Database initialization - no warnings
✓ Re-running init_db - graceful handling
✓ Super admin created correctly
✓ Login works: Picano78@gmail.com / Simone78
✓ Role-based system verified
✓ No is_superadmin attribute
```

## Come Usare

### Prima volta (nuovo database):
```bash
python3 init_db.py
```

### Login nell'applicazione:
```
Email: Picano78@gmail.com
Password: Simone78
```

### Aggiornare schema esistente:
```bash
flask db upgrade
```

### Verificare credenziali:
```python
from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    admin = User.query.filter_by(email='Picano78@gmail.com').first()
    print(f"Role: {admin.role}")
    print(f"Password OK: {admin.check_password('Simone78')}")
```

## Note di Sicurezza

⚠️ **IMPORTANTE PER PRODUZIONE:**

Le credenziali `Picano78@gmail.com` / `Simone78` sono configurate per ambienti di sviluppo/test.

In produzione, **DEVI** impostare credenziali personalizzate tramite variabili d'ambiente:

```bash
export SUPERADMIN_EMAIL="tua-email@dominio.it"
export SUPERADMIN_PASSWORD="password-sicura"
```

## Riepilogo Sistema Ruoli

SONACIP usa un sistema basato su ruoli, non su flag booleani:

- `super_admin` - Accesso completo (livello 100)
- `admin` - Amministratore (livello 90)
- `society_admin` - Admin società (livello 45)
- `societa` - Società sportiva (livello 40)
- `staff` / `coach` - Staff/allenatore (livello 30)
- `atleta` / `athlete` - Atleta (livello 20)
- `appassionato` / `user` - Utente standard (livello 10)

## Conclusione

✅ Entrambi i problemi sono stati risolti:

1. **DuplicateTable**: Eliminato tramite logica intelligente in `init_db.py`
2. **Credenziali Super Admin**: Verificate e funzionanti con sistema basato su ruoli

Il sistema è pronto per l'uso con le credenziali fisse richieste.
