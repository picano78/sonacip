# Sistema di Fatturazione Automatica - SONACIP

## Panoramica

Il sistema di fatturazione automatica genera fatture elettroniche dopo ogni pagamento completato. Le fatture sono completamente configurabili dal super admin e scaricabili dagli utenti.

## Caratteristiche Principali

### 1. Generazione Automatica Fatture
- ✅ Generazione automatica dopo pagamento completato
- ✅ Collegamento con FeePayment
- ✅ Calcolo automatico IVA/Tax
- ✅ Numerazione progressiva fatture (formato: INV-2026-00001)

### 2. Pannello Configurazione Super Admin
**Percorso:** `/admin/invoice-settings`

Il super admin può configurare:

#### Informazioni Aziendali
- Nome azienda
- Indirizzo completo (via, città, CAP, paese)
- Partita IVA
- Codice Fiscale
- Telefono
- Email aziendale
- Sito web
- Logo aziendale (upload)

#### Impostazioni Fattura
- Prefisso numero fattura (default: INV)
- Aliquota IVA predefinita (default: 22% per Italia)
- Note piè di pagina
- Note aggiuntive

#### Fatturazione Elettronica
- Abilitazione fatturazione elettronica
- Selezione provider:
  - Fatture in Cloud
  - Aruba Fatturazione Elettronica
  - Personalizzato
- API Key e API Secret
- Company ID del provider
- Codice Destinatario SDI (7 caratteri)
- Email PEC

### 3. Sezione Utente - Le Mie Fatture
**Percorso:** `/payments/invoices`

Gli utenti possono:
- Visualizzare tutte le proprie fatture
- Vedere stato fattura (Pagata, Bozza, Inviata)
- Scaricare fatture in PDF
- Vedere dettagli (numero, data, importo, IVA)

### 4. Download PDF Fatture
**Percorso:** `/payments/invoice/<invoice_id>/download`

Le fatture PDF includono:
- Logo aziendale (se configurato)
- Intestazione con dati azienda
- Dati cliente
- Numero e data fattura
- Dettaglio importi (imponibile, IVA, totale)
- Note piè di pagina personalizzate
- Formattazione professionale

## Flusso di Lavoro

### Generazione Automatica

```
Pagamento Completato
    ↓
Webhook Stripe / Success Route
    ↓
generate_invoice_for_payment()
    ↓
Crea Invoice con:
  - Dati da InvoiceSettings
  - Calcolo IVA automatico
  - Numero progressivo
  - Link a FeePayment
    ↓
Salva in database
    ↓
Fattura disponibile per utente
```

### Download Fattura

```
Utente clicca "Scarica Fattura"
    ↓
Verifica permessi (owner o admin)
    ↓
Recupera InvoiceSettings
    ↓
Genera PDF con ReportLab
  - Header con logo
  - Dati azienda e cliente
  - Dettagli fattura
  - Totali
  - Footer personalizzato
    ↓
Invia PDF all'utente
```

## Modelli Database

### InvoiceSettings
```python
- id: Integer (PK)
- company_name: String(200)
- company_address: Text
- company_city: String(100)
- company_postal_code: String(20)
- company_country: String(100)
- company_vat: String(50)  # Partita IVA
- company_tax_code: String(50)  # Codice Fiscale
- company_phone: String(50)
- company_email: String(120)
- company_website: String(200)
- invoice_prefix: String(20)
- invoice_footer: Text
- invoice_notes: Text
- default_tax_rate: Float
- logo_path: String(500)
- enable_electronic_invoice: Boolean
- e_invoice_provider: String(50)
- e_invoice_api_key: String(500)
- e_invoice_api_secret: String(500)
- e_invoice_company_id: String(100)
- sdi_code: String(7)
- pec_email: String(120)
```

### Invoice (già esistente, esteso)
```python
- id: Integer (PK)
- invoice_number: String(50) UNIQUE
- payment_id: Integer (FK)
- fee_payment_id: Integer (FK)
- user_id: Integer (FK)
- society_id: Integer (FK)
- amount: Float
- tax_amount: Float
- total_amount: Float
- currency: String(3)
- billing_name: String(200)
- billing_address: Text
- billing_city: String(100)
- billing_postal_code: String(20)
- billing_country: String(100)
- tax_id: String(50)
- invoice_date: DateTime
- due_date: DateTime
- paid_date: DateTime
- status: String(20)
- description: Text
- notes: Text
- pdf_path: String(500)
```

## Routes

### Admin Routes
- `GET/POST /admin/invoice-settings` - Configurazione impostazioni fattura

### User Routes
- `GET /payments/invoices` - Lista fatture utente
- `GET /payments/invoice/<id>` - Dettaglio fattura
- `GET /payments/invoice/<id>/download` - Download PDF fattura

