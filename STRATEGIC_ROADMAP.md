# SONACIP: Roadmap to Market Leadership
Documento strategico di evoluzione della piattaforma.

## 🎯 Obiettivo
Trasformare Sonacip nella piattaforma all-in-one numero 1 per società sportive, atleti e coach, superando i competitor su UX, funzionalità verticali e strumenti di monetizzazione.

---

## 🚀 FASE 1: Modernizzazione UX e Mobile (1-2 mesi)
Il primo impatto è tutto. L'utente non deve percepire "un sito web", ma un'applicazione.

- [ ] **PWA (Progressive Web App):**
    - [ ] Aggiungere `manifest.json` e Service Workers.
    - [ ] Abilitare installazione su Home Screen mobile.
    - [ ] Gestione offline di base (cache).
- [ ] **Interattività (HTMX/Alpine.js):**
    - [ ] Convertire like, follow e commenti in chiamate AJAX senza refresh.
    - [ ] Caricamento infinito (Infinite Scroll) per il feed dei post.
- [ ] **Dark Mode:** Implementazione toggle tema chiaro/scuro (standard di mercato).

## ⚽ FASE 2: Sport Tech "Deep Dive" (2-3 mesi)
Funzionalità che rendono il software indispensabile per la gestione quotidiana.

- [ ] **Gestione Atleti Avanzata:**
    - [ ] **Scadenziario Medico:** Upload certificati, OCR per lettura date, alert automatici scadenze.
    - [ ] **Digital Locker:** Archivio documenti atleta (tesserini, liberatorie).
- [ ] **Eventi & Partite 2.0:**
    - [ ] **Sistema Convocazioni:** Il coach convoca, l'atleta risponde con un tap. Dashboard presenze.
    - [ ] **Match Center:** Tabellino live (marcatori, tempo, sostituzioni) aggiornabile da bordo campo.
    - [ ] **Car Pooling:** Organizzazione passaggi auto per trasferte (feature molto richiesta dai genitori).

## 📢 FASE 3: Engagement & Social (Corrente)
Aumentare il tempo di permanenza sulla piattaforma.

- [ ] **Video First:**
    - [ ] Ottimizzazione upload video (compressione asincrona).
    - [ ] Player video custom con supporto streaming adattivo (HLS).
- [ ] **Real-time Communication:**
    - [ ] Implementare `Flask-SocketIO`.
    - [ ] Chat di squadra (Gruppi automatici basati sulla rosa).
    - [ ] Notifiche push immediate.
- [ ] **Gamification:**
    - [ ] Badge (es. "Bomber", "Stakanovista", "Top Fan").
    - [ ] Classifiche attività social e sportive.

## 💰 FASE 4: Business & Monetizzazione per le Società (Prossimo Futuro)
Aiutare le società a fatturare grazie a Sonacip.

- [ ] **Sonacip Pay:**
    - [ ] Pagamento quote annuali/mensili in-app (Stripe Connect).
    - [ ] Vendita biglietti partite ed eventi.
- [ ] **Merchandising:**
    - [ ] Mini-shop per ogni società (vendita sciarpe, maglie, tute).
- [ ] **Sponsor:**
    - [ ] Spazi pubblicitari mirati gestibili dalla società sui propri feed.

## 🛠️ Evoluzione Tecnica (Necessaria per scalare)

1. **API Layer:** Separare nettamente logica e vista. Creare API REST documentate (Swagger) per future app native.
2. **Coda Asincrona (Celery/Redis):** Spostare invio mail, processing video e calcoli pesanti in background.
3. **Search Engine:** Implementare Elasticsearch o Meilisearch per ricerca fulminea di atleti/post.
