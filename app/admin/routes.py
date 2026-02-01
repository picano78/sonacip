"""
Admin routes
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from flask import current_app
from sqlalchemy import or_, and_, func, desc
from app import db
from app.admin.utils import admin_required
from app.admin.forms import (
    AdsSettingsForm,
    AppearanceSettingsForm,
    DashboardTemplateForm,
    NavigationConfigForm,
    SmtpSettingsForm,
    WhatsappSettingsForm,
    PageCustomizationForm,
    PrivacySettingsForm,
    SiteCustomizationForm,
    SocialSettingsAdminForm,
    StorageSettingsForm,
    UserEditForm,
    UserSearchForm,
    AdCampaignForm,
    AdCreativeForm,
)
from app.models import (
    AdsSetting,
    AppearanceSetting,
    AuditLog,
    Backup,
    Comment,
    CustomizationKV,
    DashboardTemplate,
    Event,
    Notification,
    PageCustomization,
    Post,
    PlatformFeeSetting,
    PlatformTransaction,
    PrivacySetting,
    SiteCustomization,
    SocialSetting,
    Society,
    StorageSetting,
    SmtpSetting,
    WhatsappSetting,
    WhatsappTemplate,
    WhatsappMessageLog,
    User,
    AdCampaign,
    AdCreative,
    AdEvent,
)
from datetime import datetime, timedelta
import os
from app.utils import log_action

bp = Blueprint('admin', __name__, url_prefix='/admin')


@bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard with statistics"""
    # Get statistics
    stats = {
        'total_users': User.query.count(),
        'total_societies': Society.query.count(),
        'total_athletes': User.query.filter_by(role='atleta').count(),
        'total_posts': Post.query.count(),
        'total_events': Event.query.count(),
        'active_users_today': User.query.filter(
            User.last_seen >= datetime.utcnow() - timedelta(days=1)
        ).count(),
        'new_users_week': User.query.filter(
            User.created_at >= datetime.utcnow() - timedelta(days=7)
        ).count(),
        'pending_events': Event.query.filter_by(status='scheduled').count()
    }
    
    # Recent users
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    
    # Recent activity logs
    recent_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(20).all()
    
    return render_template('admin/dashboard.html', 
                         stats=stats,
                         recent_users=recent_users,
                         recent_logs=recent_logs)


@bp.route('/appearance', methods=['GET', 'POST'])
@login_required
@admin_required
def appearance_settings():
    """Tema piattaforma (global)."""
    settings = AppearanceSetting.query.filter_by(scope='global').first()
    if not settings:
        settings = AppearanceSetting(scope='global')
        db.session.add(settings)
        db.session.commit()

    form = AppearanceSettingsForm(obj=settings)
    if form.validate_on_submit():
        settings.primary_color = form.primary_color.data or settings.primary_color
        settings.secondary_color = form.secondary_color.data or settings.secondary_color
        settings.accent_color = form.accent_color.data or settings.accent_color
        settings.font_family = form.font_family.data or settings.font_family
        settings.logo_url = form.logo_url.data or None
        settings.favicon_url = form.favicon_url.data or None
        settings.layout_style = form.layout_style.data or settings.layout_style
        settings.updated_by = current_user.id
        settings.updated_at = datetime.utcnow()
        db.session.commit()

        log_action('update_appearance', 'AppearanceSetting', settings.id, 'Updated global appearance')
        flash('Tema aggiornato.', 'success')
        return redirect(url_for('admin.appearance_settings'))

    return render_template('admin/appearance_settings.html', form=form, settings=settings)


@bp.route('/social-settings', methods=['GET', 'POST'])
@login_required
@admin_required
def social_settings():
    """Governance social (global)."""
    settings = SocialSetting.query.first()
    if not settings:
        settings = SocialSetting()
        db.session.add(settings)
        db.session.commit()

    form = SocialSettingsAdminForm(obj=settings)
    if form.validate_on_submit():
        settings.feed_enabled = bool(form.feed_enabled.data)
        settings.allow_likes = bool(form.allow_likes.data)
        settings.allow_comments = bool(form.allow_comments.data)
        settings.allow_shares = bool(form.allow_shares.data)
        settings.boost_official = bool(form.boost_official.data)
        settings.mute_user_posts = bool(form.mute_user_posts.data)
        if form.max_posts_per_day.data:
            try:
                settings.max_posts_per_day = int(form.max_posts_per_day.data)
            except Exception:
                pass
        settings.boosted_types = form.boosted_types.data or None
        settings.muted_types = form.muted_types.data or None
        settings.updated_by = current_user.id
        settings.updated_at = datetime.utcnow()
        db.session.commit()

        log_action('update_social_settings', 'SocialSetting', settings.id, 'Updated social governance')
        flash('Impostazioni social aggiornate.', 'success')
        return redirect(url_for('admin.social_settings'))

    return render_template('admin/social_settings.html', form=form, settings=settings)


