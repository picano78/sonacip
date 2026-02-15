from datetime import datetime, timezone
from flask import render_template_string, url_for
from flask_login import current_user
from app import db


WIDGET_REGISTRY = [
    {
        'key': 'feed_preview',
        'name': 'Ultime dal Feed',
        'description': 'Ultimi 5 post dal tuo feed',
        'icon': 'bi-rss-fill',
        'category': 'social',
    },
    {
        'key': 'upcoming_events',
        'name': 'Prossimi Eventi',
        'description': 'I prossimi 5 eventi in programma',
        'icon': 'bi-calendar-event-fill',
        'category': 'attività',
    },
    {
        'key': 'my_tasks',
        'name': 'Le Mie Attività',
        'description': 'Le tue attività in sospeso',
        'icon': 'bi-check2-square',
        'category': 'attività',
    },
    {
        'key': 'notifications_widget',
        'name': 'Notifiche Recenti',
        'description': 'Le ultime notifiche non lette',
        'icon': 'bi-bell-fill',
        'category': 'sistema',
    },
    {
        'key': 'stats_summary',
        'name': 'Statistiche Rapide',
        'description': 'Riepilogo statistiche personali',
        'icon': 'bi-bar-chart-fill',
        'category': 'statistiche',
    },
    {
        'key': 'calendar_mini',
        'name': 'Mini Calendario',
        'description': 'Panoramica della settimana corrente',
        'icon': 'bi-calendar-week',
        'category': 'attività',
    },
    {
        'key': 'my_groups',
        'name': 'I Miei Gruppi',
        'description': 'I gruppi di cui fai parte',
        'icon': 'bi-people-fill',
        'category': 'social',
    },
    {
        'key': 'polls_active',
        'name': 'Sondaggi Attivi',
        'description': 'Sondaggi aperti a cui partecipare',
        'icon': 'bi-bar-chart-steps',
        'category': 'social',
    },
    {
        'key': 'documents_recent',
        'name': 'Documenti Recenti',
        'description': 'Ultimi documenti caricati',
        'icon': 'bi-file-earmark-text-fill',
        'category': 'documenti',
    },
    {
        'key': 'weather',
        'name': 'Meteo',
        'description': 'Widget meteo decorativo',
        'icon': 'bi-cloud-sun-fill',
        'category': 'utility',
    },
    {
        'key': 'quick_links',
        'name': 'Link Rapidi',
        'description': 'Accesso rapido alle sezioni principali',
        'icon': 'bi-link-45deg',
        'category': 'utility',
    },
]

DEFAULT_WIDGETS = ['quick_links', 'stats_summary', 'notifications_widget', 'feed_preview', 'upcoming_events']


def get_widget_registry():
    return WIDGET_REGISTRY


def get_widget_info(widget_key):
    for w in WIDGET_REGISTRY:
        if w['key'] == widget_key:
            return w
    return None


def render_widget(widget_key, user):
    try:
        # Backward compatibility: previously saved layouts may reference removed widgets.
        if widget_key in ('leaderboard_mini',):
            return ''
        renderer = _RENDERERS.get(widget_key)
        if renderer:
            return renderer(user)
        return f'<div class="alert alert-warning">Widget non disponibile: {widget_key}</div>'
    except Exception as e:
        return f'<div class="alert alert-danger">Errore widget: {widget_key}</div>'


def _render_feed_preview(user):
    from app.models import Post
    try:
        posts = Post.query.filter_by(is_public=True).order_by(Post.created_at.desc()).limit(5).all()
    except Exception:
        posts = []
    items = ''
    for p in posts:
        author = p.author.get_full_name() if p.author else 'Utente'
        content = (p.content or '')[:120]
        items += f'''<div class="list-group-item">
            <div class="fw-semibold small">{author}</div>
            <div class="text-muted small">{content}...</div>
        </div>'''
    if not items:
        items = '<div class="list-group-item text-muted small">Nessun post recente.</div>'
    return f'''<div class="card h-100">
        <div class="card-header d-flex justify-content-between align-items-center">
            <strong><i class="bi bi-rss-fill me-1"></i> Ultime dal Feed</strong>
            <a href="{url_for('social.feed')}" class="btn btn-sm btn-outline-primary">Vai</a>
        </div>
        <div class="list-group list-group-flush">{items}</div>
    </div>'''


def _render_upcoming_events(user):
    from app.models import Event
    from datetime import datetime
    try:
        events = Event.query.filter(Event.start_date >= datetime.now(timezone.utc)).order_by(Event.start_date.asc()).limit(5).all()
    except Exception:
        events = []
    items = ''
    for e in events:
        date_str = e.start_date.strftime('%d/%m/%Y %H:%M') if e.start_date else ''
        items += f'''<div class="list-group-item">
            <div class="fw-semibold small">{e.title}</div>
            <div class="text-muted small"><i class="bi bi-clock me-1"></i>{date_str}</div>
        </div>'''
    if not items:
        items = '<div class="list-group-item text-muted small">Nessun evento in programma.</div>'
    return f'''<div class="card h-100">
        <div class="card-header d-flex justify-content-between align-items-center">
            <strong><i class="bi bi-calendar-event-fill me-1"></i> Prossimi Eventi</strong>
            <a href="{url_for('events.index')}" class="btn btn-sm btn-outline-primary">Tutti</a>
        </div>
        <div class="list-group list-group-flush">{items}</div>
    </div>'''


