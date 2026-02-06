"""
Page Builder – section registry, defaults, and helpers.

Each page is identified by a slug (matching Flask endpoint, e.g. 'main.index').
A page has an ordered list of *sections*, each with:
  - id:       stable identifier (e.g. 'hero', 'features', 'cta_users')
  - type:     section template type (hero, features_grid, cta, rich_html, stats, values, contact_cards, faq)
  - label:    human-readable Italian label for the admin UI
  - visible:  bool – whether the section is rendered
  - content:  dict – editable content fields (vary by type)
"""
from __future__ import annotations

import copy
import json
from typing import Any

from app import db
from app.models import CustomizationKV

PAGE_REGISTRY: dict[str, dict[str, Any]] = {}


def _r(slug: str, *, label: str, sections: list[dict]) -> None:
    PAGE_REGISTRY[slug] = {'label': label, 'sections': sections}


def _sec(id: str, type: str, label: str, content: dict | None = None, visible: bool = True) -> dict:
    return {'id': id, 'type': type, 'label': label, 'visible': visible, 'content': content or {}}


SECTION_FIELD_SCHEMA: dict[str, list[dict]] = {
    'hero': [
        {'key': 'title', 'label': 'Titolo', 'input': 'text'},
        {'key': 'subtitle', 'label': 'Sottotitolo', 'input': 'textarea'},
        {'key': 'btn1_text', 'label': 'Pulsante 1 – Testo', 'input': 'text'},
        {'key': 'btn1_url', 'label': 'Pulsante 1 – Link', 'input': 'text'},
        {'key': 'btn2_text', 'label': 'Pulsante 2 – Testo', 'input': 'text'},
        {'key': 'btn2_url', 'label': 'Pulsante 2 – Link', 'input': 'text'},
        {'key': 'btn3_text', 'label': 'Pulsante 3 – Testo', 'input': 'text'},
        {'key': 'btn3_url', 'label': 'Pulsante 3 – Link', 'input': 'text'},
    ],
    'features_grid': [
        {'key': 'title', 'label': 'Titolo Sezione', 'input': 'text'},
        {'key': 'subtitle', 'label': 'Sottotitolo', 'input': 'text'},
        {'key': 'items', 'label': 'Elementi (JSON)', 'input': 'items'},
    ],
    'cta': [
        {'key': 'title', 'label': 'Titolo', 'input': 'text'},
        {'key': 'text', 'label': 'Testo', 'input': 'textarea'},
        {'key': 'btn1_text', 'label': 'Pulsante 1 – Testo', 'input': 'text'},
        {'key': 'btn1_url', 'label': 'Pulsante 1 – Link', 'input': 'text'},
        {'key': 'btn2_text', 'label': 'Pulsante 2 – Testo', 'input': 'text'},
        {'key': 'btn2_url', 'label': 'Pulsante 2 – Link', 'input': 'text'},
    ],
    'rich_html': [
        {'key': 'title', 'label': 'Titolo', 'input': 'text'},
        {'key': 'html', 'label': 'Contenuto HTML', 'input': 'html'},
    ],
    'values': [
        {'key': 'title', 'label': 'Titolo Sezione', 'input': 'text'},
        {'key': 'items', 'label': 'Valori (JSON)', 'input': 'items'},
    ],
    'contact_cards': [
        {'key': 'title', 'label': 'Titolo Sezione', 'input': 'text'},
        {'key': 'items', 'label': 'Schede Contatto (JSON)', 'input': 'items'},
    ],
    'faq': [
        {'key': 'title', 'label': 'Titolo Sezione', 'input': 'text'},
        {'key': 'items', 'label': 'Domande e Risposte (JSON)', 'input': 'items'},
    ],
    'stats': [
        {'key': 'items', 'label': 'Statistiche (JSON)', 'input': 'items'},
    ],
    'checklist': [
        {'key': 'title', 'label': 'Titolo Sezione', 'input': 'text'},
        {'key': 'items', 'label': 'Elementi (JSON)', 'input': 'items'},
    ],
}

