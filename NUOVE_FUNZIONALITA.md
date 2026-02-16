# Nuove Funzionalità - Guida Utente

## Panoramica

Questa guida descrive tre nuove funzionalità aggiunte alla piattaforma SONACIP:

1. **Esportazione Dati Società** - Scarica tutti i dati della tua società
2. **Notifiche Planner** - Controlla le notifiche automatiche per il planner
3. **Banner Pubblicitari Live** - Gestisci banner durante le dirette (solo Super Admin)

---

## 1. Esportazione Dati Società

### Descrizione
Le società possono ora esportare tutti i propri dati in vari formati (CSV, Excel, JSON) direttamente dal pannello impostazioni.

### Come Accedere
1. Accedi come amministratore della società
2. Vai a **Impostazioni Società** dal menu
3. Scorri fino alla sezione **"Esportazione Dati"**

### Tipi di Dati Esportabili

#### 📊 Atleti
Esporta l'elenco completo dei membri della società:
- ID, Username, Email
- Nome e Cognome
- Telefono, Data di nascita
- Ruolo nella società
- Data di iscrizione

**Formati disponibili:** CSV, Excel, JSON

#### 📅 Eventi
Esporta tutti gli eventi e convocazioni:
- Titolo, Descrizione
- Tipo evento
- Data e ora inizio/fine
- Luogo
- Data creazione

**Formati disponibili:** CSV, Excel, JSON

#### 🏆 Tornei
Esporta i tornei organizzati dalla società:
- Nome, Descrizione
- Sport, Tipo torneo
- Date inizio/fine
- Stato
- Data creazione

**Formati disponibili:** CSV, Excel, JSON

#### 🗓️ Planner Campi
Esporta la pianificazione dei campi:
- Titolo evento
- Nome campo/struttura
- Tipo evento
- Orari
- Note
- Data creazione

**Formati disponibili:** CSV, Excel, JSON

### Esportazione Completa
Clicca su **"Scarica Tutti i Dati (CSV Completo)"** per ottenere un file CSV unico con:
- Dati della società
- Elenco membri
- Eventi società
- Post società

### Note Tecniche
- I file vengono generati al momento del download
- Nessun dato viene memorizzato sul server durante l'esportazione
- I nomi dei file includono il nome della società e timestamp per evitare sovrascritture
- Tutti i nomi file sono sanitizzati per sicurezza

---

## 2. Notifiche Planner

### Descrizione
Le società possono ora decidere se i membri ricevono automaticamente notifiche quando vengono apportate modifiche al planner dei campi.

### Come Funziona

#### Attivazione/Disattivazione
1. Vai a **Impostazioni Società**
2. Scorri fino alla sezione **"Notifiche Planner"**
3. Usa l'interruttore per attivare o disattivare le notifiche automatiche
4. Clicca **"Salva Impostazioni"**

#### Comportamento
- **Attivato** (predefinito): Quando un evento del planner viene creato o modificato, tutti i membri delle categorie interessate ricevono una notifica
- **Disattivato**: Le modifiche al planner non generano notifiche automatiche ai membri

### Chi Riceve le Notifiche
Le notifiche vengono inviate solo a:
- Membri attivi della società
- Che hanno abilitato la ricezione di notifiche planner nel loro profilo
- Appartenenti alle categorie interessate dall'evento

### Esempio Pratico
```
Scenario: Creazione allenamento categoria U15
- Notifiche Planner: ATTIVE
- Risultato: Tutti gli atleti U15 ricevono notifica immediata

Scenario: Modifica orario partita categoria U17
- Notifiche Planner: DISATTIVATE
- Risultato: Nessuna notifica automatica inviata
```

---

## 3. Banner Pubblicitari Live (Solo Super Admin)

### Descrizione
I super admin possono creare e gestire banner pubblicitari che vengono visualizzati durante le dirette live sulla piattaforma.

### Accesso
1. Login come Super Admin
2. Vai al **Pannello Amministratore**
3. Clicca su **"Gestione Banner Live"**

### Creazione Banner