def _render_my_tasks(user):
    from app.models import Task
    try:
        tasks = Task.query.filter_by(assigned_to=user.id, status='pending').order_by(Task.created_at.desc()).limit(5).all()
    except Exception:
        tasks = []
    items = ''
    for t in tasks:
        prio_badge = {'high': 'danger', 'medium': 'warning', 'low': 'info'}.get(t.priority, 'secondary')
        items += f'''<div class="list-group-item d-flex justify-content-between align-items-center">
            <span class="small">{t.title}</span>
            <span class="badge bg-{prio_badge}">{t.priority or 'N/D'}</span>
        </div>'''
    if not items:
        items = '<div class="list-group-item text-muted small">Nessuna attività in sospeso.</div>'
    return f'''<div class="card h-100">
        <div class="card-header"><strong><i class="bi bi-check2-square me-1"></i> Le Mie Attività</strong></div>
        <div class="list-group list-group-flush">{items}</div>
    </div>'''


def _render_notifications_widget(user):
    from app.models import Notification
    try:
        notifs = Notification.query.filter_by(user_id=user.id, is_read=False).order_by(Notification.created_at.desc()).limit(5).all()
    except Exception:
        notifs = []
    items = ''
    for n in notifs:
        items += f'''<div class="list-group-item">
            <div class="fw-semibold small">{n.title or ''}</div>
            <div class="text-muted small">{n.message or ''}</div>
        </div>'''
    if not items:
        items = '<div class="list-group-item text-muted small">Nessuna notifica.</div>'
    return f'''<div class="card h-100">
        <div class="card-header d-flex justify-content-between align-items-center">
            <strong><i class="bi bi-bell-fill me-1"></i> Notifiche Recenti</strong>
            <a href="{url_for('notifications.index')}" class="btn btn-sm btn-outline-primary">Tutte</a>
        </div>
        <div class="list-group list-group-flush">{items}</div>
    </div>'''


def _render_stats_summary(user):
    from app.models import Post, Event, Task, Notification, Message
    stats = {}
    try:
        stats = {
            'posts': Post.query.filter_by(user_id=user.id).count(),
            'events': Event.query.filter_by(creator_id=user.id).count(),
            'tasks': Task.query.filter_by(assigned_to=user.id).count(),
            'unread': Notification.query.filter_by(user_id=user.id, is_read=False).count() + Message.query.filter_by(recipient_id=user.id, is_read=False).count(),
        }
    except Exception:
        stats = {'posts': 0, 'events': 0, 'tasks': 0, 'unread': 0}
    return f'''<div class="card h-100">
        <div class="card-header"><strong><i class="bi bi-bar-chart-fill me-1"></i> Statistiche Rapide</strong></div>
        <div class="card-body">
            <div class="row g-2">
                <div class="col-6">
                    <div class="p-2 border rounded text-center">
                        <div class="text-muted small">Post</div>
                        <div class="h5 mb-0" style="color:#1877f2">{stats.get('posts', 0)}</div>
                    </div>
                </div>
                <div class="col-6">
                    <div class="p-2 border rounded text-center">
                        <div class="text-muted small">Eventi</div>
                        <div class="h5 mb-0" style="color:#1877f2">{stats.get('events', 0)}</div>
                    </div>
                </div>
                <div class="col-6">
                    <div class="p-2 border rounded text-center">
                        <div class="text-muted small">Attività</div>
                        <div class="h5 mb-0" style="color:#1877f2">{stats.get('tasks', 0)}</div>
                    </div>
                </div>
                <div class="col-6">
                    <div class="p-2 border rounded text-center">
                        <div class="text-muted small">Non letti</div>
                        <div class="h5 mb-0" style="color:#1877f2">{stats.get('unread', 0)}</div>
                    </div>
                </div>
            </div>
        </div>
    </div>'''


def _render_calendar_mini(user):
    from datetime import datetime, timedelta
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=today.weekday())
    days_html = ''
    day_names = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom']
    for i in range(7):
        d = start + timedelta(days=i)
        is_today = d == today
        cls = 'bg-primary text-white rounded-circle' if is_today else ''
        days_html += f'<div class="text-center flex-fill"><div class="text-muted small">{day_names[i]}</div><div class="fw-bold {cls}" style="width:32px;height:32px;line-height:32px;margin:0 auto;">{d.day}</div></div>'
    return f'''<div class="card h-100">
        <div class="card-header"><strong><i class="bi bi-calendar-week me-1"></i> Mini Calendario</strong></div>
        <div class="card-body">
            <div class="d-flex justify-content-between">{days_html}</div>
        </div>
    </div>'''