_r('main.index', label='Homepage', sections=[
    _sec('hero', 'hero', 'Sezione Hero', {
        'title': 'Benvenuto su SONACIP',
        'subtitle': 'La piattaforma completa per la gestione delle società sportive, atleti e appassionati di sport in Italia.',
        'btn1_text': 'Accedi', 'btn1_url': '/auth/login',
        'btn2_text': 'Registrati come Appassionato', 'btn2_url': '/auth/register',
        'btn3_text': 'Registra Società', 'btn3_url': '/auth/register-society',
    }),
    _sec('features', 'features_grid', 'Funzionalità Principali', {
        'title': 'Funzionalità Principali',
        'subtitle': 'Tutto ciò che serve per gestire le tue società sportive in un\'unica piattaforma',
        'items': [
            {'icon': 'bi-building', 'title': 'Gestione Società', 'text': 'Amministra società, gestisci membri, ruoli e permessi con facilità.'},
            {'icon': 'bi-calendar-event', 'title': 'Eventi e Calendario', 'text': 'Crea e gestisci eventi, allenamenti e gare.'},
            {'icon': 'bi-share-fill', 'title': 'Social Network', 'text': 'Comunica con la tua comunità. Feed, post, like, commenti.'},
            {'icon': 'bi-bag-check', 'title': 'Marketplace', 'text': 'Vendi e acquista equipaggiamenti sportivi.'},
            {'icon': 'bi-chat-dots', 'title': 'Messaggistica', 'text': 'Comunica in tempo reale con atleti, staff e altre società.'},
            {'icon': 'bi-trophy', 'title': 'Gestione Tornei', 'text': 'Organizza tornei e competizioni con tabelloni e classifiche.'},
        ],
    }),
    _sec('cta_users', 'cta', 'CTA Appassionati', {
        'title': 'Sei un Appassionato di Sport?',
        'text': 'Unisciti a migliaia di atleti e appassionati che già usano SONACIP per connettersi, competere e crescere nello sport.',
        'btn1_text': 'Registrati Subito', 'btn1_url': '/auth/register',
        'btn2_text': 'Leggi la Guida', 'btn2_url': '/contatto',
    }),
    _sec('cta_societies', 'cta', 'CTA Società', {
        'title': 'Gestisci la Tua Società Sportiva',
        'text': 'SONACIP è lo strumento completo per le società sportive italiane.',
        'btn1_text': 'Registra la Tua Società', 'btn1_url': '/auth/register-society',
        'btn2_text': 'Scopri di Più', 'btn2_url': '/contatto',
    }),
    _sec('why_us', 'checklist', 'Perché Scegliere SONACIP', {
        'title': 'Perché Scegliere SONACIP?',
        'items': [
            {'title': 'Piattaforma Italiana', 'text': 'Sviluppata per le esigenze specifiche delle società sportive italiane'},
            {'title': 'Facile da Usare', 'text': 'Interfaccia intuitiva che non richiede competenze tecniche'},
            {'title': 'Supporto 24/7', 'text': 'Team di supporto sempre disponibile per aiutarti'},
            {'title': 'Sicuro e Affidabile', 'text': 'Dati protetti con i più alti standard di sicurezza'},
        ],
    }),
])

_r('main.about', label='Chi Siamo', sections=[
    _sec('hero', 'hero', 'Sezione Hero', {
        'title': 'Chi Siamo',
        'subtitle': 'SONACIP è la piattaforma italiana dedicata alla gestione delle società sportive.',
    }),
    _sec('mission', 'rich_html', 'Missione', {
        'title': 'La Nostra Missione',
        'html': '<p>Facilitare la gestione delle società sportive italiane, offrendo strumenti digitali moderni e accessibili a tutti.</p>',
    }),
    _sec('values', 'values', 'I Nostri Valori', {
        'title': 'I Nostri Valori',
        'items': [
            {'icon': 'bi-heart-fill', 'title': 'Passione', 'text': 'Lo sport è il cuore di tutto ciò che facciamo.'},
            {'icon': 'bi-people-fill', 'title': 'Comunità', 'text': 'Crediamo nel potere della connessione tra le persone.'},
            {'icon': 'bi-shield-check', 'title': 'Affidabilità', 'text': 'Sicurezza e stabilità in ogni funzione della piattaforma.'},
            {'icon': 'bi-lightbulb-fill', 'title': 'Innovazione', 'text': 'Sempre alla ricerca di soluzioni migliori per i nostri utenti.'},
        ],
    }),
    _sec('stats', 'stats', 'Statistiche', {
        'items': [
            {'value': '1000+', 'label': 'Utenti Registrati'},
            {'value': '50+', 'label': 'Società Sportive'},
            {'value': '500+', 'label': 'Eventi Organizzati'},
            {'value': '24/7', 'label': 'Supporto Disponibile'},
        ],
    }),
])

