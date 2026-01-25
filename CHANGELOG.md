# CHANGELOG

Tutti i cambiamenti significativi di SONACIP saranno documentati in questo file.

## [2.0.0] - 2026-01-24 - CONSOLIDAMENTO E POTENZIAMENTO COMPLETO

### 🎉 Aggiunte Principali

#### Nuovi Modelli Database
- **Role**: Sistema ruoli avanzato con livelli gerarchici
- **Permission**: Permessi granulari per RBAC
- **Plan**: Piani di sottoscrizione SaaS (Free, Basic, Professional, Enterprise)
- **Subscription**: Gestione abbonamenti utenti
- **Payment**: Tracciamento transazioni e pagamenti
- **Society**: Profilo esteso per società sportive

#### Nuovo Blueprint: Subscription
- `/subscription/plans` - Visualizzazione piani
- `/subscription/subscribe/<plan_id>` - Sottoscrizione
- `/subscription/my-subscription` - Dashboard personale
- `/subscription/cancel/<id>` - Cancellazione abbonamento
- `/subscription/payment/<id>` - Gestione pagamenti
- `/subscription/admin/*` - Amministrazione piani e pagamenti

#### Sistema Inizializzazione Database
- `init_roles()` - Crea 5 ruoli base del sistema
- `init_permissions()` - Crea 17 permessi categorizzati
- `init_plans()` - Crea 4 piani di sottoscrizione
- `create_super_admin()` - Crea automaticamente Super Admin

#### Nuovi Metodi Modello User
- `has_permission(resource, action)` - Controllo permessi
- `get_active_subscription()` - Ottieni abbonamento attivo
- `has_feature(feature_name)` - Verifica feature del piano
- `can_add_athlete()` - Controlla limiti piano

#### Nuovi Decoratori e Utilities
- `@permission_required(resource, action)` - Richiede permesso specifico
- `@feature_required(feature)` - Richiede feature del piano
- `safe_get_or_404()` - Get sicuro con fallback
- `log_action()` - Logging automatico azioni

#### Sistema Notifiche Potenziato
- `notify_user()` - Notifica singolo utente
- `notify_followers()` - Notifica tutti i follower
- `notify_society_members()` - Notifica membri società
- `get_unread_count()` - Conta notifiche non lette
- `cleanup_old_notifications()` - Pulizia automatica

#### Template
- `subscription/plans.html` - Card responsive piani
- `subscription/my_subscription.html` - Dashboard abbonamento

#### Scripts e Documentazione
- `create_test_users.py` - Popolazione database test
- `CONSOLIDAMENTO.md` - Documentazione tecnica completa

### 🔧 Correzioni

#### Bug Critici Risolti
- ✅ **SQLAlchemy Reserved Word**: Rinominato campo `metadata` → `payment_metadata` in model Payment
- ✅ **String Escaping**: Corretti errori escape caratteri in admin/routes.py
- ✅ **Permission NOT NULL**: Aggiunto campo `name` obbligatorio in Permission con valori univoci
- ✅ **Database Initialization**: Sequenza corretta di creazione tabelle e dati base

#### Miglioramenti Stabilità
- Gestione errori con try/except su:
  - Admin statistics queries
  - Social feed generation
  - CRM value calculations
  - Top users/societies queries
- Fallback sicuri in caso di errori database
- Validazione input robusta

### 🚀 Miglioramenti

#### Architettura
- Application Factory Pattern preservato
- Blueprint structure estesa e coerente
- Single entry point mantenuto (run.py)
- Migration-ready con Flask-Migrate

#### Sicurezza
- RBAC completo implementato
- 17 permessi base categorizzati
- Audit logging su azioni critiche
- Session management sicuro

#### SaaS Features
- Multi-tenant architecture ready
- 4 piani subscription predefiniti
- Feature flags per piano
- Usage limits enforcement
- Payment tracking completo

#### Developer Experience
- Codice ben documentato
- Error handling robusto
- Helper functions riutilizzabili
- Test users creation script

### 📊 Statistiche Progetto

- **Modelli Database**: 16 totali (6 nuovi)
- **Blueprints**: 8 totali (1 nuovo)
- **Ruoli Sistema**: 5
- **Permessi**: 17
- **Piani Disponibili**: 4
- **Routes Totali**: ~80+

### ⚠️ Breaking Changes

Nessun breaking change - tutti i moduli esistenti sono compatibili.

### 🔄 Migrations Required

Eseguire dopo l'aggiornamento:
```bash
# Backup database esistente
python -c "from app.backup.utils import create_backup; create_backup(1, 'full', 'Pre-upgrade backup')"

# Eliminare vecchio database (se necessario)
rm sonacip.db

# Avviare app per auto-initialization
flask --app run run
```

### 📝 Note di Upgrade

1. **Database Reset Raccomandato**: Per beneficiare di tutti i nuovi modelli
2. **Password Admin**: Impostare `SUPERADMIN_PASSWORD` prima del primo avvio e ruotare la password dopo il primo accesso
3. **Secret Key**: Impostare SECRET_KEY sicura in produzione
4. **Email Config**: Configurare SMTP per notifiche email

### 🎯 Prossimi Passi Consigliati

1. **Payment Gateway Integration**
   - Stripe API
   - PayPal integration
   - Bonifico bancario

2. **API REST**
   - Endpoint pubblici documentati
   - API keys per integrations
   - Rate limiting

3. **Advanced Features**
   - Real-time chat
   - Mobile app (React Native)
   - Calendar sync
   - Advanced analytics

4. **Performance**
   - Redis caching
   - CDN integration
   - Query optimization
   - Background tasks (Celery)

---

## [1.0.0] - 2025-12-15 - RELEASE INIZIALE

### Aggiunte
- Sistema base Flask con blueprints
- Modelli core: User, Post, Comment, Event
- Autenticazione e autorizzazione
- Social network features
- CRM base
- Event management
- Backup system
- Admin panel

---

## Formato Versioning

Questo progetto segue [Semantic Versioning](https://semver.org/):
- MAJOR: Breaking changes
- MINOR: Nuove features backwards-compatible
- PATCH: Bug fixes

## Tipi di Cambiamenti

- **Aggiunte**: Nuove features
- **Modifiche**: Changes in existing functionality
- **Deprecazioni**: Features che saranno rimosse
- **Rimozioni**: Features rimosse
- **Correzioni**: Bug fixes
- **Sicurezza**: Security fixes