def _render_my_groups(user):
    from app.models import Group, GroupMembership
    try:
        memberships = GroupMembership.query.filter_by(user_id=user.id).limit(5).all()
        group_ids = [m.group_id for m in memberships]
        groups = Group.query.filter(Group.id.in_(group_ids)).all() if group_ids else []
    except Exception:
        groups = []
    items = ''
    for g in groups:
        items += f'<div class="list-group-item small"><i class="bi bi-people me-1"></i> {g.name}</div>'
    if not items:
        items = '<div class="list-group-item text-muted small">Non fai parte di nessun gruppo.</div>'
    return f'''<div class="card h-100">
        <div class="card-header d-flex justify-content-between align-items-center">
            <strong><i class="bi bi-people-fill me-1"></i> I Miei Gruppi</strong>
            <a href="{url_for('groups.my_groups')}" class="btn btn-sm btn-outline-primary">Tutti</a>
        </div>
        <div class="list-group list-group-flush">{items}</div>
    </div>'''


def _render_polls_active(user):
    from app.models import Poll
    try:
        polls = Poll.query.filter_by(is_active=True).order_by(Poll.created_at.desc()).limit(5).all()
    except Exception:
        polls = []
    items = ''
    for p in polls:
        items += f'<div class="list-group-item small"><i class="bi bi-bar-chart-steps me-1"></i> {p.title}</div>'
    if not items:
        items = '<div class="list-group-item text-muted small">Nessun sondaggio attivo.</div>'
    return f'''<div class="card h-100">
        <div class="card-header"><strong><i class="bi bi-bar-chart-steps me-1"></i> Sondaggi Attivi</strong></div>
        <div class="list-group list-group-flush">{items}</div>
    </div>'''


def _render_documents_recent(user):
    from app.models import Document
    try:
        docs = Document.query.order_by(Document.created_at.desc()).limit(5).all()
    except Exception:
        docs = []
    items = ''
    for d in docs:
        items += f'<div class="list-group-item small"><i class="bi bi-file-earmark me-1"></i> {d.title}</div>'
    if not items:
        items = '<div class="list-group-item text-muted small">Nessun documento recente.</div>'
    return f'''<div class="card h-100">
        <div class="card-header d-flex justify-content-between align-items-center">
            <strong><i class="bi bi-file-earmark-text-fill me-1"></i> Documenti Recenti</strong>
            <a href="{url_for('documents.index')}" class="btn btn-sm btn-outline-primary">Tutti</a>
        </div>
        <div class="list-group list-group-flush">{items}</div>
    </div>'''


def _render_weather(user):
    return '''<div class="card h-100">
        <div class="card-header"><strong><i class="bi bi-cloud-sun-fill me-1"></i> Meteo</strong></div>
        <div class="card-body text-center">
            <div style="font-size:3rem;color:#1877f2"><i class="bi bi-sun-fill"></i></div>
            <div class="h4 mb-1">22°C</div>
            <div class="text-muted">Soleggiato</div>
            <div class="mt-2 small text-muted">
                <i class="bi bi-droplet me-1"></i>45%
                <i class="bi bi-wind ms-2 me-1"></i>12 km/h
            </div>
        </div>
    </div>'''


def _render_quick_links(user):
    links = [
        ('social.feed', 'bi-house-fill', 'Feed'),
        ('social.profile', 'bi-person-fill', 'Profilo'),
        ('notifications.index', 'bi-bell-fill', 'Notifiche'),
        ('messages.inbox', 'bi-envelope-fill', 'Messaggi'),
        ('events.index', 'bi-calendar-event-fill', 'Eventi'),
        ('gamification.index', 'bi-trophy-fill', 'Gamification'),
    ]
    btns = ''
    for endpoint, icon, label in links:
        try:
            if endpoint == 'social.profile':
                href = url_for(endpoint, user_id=user.id)
            else:
                href = url_for(endpoint)
        except Exception:
            continue
        btns += f'<a class="btn btn-sm btn-outline-primary me-1 mb-1" href="{href}"><i class="bi {icon} me-1"></i>{label}</a>'
    return f'''<div class="card h-100">
        <div class="card-header"><strong><i class="bi bi-link-45deg me-1"></i> Link Rapidi</strong></div>
        <div class="card-body"><div class="d-flex flex-wrap">{btns}</div></div>
    </div>'''


_RENDERERS = {
    'feed_preview': _render_feed_preview,
    'upcoming_events': _render_upcoming_events,
    'my_tasks': _render_my_tasks,
    'notifications_widget': _render_notifications_widget,
    'stats_summary': _render_stats_summary,
    'calendar_mini': _render_calendar_mini,
    'my_groups': _render_my_groups,
    'polls_active': _render_polls_active,
    'documents_recent': _render_documents_recent,
    'weather': _render_weather,
    'quick_links': _render_quick_links,
}