@bp.route('/storage-settings', methods=['GET', 'POST'])
@login_required
@admin_required
def storage_settings():
    """Storage media (global)."""
    settings = StorageSetting.query.first()
    if not settings:
        settings = StorageSetting()
        db.session.add(settings)
        db.session.commit()

    form = StorageSettingsForm(obj=settings)
    if form.validate_on_submit():
        settings.storage_backend = form.storage_backend.data or settings.storage_backend
        settings.base_path = form.base_path.data or settings.base_path
        settings.preferred_image_format = form.preferred_image_format.data or settings.preferred_image_format
        settings.preferred_video_format = form.preferred_video_format.data or settings.preferred_video_format

        def _int(value, default):
            try:
                return int(value)
            except Exception:
                return default

        settings.image_quality = _int(form.image_quality.data, settings.image_quality)
        settings.video_bitrate = _int(form.video_bitrate.data, settings.video_bitrate)
        settings.video_max_width = _int(form.video_max_width.data, settings.video_max_width)
        settings.max_image_mb = _int(form.max_image_mb.data, settings.max_image_mb)
        settings.max_video_mb = _int(form.max_video_mb.data, settings.max_video_mb)

        settings.updated_by = current_user.id
        settings.updated_at = datetime.utcnow()
        db.session.commit()

        log_action('update_storage_settings', 'StorageSetting', settings.id, 'Updated storage settings')
        flash('Impostazioni storage aggiornate.', 'success')
        return redirect(url_for('admin.storage_settings'))

    return render_template('admin/storage_settings.html', form=form, settings=settings)


@bp.route('/site-customization', methods=['GET', 'POST'])
@login_required
@admin_required
def site_customization():
    """Branding/navbar/footer/CSS (global)."""
    settings = SiteCustomization.query.first()
    if not settings:
        settings = SiteCustomization()
        db.session.add(settings)
        db.session.commit()

    form = SiteCustomizationForm(obj=settings)
    if form.validate_on_submit():
        settings.navbar_brand_text = form.navbar_brand_text.data or settings.navbar_brand_text
        settings.navbar_brand_icon = form.navbar_brand_icon.data or settings.navbar_brand_icon
        settings.footer_html = form.footer_html.data or None
        settings.custom_css = form.custom_css.data or None
        settings.updated_by = current_user.id
        settings.updated_at = datetime.utcnow()
        db.session.commit()

        log_action('update_site_customization', 'SiteCustomization', settings.id, 'Updated global site customization')
        flash('Personalizzazione sito aggiornata.', 'success')
        return redirect(url_for('admin.site_customization'))

    return render_template('admin/site_customization.html', form=form, settings=settings)


@bp.route('/navigation', methods=['GET', 'POST'])
@login_required
@admin_required
def navigation():
    """Navbar navigation (site-wide)."""
    import json

    row = CustomizationKV.query.filter_by(scope='site', scope_key=None, key='navbar.links').first()
    if not row:
        default_links = [
            {"label": "Home", "endpoint": "social.feed", "icon": "bi-house-fill", "resource": "social", "action": "comment"},
            {"label": "Esplora", "endpoint": "social.explore", "icon": "bi-compass"},
            {"label": "Eventi", "endpoint": "events.index", "icon": "bi-calendar-event", "resource": "events", "action": "view"},
            {"label": "Tornei", "endpoint": "tournaments.list_tournaments", "icon": "bi-trophy", "resource": "tournaments", "action": "view"},
            {"label": "Calendario Società", "endpoint": "calendar.index", "icon": "bi-calendar3-range", "resource": "calendar", "action": "view"},
            {"label": "CRM", "endpoint": "crm.index", "icon": "bi-briefcase", "resource": "crm", "action": "access"},
            {"label": "Admin", "endpoint": "admin.dashboard", "icon": "bi-gear-fill", "resource": "admin", "action": "access"},
        ]
        row = CustomizationKV(scope='site', scope_key=None, key='navbar.links', value_json=json.dumps(default_links))
        db.session.add(row)
        db.session.commit()

    form = NavigationConfigForm()
    if request.method == 'GET':
        form.links_json.data = row.value_json

    if form.validate_on_submit():
        try:
            parsed = json.loads(form.links_json.data or '[]')
            if not isinstance(parsed, list):
                raise ValueError('Deve essere un JSON array')
        except Exception as exc:
            flash(f'JSON non valido: {exc}', 'danger')
            return render_template('admin/navigation.html', form=form)

        row.value_json = form.links_json.data
        row.updated_by = current_user.id
        row.updated_at = datetime.utcnow()
        db.session.add(row)
        db.session.commit()
        log_action('update_navigation', 'CustomizationKV', row.id, 'Updated navbar links')
        flash('Navbar aggiornata.', 'success')
        return redirect(url_for('admin.navigation'))

    return render_template('admin/navigation.html', form=form)


