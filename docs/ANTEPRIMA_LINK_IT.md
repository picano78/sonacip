# Anteprima Link per YouTube, Instagram e TikTok

## Descrizione

Questa funzionalità aggiunge automaticamente le anteprime dei link quando gli utenti condividono URL da YouTube, Instagram e TikTok nei loro post sul feed sociale.

## Funzionalità

- ✅ Rilevamento automatico di link da YouTube, Instagram e TikTok
- ✅ Visualizzazione di anteprime ricche con:
  - Immagine di anteprima
  - Titolo del contenuto
  - Descrizione
  - Nome del provider
- ✅ Apertura sicura dei link in nuove schede
- ✅ Gestione errori robusta (la creazione del post continua anche se il recupero dell'anteprima fallisce)

## Come Funziona

1. **L'utente crea un post** con un link da una delle piattaforme supportate
2. **Il sistema rileva il link** usando pattern regex specifici per piattaforma
3. **Recupera i metadati** tramite API oEmbed (YouTube) o Open Graph (Instagram, TikTok)
4. **Salva l'anteprima** nel database insieme al post
5. **Visualizza l'anteprima** nel feed in un card design accattivante

## Esempi di URL Supportati

### YouTube
```
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://youtu.be/dQw4w9WgXcQ
https://www.youtube.com/shorts/abc123
```

### Instagram
```
https://www.instagram.com/p/ABC123xyz/
https://www.instagram.com/reel/XYZ789/
```

### TikTok
```
https://www.tiktok.com/@utente/video/1234567890
https://vm.tiktok.com/ZMabcdefg/
```

## Modifiche Tecniche

### Database
Aggiunti 5 nuovi campi alla tabella `post`:
- `link_url` - URL estratto
- `link_title` - Titolo del contenuto
- `link_description` - Descrizione
- `link_image` - URL dell'immagine di anteprima
- `link_provider` - Nome del provider (youtube, instagram, tiktok)

### Backend
- Nuovo modulo `app/social/link_preview.py` per l'estrazione e il recupero dei metadati
- Aggiornato `app/social/routes.py` per elaborare i link durante la creazione dei post
- Integrazione con YouTube oEmbed API
- Parser Open Graph per Instagram e TikTok

### Frontend
- Aggiornato `app/templates/components/post_card.html` per visualizzare le anteprime
- Design responsive con layout adattivo
- Apertura sicura dei link con attributi `noopener noreferrer`

### Dipendenze
- `requests==2.32.3` - Client HTTP per recuperare URL
- `beautifulsoup4==4.12.3` - Parser HTML per tag Open Graph

## Sicurezza

✅ Timeout di 5 secondi per tutte le richieste esterne
✅ Gestione errori che non blocca la creazione dei post
✅ Link esterni aperti in modo sicuro per prevenire attacchi tabnapping
✅ Nessuna vulnerabilità rilevata da CodeQL

## Test

Esegui i test con:
```bash
python -m unittest tests.test_link_preview
```

I test coprono:
- Estrazione URL da tutte le piattaforme supportate
- Rilevamento accurato della piattaforma
- Gestione di più URL
- Filtro URL non supportati
- Recupero metadati con risposte simulate
- Scenari di gestione errori

## Migrazione Database

Per applicare le modifiche al database:

```bash
flask db upgrade
```

Per ripristinare:

```bash
flask db downgrade
```

## Documentazione Completa

Per maggiori dettagli tecnici, consultare [LINK_PREVIEW_FEATURE.md](./LINK_PREVIEW_FEATURE.md)
