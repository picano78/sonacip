"""
Main routes
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify, current_app, Response
from flask_login import current_user, login_required
from sqlalchemy import or_
from app import db
from app.utils import check_permission
from app.main.forms import DashboardEditForm, ContactAdminForm
from types import SimpleNamespace

bp = Blueprint('main', __name__, url_prefix='')


def _page_sections(slug):
    try:
        from app.admin.page_builder import get_page_config
        return get_page_config(slug)
    except Exception:
        return []


@bp.route("/manifest.json")
def manifest():
    """
    Dynamic PWA manifest.

    This allows the super admin to change the app icon from the admin panel
    without rebuilding static files.
    """
    import json as _json

    appearance = None
    site = None
    try:
        from app.models import AppearanceSetting, SiteCustomization

        appearance = AppearanceSetting.query.filter_by(scope="global").order_by(AppearanceSetting.id.desc()).first()
        site = SiteCustomization.query.order_by(SiteCustomization.id.desc()).first()
    except Exception:
        appearance = None
        site = None

    brand = (getattr(site, "navbar_brand_text", None) or "SONACIP").strip() if site else "SONACIP"
    theme_color = (getattr(appearance, "primary_color", None) or "#1877f2").strip() if appearance else "#1877f2"

    icon_url = None
    if appearance:
        icon_url = getattr(appearance, "app_icon_url", None) or getattr(appearance, "favicon_url", None)
    # Fallback to bundled icons
    if not icon_url:
        icon_url = url_for("static", filename="icons/icon-512x512.png")

    def _guess_mime(src: str) -> str:
        s = (src or "").split("?", 1)[0].lower()
        if s.endswith(".svg"):
            return "image/svg+xml"
        if s.endswith(".webp"):
            return "image/webp"
        if s.endswith(".jpg") or s.endswith(".jpeg"):
            return "image/jpeg"
        return "image/png"

    icon_type = _guess_mime(icon_url)
    icon_192 = icon_url or url_for("static", filename="icons/icon-192x192.png")
    icon_512 = icon_url or url_for("static", filename="icons/icon-512x512.png")
    icon_apple = icon_url or url_for("static", filename="icons/apple-touch-icon.png")

    data = {
        "name": f"{brand} - Piattaforma Sport Dilettantistico",
        "short_name": brand,
        "description": "Piattaforma per la gestione dello sport dilettantistico: società, atleti, eventi e tornei.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": theme_color,
        "orientation": "any",
        "id": "/",
        "lang": "it",
        "dir": "ltr",
        "prefer_related_applications": False,
        "icons": [
            {"src": icon_192, "sizes": "192x192", "type": icon_type, "purpose": "any"},
            {"src": icon_192, "sizes": "192x192", "type": icon_type, "purpose": "maskable"},
            {"src": icon_512, "sizes": "512x512", "type": icon_type, "purpose": "any"},
            {"src": icon_512, "sizes": "512x512", "type": icon_type, "purpose": "maskable"},
            {"src": icon_apple, "sizes": "180x180", "type": icon_type, "purpose": "any"},
        ],
        "shortcuts": [
            {"name": "Feed", "short_name": "Feed", "description": "Vedi il feed social", "url": "/social/feed",
             "icons": [{"src": icon_192, "sizes": "192x192"}]},
            {"name": "Messaggi", "short_name": "Messaggi", "description": "Apri i messaggi", "url": "/messages/",
             "icons": [{"src": icon_192, "sizes": "192x192"}]},
            {"name": "Calendario", "short_name": "Calendario", "description": "Vedi il planner eventi", "url": "/scheduler/",
             "icons": [{"src": icon_192, "sizes": "192x192"}]},
            {"name": "Profilo", "short_name": "Profilo", "description": "Vai al tuo profilo", "url": "/social/profile",
             "icons": [{"src": icon_192, "sizes": "192x192"}]},
        ],
        "categories": ["sports", "social", "lifestyle"],
        "share_target": {"action": "/social/create_post", "method": "GET", "params": {"text": "content"}},
    }

    body = _json.dumps(data, ensure_ascii=False)
    resp = Response(body, mimetype="application/manifest+json")
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


@bp.route('/')
def index():
    """Homepage - redirect based on auth status"""
    if current_user.is_authenticated:
        return redirect(url_for('social.feed'))
    sections = _page_sections('main.index')
    landing_stats = {'users': 0, 'societies': 0, 'events': 0, 'posts': 0}
    try:
        from app.models import User, SportsSociety, Event, Post
        landing_stats['users'] = db.session.query(User).count()
        landing_stats['societies'] = db.session.query(SportsSociety).count()
        landing_stats['events'] = db.session.query(Event).count()
        landing_stats['posts'] = db.session.query(Post).count()
    except Exception:
        pass
    return render_template('main/index.html', pb_sections=sections, landing_stats=landing_stats)


@bp.route('/login')
def login_redirect():
    """
    Compatibility route.

    Some deployments (or old links) point to `/login`, while the auth blueprint
    uses `/auth/login`. Keep this stable to avoid 404/500 at the edge (nginx rewrites).
    """
    next_page = request.args.get("next")
    if next_page:
        return redirect(url_for("auth.login", next=next_page), code=302)
    return redirect(url_for("auth.login"), code=302)


@bp.route('/about')
def about():
    """About page"""
    sections = _page_sections('main.about')
    return render_template('main/about.html', pb_sections=sections)


@bp.route('/contact', methods=['GET', 'POST'])
def contact():
    """Contact page with optional message form"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        subject = request.form.get('subject', '').strip()
        message_text = request.form.get('message', '').strip()
        if name and email and subject and message_text:
            try:
                from app.models import ContactMessage
                msg = ContactMessage(name=name, email=email, subject=subject, message=message_text)
                db.session.add(msg)
                db.session.commit()
                flash('Messaggio inviato con successo! Ti risponderemo al più presto.', 'success')
            except Exception:
                db.session.rollback()
                import logging
                logging.getLogger(__name__).exception('Errore salvataggio messaggio di contatto')
                flash('Messaggio inviato con successo! Ti risponderemo al più presto.', 'success')
        else:
            flash('Per favore compila tutti i campi.', 'warning')
        return redirect(url_for('main.contact'))
    sections = _page_sections('main.contact')
    return render_template('main/contact.html', pb_sections=sections)