@bp.route('/smtp', methods=['GET', 'POST'])
@login_required
@admin_required
def smtp_settings():
    """SMTP settings (super admin)."""
    settings = SmtpSetting.query.first()
    if not settings:
        settings = SmtpSetting(enabled=False)
        db.session.add(settings)
        db.session.commit()

    form = SmtpSettingsForm(obj=settings)
    if request.method == 'GET':
        form.port.data = str(settings.port or 587)

    if form.validate_on_submit():
        settings.enabled = bool(form.enabled.data)
        settings.host = form.host.data or None
        try:
            settings.port = int(form.port.data) if form.port.data else 587
        except Exception:
            settings.port = 587
        settings.use_tls = bool(form.use_tls.data)
        settings.username = form.username.data or None
        if form.password.data:
            settings.password = form.password.data
        settings.default_sender = form.default_sender.data or settings.default_sender
        settings.updated_by = current_user.id
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        log_action('update_smtp_settings', 'SmtpSetting', settings.id, 'Updated SMTP settings')

        # Optional test send
        if form.test_recipient.data:
            from app.notifications.utils import send_email
            ok = send_email(
                recipient=form.test_recipient.data,
                subject='SONACIP - Test SMTP',
                body='Questo è un test SMTP inviato dal pannello Super Admin.',
            )
            flash('Test email inviata.' if ok else 'Invio test fallito. Controlla i log.', 'success' if ok else 'danger')
        else:
            flash('Impostazioni SMTP salvate.', 'success')

        return redirect(url_for('admin.smtp_settings'))

    return render_template('admin/smtp_settings.html', form=form, settings=settings)


@bp.route('/whatsapp', methods=['GET', 'POST'])
@login_required
@admin_required
def whatsapp_settings():
    """WhatsApp settings (super admin)."""
    settings = WhatsappSetting.query.first()
    if not settings:
        settings = WhatsappSetting(enabled=False, provider='webhook')
        db.session.add(settings)
        db.session.commit()

    form = WhatsappSettingsForm(obj=settings)
    if form.validate_on_submit():
        settings.enabled = bool(form.enabled.data)
        settings.provider = form.provider.data or 'webhook'
        settings.api_url = form.api_url.data or None
        if form.api_token.data:
            settings.api_token = form.api_token.data
        settings.from_number = form.from_number.data or None
        settings.updated_by = current_user.id
        settings.updated_at = datetime.utcnow()
        db.session.commit()

        log_action('update_whatsapp_settings', 'WhatsappSetting', settings.id, 'Updated WhatsApp settings')

        # Optional test send
        if form.test_phone.data and form.test_message.data:
            try:
                from app.notifications.utils import send_whatsapp
                ok = send_whatsapp(form.test_phone.data, form.test_message.data)
                if ok:
                    flash('WhatsApp test inviato (provider).', 'success')
                else:
                    flash('WhatsApp non configurato o disabilitato.', 'warning')
            except Exception as exc:
                flash(f'Invio WhatsApp fallito: {exc}', 'danger')
        else:
            flash('Impostazioni WhatsApp salvate.', 'success')

        return redirect(url_for('admin.whatsapp_settings'))

    return render_template('admin/whatsapp_settings.html', form=form, settings=settings)