_r('main.contact', label='Contatti', sections=[
    _sec('hero', 'hero', 'Sezione Hero', {
        'title': 'Contattaci',
        'subtitle': 'Siamo qui per aiutarti. Scegli il metodo che preferisci per metterti in contatto con noi.',
    }),
    _sec('contact_cards', 'contact_cards', 'Schede Contatto', {
        'title': 'Come Raggiungerci',
        'items': [
            {'icon': 'bi-envelope-fill', 'title': 'Email', 'text': 'info@sonacip.it', 'link': 'mailto:info@sonacip.it'},
            {'icon': 'bi-telephone-fill', 'title': 'Telefono', 'text': '+39 000 000 0000', 'link': 'tel:+390000000000'},
            {'icon': 'bi-geo-alt-fill', 'title': 'Sede', 'text': 'Italia', 'link': ''},
        ],
    }),
    _sec('cta', 'cta', 'CTA Assistenza', {
        'title': 'Hai Bisogno di Assistenza?',
        'text': 'Il nostro team è pronto ad aiutarti con qualsiasi domanda o problema.',
        'btn1_text': 'Scrivi al Supporto', 'btn1_url': '/contatta-admin',
        'btn2_text': 'Guida Utente', 'btn2_url': '/guida-utente',
    }),
])

_r('main.privacy_policy', label='Privacy Policy', sections=[
    _sec('content', 'rich_html', 'Contenuto Privacy', {
        'title': 'Informativa sulla Privacy',
        'html': '',
    }),
])

_r('main.terms', label='Termini di Servizio', sections=[
    _sec('content', 'rich_html', 'Contenuto Termini', {
        'title': 'Termini e Condizioni',
        'html': '',
    }),
])

_r('main.guide_user', label='Guida Utente', sections=[
    _sec('hero', 'hero', 'Sezione Hero', {
        'title': 'Guida Utente',
        'subtitle': 'Tutto quello che devi sapere per usare SONACIP al meglio.',
    }),
    _sec('content', 'rich_html', 'Contenuto Guida', {
        'title': '',
        'html': '',
    }),
])

_r('main.guide_society', label='Guida Società', sections=[
    _sec('hero', 'hero', 'Sezione Hero', {
        'title': 'Guida per le Società',
        'subtitle': 'Impara a gestire la tua società sportiva con SONACIP.',
    }),
    _sec('content', 'rich_html', 'Contenuto Guida', {
        'title': '',
        'html': '',
    }),
])


def get_page_config(slug: str) -> list[dict]:
    """Return the merged section list for a page: admin overrides + defaults."""
    defaults = PAGE_REGISTRY.get(slug, {}).get('sections', [])
    if not defaults:
        return []

    row = CustomizationKV.query.filter_by(scope='page', scope_key=slug, key='sections').first()
    if not row:
        return copy.deepcopy(defaults)

    try:
        saved = json.loads(row.value_json) if isinstance(row.value_json, str) else row.value_json
    except Exception:
        return copy.deepcopy(defaults)

    if not isinstance(saved, list):
        return copy.deepcopy(defaults)

    default_map = {s['id']: s for s in defaults}
    saved_ids = {s['id'] for s in saved if isinstance(s, dict)}

    merged = []
    for s in saved:
        if not isinstance(s, dict) or 'id' not in s:
            continue
        base = copy.deepcopy(default_map.get(s['id'], {}))
        base.update({
            'visible': s.get('visible', True),
            'content': s.get('content', base.get('content', {})),
        })
        if 'label' not in base:
            base['label'] = s.get('label', s['id'])
        if 'type' not in base:
            base['type'] = s.get('type', 'rich_html')
        merged.append(base)

    for d in defaults:
        if d['id'] not in saved_ids:
            merged.append(copy.deepcopy(d))

    return merged


def save_page_config(slug: str, sections: list[dict], user_id: int) -> None:
    """Persist section config for a page."""
    row = CustomizationKV.query.filter_by(scope='page', scope_key=slug, key='sections').first()
    if not row:
        row = CustomizationKV(scope='page', scope_key=slug, key='sections')
        db.session.add(row)

    row.value_json = json.dumps(sections, ensure_ascii=False)
    row.updated_by = user_id
    db.session.commit()


def reset_page_config(slug: str) -> None:
    """Remove admin overrides, reverting to defaults."""
    row = CustomizationKV.query.filter_by(scope='page', scope_key=slug, key='sections').first()
    if row:
        db.session.delete(row)
        db.session.commit()


def get_section_for_page(slug: str, section_id: str) -> dict | None:
    """Get a single section's config (merged)."""
    for s in get_page_config(slug):
        if s['id'] == section_id:
            return s
    return None