@bp.route('/healthz')
def healthz():
    """Health check for uptime monitoring (DB + basic app checks)."""
    from sqlalchemy import text
    from datetime import datetime, timezone
    try:
        db.session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    status = "ok" if db_ok else "degraded"
    code = 200 if db_ok else 500
    return {
        "status": status,
        "db": "ok" if db_ok else "error",
        "ts": datetime.now(timezone.utc).isoformat() + "Z",
    }, code


@bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard (personal, configurable)."""
    if not getattr(current_user, 'onboarding_completed', True):
        return redirect(url_for('main.onboarding'))
    from app.models import Dashboard, DashboardTemplate, Notification, Message, Post, Event, Task, UserDashboardLayout
    from app.main.dashboard_widgets import render_widget, get_widget_registry, get_widget_info, DEFAULT_WIDGETS
    import json

    try:
        user_layouts = UserDashboardLayout.query.filter_by(
            user_id=current_user.id, is_visible=True
        ).order_by(UserDashboardLayout.position).all()
    except Exception:
        if current_app:
            current_app.logger.exception('Dashboard layouts load failed')
        user_layouts = []

    rendered_widgets = []
    if user_layouts:
        for layout in user_layouts:
            html = render_widget(layout.widget_key, current_user)
            info = get_widget_info(layout.widget_key)
            size_class = {'small': 'col-12 col-md-4', 'medium': 'col-12 col-md-6', 'large': 'col-12'}.get(layout.size, 'col-12 col-md-6')
            rendered_widgets.append({
                'key': layout.widget_key,
                'html': html,
                'size_class': size_class,
                'info': info,
            })
    else:
        for wkey in DEFAULT_WIDGETS:
            html = render_widget(wkey, current_user)
            info = get_widget_info(wkey)
            rendered_widgets.append({
                'key': wkey,
                'html': html,
                'size_class': 'col-12 col-md-6',
                'info': info,
            })

    dash = None
    try:
        dash = Dashboard.query.filter_by(user_id=current_user.id, is_default=True).first()
        if not dash:
            dash = Dashboard.query.filter_by(user_id=current_user.id).order_by(Dashboard.id.asc()).first()

        if not dash:
            tpl = DashboardTemplate.query.filter_by(role_name=current_user.role).first()
            if not tpl:
                tpl = DashboardTemplate.query.filter_by(role_name=None).first()
            widgets = []
            layout = 'grid'
            if tpl:
                try:
                    widgets = json.loads(tpl.widgets or '[]')
                except Exception:
                    widgets = []
                layout = tpl.layout or 'grid'
            if not widgets:
                widgets = [
                    {"type": "quick_links"},
                    {"type": "stats"},
                    {"type": "recent_notifications"},
                ]
            dash = Dashboard(
                name='Il mio cruscotto',
                description='Dashboard personale',
                user_id=current_user.id,
                widgets=json.dumps(widgets),
                layout=layout,
                is_default=True,
            )
            db.session.add(dash)
            db.session.commit()
    except Exception:
        db.session.rollback()
        if current_app:
            current_app.logger.exception('Dashboard load/create failed')

    if not dash:
        dash = SimpleNamespace(name='Cruscotto', description='Dashboard personale')
        dash.get_widgets = lambda: []

    try:
        widgets = dash.get_widgets()
    except Exception:
        widgets = []

    stats = {}
    try:
        stats = {
            "posts": Post.query.filter_by(user_id=current_user.id).count(),
            "events_created": Event.query.filter_by(creator_id=current_user.id).count(),
            "tasks_assigned": Task.query.filter_by(assigned_to=current_user.id).count(),
            "notifications_unread": Notification.query.filter_by(user_id=current_user.id, is_read=False).count(),
            "messages_unread": Message.query.filter_by(recipient_id=current_user.id, is_read=False).count(),
        }
    except Exception:
        stats = {}

    recent_notifications = []
    try:
        recent_notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(5).all()
    except Exception:
        recent_notifications = []

    from datetime import datetime
    hour = datetime.now().hour
    if hour < 6:
        greeting = 'Buonanotte'
        greeting_icon = 'bi-moon-stars-fill'
    elif hour < 12:
        greeting = 'Buongiorno'
        greeting_icon = 'bi-sunrise-fill'
    elif hour < 18:
        greeting = 'Buon pomeriggio'
        greeting_icon = 'bi-sun-fill'
    else:
        greeting = 'Buonasera'
        greeting_icon = 'bi-sunset-fill'

    return render_template(
        'main/dashboard.html',
        dashboard=dash,
        widgets=widgets,
        stats=stats,
        recent_notifications=recent_notifications,
        rendered_widgets=rendered_widgets,
        has_custom_layout=bool(user_layouts),
        greeting=greeting,
        greeting_icon=greeting_icon,
    )


@bp.route('/onboarding')
@login_required
def onboarding():
    if getattr(current_user, 'onboarding_completed', False):
        return redirect(url_for('main.dashboard'))
    return render_template('main/onboarding.html')


@bp.route('/onboarding/complete', methods=['POST'])
@login_required
def complete_onboarding():
    try:
        current_user.onboarding_completed = True
        db.session.commit()
    except Exception:
        db.session.rollback()
    return redirect(url_for('main.dashboard'))


@bp.route('/dashboard/customize')
@login_required
def customize_dashboard():
    """Dashboard customization page with drag-drop widgets."""
    from app.models import UserDashboardLayout
    from app.main.dashboard_widgets import get_widget_registry, DEFAULT_WIDGETS
    import json

    all_widgets = get_widget_registry()
    user_layouts = UserDashboardLayout.query.filter_by(
        user_id=current_user.id
    ).order_by(UserDashboardLayout.position).all()

    active_keys = {l.widget_key for l in user_layouts}
    active_widgets = []
    for l in user_layouts:
        winfo = None
        for w in all_widgets:
            if w['key'] == l.widget_key:
                winfo = w
                break
        active_widgets.append({
            'key': l.widget_key,
            'size': l.size or 'medium',
            'visible': l.is_visible,
            'info': winfo or {'key': l.widget_key, 'name': l.widget_key, 'icon': 'bi-square', 'description': ''},
        })

    available_widgets = [w for w in all_widgets if w['key'] not in active_keys]

    return render_template('main/dashboard_customize.html',
        all_widgets=all_widgets,
        active_widgets=active_widgets,
        available_widgets=available_widgets,
        has_layout=bool(user_layouts))


@bp.route('/dashboard/save-layout', methods=['POST'])
@login_required
def save_dashboard_layout():
    """Save widget layout from customization page."""
    from app.models import UserDashboardLayout
    import json

    try:
        data = request.get_json()
        if not data or 'widgets' not in data:
            return jsonify({'status': 'error', 'message': 'Dati non validi'}), 400

        UserDashboardLayout.query.filter_by(user_id=current_user.id).delete()

        for i, w in enumerate(data['widgets']):
            layout = UserDashboardLayout(
                user_id=current_user.id,
                widget_key=w.get('key', ''),
                position=i,
                size=w.get('size', 'medium'),
                is_visible=w.get('visible', True),
            )
            db.session.add(layout)

        db.session.commit()
        return jsonify({'status': 'ok', 'message': 'Layout salvato con successo!'})
    except Exception:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Errore nel salvataggio'}), 500


@bp.route('/dashboard/reset-layout', methods=['POST'])
@login_required
def reset_dashboard_layout():
    """Reset widget layout to defaults."""
    from app.models import UserDashboardLayout

    try:
        UserDashboardLayout.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        flash('Layout del cruscotto ripristinato.', 'success')
    except Exception:
        db.session.rollback()
        flash('Errore nel ripristino.', 'danger')
    return redirect(url_for('main.dashboard'))


@bp.route('/dashboard/edit', methods=['GET', 'POST'])
@login_required
def edit_dashboard():
    """Edit the current user's default dashboard."""
    from app.models import Dashboard, DashboardTemplate
    import json

    dash = Dashboard.query.filter_by(user_id=current_user.id, is_default=True).first()
    if not dash:
        dash = Dashboard.query.filter_by(user_id=current_user.id).order_by(Dashboard.id.asc()).first()
    if not dash:
        # Force creation by visiting /dashboard first
        return redirect(url_for('main.dashboard'))

    form = DashboardEditForm()
    if request.method == 'GET':
        form.name.data = dash.name
        form.widgets.data = dash.widgets

    if form.validate_on_submit():
        try:
            parsed = json.loads(form.widgets.data or '[]')
            if not isinstance(parsed, list):
                raise ValueError('Widgets must be a JSON array')
        except Exception as exc:
            flash(f'JSON non valido: {exc}', 'danger')
            return render_template('main/dashboard_edit.html', form=form, dashboard=dash)

        dash.name = form.name.data
        dash.widgets = form.widgets.data
        db.session.commit()
        flash('Cruscotto aggiornato.', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('main/dashboard_edit.html', form=form, dashboard=dash)


@bp.route('/dashboard/reset', methods=['POST'])
@login_required
def reset_dashboard():
    """Reset dashboard to the role template."""
    from app.models import Dashboard, DashboardTemplate
    import json

    dash = Dashboard.query.filter_by(user_id=current_user.id, is_default=True).first()
    if not dash:
        flash('Nessun cruscotto trovato.', 'warning')
        return redirect(url_for('main.dashboard'))

    tpl = DashboardTemplate.query.filter_by(role_name=current_user.role).first()
    if not tpl:
        tpl = DashboardTemplate.query.filter_by(role_name=None).first()
    if not tpl:
        flash('Nessun template disponibile.', 'warning')
        return redirect(url_for('main.dashboard'))

    dash.layout = tpl.layout or dash.layout
    dash.widgets = tpl.widgets
    db.session.commit()
    flash('Cruscotto ripristinato al template.', 'success')
    return redirect(url_for('main.dashboard'))


@bp.route('/scope/society', methods=['POST'])
@login_required
def set_society_scope():
    """
    Set active society scope in session.
    Used to switch context when a user has multiple memberships.
    """
    society_id = request.form.get('society_id', type=int)
    if not society_id:
        session.pop('active_society_id', None)
        flash('Contesto società ripristinato.', 'success')
        return redirect(request.referrer or url_for('main.dashboard'))

    if not current_user.can_access_society(society_id) and not check_permission(current_user, 'admin', 'access'):
        flash('Non puoi selezionare questa società.', 'danger')
        return redirect(request.referrer or url_for('main.dashboard'))

    session['active_society_id'] = int(society_id)
    flash('Contesto società aggiornato.', 'success')
    return redirect(request.referrer or url_for('main.dashboard'))


@bp.route('/guida-utente')
def guide_user():
    """User guide page."""
    return render_template('main/guide_user.html')


@bp.route('/guida-societa')
def guide_society():
    """Society admin guide page."""
    return render_template('main/guide_society.html')


@bp.route('/contatta-admin', methods=['GET', 'POST'])
@login_required
def contact_admin():
    """Contact super admin via internal message."""
    from app.models import User, Message
    form = ContactAdminForm()
    if form.validate_on_submit():
        admin_user = User.query.filter_by(role='super_admin').first()
        if not admin_user:
            admin_user = User.query.filter(
                User.role.in_(['super_admin', 'admin'])
            ).first()
        if not admin_user:
            flash('Nessun amministratore disponibile al momento. Riprova più tardi.', 'warning')
            return redirect(url_for('main.contact_admin'))

        category_labels = {
            'supporto_tecnico': 'Supporto Tecnico',
            'segnalazione_bug': 'Segnalazione Bug',
            'richiesta_funzionalita': 'Richiesta Funzionalità',
            'domanda_generale': 'Domanda Generale',
            'problemi_account': 'Problemi Account',
            'altro': 'Altro'
        }
        cat_label = category_labels.get(form.category.data, form.category.data)
        full_subject = f'[{cat_label}] {form.subject.data}'

        try:
            msg = Message(
                sender_id=current_user.id,
                recipient_id=admin_user.id,
                subject=full_subject,
                body=form.message.data,
                is_read=False
            )
            db.session.add(msg)
            db.session.commit()
            flash('Il tuo messaggio è stato inviato con successo! Riceverai una risposta il prima possibile.', 'success')
            return redirect(url_for('main.contact_admin'))
        except Exception:
            db.session.rollback()
            flash('Si è verificato un errore nell\'invio del messaggio. Riprova.', 'danger')

    return render_template('main/contact_admin.html', form=form)


@bp.route('/privacy')
def privacy_policy():
    """Privacy policy page."""
    return render_template('main/privacy_policy.html')


@bp.route('/termini')
def terms():
    """Terms of service page."""
    return render_template('main/terms.html')


@bp.route('/set-language', methods=['POST'])
def set_language():
    """Set user language preference."""
    from app.translations import SUPPORTED_LANGUAGES
    lang = request.form.get('language', 'it')
    if lang not in SUPPORTED_LANGUAGES:
        lang = 'it'
    session['language'] = lang
    if current_user.is_authenticated:
        try:
            current_user.language = lang
            db.session.commit()
        except Exception:
            db.session.rollback()
    referrer = request.referrer
    if referrer and (referrer.startswith('/') or referrer.startswith(request.host_url)):
        return redirect(referrer)
    return redirect(url_for('main.index'))


@bp.route('/cookie-policy')
def cookie_policy():
    """Cookie policy page - redirects to privacy with cookie section."""
    return redirect(url_for('main.privacy_policy') + '#cookieSection')


@bp.route('/api/search-suggestions')
@login_required
def search_suggestions():
    q = request.args.get('q', '').strip()
    scope = request.args.get('scope', 'all')
    if not q or len(q) < 2:
        return jsonify([])

    results = []
    search_term = f'%{q}%'

    from app.models import User, Event, MarketplaceListing, Society, Role

    if scope in ('all', 'users'):
        super_admin_role = Role.query.filter_by(name='super_admin').first()
        users_q = User.query.filter(
            User.is_active == True,
            or_(
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term),
                User.username.ilike(search_term),
                User.company_name.ilike(search_term)
            )
        )
        if super_admin_role and not current_user.is_admin():
            users_q = users_q.filter(User.role_id != super_admin_role.id)
        users = users_q.limit(8).all()
        for u in users:
            results.append({
                'type': 'user',
                'id': u.id,
                'text': u.get_full_name(),
                'sub': f'@{u.username}',
                'icon': 'bi-person-fill',
                'url': url_for('social.profile', user_id=u.id),
                'avatar': url_for('static', filename='uploads/' + u.avatar) if u.avatar else None
            })

    if scope in ('all', 'marketplace'):
        listings = MarketplaceListing.query.filter(
            MarketplaceListing.status == 'active',
            or_(
                MarketplaceListing.title.ilike(search_term),
                MarketplaceListing.description.ilike(search_term),
                MarketplaceListing.location.ilike(search_term)
            )
        ).limit(6).all()
        for l in listings:
            results.append({
                'type': 'listing',
                'id': l.id,
                'text': l.title,
                'sub': f'{l.price:.2f} EUR' if l.price else 'Gratis',
                'icon': 'bi-shop',
                'url': url_for('marketplace.listing_detail', listing_id=l.id),
                'avatar': None
            })

    if scope in ('all', 'events'):
        events = Event.query.filter(
            or_(
                Event.title.ilike(search_term),
                Event.description.ilike(search_term)
            )
        ).order_by(Event.start_date.desc()).limit(5).all()
        for e in events:
            results.append({
                'type': 'event',
                'id': e.id,
                'text': e.title,
                'sub': e.start_date.strftime('%d/%m/%Y') if e.start_date else '',
                'icon': 'bi-calendar-event-fill',
                'url': url_for('events.detail', event_id=e.id),
                'avatar': None
            })

    if scope in ('all', 'societies'):
        societies = Society.query.filter(
            or_(
                Society.legal_name.ilike(search_term),
                Society.sport_type.ilike(search_term)
            )
        ).limit(5).all()
        for s in societies:
            results.append({
                'type': 'society',
                'id': s.id,
                'text': s.legal_name,
                'sub': s.sport_type or '',
                'icon': 'bi-building',
                'url': url_for('social.profile', user_id=s.admin_id) if s.admin_id else '#',
                'avatar': None
            })

    return jsonify(results[:15])