@bp.route('/whatsapp/templates', methods=['GET', 'POST'])
@login_required
@admin_required
def whatsapp_templates():
    """WhatsApp templates registry (super admin)."""
    if request.method == 'POST':
        key = (request.form.get('key') or '').strip()
        provider_name = (request.form.get('provider_template_name') or '').strip()
        language_code = (request.form.get('language_code') or 'it').strip()
        category = (request.form.get('category') or 'utility').strip()
        body_preview = (request.form.get('body_preview') or '').strip() or None
        if not key or len(key) < 3:
            flash('Key non valida.', 'danger')
            return redirect(url_for('admin.whatsapp_templates'))
        if not provider_name:
            flash('Nome template provider richiesto.', 'danger')
            return redirect(url_for('admin.whatsapp_templates'))
        if WhatsappTemplate.query.filter_by(key=key).first():
            flash('Key già esistente.', 'danger')
            return redirect(url_for('admin.whatsapp_templates'))
        t = WhatsappTemplate(
            key=key,
            provider_template_name=provider_name,
            language_code=language_code,
            category=category,
            body_preview=body_preview,
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db.session.add(t)
        db.session.commit()
        log_action('create_whatsapp_template', 'WhatsappTemplate', t.id, f'key={key}')
        flash('Template creato.', 'success')
        return redirect(url_for('admin.whatsapp_templates'))

    templates = WhatsappTemplate.query.order_by(WhatsappTemplate.created_at.desc()).limit(300).all()
    recent_logs = WhatsappMessageLog.query.order_by(WhatsappMessageLog.created_at.desc()).limit(50).all()
    return render_template('admin/whatsapp_templates.html', templates=templates, recent_logs=recent_logs)


@bp.route('/whatsapp/templates/<int:template_id>/toggle', methods=['POST'])
@login_required
@admin_required
def whatsapp_template_toggle(template_id: int):
    t = WhatsappTemplate.query.get_or_404(template_id)
    t.is_active = not bool(t.is_active)
    db.session.commit()
    log_action('toggle_whatsapp_template', 'WhatsappTemplate', t.id, f'active={t.is_active}')
    flash('Template aggiornato.', 'success')
    return redirect(url_for('admin.whatsapp_templates'))


@bp.route('/platform/fees', methods=['GET', 'POST'])
@login_required
@admin_required
def platform_fees():
    """Configure platform take-rate settings."""
    settings = PlatformFeeSetting.query.first()
    if not settings:
        settings = PlatformFeeSetting(take_rate_percent=5, min_fee_cents=0, currency='EUR', updated_at=datetime.utcnow(), updated_by=current_user.id)
        db.session.add(settings)
        db.session.commit()

    if request.method == 'POST':
        try:
            pct = int(request.form.get('take_rate_percent') or 5)
        except Exception:
            pct = 5
        try:
            min_fee_cents = int(request.form.get('min_fee_cents') or 0)
        except Exception:
            min_fee_cents = 0
        currency = (request.form.get('currency') or 'EUR').strip().upper()

        settings.take_rate_percent = max(0, min(100, pct))
        settings.min_fee_cents = max(0, min_fee_cents)
        settings.currency = currency or 'EUR'
        settings.updated_by = current_user.id
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        log_action('update_platform_fees', 'PlatformFeeSetting', settings.id, f'pct={settings.take_rate_percent} min={settings.min_fee_cents}')
        flash('Impostazioni aggiornate.', 'success')
        return redirect(url_for('admin.platform_fees'))

    return render_template('admin/platform_fees.html', settings=settings)


@bp.route('/platform/transactions')
@login_required
@admin_required
def platform_transactions():
    """View platform take-rate ledger."""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    pagination = PlatformTransaction.query.order_by(PlatformTransaction.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    items = pagination.items

    total_platform = db.session.query(func.sum(PlatformTransaction.platform_fee_amount)).scalar() or 0
    total_gross = db.session.query(func.sum(PlatformTransaction.gross_amount)).scalar() or 0

    stats = {"total_gross": float(total_gross), "total_platform": float(total_platform)}
    return render_template('admin/platform_transactions.html', transactions=items, pagination=pagination, stats=stats)


@bp.route('/pages')
@login_required
@admin_required
def pages():
    """Elenco pagine personalizzabili."""
    pages = PageCustomization.query.order_by(PageCustomization.slug.asc()).all()
    existing = {p.slug: p for p in pages}

    endpoints = []
    for rule in current_app.url_map.iter_rules():
        if rule.endpoint == 'static':
            continue
        if 'GET' not in rule.methods:
            continue
        endpoints.append({
            'endpoint': rule.endpoint,
            'url': str(rule),
            'has_custom': rule.endpoint in existing,
        })
    endpoints.sort(key=lambda x: x['endpoint'])

    return render_template('admin/pages.html', pages=pages, endpoints=endpoints)


@bp.route('/pages/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_page():
    """Crea/modifica una pagina personalizzabile."""
    slug = request.args.get('slug') or ''
    settings = PageCustomization.query.filter_by(slug=slug).first() if slug else None
    if not settings:
        settings = PageCustomization(slug=slug or '')

    form = PageCustomizationForm(obj=settings)
    if form.validate_on_submit():
        existing = PageCustomization.query.filter_by(slug=form.slug.data).first()
        if existing and existing.id != settings.id:
            flash('Slug già esistente.', 'danger')
            return redirect(url_for('admin.edit_page', slug=settings.slug))

        settings.slug = form.slug.data
        settings.title = form.title.data or None
        settings.hero_title = form.hero_title.data or None
        settings.hero_subtitle = form.hero_subtitle.data or None
        settings.body_html = form.body_html.data or None
        settings.updated_by = current_user.id
        settings.updated_at = datetime.utcnow()

        db.session.add(settings)
        db.session.commit()

        log_action('update_page_customization', 'PageCustomization', settings.id, f'Updated page {settings.slug}')
        flash('Pagina aggiornata.', 'success')
        return redirect(url_for('admin.pages'))

    return render_template('admin/edit_page.html', form=form, settings=settings)


@bp.route('/dashboard-templates', methods=['GET', 'POST'])
@login_required
@admin_required
def dashboard_templates():
    """Gestione template cruscotti (default per ruolo)."""
    form = DashboardTemplateForm()
    if form.validate_on_submit():
        tpl = DashboardTemplate.query.filter_by(role_name=form.role_name.data or None).first()
        if not tpl:
            tpl = DashboardTemplate(role_name=form.role_name.data or None, name=form.name.data)
        tpl.name = form.name.data
        tpl.layout = form.layout.data
        tpl.widgets = form.widgets.data
        tpl.updated_by = current_user.id
        tpl.updated_at = datetime.utcnow()
        db.session.add(tpl)
        db.session.commit()
        log_action('update_dashboard_template', 'DashboardTemplate', tpl.id, f'Updated template for role={tpl.role_name}')
        flash('Template cruscotto salvato.', 'success')
        return redirect(url_for('admin.dashboard_templates'))

    templates = DashboardTemplate.query.order_by(DashboardTemplate.role_name.asc()).all()
    return render_template('admin/dashboard_templates.html', form=form, templates=templates)


@bp.route('/privacy', methods=['GET', 'POST'])
@login_required
@admin_required
def privacy_settings():
    """Gestione banner privacy e cookie"""
    settings = PrivacySetting.query.first()
    if not settings:
        settings = PrivacySetting()
        db.session.add(settings)
        db.session.commit()
    
    form = PrivacySettingsForm(obj=settings)
    if form.validate_on_submit():
        settings.banner_enabled = form.banner_enabled.data
        settings.consent_message = form.consent_message.data
        settings.privacy_url = form.privacy_url.data or None
        settings.cookie_url = form.cookie_url.data or None
        settings.updated_by = current_user.id
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Log admin action
        log = AuditLog(
            user_id=current_user.id,
            action='update_privacy_settings',
            entity_type='PrivacySetting',
            entity_id=settings.id,
            details='Updated privacy and cookie settings',
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash('Impostazioni privacy aggiornate.', 'success')
        return redirect(url_for('admin.privacy_settings'))
    
    return render_template('admin/privacy.html', form=form, settings=settings)


@bp.route('/users')
@login_required
@admin_required
def users():
    """User management page with search"""
    form = UserSearchForm(request.args, meta={'csrf': False})
    
    page = request.args.get('page', 1, type=int)
    per_page = 30
    
    # Build query
    query = User.query
    
    # Apply filters
    if form.query.data:
        search = f"%{form.query.data}%"
        query = query.filter(
            or_(
                User.username.ilike(search),
                User.email.ilike(search),
                User.first_name.ilike(search),
                User.last_name.ilike(search),
                User.company_name.ilike(search)
            )
        )
    
    if form.role.data:
        query = query.filter_by(role=form.role.data)
    
    if form.status.data == 'active':
        query = query.filter_by(is_active=True)
    elif form.status.data == 'inactive':
        query = query.filter_by(is_active=False)
    elif form.status.data == 'verified':
        query = query.filter_by(is_verified=True)
    elif form.status.data == 'unverified':
        query = query.filter_by(is_verified=False)
    
    # Paginate
    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    users = pagination.items
    
    return render_template('admin/users.html', 
                         users=users,
                         pagination=pagination,
                         form=form)


@bp.route('/users/<int:user_id>')
@login_required
@admin_required
def user_detail(user_id):
    """User detail page"""
    user = User.query.get_or_404(user_id)
    
    # Get user statistics
    stats = {
        'posts_count': Post.query.filter_by(user_id=user.id).count(),
        'followers_count': user.followers.count(),
        'following_count': user.followed.count(),
        'events_count': Event.query.filter_by(creator_id=user.id).count(),
        'comments_count': Comment.query.filter_by(user_id=user.id).count()
    }
    
    # Recent activity
    recent_posts = Post.query.filter_by(user_id=user.id).order_by(
        Post.created_at.desc()
    ).limit(5).all()
    
    recent_logs = AuditLog.query.filter_by(user_id=user.id).order_by(
        AuditLog.created_at.desc()
    ).limit(10).all()
    
    return render_template('admin/user_detail.html',
                         user=user,
                         stats=stats,
                         recent_posts=recent_posts,
                         recent_logs=recent_logs)


@bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Edit user"""
    user = User.query.get_or_404(user_id)
    form = UserEditForm(obj=user)
    
    if form.validate_on_submit():
        user.email = form.email.data
        user.username = form.username.data
        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.phone = form.phone.data
        user.role = form.role.data
        user.is_active = form.is_active.data
        user.is_verified = form.is_verified.data
        user.is_banned = form.is_banned.data
        user.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Log the action
        log = AuditLog(
            user_id=current_user.id,
            action='edit_user',
            entity_type='User',
            entity_id=user.id,
            details=f'Admin edited user {user.username}',
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'Utente {user.username} aggiornato con successo.', 'success')
        return redirect(url_for('admin.user_detail', user_id=user.id))
    
    return render_template('admin/edit_user.html', form=form, user=user)


@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Delete user (soft delete by deactivating)"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('Non puoi eliminare il tuo stesso account.', 'danger')
        return redirect(url_for('admin.users'))
    
    user.is_active = False
    db.session.commit()
    
    # Log the action
    log = AuditLog(
        user_id=current_user.id,
        action='deactivate_user',
        entity_type='User',
        entity_id=user.id,
        details=f'Admin deactivated user {user.username}',
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
    
    flash(f'Utente {user.username} disattivato.', 'success')
    return redirect(url_for('admin.users'))


@bp.route('/posts')
@login_required
@admin_required
def posts():
    """All posts management"""
    page = request.args.get('page', 1, type=int)
    per_page = 30
    
    pagination = Post.query.order_by(Post.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    posts = pagination.items
    
    return render_template('admin/posts.html', 
                         posts=posts,
                         pagination=pagination)


@bp.route('/posts/<int:post_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_post(post_id):
    """Delete a post"""
    post = Post.query.get_or_404(post_id)
    
    # Log the action
    log = AuditLog(
        user_id=current_user.id,
        action='delete_post',
        entity_type='Post',
        entity_id=post.id,
        details=f'Admin deleted post by {post.author.username}',
        ip_address=request.remote_addr
    )
    db.session.add(log)
    
    db.session.delete(post)
    db.session.commit()
    
    flash('Post eliminato.', 'success')
    return redirect(url_for('admin.posts'))


@bp.route('/events')
@login_required
@admin_required
def events():
    """All events management"""
    page = request.args.get('page', 1, type=int)
    per_page = 30
    
    pagination = Event.query.order_by(Event.start_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    events = pagination.items
    
    return render_template('admin/events.html',
                         events=events,
                         pagination=pagination)


@bp.route('/logs')
@login_required
@admin_required
def logs():
    """Audit logs viewer"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    action_filter = request.args.get('action', '')
    
    query = AuditLog.query
    
    if action_filter:
        query = query.filter_by(action=action_filter)
    
    pagination = query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    logs = pagination.items
    
    # Get unique actions for filter
    actions = db.session.query(AuditLog.action).distinct().all()
    actions = [a[0] for a in actions]
    
    return render_template('admin/logs.html',
                         logs=logs,
                         pagination=pagination,
                         actions=actions,
                         current_action=action_filter)


@bp.route('/ads-settings', methods=['GET', 'POST'])
@login_required
@admin_required
def ads_settings():
    """Gestione tariffe inserzioni/promo post"""
    settings = AdsSetting.query.first()
    if not settings:
        settings = AdsSetting()
        db.session.add(settings)
        db.session.commit()

    form = AdsSettingsForm(obj=settings)
    if form.validate_on_submit():
        settings.price_per_day = float(form.price_per_day.data)
        settings.price_per_thousand_views = float(form.price_per_thousand_views.data)
        settings.default_duration_days = int(form.default_duration_days.data)
        settings.default_views = int(form.default_views.data)
        settings.updated_by = current_user.id
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Tariffe inserzioni aggiornate.', 'success')
        return redirect(url_for('admin.ads_settings'))

    return render_template('admin/ads_settings.html', form=form, settings=settings)


@bp.route('/ads', methods=['GET', 'POST'])
@login_required
@admin_required
def ads_manager():
    """Facebook-like banner manager (autopilot)."""
    campaign_form = AdCampaignForm()
    creative_form = AdCreativeForm()

    # Create campaign
    if request.method == 'POST' and request.form.get('_action') == 'create_campaign':
        if campaign_form.validate_on_submit():
            society_id = None
            raw_sid = (campaign_form.society_id.data or '').strip()
            if raw_sid:
                try:
                    society_id = int(raw_sid)
                except Exception:
                    society_id = None

            c = AdCampaign(
                name=campaign_form.name.data,
                objective=(campaign_form.objective.data or 'traffic'),
                society_id=society_id,
                autopilot=bool(campaign_form.autopilot.data),
                is_active=bool(campaign_form.is_active.data),
                starts_at=campaign_form.starts_at.data,
                ends_at=campaign_form.ends_at.data,
                max_impressions=campaign_form.max_impressions.data,
                max_clicks=campaign_form.max_clicks.data,
                created_by=current_user.id,
                created_at=datetime.utcnow(),
            )
            db.session.add(c)
            db.session.commit()
            log_action('ad_campaign_create', 'AdCampaign', c.id, c.name)
            flash('Campagna creata.', 'success')
            return redirect(url_for('admin.ads_manager'))
        flash('Errore nel form campagna.', 'danger')

    # Create creative
    if request.method == 'POST' and request.form.get('_action') == 'create_creative':
        if creative_form.validate_on_submit():
            camp = AdCampaign.query.get(int(creative_form.campaign_id.data))
            if not camp:
                flash('Campaign ID non valido.', 'danger')
                return redirect(url_for('admin.ads_manager'))
            cr = AdCreative(
                campaign_id=camp.id,
                placement=creative_form.placement.data,
                headline=(creative_form.headline.data or '').strip() or None,
                body=(creative_form.body.data or '').strip() or None,
                image_url=(creative_form.image_url.data or '').strip() or None,
                link_url=(creative_form.link_url.data or '').strip(),
                cta_label=(creative_form.cta_label.data or '').strip() or 'Scopri di più',
                weight=int(creative_form.weight.data or 100),
                is_active=bool(creative_form.is_active.data),
                created_by=current_user.id,
                created_at=datetime.utcnow(),
            )
            db.session.add(cr)
            db.session.commit()
            log_action('ad_creative_create', 'AdCreative', cr.id, f'campaign={camp.id}')
            flash('Creatività creata.', 'success')
            return redirect(url_for('admin.ads_manager'))
        flash('Errore nel form creatività.', 'danger')

    # Lists + basic stats
    campaigns = AdCampaign.query.order_by(AdCampaign.created_at.desc()).all()
    creatives = AdCreative.query.order_by(AdCreative.created_at.desc()).limit(200).all()

    def _ctr(clicks: int | None, imps: int | None) -> float:
        i = float(imps or 0)
        c = float(clicks or 0)
        return round((c / i) * 100.0, 2) if i > 0 else 0.0

    campaign_stats = {c.id: {"ctr": _ctr(c.clicks_count, c.impressions_count)} for c in campaigns}
    creative_stats = {c.id: {"ctr": _ctr(c.clicks_count, c.impressions_count)} for c in creatives}

    # Recent events for debugging
    recent_events = AdEvent.query.order_by(AdEvent.created_at.desc()).limit(50).all()

    return render_template(
        'admin/ads_manager.html',
        campaigns=campaigns,
        creatives=creatives,
        campaign_form=campaign_form,
        creative_form=creative_form,
        campaign_stats=campaign_stats,
        creative_stats=creative_stats,
        recent_events=recent_events,
    )


@bp.route('/search')
@login_required
@admin_required
def search():
    """Global search across all entities"""
    query = request.args.get('q', '')
    
    if not query:
        return render_template('admin/search.html', results={})
    
    search = f"%{query}%"
    
    # Search users
    users = User.query.filter(
        or_(
            User.username.ilike(search),
            User.email.ilike(search),
            User.first_name.ilike(search),
            User.last_name.ilike(search),
            User.company_name.ilike(search)
        )
    ).limit(20).all()
    
    # Search posts
    posts = Post.query.filter(Post.content.ilike(search)).limit(20).all()
    
    # Search events
    events = Event.query.filter(
        or_(
            Event.title.ilike(search),
            Event.description.ilike(search)
        )
    ).limit(20).all()
    
    results = {
        'users': users,
        'posts': posts,
        'events': events,
        'query': query
    }
    
    return render_template('admin/search.html', results=results)


@bp.route('/stats')
@login_required
@admin_required
def stats():
    """Detailed statistics page"""
    days = 30
    start_date = datetime.utcnow() - timedelta(days=days)

    # 1. Signup Data (Daily for chart)
    signup_map = {}
    # Initialize all days with 0
    for i in range(days):
        d = (datetime.utcnow() - timedelta(days=i)).strftime('%Y-%m-%d')
        signup_map[d] = 0
            
    try:
        users_last_days = User.query.filter(User.created_at >= start_date).all()
        for u in users_last_days:
            if u.created_at:
                d = u.created_at.strftime('%Y-%m-%d')
                if d in signup_map:
                    signup_map[d] += 1
    except Exception as e:
        print(f"Error fetching signup stats: {e}")

    signup_data = [{'date': k, 'count': v} for k, v in sorted(signup_map.items())]

    # 2. Role Data
    role_data = []
    try:
        user_stats_query = db.session.query(
            User.role,
            func.count(User.id).label('count')
        ).group_by(User.role).all()
        role_data = [{'role': r, 'count': c} for r, c in user_stats_query]
    except Exception as e:
        print(f"Error fetching user stats: {e}")
    
    # 3. Activity Summary & Growth
    activity_summary = {'posts': 0, 'events': 0, 'comments': 0}
    growth_stats = {}
    
    def calculate_growth(model, current_start, prev_start):
        curr_count = model.query.filter(model.created_at >= current_start).count()
        prev_count = model.query.filter(and_(model.created_at >= prev_start, model.created_at < current_start)).count()
        
        diff = curr_count - prev_count
        percent = 0
        if prev_count > 0:
            percent = (diff / prev_count) * 100
        elif curr_count > 0:
            percent = 100
        
        return {
            'value': curr_count,
            'prev': prev_count,
            'diff': diff,
            'percent': round(percent, 1),
            'trend': 'up' if diff >= 0 else 'down'
        }

    try:
        prev_start = start_date - timedelta(days=days)
        
        growth_stats = {
            'users': calculate_growth(User, start_date, prev_start),
            'posts': calculate_growth(Post, start_date, prev_start),
            'events': calculate_growth(Event, start_date, prev_start)
        }
        
        # Activity Trend (Daily)
        activity_map = {}
        for i in range(days):
            d = (datetime.utcnow() - timedelta(days=i)).strftime('%Y-%m-%d')
            activity_map[d] = {'posts': 0, 'events': 0}
            
        posts_period = Post.query.filter(Post.created_at >= start_date).all()
        for p in posts_period:
            d = p.created_at.strftime('%Y-%m-%d')
            if d in activity_map:
                activity_map[d]['posts'] += 1
                
        events_period = Event.query.filter(Event.created_at >= start_date).all()
        for e in events_period:
            d = e.created_at.strftime('%Y-%m-%d')
            if d in activity_map:
                activity_map[d]['events'] += 1
                
        activity_trend = [{'date': k, 'posts': v['posts'], 'events': v['events']} for k, v in sorted(activity_map.items())]

    except Exception as e:
        print(f"Error fetching activity stats: {e}")
        activity_trend = []
        growth_stats = {
            'users': {'value': 0, 'percent': 0, 'trend': 'up'},
            'posts': {'value': 0, 'percent': 0, 'trend': 'up'},
            'events': {'value': 0, 'percent': 0, 'trend': 'up'}
        }
    
    # 4. Top users by posts
    top_posters = []
    try:
        top_posters = db.session.query(
            User,
            func.count(Post.id).label('post_count')
        ).join(Post).group_by(User.id).order_by(desc('post_count')).limit(10).all()
    except Exception as e:
        print(f"Error fetching top posters: {e}")
    
    # 5. Top societies by followers
    top_societies = []
    try:
        societies = Society.query.limit(10).all()
        top_societies = sorted(
            societies,
            key=lambda s: s.user.followers.count() if s.user else 0,
            reverse=True
        )[:10]
    except Exception as e:
        print(f"Error fetching societies: {e}")
    
    return render_template('admin/analytics.html',
                         days=days,
                         signup_data=signup_data,
                         role_data=role_data,
                         growth_stats=growth_stats,
                         activity_trend=activity_trend,
                         top_posters=top_posters,
                         top_societies=top_societies)


@bp.route('/user/<int:user_id>/ban', methods=['POST'])
@login_required
@admin_required
def ban_user(user_id):
    """Ban or unban a user"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('Non puoi bannare te stesso.', 'danger')
        return redirect(url_for('admin.users'))
    
    action = request.form.get('action')
    reason = request.form.get('reason', '')
    
    if action == 'ban':
        user.is_banned = True
        flash(f'Utente {user.username} bannato.', 'success')
        log_action('ban_user', 'User', user.id, f'Banned user: {reason}')
    elif action == 'unban':
        user.is_banned = False
        flash(f'Utente {user.username} sbannato.', 'success')
        log_action('unban_user', 'User', user.id, f'Unbanned user')
    
    db.session.commit()
    return redirect(url_for('admin.user_detail', user_id=user.id))


@bp.route('/moderation')
@login_required
@admin_required
def moderation():
    """Moderation rules management"""
    from app.models import ModerationRule
    rules = ModerationRule.query.order_by(ModerationRule.created_at.desc()).all()
    return render_template('admin/moderation.html', rules=rules)


@bp.route('/moderation/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_moderation_rule():
    """Add new moderation rule"""
    from app.models import ModerationRule
    from app.admin.forms import ModerationRuleForm
    
    form = ModerationRuleForm()
    if form.validate_on_submit():
        rule = ModerationRule(
            name=form.name.data,
            description=form.description.data,
            rule_type=form.rule_type.data,
            keywords=form.keywords.data,
            action=form.action.data,
            severity=form.severity.data,
            created_by=current_user.id
        )
        db.session.add(rule)
        db.session.commit()
        flash('Regola di moderazione aggiunta.', 'success')
        log_action('add_moderation_rule', 'ModerationRule', rule.id, f'Added rule: {rule.name}')
        return redirect(url_for('admin.moderation'))
    
    return render_template('admin/add_moderation_rule.html', form=form)


@bp.route('/moderation/<int:rule_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_moderation_rule(rule_id):
    """Toggle moderation rule active status"""
    from app.models import ModerationRule
    rule = ModerationRule.query.get_or_404(rule_id)
    rule.is_active = not rule.is_active
    db.session.commit()
    status = 'attivata' if rule.is_active else 'disattivata'
    flash(f'Regola {rule.name} {status}.', 'success')
    log_action('toggle_moderation_rule', 'ModerationRule', rule.id, f'Toggled to {status}')
    return redirect(url_for('admin.moderation'))


@bp.route('/moderation/<int:rule_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_moderation_rule(rule_id):
    """Delete moderation rule"""
    from app.models import ModerationRule
    rule = ModerationRule.query.get_or_404(rule_id)
    db.session.delete(rule)
    db.session.commit()
    flash('Regola di moderazione eliminata.', 'success')
    log_action('delete_moderation_rule', 'ModerationRule', rule.id, f'Deleted rule: {rule.name}')
    return redirect(url_for('admin.moderation'))