#### Informazioni Richieste
- **Titolo**: Nome descrittivo (uso interno)
- **Contenuto HTML/Testo**: Testo del banner (facoltativo)
- **URL Immagine**: Link all'immagine del banner (https://...)
- **URL Link Click**: Destinazione quando l'utente clicca (https://...)
- **Posizione**: Dove appare il banner
  - Destra (consigliato)
  - Sinistra
  - Sopra
  - Sotto
- **Dimensioni**: Larghezza e altezza in pixel (default 300x250)
- **Ordine Visualizzazione**: Priorità (0 = massima)
- **Stato**: Attivo/Inattivo

#### Procedura Creazione
1. Clicca **"Nuovo Banner"**
2. Compila il form con le informazioni
3. Clicca **"Crea Banner"**

### Gestione Banner

#### Lista Banner
Visualizza tutti i banner con:
- ID e Titolo
- Posizione e dimensioni
- Ordine di visualizzazione
- Stato (Attivo/Inattivo)
- Data creazione

#### Azioni Disponibili
- ✏️ **Modifica**: Aggiorna le informazioni del banner
- 🔄 **Attiva/Disattiva**: Cambia lo stato rapidamente
- 🗑️ **Elimina**: Rimuovi il banner permanentemente

### Visualizzazione Durante Live

#### Come Appaiono
I banner attivi vengono mostrati automaticamente durante le dirette live:
- Posizionati secondo le impostazioni (sinistra/destra/sopra/sotto)
- Con le dimensioni specificate
- Cliccabili se è stato impostato un URL di destinazione
- Rotazione automatica se ci sono più banner attivi (basata sull'ordine)

#### Sicurezza
- Solo URL HTTPS validi sono accettati
- Il contenuto HTML viene sanitizzato per prevenire attacchi XSS
- I link si aprono in nuove schede con `rel="noopener"` per sicurezza

### Best Practices

#### Dimensioni Consigliate
- **Destra/Sinistra**: 300x250px (banner medio)
- **Sopra/Sotto**: 728x90px (banner orizzontale)

#### Contenuto
- Usa immagini ottimizzate (max 200KB)
- Testo breve e leggibile
- Call-to-action chiara
- Contrasta bene con sfondo scuro delle live

#### Gestione
- Non attivare troppi banner contemporaneamente (max 2-3)
- Usa l'ordine per prioritizzare i banner più importanti
- Monitora i click-through se possibile
- Aggiorna regolarmente i contenuti

---

## Database Migration

Per applicare le modifiche al database, esegui:

```bash
cd /path/to/sonacip
flask db upgrade
```

Questo creerà:
- Campo `planner_notifications_enabled` nella tabella `society`
- Nuova tabella `live_banner` per i banner pubblicitari

---

## Risoluzione Problemi

### Esportazione Dati
**Problema**: Il download non parte
- Verifica di essere loggato come admin società
- Controlla che ci siano dati da esportare
- Prova con un formato diverso (CSV invece di Excel)

**Problema**: File vuoto
- Verifica che la società abbia dati nel periodo richiesto
- Controlla i permessi di accesso ai dati

### Notifiche Planner
**Problema**: Le notifiche non vengono inviate
- Verifica che l'opzione sia attivata in Impostazioni Società
- Controlla che i membri abbiano abilitato le notifiche nel loro profilo
- Verifica che l'evento planner sia associato a categorie specifiche

### Banner Live
**Problema**: Il banner non appare
- Verifica che il banner sia in stato "Attivo"
- Controlla che l'URL dell'immagine sia valido e accessibile
- Verifica che la live sia effettivamente attiva
- Prova a svuotare la cache del browser

**Problema**: Immagine non caricata
- Usa solo URL HTTPS validi
- Verifica che l'immagine sia accessibile pubblicamente
- Controlla la console browser per errori CORS

---

## Supporto

Per assistenza o segnalazione bug:
- Email: support@sonacip.local
- Issue tracker: [GitHub Issues](https://github.com/picano78/sonacip/issues)

---

*Ultimo aggiornamento: 16 Febbraio 2026*
