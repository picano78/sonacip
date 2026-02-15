# Sistema di Gestione Moduli

## Panoramica
Il sistema di gestione moduli permette agli amministratori di caricare, attivare e gestire aggiornamenti e estensioni del sistema in modo modulare.

## Caratteristiche Principali

### 1. Caricamento Moduli
- Supporto per file ZIP contenenti moduli di sistema
- Validazione del tipo di file (solo ZIP)
- Metadati del modulo (nome, versione, descrizione)
- Tracciamento dell'utente che ha caricato il modulo

### 2. Gestione Moduli
- **Attivazione/Disattivazione**: I moduli possono essere attivati o disattivati senza eliminarli
- **Download**: Possibilità di scaricare i moduli caricati
- **Eliminazione**: Rimozione completa del modulo e del file associato
- **Cronologia**: Tracciamento delle date di caricamento, attivazione e disattivazione

### 3. Sicurezza
- Accesso limitato agli amministratori (`@admin_required`)
- Validazione sicura dei nomi dei file con `secure_filename()`
- Protezione CSRF su tutti i form
- Scansione di sicurezza CodeQL: 0 vulnerabilità
- Audit logging per tutte le operazioni sui moduli

## Utilizzo

### Accesso all'Interfaccia
1. Accedi come amministratore
2. Vai su Admin > Gestione Moduli (`/admin/modules`)

### Caricare un Modulo
1. Clicca su "Carica Nuovo Modulo"
2. Inserisci:
   - Nome del modulo
   - Versione (es. "1.0.0")
   - Descrizione (opzionale)
   - File ZIP del modulo
3. Clicca su "Carica Modulo"
4. Il modulo verrà salvato ma **non attivato automaticamente**

### Attivare/Disattivare un Modulo
1. Nella lista moduli, trova il modulo desiderato
2. Clicca sul pulsante "Attiva" o "Disattiva"
3. Lo stato del modulo verrà aggiornato immediatamente

### Eliminare un Modulo
1. Nella lista moduli, trova il modulo da eliminare
2. Clicca sul pulsante di eliminazione (icona cestino)
3. Conferma l'eliminazione
4. Il modulo e il file associato verranno eliminati permanentemente

## Struttura dei File
- **Cartella moduli**: `/aggiornamento/`
- **Formato file**: Solo file ZIP
- **Database**: Tabella `system_module`

## Modello di Database

```python
class SystemModule(db.Model):
    id              # ID univoco
    name            # Nome del modulo
    version         # Versione (es. "1.0.0")
    filename        # Nome del file ZIP
    description     # Descrizione opzionale
    enabled         # Stato (attivo/disattivo)
    uploaded_by     # ID dell'utente che ha caricato
    uploaded_at     # Data e ora di caricamento
    enabled_at      # Data e ora di attivazione
    disabled_at     # Data e ora di disattivazione
```

## API Routes

| Route | Metodo | Descrizione |
|-------|--------|-------------|
| `/admin/modules` | GET | Lista tutti i moduli |
| `/admin/modules/upload` | GET/POST | Form di caricamento modulo |
| `/admin/modules/<id>/toggle` | POST | Attiva/disattiva modulo |
| `/admin/modules/<id>/delete` | POST | Elimina modulo |
| `/admin/modules/<id>/download` | GET | Scarica file modulo |

## Note Importanti

⚠️ **Attenzioni**:
- I moduli vengono salvati ma NON attivati automaticamente
- Verifica la compatibilità dei moduli prima di attivarli
- I moduli disattivati non vengono caricati all'avvio del sistema
- L'eliminazione di un modulo è permanente

✅ **Best Practices**:
- Usa un naming consistente per i moduli (es. "modulo-nome")
- Segui il semantic versioning (major.minor.patch)
- Includi una descrizione chiara delle funzionalità
- Testa i moduli in ambiente di sviluppo prima della produzione
- Mantieni backup dei moduli importanti

## Test

Il sistema include test automatizzati per:
- Creazione del modello SystemModule
- Attivazione/disattivazione moduli
- Eliminazione moduli
- Verifica assenza errori 500/503

Per eseguire i test:
```bash
python3 -m pytest tests/test_system_module_model.py -v
python3 -m pytest tests/test_routes_no_500.py -v
```

## Sviluppo Futuro

Possibili miglioramenti:
- [ ] Validazione contenuto ZIP
- [ ] Rollback automatico in caso di errori
- [ ] Versioning e gestione conflitti
- [ ] Auto-update da repository esterni
- [ ] Dashboard statistiche utilizzo moduli
- [ ] Sistema di dipendenze tra moduli
