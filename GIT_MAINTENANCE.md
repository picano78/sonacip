# Manutenzione Repository Git / Git Repository Maintenance

Questo documento spiega come mantenere pulito il repository Git del progetto SONACIP, rimuovendo rami sospesi (dangling branches) e oggetti non raggiungibili.

This document explains how to keep the SONACIP project Git repository clean by removing dangling branches and unreachable objects.

## 🧹 Pulizia Automatica / Automatic Cleanup

Il progetto include uno script automatico per la pulizia del repository:

The project includes an automatic script for repository cleanup:

```bash
./scripts/git_cleanup.sh
```

### 🧪 Test Suite / Testing

Per verificare che lo script funzioni correttamente, esegui la suite di test automatica:

To verify that the script works correctly, run the automated test suite:

```bash
./scripts/test_git_cleanup.sh
```

Lo script esegue le seguenti operazioni / The script performs the following operations:

1. **Elenca rami locali e remoti** / Lists local and remote branches
2. **Identifica rami merged** / Identifies merged branches
3. **Cerca oggetti sospesi** / Searches for dangling objects
4. **Esegue garbage collection** / Runs garbage collection
5. **Verifica integrità del repository** / Verifies repository integrity
6. **Mostra statistiche** / Shows statistics

## 🔍 Cosa sono i "Rami Sospesi"? / What are "Dangling Branches"?

I rami sospesi (dangling branches) sono riferimenti Git che puntano a commit non più raggiungibili dalla storia principale del repository. Possono verificarsi quando:

Dangling branches are Git references that point to commits no longer reachable from the main repository history. They can occur when:

- Un ramo viene eliminato ma i suoi commit rimangono nel database
  - A branch is deleted but its commits remain in the database
- Viene eseguito un rebase che scarta alcuni commit
  - A rebase is performed that discards some commits
- Viene eseguito un reset che sposta il puntatore del ramo
  - A reset is performed that moves the branch pointer

## 🛠️ Comandi Manuali / Manual Commands

### Pulizia Oggetti Sospesi / Cleanup Dangling Objects

```bash
# Trova oggetti sospesi / Find dangling objects
git fsck --dangling

# Garbage collection completo / Complete garbage collection
git gc --prune=now --aggressive

# Verifica integrità / Verify integrity
git fsck --full
```

### Gestione Rami / Branch Management

```bash
# Lista rami locali / List local branches
git branch -v

# Lista rami remoti / List remote branches
git branch -r

# Lista rami già merged / List merged branches
git branch --merged

# Elimina ramo locale / Delete local branch
git branch -d <nome-ramo>

# Forza eliminazione ramo locale / Force delete local branch
git branch -D <nome-ramo>

# Pulisci riferimenti a rami remoti eliminati / Clean references to deleted remote branches
git remote prune origin
```

### Verifica Stato Repository / Check Repository Status

```bash
# Conta oggetti nel repository / Count objects in repository
git count-objects -v

# Mostra dimensione del repository / Show repository size
du -sh .git

# Lista tutti i riferimenti / List all references
git show-ref
```

## 📅 Manutenzione Consigliata / Recommended Maintenance

Si consiglia di eseguire la pulizia del repository:

It is recommended to run repository cleanup:

- **Settimanalmente** durante lo sviluppo attivo
  - **Weekly** during active development
- **Dopo merge di grandi feature**
  - **After merging large features**
- **Prima di release importanti**
  - **Before important releases**
- **Quando il repository cresce significativamente**
  - **When the repository grows significantly**

## ⚠️ Precauzioni / Precautions

Prima di eseguire operazioni di pulizia:

Before running cleanup operations:

1. **Assicurati che tutti i cambiamenti siano committati**
   - Make sure all changes are committed
2. **Fai un backup se necessario** (il database è in `.git`)
   - Make a backup if necessary (the database is in `.git`)
3. **Verifica che non ci siano operazioni Git in corso**
   - Verify that no Git operations are in progress
4. **Non eliminare rami che potrebbero servire**
   - Don't delete branches that might be needed

## 🔒 Sicurezza / Safety

Le operazioni di garbage collection sono sicure e non eliminano:

Garbage collection operations are safe and don't delete:

- Commit raggiungibili da qualsiasi ramo o tag
  - Commits reachable from any branch or tag
- File nell'area di staging
  - Files in the staging area
- File modificati ma non committati (working directory)
  - Modified but uncommitted files (working directory)

## 📊 Interpretare i Risultati / Interpreting Results

### Output Garbage Collection

```
count: 0               # Oggetti sciolti (loose objects)
size: 0                # Dimensione oggetti sciolti
in-pack: 560          # Oggetti compressi nel pack
packs: 1              # Numero di pack files
size-pack: 2419       # Dimensione pack (KB)
prune-packable: 0     # Oggetti che possono essere eliminati
garbage: 0            # File garbage
```

### Segni di un Repository Sano / Signs of a Healthy Repository

✅ Nessun oggetto sospeso
   - No dangling objects

✅ `git fsck --full` completa senza errori
   - `git fsck --full` completes without errors

✅ Garbage collection riduce la dimensione del repository
   - Garbage collection reduces repository size

✅ Numero di pack files basso (idealmente 1)
   - Low number of pack files (ideally 1)

## 🆘 Risoluzione Problemi / Troubleshooting

### Repository Corrotto / Corrupted Repository

Se `git fsck` riporta errori:

If `git fsck` reports errors:

```bash
# Tenta di riparare / Attempt to repair
git fsck --full
git gc --aggressive

# Se non funziona, considera un clone fresco
# If it doesn't work, consider a fresh clone
cd ..
git clone https://github.com/picano78/sonacip.git sonacip-new
```

### Oggetti Non Raggiungibili Persistenti / Persistent Unreachable Objects

```bash
# Mostra oggetti non raggiungibili / Show unreachable objects
git fsck --unreachable

# Recupera un commit specifico / Recover a specific commit
git show <commit-hash>

# Se necessario, crea un nuovo ramo dal commit
# If needed, create a new branch from the commit
git branch recovery-branch <commit-hash>
```

## 📚 Risorse Aggiuntive / Additional Resources

- [Git Documentation - git-gc](https://git-scm.com/docs/git-gc)
- [Git Documentation - git-fsck](https://git-scm.com/docs/git-fsck)
- [Git Documentation - git-prune](https://git-scm.com/docs/git-prune)