## Utility Functions

### `generate_invoice_for_payment(fee_payment_id)`
Genera automaticamente una fattura per un pagamento completato.

**Parametri:**
- `fee_payment_id`: ID del FeePayment

**Return:**
- Invoice object se creata
- None se già esistente o errore

**Logica:**
1. Verifica che fattura non esista già
2. Recupera FeePayment e verifica status = 'completed'
3. Recupera InvoiceSettings per dati azienda e tax rate
4. Calcola importi (imponibile, IVA, totale)
5. Crea record Invoice
6. Genera numero fattura
7. Salva in database

### `generate_invoice_number(invoice_id, settings)`
Genera numero fattura progressivo.

**Formato:** `PREFIX-YYYY-NNNNN`
**Esempio:** `INV-2026-00001`

### `send_to_electronic_invoice_provider(invoice_id)`
Invia fattura al provider di fatturazione elettronica (placeholder).

## Integrazione con Provider Esterni

### Fatture in Cloud
- API Documentation: https://docs.fattureincloud.it/
- Richiede: API Key, API Secret, Company ID

### Aruba Fatturazione Elettronica
- Richiede configurazione account Aruba

### Implementazione Futura
```python
def send_to_fatture_in_cloud(invoice, settings):
    """
    1. Autenticazione con API Key/Secret
    2. Formattazione dati fattura secondo schema FIC
    3. POST a endpoint FIC
    4. Gestione risposta e tracking
    """
    # TODO: Implementare integrazione reale
```

## Testing

### Test Automatici
File: `tests/test_invoice_generation.py`

Test inclusi:
- ✅ Creazione InvoiceSettings
- ✅ Generazione numero fattura
- ✅ Generazione automatica fattura dopo pagamento
- ✅ Prevenzione duplicati
- ✅ Calcolo corretto IVA

### Test Manuali

1. **Configurazione Admin:**
   - Login come super admin
   - Vai a `/admin/invoice-settings`
   - Compila tutti i campi
   - Carica logo
   - Salva impostazioni

2. **Generazione Fattura:**
   - Completa un pagamento come utente
   - Verifica che fattura sia generata automaticamente
   - Controlla che numero fattura sia corretto

3. **Download Fattura:**
   - Vai a `/payments/invoices`
   - Verifica lista fatture
   - Clicca "Download" su una fattura
   - Verifica contenuto PDF

## Configurazione Produzione

### Variabili Ambiente
Nessuna variabile aggiuntiva richiesta. Le configurazioni sono salvate in database.

### Migrazione Database
```bash
python manage.py db upgrade
```

### Permessi File
Assicurarsi che la cartella `uploads/invoice_logos/` sia scrivibile:
```bash
mkdir -p app/static/uploads/invoice_logos
chmod 755 app/static/uploads/invoice_logos
```

## Sicurezza

### Controlli Implementati
- ✅ Verifica permessi su download fatture (owner o admin)
- ✅ Sanitizzazione input form
- ✅ CSRF protection su form admin
- ✅ Validazione file upload logo
- ✅ Prevenzione SQL injection (SQLAlchemy ORM)

### Dati Sensibili
- API Key e Secret sono salvati in database
- Considerare encryption per API credentials in produzione
- Logo aziendale salvato in uploads (accessibile pubblicamente)

## Performance

### Ottimizzazioni
- Generazione PDF on-demand (non pre-generato)
- Caching non implementato (PDF leggeri)
- Query database ottimizzate con indexes

## Roadmap Futura

### Da Implementare
- [ ] XML fattura elettronica (formato SDI)
- [ ] Integrazione reale con Fatture in Cloud
- [ ] Integrazione reale con Aruba
- [ ] Invio automatico via email
- [ ] Export CSV/Excel fatture
- [ ] Dashboard statistiche fatture
- [ ] Multi-currency avanzato
- [ ] Template fattura personalizzabili
- [ ] Note di credito
- [ ] Fatture ricorrenti

## Support & Manutenzione

### Logs
Le operazioni di fatturazione sono registrate tramite `log_action()`:
- Creazione fattura
- Aggiornamento impostazioni
- Download fattura

### Debug
In caso di problemi:
1. Verificare che InvoiceSettings sia configurato
2. Controllare logs applicazione
3. Verificare permessi cartelle upload
4. Testare con payments di prova

## Note Legali

**Disclaimer:** Questo sistema genera fatture per uso interno. Per fatturazione elettronica B2B/B2C ufficiale verso Agenzia delle Entrate (Italia), è necessario:
1. Configurare provider certificato
2. Implementare formato XML FatturaPA
3. Validare con Sistema di Interscambio (SDI)
4. Conservazione sostitutiva a norma

Consultare un commercialista per conformità fiscale.
