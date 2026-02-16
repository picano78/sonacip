"""
Admin routes
"""
import csv
import io
import logging

logger = logging.getLogger(__name__)

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, Response, make_response
from flask_login import login_required, current_user
from flask import current_app
from sqlalchemy import or_, and_, func, desc, case
from sqlalchemy.orm import joinedload
from app import db
from app.cache import get_cache
from app.admin.utils import admin_required
from app.social.utils import save_picture
from app.social.feed_ranking import get_connection_ids, rank_feed_posts
from app.admin.forms import (
    AdsSettingsForm,
    AppearanceSettingsForm,
    DashboardTemplateForm,
    NavigationConfigForm,
    SmtpSettingsForm,
    PageCustomizationForm,
    PrivacySettingsForm,
    SiteCustomizationForm,
    SocialSettingsAdminForm,
    StorageSettingsForm,
    UserEditForm,
    UserSearchForm,
    AdCampaignForm,
    AdCreativeForm,
    ModuleUploadForm,
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
    EnterpriseSSOSetting,
    Notification,
    MaintenanceRun,
    PageCustomization,
    Post,
    PlatformFeeSetting,
    PlatformTransaction,
    PrivacySetting,
    SiteCustomization,
    SocialSetting,
    Society,
    SocietyHealthSnapshot,
    StorageSetting,
    SmtpSetting,
    User,
    Payment,
    Subscription,
    AddOnEntitlement,
    MarketplacePurchase,
    AdCampaign,
    AdCreative,
    AdEvent,
    PlatformFeature,
    PlatformPaymentSetting,
    ListingPromotion,
    PromotionTier,
    MarketplaceListing,
    BroadcastMessage,
    BroadcastRecipient,
    Message,
    Role,
    EmailConfirmationSetting,
    AutomationRule,
    AutomationRun,
    InvoiceSettings,
    FeePayment,
    Invoice,
    SystemModule,
)
from datetime import datetime, timedelta, timezone
import os
import json
from app.utils import log_action

from app.automation.forms import AutomationRuleForm

DEFAULT_SIDEBAR_MENU = [
    {'id': 'dashboard', 'label': 'Cruscotto', 'icon': 'bi-speedometer2', 'endpoint': 'main.dashboard', 'feature': None, 'section': 'main', 'fixed': True},
    {'id': 'planner', 'label': 'Planner', 'icon': 'bi-calendar-check', 'endpoint': 'calendar.grid', 'feature': 'planner', 'section': 'main'},
    {'id': 'calendario', 'label': 'Calendario', 'icon': 'bi-calendar3-range', 'endpoint': 'calendar.index', 'feature': 'planner', 'section': 'main'},
    {'id': 'social', 'label': 'Social', 'icon': 'bi-people-fill', 'endpoint': 'social.feed', 'feature': 'social_feed', 'section': 'main'},
    {'id': 'esplora', 'label': 'Esplora', 'icon': 'bi-compass', 'endpoint': 'social.explore', 'feature': 'social_feed', 'section': 'main'},
    {'id': 'eventi', 'label': 'Eventi', 'icon': 'bi-calendar-event', 'endpoint': 'events.index', 'feature': 'events', 'section': 'main', 'resource': 'events', 'action': 'view'},
    {'id': 'tornei', 'label': 'Tornei', 'icon': 'bi-trophy', 'endpoint': 'tournaments.list_tournaments', 'feature': 'tournaments', 'section': 'main', 'resource': 'tournaments', 'action': 'view'},
    {'id': 'marketplace', 'label': 'Marketplace', 'icon': 'bi-shop', 'endpoint': 'marketplace.index', 'feature': 'marketplace', 'section': 'main'},
    {'id': 'crm', 'label': 'CRM', 'icon': 'bi-briefcase', 'endpoint': 'crm.index', 'feature': 'crm', 'section': 'main', 'resource': 'crm', 'action': 'access'},
    {'id': 'analytics', 'label': 'Analytics', 'icon': 'bi-graph-up', 'endpoint': 'analytics.dashboard', 'feature': 'advanced_stats', 'section': 'main', 'resource': 'analytics', 'action': 'access'},
    {'id': 'admin', 'label': 'Admin', 'icon': 'bi-gear-fill', 'endpoint': 'admin.dashboard', 'feature': None, 'section': 'main', 'resource': 'admin', 'action': 'access'},
    {'id': 'cerca', 'label': 'Cerca', 'icon': 'bi-search', 'endpoint': 'social.search', 'feature': None, 'section': 'bottom'},
    {'id': 'notifiche', 'label': 'Notifiche', 'icon': 'bi-bell-fill', 'endpoint': 'notifications.index', 'feature': 'notifications', 'section': 'bottom'},
    {'id': 'messaggi', 'label': 'Messaggi', 'icon': 'bi-envelope', 'endpoint': 'messages.inbox', 'feature': 'messaging', 'section': 'bottom'},
    {'id': 'assistenza', 'label': 'Assistenza', 'icon': 'bi-headset', 'endpoint': 'main.contact_admin', 'feature': None, 'section': 'bottom'},
    {'id': 'guida', 'label': 'Guida', 'icon': 'bi-question-circle', 'endpoint': 'main.guide_user', 'feature': None, 'section': 'bottom'},
]


def _get_sidebar_menu_config():
    row = CustomizationKV.query.filter_by(scope='site', scope_key=None, key='sidebar.menu_order').first()
    if row:
        saved = row.get_value(default=None)
        if saved:
            default_by_id = {item['id']: item for item in DEFAULT_SIDEBAR_MENU}
            result = []
            seen_ids = set()
            for item in saved:
                item_id = item.get('id')
                if item_id in default_by_id:
                    merged = dict(default_by_id[item_id])
                    merged['visible'] = item.get('visible', True)
                    merged['section'] = item.get('section', merged.get('section', 'main'))
                    result.append(merged)
                    seen_ids.add(item_id)
            for item in DEFAULT_SIDEBAR_MENU:
                if item['id'] not in seen_ids:
                    item['visible'] = True
                    result.append(item)
            return result
    return [dict(item, visible=True) for item in DEFAULT_SIDEBAR_MENU]

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
            User.last_seen >= datetime.now(timezone.utc) - timedelta(days=1)
        ).count(),
        'new_users_week': User.query.filter(
            User.created_at >= datetime.now(timezone.utc) - timedelta(days=7)
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
        if form.logo_upload.data:
            try:
                saved_path = save_picture(form.logo_upload.data, folder='avatars', size=(512, 512))
                settings.logo_url = url_for('static', filename='uploads/' + saved_path)
            except Exception:
                if current_app:
                    current_app.logger.exception('Logo upload failed')
                flash('Caricamento logo non riuscito.', 'danger')
        else:
            settings.logo_url = form.logo_url.data or None
        settings.favicon_url = form.favicon_url.data or None
        # PWA / app icon
        if getattr(form, "app_icon_upload", None) is not None and form.app_icon_upload.data:
            try:
                saved_path = save_picture(form.app_icon_upload.data, folder='icons', size=(512, 512))
                settings.app_icon_url = url_for('static', filename='uploads/' + saved_path)
            except Exception:
                if current_app:
                    current_app.logger.exception('App icon upload failed')
                flash('Caricamento icona app non riuscito.', 'danger')
        else:
            settings.app_icon_url = (form.app_icon_url.data or None) if hasattr(form, "app_icon_url") else getattr(settings, "app_icon_url", None)
        settings.layout_style = form.layout_style.data or settings.layout_style
        settings.updated_by = current_user.id
        settings.updated_at = datetime.now(timezone.utc)
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
        settings.allow_photos = bool(form.allow_photos.data)
        settings.allow_videos = bool(form.allow_videos.data)
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
        settings.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        log_action('update_social_settings', 'SocialSetting', settings.id, 'Updated social governance')
        flash('Impostazioni social aggiornate.', 'success')
        return redirect(url_for('admin.social_settings'))

    return render_template('admin/social_settings.html', form=form, settings=settings)


@bp.route('/automation')
@login_required
@admin_required
def automation_rules():
    """List declarative automation rules."""
    page = request.args.get('page', 1, type=int)
    per_page = 20

    rules = AutomationRule.query.order_by(AutomationRule.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    rule_stats = {}
    try:
        rows = (
            db.session.query(
                AutomationRun.rule_id.label('rule_id'),
                func.count(AutomationRun.id).label('total'),
                func.sum(case((AutomationRun.status == 'success', 1), else_=0)).label('success'),
                func.sum(case((AutomationRun.status == 'failed', 1), else_=0)).label('failed'),
                func.max(AutomationRun.created_at).label('last_run'),
            )
            .group_by(AutomationRun.rule_id)
            .all()
        )
        for r in rows:
            rule_stats[int(r.rule_id)] = {
                'total': int(r.total or 0),
                'success': int(r.success or 0),
                'failed': int(r.failed or 0),
                'last_run': r.last_run,
            }
    except Exception:
        current_app.logger.exception("Failed to compute automation rule stats")
        rule_stats = {}

    return render_template('admin/automation_rules.html', rules=rules, rule_stats=rule_stats)


@bp.route('/automation/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create_automation_rule():
    """Create a new automation rule."""
    form = AutomationRuleForm()
    if form.validate_on_submit():
        rule = AutomationRule(
            name=form.name.data.strip(),
            event_type=form.event_type.data,
            condition=(form.condition.data or '').strip() or None,
            actions=form.actions.data.strip(),
            is_active=bool(form.is_active.data),
            max_retries=form.max_retries.data or 0,
            retry_delay=form.retry_delay.data or 60,
            created_by=getattr(current_user, 'id', None),
        )
        db.session.add(rule)
        db.session.commit()
        flash('Regola creata con successo.', 'success')
        return redirect(url_for('admin.automation_rules'))
    return render_template('admin/automation_form.html', form=form, rule=None)


@bp.route('/automation/<int:rule_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_automation_rule(rule_id: int):
    """Edit an existing automation rule."""
    rule = AutomationRule.query.get_or_404(rule_id)
    form = AutomationRuleForm(obj=rule)
    if request.method == 'GET':
        form.actions.data = rule.actions or ''
        form.condition.data = rule.condition or ''

    if form.validate_on_submit():
        rule.name = form.name.data.strip()
        rule.event_type = form.event_type.data
        rule.condition = (form.condition.data or '').strip() or None
        rule.actions = form.actions.data.strip()
        rule.is_active = bool(form.is_active.data)
        rule.max_retries = form.max_retries.data or 0
        rule.retry_delay = form.retry_delay.data or 60
        db.session.commit()
        flash('Regola aggiornata.', 'success')
        return redirect(url_for('admin.automation_rules'))

    return render_template('admin/automation_form.html', form=form, rule=rule)


@bp.route('/automation/<int:rule_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_automation_rule(rule_id: int):
    """Delete an automation rule."""
    rule = AutomationRule.query.get_or_404(rule_id)
    try:
        # Delete runs first to avoid FK issues
        AutomationRun.query.filter_by(rule_id=rule.id).delete(synchronize_session=False)
        db.session.delete(rule)
        db.session.commit()
        flash('Regola eliminata.', 'success')
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to delete automation rule %s", rule_id)
        flash('Eliminazione non riuscita.', 'danger')
    return redirect(url_for('admin.automation_rules'))


@bp.route('/automation/<int:rule_id>/runs')
@login_required
@admin_required
def automation_runs(rule_id: int):
    """List execution runs for a given rule."""
    rule = AutomationRule.query.get_or_404(rule_id)
    page = request.args.get('page', 1, type=int)
    per_page = 25
    runs = AutomationRun.query.filter_by(rule_id=rule.id).order_by(AutomationRun.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return render_template('admin/automation_runs.html', rule=rule, runs=runs)


@bp.route('/social-feed-algorithm', methods=['GET', 'POST'])
@login_required
@admin_required
def social_feed_algorithm():
    settings = SocialSetting.query.first()
    if not settings:
        settings = SocialSetting()
        db.session.add(settings)
        db.session.commit()

    if request.method == 'POST':
        def _parse_int_from_form(name, default):
            try:
                return int(request.form.get(name, default))
            except Exception:
                return default

        def _parse_float_from_form(name, default):
            try:
                return float(request.form.get(name, default))
            except Exception:
                return default

        settings.priority_followed = _parse_int_from_form('priority_followed', settings.priority_followed or 0)
        settings.priority_friends = _parse_int_from_form('priority_friends', settings.priority_friends or 1)
        settings.priority_others = _parse_int_from_form('priority_others', settings.priority_others or 2)
        settings.weight_engagement = _parse_float_from_form('weight_engagement', settings.weight_engagement or 1.0)
        settings.weight_recency = _parse_float_from_form('weight_recency', settings.weight_recency or 1.0)
        settings.weight_promoted = _parse_float_from_form('weight_promoted', settings.weight_promoted or 20.0)
        settings.weight_official = _parse_float_from_form('weight_official', settings.weight_official or 30.0)
        settings.weight_tournament = _parse_float_from_form('weight_tournament', settings.weight_tournament or 20.0)
        settings.weight_automation = _parse_float_from_form('weight_automation', settings.weight_automation or 10.0)
        settings.updated_by = current_user.id
        settings.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        log_action('update_social_feed_algorithm', 'SocialSetting', settings.id, 'Updated feed ranking weights')
        flash('Algoritmo feed aggiornato.', 'success')
        return redirect(url_for('admin.social_feed_algorithm'))

    preview_posts = []
    try:
        followed_ids = {u.id for u in current_user.followed.all()}
    except Exception:
        followed_ids = set()
    friend_ids = get_connection_ids(current_user)
    friend_ids -= followed_ids
    if current_user.id in friend_ids:
        friend_ids.remove(current_user.id)
    try:
        posts = (Post.query.options(joinedload(Post.author))
                 .order_by(Post.created_at.desc())
                 .limit(40)
                 .all())
        preview_posts = rank_feed_posts(posts, current_user, followed_ids, friend_ids, settings)[:10]
    except Exception:
        preview_posts = []

    return render_template('admin/social_feed_algorithm.html', settings=settings, preview_posts=preview_posts)


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

        def _safe_int_conversion(value, default):
            try:
                return int(value)
            except Exception:
                return default

        settings.image_quality = _safe_int_conversion(form.image_quality.data, settings.image_quality)
        settings.video_bitrate = _safe_int_conversion(form.video_bitrate.data, settings.video_bitrate)
        settings.video_max_width = _safe_int_conversion(form.video_max_width.data, settings.video_max_width)
        settings.max_image_mb = _safe_int_conversion(form.max_image_mb.data, settings.max_image_mb)
        settings.max_video_mb = _safe_int_conversion(form.max_video_mb.data, settings.max_video_mb)
        settings.max_upload_mb = _safe_int_conversion(form.max_upload_mb.data, settings.max_upload_mb)

        settings.updated_by = current_user.id
        settings.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        # Update MAX_CONTENT_LENGTH from admin setting
        if settings.max_upload_mb:
            current_app.config['MAX_CONTENT_LENGTH'] = settings.max_upload_mb * 1024 * 1024

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
        settings.updated_at = datetime.now(timezone.utc)
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
        row.updated_at = datetime.now(timezone.utc)
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
        settings.updated_at = datetime.now(timezone.utc)
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


@bp.route('/platform/fees', methods=['GET', 'POST'])
@login_required
@admin_required
def platform_fees():
    """Configure platform take-rate settings."""
    settings = PlatformFeeSetting.query.first()
    if not settings:
        settings = PlatformFeeSetting(take_rate_percent=5, min_fee_cents=0, currency='EUR', updated_at=datetime.now(timezone.utc), updated_by=current_user.id)
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
        settings.updated_at = datetime.now(timezone.utc)
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


@bp.route('/payment-settings', methods=['GET', 'POST'])
@login_required
@admin_required
def payment_settings():
    settings = PlatformPaymentSetting.query.first()
    if not settings:
        settings = PlatformPaymentSetting(payout_method='stripe', currency='EUR', updated_at=datetime.now(timezone.utc), updated_by=current_user.id)
        db.session.add(settings)
        db.session.commit()

    if request.method == 'POST':
        settings.payout_method = (request.form.get('payout_method') or 'stripe').strip()
        settings.stripe_enabled = bool(request.form.get('stripe_enabled'))
        settings.stripe_account_id = (request.form.get('stripe_account_id') or '').strip() or None
        settings.bank_account_holder = (request.form.get('bank_account_holder') or '').strip() or None
        settings.bank_name = (request.form.get('bank_name') or '').strip() or None
        settings.bank_iban = (request.form.get('bank_iban') or '').strip() or None
        settings.bank_bic_swift = (request.form.get('bank_bic_swift') or '').strip() or None
        settings.bank_country = (request.form.get('bank_country') or 'Italia').strip()
        settings.paypal_email = (request.form.get('paypal_email') or '').strip() or None
        settings.payout_frequency = (request.form.get('payout_frequency') or 'monthly').strip()
        settings.currency = (request.form.get('currency') or 'EUR').strip().upper()
        settings.notes = (request.form.get('notes') or '').strip() or None
        try:
            settings.min_payout_amount = float(request.form.get('min_payout_amount') or 50)
        except (ValueError, TypeError):
            settings.min_payout_amount = 50.0
        settings.updated_by = current_user.id
        settings.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        log_action('update_payment_settings', 'PlatformPaymentSetting', settings.id, f'method={settings.payout_method}')
        flash('Impostazioni pagamento salvate.', 'success')
        return redirect(url_for('admin.payment_settings'))

    total_payments = Payment.query.filter_by(status='completed').count()
    total_revenue = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(Payment.status == 'completed').scalar() or 0
    active_promotions = ListingPromotion.query.filter_by(status='active').count()

    return render_template('admin/payment_settings.html', settings=settings,
                           total_payments=total_payments, total_revenue=float(total_revenue),
                           active_promotions=active_promotions)


@bp.route('/invoice-settings', methods=['GET', 'POST'])
@login_required
@admin_required
def invoice_settings():
    """Invoice configuration and electronic invoice settings"""
    settings = InvoiceSettings.query.first()
    if not settings:
        settings = InvoiceSettings(
            company_country='Italia',
            invoice_prefix='INV',
            default_tax_rate=22.0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.session.add(settings)
        db.session.commit()

    if request.method == 'POST':
        # Company information
        settings.company_name = (request.form.get('company_name') or '').strip() or None
        settings.company_address = (request.form.get('company_address') or '').strip() or None
        settings.company_city = (request.form.get('company_city') or '').strip() or None
        settings.company_postal_code = (request.form.get('company_postal_code') or '').strip() or None
        settings.company_country = (request.form.get('company_country') or 'Italia').strip()
        settings.company_vat = (request.form.get('company_vat') or '').strip() or None
        settings.company_tax_code = (request.form.get('company_tax_code') or '').strip() or None
        settings.company_phone = (request.form.get('company_phone') or '').strip() or None
        settings.company_email = (request.form.get('company_email') or '').strip() or None
        settings.company_website = (request.form.get('company_website') or '').strip() or None

        # Invoice settings
        settings.invoice_prefix = (request.form.get('invoice_prefix') or 'INV').strip()
        settings.invoice_footer = (request.form.get('invoice_footer') or '').strip() or None
        settings.invoice_notes = (request.form.get('invoice_notes') or '').strip() or None
        
        try:
            settings.default_tax_rate = float(request.form.get('default_tax_rate') or 22.0)
        except (ValueError, TypeError):
            settings.default_tax_rate = 22.0

        # Electronic invoice settings
        settings.enable_electronic_invoice = bool(request.form.get('enable_electronic_invoice'))
        settings.e_invoice_provider = (request.form.get('e_invoice_provider') or '').strip() or None
        settings.e_invoice_api_key = (request.form.get('e_invoice_api_key') or '').strip() or None
        settings.e_invoice_api_secret = (request.form.get('e_invoice_api_secret') or '').strip() or None
        settings.e_invoice_company_id = (request.form.get('e_invoice_company_id') or '').strip() or None
        settings.sdi_code = (request.form.get('sdi_code') or '').strip() or None
        settings.pec_email = (request.form.get('pec_email') or '').strip() or None

        # Handle logo upload
        if 'logo_file' in request.files:
            file = request.files['logo_file']
            if file and file.filename:
                try:
                    # save_picture validates file type, resizes image, and saves to uploads folder
                    # Returns relative path or None if validation fails
                    # May raise exceptions for invalid files or disk errors
                    logo_path = save_picture(file, folder='invoice_logos', resize=(400, 200))
                    if logo_path:
                        settings.logo_path = logo_path
                except Exception as e:
                    flash(f'Errore nel caricamento del logo: {str(e)}', 'warning')

        settings.updated_by = current_user.id
        settings.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        log_action('update_invoice_settings', 'InvoiceSettings', settings.id, 'Impostazioni fattura aggiornate')
        flash('Impostazioni fattura salvate con successo.', 'success')
        return redirect(url_for('admin.invoice_settings'))

    # Stats for the page
    total_invoices = Invoice.query.count()
    invoices_this_month = Invoice.query.filter(
        Invoice.created_at >= datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ).count()

    return render_template('admin/invoice_settings.html', 
                         settings=settings,
                         total_invoices=total_invoices,
                         invoices_this_month=invoices_this_month)


@bp.route('/promotion-tiers', methods=['GET', 'POST'])
@login_required
@admin_required
def promotion_tiers():
    if request.method == 'POST':
        action = request.form.get('action', '')
        tier_id = request.form.get('tier_id')

        if action == 'create':
            name = (request.form.get('name') or '').strip()
            slug = (request.form.get('slug') or '').strip().lower().replace(' ', '_')
            try:
                duration_days = int(request.form.get('duration_days') or 7)
            except (ValueError, TypeError):
                duration_days = 7
            try:
                price = float(request.form.get('price') or 0)
            except (ValueError, TypeError):
                price = 0.0
            if name and slug:
                existing = PromotionTier.query.filter_by(slug=slug).first()
                if not existing:
                    tier = PromotionTier(
                        name=name, slug=slug,
                        description=(request.form.get('description') or '').strip() or None,
                        duration_days=duration_days, price=price,
                        icon=request.form.get('icon') or 'bi-star',
                        color=request.form.get('color') or '#ff9800',
                        stripe_price_id=(request.form.get('stripe_price_id') or '').strip() or None,
                        is_active=True,
                        updated_by=current_user.id,
                    )
                    db.session.add(tier)
                    db.session.commit()
                    flash('Piano creato.', 'success')
                else:
                    flash('Slug già esistente.', 'danger')

        elif action == 'toggle' and tier_id:
            tier = db.session.get(PromotionTier, int(tier_id))
            if tier:
                tier.is_active = not tier.is_active
                db.session.commit()
                flash(f'Piano {"attivato" if tier.is_active else "disattivato"}.', 'success')

        elif action == 'update' and tier_id:
            tier = db.session.get(PromotionTier, int(tier_id))
            if tier:
                tier.name = (request.form.get('name') or tier.name).strip()
                tier.description = (request.form.get('description') or '').strip() or None
                try:
                    tier.price = float(request.form.get('price') or tier.price)
                except (ValueError, TypeError):
                    pass
                try:
                    tier.duration_days = int(request.form.get('duration_days') or tier.duration_days)
                except (ValueError, TypeError):
                    pass
                tier.stripe_price_id = (request.form.get('stripe_price_id') or '').strip() or None
                tier.icon = request.form.get('icon') or tier.icon
                tier.color = request.form.get('color') or tier.color
                tier.updated_by = current_user.id
                db.session.commit()
                flash('Piano aggiornato.', 'success')

        elif action == 'delete' and tier_id:
            tier = db.session.get(PromotionTier, int(tier_id))
            if tier:
                db.session.delete(tier)
                db.session.commit()
                flash('Piano eliminato.', 'success')

        return redirect(url_for('admin.promotion_tiers'))

    tiers = PromotionTier.query.order_by(PromotionTier.display_order.asc()).all()
    active_promos = ListingPromotion.query.filter_by(status='active').count()
    total_promo_revenue = db.session.query(func.coalesce(func.sum(ListingPromotion.amount_paid), 0)).filter(ListingPromotion.status == 'active').scalar() or 0
    return render_template('admin/promotion_tiers.html', tiers=tiers,
                           active_promos=active_promos, total_promo_revenue=float(total_promo_revenue))


@bp.route('/broadcasts')
@login_required
@admin_required
def broadcasts():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    query = BroadcastMessage.query.filter_by(scope_type='global')
    if status_filter:
        query = query.filter_by(status=status_filter)
    pagination = query.order_by(BroadcastMessage.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    broadcasts_list = pagination.items
    total = BroadcastMessage.query.filter_by(scope_type='global').count()
    total_sent = BroadcastMessage.query.filter_by(scope_type='global', status='sent').count()
    return render_template('admin/broadcasts.html', broadcasts=broadcasts_list, pagination=pagination,
                           total=total, total_sent=total_sent, status_filter=status_filter)


@bp.route('/broadcasts/compose', methods=['GET', 'POST'])
@login_required
@admin_required
def broadcast_compose():
    roles = Role.query.filter_by(is_active=True).order_by(Role.level.desc()).all()

    if request.method == 'POST':
        subject = (request.form.get('subject') or '').strip()
        body = (request.form.get('body') or '').strip()
        selected_roles = request.form.getlist('target_roles')
        send_email = bool(request.form.get('send_email'))

        if not subject or not body:
            flash('Oggetto e messaggio sono obbligatori.', 'danger')
            return render_template('admin/broadcast_compose.html', roles=roles,
                                   subject=subject, body=body, selected_roles=selected_roles)

        broadcast = BroadcastMessage(
            sender_id=current_user.id,
            scope_type='global',
            subject=subject,
            body=body,
            target_roles=','.join(selected_roles) if selected_roles else None,
            send_email=send_email,
            status='draft',
        )
        db.session.add(broadcast)
        db.session.flush()

        users_query = User.query.filter_by(is_active=True, is_banned=False).filter(User.id != current_user.id)
        if selected_roles:
            role_objs = Role.query.filter(Role.name.in_(selected_roles)).all()
            role_ids = [r.id for r in role_objs]
            if role_ids:
                users_query = users_query.filter(User.role_id.in_(role_ids))

        target_users = users_query.all()
        count = 0
        for u in target_users:
            msg = Message(
                sender_id=current_user.id,
                recipient_id=u.id,
                subject=f"[Newsletter] {subject}",
                body=body,
                is_read=False,
            )
            db.session.add(msg)
            db.session.flush()
            recipient = BroadcastRecipient(
                broadcast_id=broadcast.id,
                user_id=u.id,
                message_id=msg.id,
                delivery_status='sent',
                sent_at=datetime.now(timezone.utc),
            )
            db.session.add(recipient)
            count += 1

        broadcast.total_recipients = count
        broadcast.status = 'sent'
        broadcast.sent_at = datetime.now(timezone.utc)
        db.session.commit()

        if send_email:
            _send_broadcast_emails(broadcast, target_users)

        log_action('send_broadcast', 'BroadcastMessage', broadcast.id, f'recipients={count} roles={selected_roles}')
        flash(f'Newsletter inviata a {count} utenti.', 'success')
        return redirect(url_for('admin.broadcast_detail', broadcast_id=broadcast.id))

    return render_template('admin/broadcast_compose.html', roles=roles,
                           subject='', body='', selected_roles=[])


@bp.route('/broadcasts/<int:broadcast_id>')
@login_required
@admin_required
def broadcast_detail(broadcast_id):
    broadcast = BroadcastMessage.query.get_or_404(broadcast_id)
    page = request.args.get('page', 1, type=int)
    recipients_page = broadcast.recipients.join(User, BroadcastRecipient.user_id == User.id)\
        .add_entity(User).paginate(page=page, per_page=50, error_out=False)

    read_count = BroadcastRecipient.query.filter_by(broadcast_id=broadcast.id)\
        .join(Message, BroadcastRecipient.message_id == Message.id)\
        .filter(Message.is_read == True).count()

    return render_template('admin/broadcast_detail.html', broadcast=broadcast,
                           recipients_page=recipients_page, read_count=read_count)


@bp.route('/broadcasts/<int:broadcast_id>/delete', methods=['POST'])
@login_required
@admin_required
def broadcast_delete(broadcast_id):
    broadcast = BroadcastMessage.query.get_or_404(broadcast_id)
    db.session.delete(broadcast)
    db.session.commit()
    flash('Newsletter eliminata.', 'success')
    return redirect(url_for('admin.broadcasts'))


def _send_broadcast_emails(broadcast, users):
    try:
        smtp = SmtpSetting.query.first()
        if not smtp or not smtp.enabled:
            return
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        server = smtplib.SMTP(smtp.host, smtp.port)
        if smtp.use_tls:
            server.starttls()
        if smtp.username and smtp.password:
            server.login(smtp.username, smtp.password)
        for u in users:
            if not u.email:
                continue
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[SONACIP] {broadcast.subject}"
            msg['From'] = smtp.default_sender or 'noreply@sonacip.it'
            msg['To'] = u.email
            text_body = broadcast.body
            html_body = f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
            <div style="background:#1877f2;color:#fff;padding:20px;border-radius:8px 8px 0 0;">
                <h2 style="margin:0;">SONACIP</h2>
            </div>
            <div style="padding:20px;background:#fff;border:1px solid #ddd;border-radius:0 0 8px 8px;">
                <h3>{broadcast.subject}</h3>
                <div style="white-space:pre-wrap;">{broadcast.body}</div>
            </div>
            </div>"""
            msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))
            try:
                server.sendmail(msg['From'], [u.email], msg.as_string())
                rec = BroadcastRecipient.query.filter_by(broadcast_id=broadcast.id, user_id=u.id).first()
                if rec:
                    rec.email_sent = True
            except Exception:
                pass
        server.quit()
        db.session.commit()
    except Exception:
        pass


@bp.route('/enterprise/sso', methods=['GET', 'POST'])
@login_required
@admin_required
def enterprise_sso():
    """Enterprise SSO (OIDC) configuration."""
    sso = EnterpriseSSOSetting.query.first()
    if not sso:
        sso = EnterpriseSSOSetting(enabled=False, scopes='openid email profile', updated_at=datetime.now(timezone.utc), updated_by=current_user.id)
        db.session.add(sso)
        db.session.commit()

    if request.method == 'POST':
        sso.enabled = bool(request.form.get('enabled'))
        sso.issuer_url = (request.form.get('issuer_url') or '').strip() or None
        sso.client_id = (request.form.get('client_id') or '').strip() or None
        sso.client_secret = (request.form.get('client_secret') or '').strip() or None
        sso.scopes = (request.form.get('scopes') or 'openid email profile').strip()
        sso.updated_by = current_user.id
        sso.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        log_action('update_enterprise_sso', 'EnterpriseSSOSetting', sso.id, f'enabled={sso.enabled}')
        flash('SSO aggiornato.', 'success')
        return redirect(url_for('admin.enterprise_sso'))

    return render_template('admin/enterprise_sso.html', sso=sso)


@bp.route('/maintenance')
@login_required
@admin_required
def maintenance_runs():
    """View recent scheduled maintenance job runs."""
    runs = MaintenanceRun.query.order_by(MaintenanceRun.started_at.desc()).limit(100).all()
    return render_template('admin/maintenance_runs.html', runs=runs)


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
        settings.updated_at = datetime.now(timezone.utc)

        db.session.add(settings)
        db.session.commit()

        log_action('update_page_customization', 'PageCustomization', settings.id, f'Updated page {settings.slug}')
        flash('Pagina aggiornata.', 'success')
        return redirect(url_for('admin.pages'))

    return render_template('admin/edit_page.html', form=form, settings=settings)


@bp.route('/page-builder')
@login_required
@admin_required
def page_builder_list():
    """Elenco pagine configurabili graficamente."""
    from app.admin.page_builder import PAGE_REGISTRY, get_page_config
    page_list = []
    for slug, info in PAGE_REGISTRY.items():
        sections = get_page_config(slug)
        has_custom = CustomizationKV.query.filter_by(scope='page', scope_key=slug, key='sections').first() is not None
        page_list.append({
            'slug': slug,
            'label': info['label'],
            'section_count': len(sections),
            'visible_count': sum(1 for s in sections if s.get('visible', True)),
            'has_custom': has_custom,
        })
    return render_template('admin/page_builder_list.html', pages=page_list)


@bp.route('/page-builder/<path:slug>', methods=['GET', 'POST'])
@login_required
@admin_required
def page_builder(slug):
    """Page builder grafico per una pagina specifica."""
    from app.admin.page_builder import PAGE_REGISTRY, get_page_config, save_page_config, SECTION_FIELD_SCHEMA
    if slug not in PAGE_REGISTRY:
        flash('Pagina non trovata nel registro.', 'danger')
        return redirect(url_for('admin.page_builder_list'))

    page_info = PAGE_REGISTRY[slug]

    if request.method == 'POST':
        try:
            data = request.get_json(silent=True)
            if data and 'sections' in data:
                save_page_config(slug, data['sections'], current_user.id)
                log_action('update_page_builder', 'CustomizationKV', 0, f'Updated page builder for {slug}')
                return jsonify({'ok': True, 'message': 'Pagina salvata con successo!'})
            return jsonify({'ok': False, 'message': 'Dati non validi.'}), 400
        except Exception as e:
            return jsonify({'ok': False, 'message': str(e)}), 500

    sections = get_page_config(slug)
    return render_template('admin/page_builder.html',
                           slug=slug,
                           page_info=page_info,
                           sections=sections,
                           field_schema=SECTION_FIELD_SCHEMA)


@bp.route('/page-builder/<path:slug>/reset', methods=['POST'])
@login_required
@admin_required
def page_builder_reset(slug):
    """Ripristina configurazione di default per una pagina."""
    from app.admin.page_builder import reset_page_config
    reset_page_config(slug)
    log_action('reset_page_builder', 'CustomizationKV', 0, f'Reset page builder for {slug}')
    flash('Configurazione ripristinata ai valori predefiniti.', 'success')
    return redirect(url_for('admin.page_builder', slug=slug))


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
        tpl.updated_at = datetime.now(timezone.utc)
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
        settings.updated_at = datetime.now(timezone.utc)
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
        from app.utils import escape_like
        query_safe = escape_like(form.query.data)
        search = f"%{query_safe}%"
        query = query.filter(
            or_(
                User.username.ilike(search, escape='\\'),
                User.email.ilike(search, escape='\\'),
                User.first_name.ilike(search, escape='\\'),
                User.last_name.ilike(search, escape='\\'),
                User.company_name.ilike(search, escape='\\')
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
        user.updated_at = datetime.now(timezone.utc)
        
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
        settings.min_duration_days = int(form.min_duration_days.data)
        settings.max_duration_days = int(form.max_duration_days.data)
        settings.updated_by = current_user.id
        settings.updated_at = datetime.now(timezone.utc)
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
                created_at=datetime.now(timezone.utc),
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
            camp = db.session.get(AdCampaign, int(creative_form.campaign_id.data))
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
                created_at=datetime.now(timezone.utc),
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

    def _calculate_ctr(clicks: int | None, imps: int | None) -> float:
        impressions = float(imps or 0)
        click_count = float(clicks or 0)
        return round((click_count / impressions) * 100.0, 2) if impressions > 0 else 0.0

    campaign_stats = {c.id: {"ctr": _calculate_ctr(c.clicks_count, c.impressions_count)} for c in campaigns}
    creative_stats = {c.id: {"ctr": _calculate_ctr(c.clicks_count, c.impressions_count)} for c in creatives}

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
    
    from app.utils import escape_like
    query_safe = escape_like(query)
    search = f"%{query_safe}%"
    
    # Search users
    users = User.query.filter(
        or_(
            User.username.ilike(search, escape='\\'),
            User.email.ilike(search, escape='\\'),
            User.first_name.ilike(search, escape='\\'),
            User.last_name.ilike(search, escape='\\'),
            User.company_name.ilike(search, escape='\\')
        )
    ).limit(20).all()
    
    # Search posts
    posts = Post.query.filter(Post.content.ilike(search, escape='\\')).limit(20).all()
    
    # Search events
    events = Event.query.filter(
        or_(
            Event.title.ilike(search, escape='\\'),
            Event.description.ilike(search, escape='\\')
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
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    now = datetime.now(timezone.utc)

    # Cache heavy stats briefly (admin page can be expensive on large DBs)
    cache = get_cache()
    cache_key = f"admin:stats:days={days}"
    cached = None
    try:
        cached = cache.get(cache_key)
    except Exception:
        cached = None
    if isinstance(cached, dict) and cached.get("ok"):
        return render_template('admin/analytics.html', **cached["payload"])

    # 1. Signup Data (Daily for chart)
    signup_map = {}
    # Initialize all days with 0
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=i)).strftime('%Y-%m-%d')
        signup_map[d] = 0
            
    try:
        users_last_days = User.query.filter(User.created_at >= start_date).all()
        for u in users_last_days:
            if u.created_at:
                d = u.created_at.strftime('%Y-%m-%d')
                if d in signup_map:
                    signup_map[d] += 1
    except Exception as e:
        logger.error(f"Error fetching signup stats: {e}", exc_info=True)

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
        logger.error(f"Error fetching user stats: {e}", exc_info=True)
    
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
            d = (datetime.now(timezone.utc) - timedelta(days=i)).strftime('%Y-%m-%d')
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
        logger.error(f"Error fetching activity stats: {e}", exc_info=True)
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
        ).join(Post, Post.user_id == User.id).group_by(User.id).order_by(desc('post_count')).limit(10).all()
    except Exception as e:
        logger.error(f"Error fetching top posters: {e}", exc_info=True)
    
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
        logger.error(f"Error fetching societies: {e}", exc_info=True)
    
    # 6. Business metrics (revenue, add-ons, marketplace, take-rate, ads, retention)
    business = {}
    try:
        revenue_30d = (
            db.session.query(func.sum(Payment.amount))
            .filter(Payment.status == 'completed', Payment.created_at >= start_date)
            .scalar()
            or 0
        )
        subs_active = Subscription.query.filter_by(status='active').count()
        subs_past_due = Subscription.query.filter_by(status='past_due').count()
        take_rate_30d = (
            db.session.query(func.sum(PlatformTransaction.platform_fee_amount))
            .filter(PlatformTransaction.created_at >= start_date)
            .scalar()
            or 0
        )
        marketplace_sales_30d = MarketplacePurchase.query.filter(MarketplacePurchase.status == 'completed', MarketplacePurchase.created_at >= start_date).count()
        addons_30d = AddOnEntitlement.query.filter(AddOnEntitlement.created_at >= start_date, AddOnEntitlement.status == 'active').count()
        ads_selfserve_budget = (
            db.session.query(func.sum(AdCampaign.budget_cents))
            .filter(AdCampaign.is_self_serve == True)  # noqa: E712
            .scalar()
            or 0
        )
        ads_selfserve_spend = (
            db.session.query(func.sum(AdCampaign.spend_cents))
            .filter(AdCampaign.is_self_serve == True)  # noqa: E712
            .scalar()
            or 0
        )
        retention_avg = (
            db.session.query(func.avg(SocietyHealthSnapshot.score))
            .filter(SocietyHealthSnapshot.created_at >= start_date)
            .scalar()
        )
        business = {
            "revenue_30d": float(revenue_30d),
            "subs_active": int(subs_active),
            "subs_past_due": int(subs_past_due),
            "take_rate_30d": float(take_rate_30d),
            "marketplace_sales_30d": int(marketplace_sales_30d),
            "addons_30d": int(addons_30d),
            "ads_selfserve_budget_eur": round(float(ads_selfserve_budget or 0) / 100.0, 2),
            "ads_selfserve_spend_eur": round(float(ads_selfserve_spend or 0) / 100.0, 2),
            "retention_avg_score": round(float(retention_avg or 0), 1) if retention_avg is not None else None,
        }
    except Exception as e:
        logger.error(f"Error fetching business stats: {e}", exc_info=True)
        business = {}

    payload = {
        "days": days,
        "signup_data": signup_data,
        "role_data": role_data,
        "growth_stats": growth_stats,
        "activity_trend": activity_trend,
        "top_posters": top_posters,
        "top_societies": top_societies,
        "business": business,
    }
    try:
        cache.set(cache_key, {"ok": True, "payload": payload}, ttl=60)
    except Exception:
        pass
    return render_template('admin/analytics.html', **payload)


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


DEFAULT_PLATFORM_FEATURES = [
    {'key': 'social_feed', 'name': 'Social Feed', 'description': 'Bacheca social con post, like e commenti', 'category': 'Social', 'icon': 'bi-newspaper', 'is_premium': False, 'display_order': 1},
    {'key': 'messaging', 'name': 'Messaggi Interni', 'description': 'Sistema di messaggistica interna tra utenti', 'category': 'Social', 'icon': 'bi-chat-dots-fill', 'is_premium': False, 'display_order': 2},
    {'key': 'connections', 'name': 'Connessioni', 'description': 'Sistema di connessioni tipo LinkedIn', 'category': 'Social', 'icon': 'bi-people-fill', 'is_premium': False, 'display_order': 3},
    {'key': 'photos', 'name': 'Pubblicazione Foto', 'description': 'Upload e condivisione foto nei post', 'category': 'Media', 'icon': 'bi-image', 'is_premium': False, 'display_order': 4},
    {'key': 'videos', 'name': 'Pubblicazione Video', 'description': 'Upload e condivisione video nei post', 'category': 'Media', 'icon': 'bi-camera-video-fill', 'is_premium': True, 'display_order': 5},
    {'key': 'crm', 'name': 'CRM', 'description': 'Gestione contatti, opportunità e pipeline commerciale', 'category': 'Business', 'icon': 'bi-kanban', 'is_premium': False, 'display_order': 6},
    {'key': 'advanced_stats', 'name': 'Statistiche Avanzate', 'description': 'Dashboard analytics con metriche dettagliate', 'category': 'Business', 'icon': 'bi-graph-up-arrow', 'is_premium': True, 'display_order': 7},
    {'key': 'api_access', 'name': 'Accesso API', 'description': 'Integrazione via API REST per sviluppatori', 'category': 'Business', 'icon': 'bi-code-slash', 'is_premium': True, 'display_order': 8},
    {'key': 'white_label', 'name': 'White Label', 'description': 'Personalizzazione completa del brand (logo, colori, dominio)', 'category': 'Business', 'icon': 'bi-palette-fill', 'is_premium': True, 'display_order': 9},
    {'key': 'priority_support', 'name': 'Supporto Prioritario', 'description': 'Assistenza dedicata con tempi di risposta rapidi', 'category': 'Supporto', 'icon': 'bi-headset', 'is_premium': True, 'display_order': 10},
    {'key': 'events', 'name': 'Gestione Eventi', 'description': 'Creazione e gestione eventi sportivi, convocazioni', 'category': 'Organizzazione', 'icon': 'bi-calendar-event', 'is_premium': False, 'display_order': 11},
    {'key': 'planner', 'name': 'Planner Calendario', 'description': 'Calendario avanzato con viste giorno/settimana/mese', 'category': 'Organizzazione', 'icon': 'bi-calendar3', 'is_premium': False, 'display_order': 12},
    {'key': 'tournaments', 'name': 'Tornei', 'description': 'Gestione tornei con tabelloni, gironi e classifiche', 'category': 'Organizzazione', 'icon': 'bi-trophy-fill', 'is_premium': True, 'display_order': 13},
    {'key': 'tasks', 'name': 'Task e Progetti', 'description': 'Gestione attività con Kanban, timeline e scadenze', 'category': 'Organizzazione', 'icon': 'bi-list-task', 'is_premium': True, 'display_order': 14},
    {'key': 'marketplace', 'name': 'Marketplace', 'description': 'Acquisto e vendita di template e risorse', 'category': 'Business', 'icon': 'bi-shop', 'is_premium': True, 'display_order': 15},
    {'key': 'automation', 'name': 'Automazioni', 'description': 'Workflow automatizzati basati su trigger e condizioni', 'category': 'Business', 'icon': 'bi-lightning-fill', 'is_premium': True, 'display_order': 16},
    {'key': 'ads_selfserve', 'name': 'Inserzioni Self-Service', 'description': 'Creazione e gestione campagne pubblicitarie', 'category': 'Business', 'icon': 'bi-megaphone-fill', 'is_premium': True, 'display_order': 17},
    {'key': 'backup', 'name': 'Backup & Ripristino', 'description': 'Backup automatici e ripristino dati', 'category': 'Sicurezza', 'icon': 'bi-cloud-arrow-up-fill', 'is_premium': False, 'display_order': 18},
    {'key': 'enterprise_pack', 'name': 'Enterprise Pack', 'description': 'SSO, audit avanzato, export illimitati e funzionalità enterprise', 'category': 'Sicurezza', 'icon': 'bi-shield-lock-fill', 'is_premium': True, 'display_order': 20},
    {'key': 'analytics_pro', 'name': 'Analytics Pro', 'description': 'Business intelligence e report personalizzati', 'category': 'Business', 'icon': 'bi-bar-chart-line-fill', 'is_premium': True, 'display_order': 21},
    {'key': 'notifications', 'name': 'Notifiche', 'description': 'Sistema di notifiche push, email e in-app', 'category': 'Comunicazione', 'icon': 'bi-bell-fill', 'is_premium': False, 'display_order': 22},
    {'key': 'profile_linkedin', 'name': 'Profilo LinkedIn-Style', 'description': 'Profili avanzati con carriera, educazione e competenze', 'category': 'Social', 'icon': 'bi-person-badge-fill', 'is_premium': False, 'display_order': 23},
    {'key': 'data_export', 'name': 'Esportazione Dati', 'description': 'Download dati della propria società in CSV', 'category': 'Business', 'icon': 'bi-download', 'is_premium': False, 'display_order': 24},
    {'key': 'groups', 'name': 'Gruppi Community', 'description': 'Gruppi tematici e community con feed e chat', 'category': 'Social', 'icon': 'bi-people', 'is_premium': False, 'display_order': 30},
    {'key': 'stories', 'name': 'Storie/Status', 'description': 'Contenuti temporanei tipo Instagram Stories', 'category': 'Social', 'icon': 'bi-circle-fill', 'is_premium': False, 'display_order': 31},
    {'key': 'polls', 'name': 'Sondaggi', 'description': 'Sistema di sondaggi e votazioni', 'category': 'Social', 'icon': 'bi-bar-chart-line', 'is_premium': False, 'display_order': 32},
    {'key': 'sports_stats', 'name': 'Statistiche Sportive', 'description': 'Tracking prestazioni e statistiche atleti', 'category': 'Organizzazione', 'icon': 'bi-activity', 'is_premium': False, 'display_order': 33},
    {'key': 'documents', 'name': 'Gestione Documenti', 'description': 'Archivio documenti condiviso con cartelle', 'category': 'Organizzazione', 'icon': 'bi-folder2-open', 'is_premium': False, 'display_order': 34},
    {'key': 'payments_online', 'name': 'Pagamenti Online', 'description': 'Pagamento quote con carta via Stripe', 'category': 'Business', 'icon': 'bi-credit-card', 'is_premium': True, 'display_order': 35},
    {'key': 'gamification', 'name': 'Gamification', 'description': 'Badge, punti, livelli e classifiche', 'category': 'Social', 'icon': 'bi-trophy-fill', 'is_premium': False, 'display_order': 36},
    {'key': 'custom_dashboard', 'name': 'Dashboard Personalizzabile', 'description': 'Dashboard con widget drag-and-drop', 'category': 'Organizzazione', 'icon': 'bi-grid-1x2', 'is_premium': False, 'display_order': 37},
    {'key': 'multi_language', 'name': 'Multi-lingua', 'description': 'Supporto multilingua (IT/EN/ES/FR/DE)', 'category': 'Comunicazione', 'icon': 'bi-translate', 'is_premium': False, 'display_order': 38},
    {'key': 'push_notifications', 'name': 'Notifiche Push', 'description': 'Notifiche push nel browser', 'category': 'Comunicazione', 'icon': 'bi-bell-fill', 'is_premium': True, 'display_order': 39},
]


def _seed_platform_features():
    for fdef in DEFAULT_PLATFORM_FEATURES:
        existing = PlatformFeature.query.filter_by(key=fdef['key']).first()
        if not existing:
            pf = PlatformFeature(
                key=fdef['key'],
                name=fdef['name'],
                description=fdef['description'],
                category=fdef['category'],
                icon=fdef['icon'],
                is_premium=fdef['is_premium'],
                is_enabled=True,
                display_order=fdef['display_order'],
            )
            db.session.add(pf)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


@bp.route('/feature-control')
@login_required
@admin_required
def feature_control():
    _seed_platform_features()
    features = PlatformFeature.query.order_by(PlatformFeature.display_order).all()
    categories = {}
    for f in features:
        cat = f.category or 'Altro'
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(f)
    return render_template('admin/feature_control.html', categories=categories, features=features)


@bp.route('/feature-control/update', methods=['POST'])
@login_required
@admin_required
def feature_control_update():
    features = PlatformFeature.query.all()
    for f in features:
        premium_key = f'premium_{f.id}'
        enabled_key = f'enabled_{f.id}'
        f.is_premium = premium_key in request.form
        f.is_enabled = enabled_key in request.form
        f.updated_by = current_user.id
        f.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    log_action('update_feature_control', 'PlatformFeature', 0, 'Updated premium/free feature settings')
    flash('Configurazione funzionalità aggiornata con successo!', 'success')
    return redirect(url_for('admin.feature_control'))


@bp.route('/feature-control/toggle/<int:feature_id>', methods=['POST'])
@login_required
@admin_required
def feature_toggle(feature_id):
    f = PlatformFeature.query.get_or_404(feature_id)
    action = request.form.get('action', 'toggle_premium')
    if action == 'toggle_premium':
        f.is_premium = not f.is_premium
    elif action == 'toggle_enabled':
        f.is_enabled = not f.is_enabled
    f.updated_by = current_user.id
    f.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    status = 'Premium' if f.is_premium else 'Free'
    log_action('toggle_feature', 'PlatformFeature', f.id, f'{f.name} -> {status}')
    return jsonify({'success': True, 'is_premium': f.is_premium, 'is_enabled': f.is_enabled})


@bp.route('/feature-control/reset', methods=['POST'])
@login_required
@admin_required
def feature_control_reset():
    for fdef in DEFAULT_PLATFORM_FEATURES:
        pf = PlatformFeature.query.filter_by(key=fdef['key']).first()
        if pf:
            pf.is_premium = fdef['is_premium']
            pf.is_enabled = True
            pf.updated_by = current_user.id
            pf.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    log_action('reset_feature_control', 'PlatformFeature', 0, 'Reset features to default')
    flash('Funzionalità ripristinate ai valori predefiniti.', 'success')
    return redirect(url_for('admin.feature_control'))


@bp.route('/export/users')
@login_required
@admin_required
def export_users():
    """Export all users as CSV."""
    users = User.query.order_by(User.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'ID', 'Username', 'Email', 'Nome', 'Cognome', 'Telefono',
        'Ruolo', 'Attivo', 'Verificato', 'Bannato', 'Lingua',
        'Data Registrazione', 'Ultimo Accesso', 'Società ID'
    ])
    for u in users:
        writer.writerow([
            u.id, u.username, u.email,
            u.first_name or '', u.last_name or '', u.phone or '',
            u.role, u.is_active, u.is_verified, u.is_banned,
            getattr(u, 'language', 'it'),
            u.created_at.strftime('%Y-%m-%d %H:%M') if u.created_at else '',
            u.last_seen.strftime('%Y-%m-%d %H:%M') if u.last_seen else '',
            u.society_id or ''
        ])
    resp = make_response(output.getvalue())
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename=utenti_sonacip_{datetime.now(timezone.utc).strftime("%Y%m%d")}.csv'
    log_action('export_users', 'User', 0, f'Exported {len(users)} users to CSV')
    return resp


@bp.route('/export/societies')
@login_required
@admin_required
def export_societies():
    """Export all societies as CSV."""
    societies = Society.query.order_by(Society.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'ID', 'Nome', 'Email', 'Telefono', 'Indirizzo', 'Città',
        'Provincia', 'CAP', 'Codice Fiscale', 'P.IVA',
        'Sport', 'Data Creazione'
    ])
    for s in societies:
        writer.writerow([
            s.id, s.legal_name or '', s.email or '',
            s.phone or '', s.address or '',
            s.city or '', s.province or '',
            s.postal_code or '', s.fiscal_code or '',
            s.vat_number or '', s.sport_categories or '',
            s.created_at.strftime('%Y-%m-%d %H:%M') if s.created_at else ''
        ])
    resp = make_response(output.getvalue())
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename=societa_sonacip_{datetime.now(timezone.utc).strftime("%Y%m%d")}.csv'
    log_action('export_societies', 'Society', 0, f'Esportate {len(societies)} società in CSV')
    return resp


@bp.route('/export/society/<int:society_id>')
@login_required
@admin_required
def export_society_detail(society_id):
    """Export detailed data for a specific society (members, events, etc)."""
    from app.models import SocietyMembership, SocietyCalendarEvent
    society = Society.query.get_or_404(society_id)
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([f'=== SOCIETÀ: {society.legal_name} ==='])
    writer.writerow(['Campo', 'Valore'])
    writer.writerow(['Nome', society.legal_name or ''])
    writer.writerow(['Email', society.email or ''])
    writer.writerow(['Telefono', society.phone or ''])
    writer.writerow(['Indirizzo', society.address or ''])
    writer.writerow(['Città', society.city or ''])
    writer.writerow(['Sport', society.sport_categories or ''])
    writer.writerow([])

    writer.writerow(['=== MEMBRI ==='])
    writer.writerow(['ID Utente', 'Nome', 'Email', 'Ruolo', 'Data Iscrizione'])
    members = SocietyMembership.query.filter_by(society_id=society_id).all()
    for m in members:
        user = db.session.get(User, m.user_id)
        if user:
            writer.writerow([
                user.id, user.get_full_name(), user.email,
                getattr(m, 'role', '') or '',
                m.created_at.strftime('%Y-%m-%d') if m.created_at else ''
            ])
    writer.writerow([])

    writer.writerow(['=== EVENTI ==='])
    writer.writerow(['ID', 'Titolo', 'Data Inizio', 'Data Fine', 'Luogo'])
    events = SocietyCalendarEvent.query.filter_by(society_id=society_id).all()
    for e in events:
        writer.writerow([
            e.id, getattr(e, 'title', '') or '',
            e.start_datetime.strftime('%Y-%m-%d %H:%M') if getattr(e, 'start_datetime', None) else '',
            e.end_datetime.strftime('%Y-%m-%d %H:%M') if getattr(e, 'end_datetime', None) else '',
            getattr(e, 'location_text', '') or ''
        ])

    resp = make_response(output.getvalue())
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    safe_name = (society.legal_name or 'societa').replace(' ', '_').lower()[:30]
    resp.headers['Content-Disposition'] = f'attachment; filename={safe_name}_{datetime.now(timezone.utc).strftime("%Y%m%d")}.csv'
    log_action('export_society_detail', 'Society', society.id, f'Exported detailed data for {society.legal_name}')
    return resp


@bp.route('/export-center')
@login_required
@admin_required
def export_center():
    """Data export center for super admin."""
    societies = Society.query.order_by(Society.legal_name).all()
    total_users = User.query.count()
    total_societies = Society.query.count()
    return render_template('admin/export_center.html',
                           societies=societies,
                           total_users=total_users,
                           total_societies=total_societies)


@bp.route('/email-confirmation', methods=['GET', 'POST'])
@login_required
@admin_required
def email_confirmation_settings():
    setting = EmailConfirmationSetting.query.first()
    if not setting:
        setting = EmailConfirmationSetting(enabled=False)
        db.session.add(setting)
        db.session.commit()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'toggle':
            setting.enabled = not setting.enabled
            setting.updated_by = current_user.id
            if setting.enabled and setting.auto_confirm_existing:
                User.query.filter_by(email_confirmed=False).update({'email_confirmed': True})
            db.session.commit()
            status = 'attivata' if setting.enabled else 'disattivata'
            if setting.enabled and setting.auto_confirm_existing:
                flash(f'Conferma email {status}. Tutti gli utenti esistenti sono stati confermati automaticamente.', 'success')
            else:
                flash(f'Conferma email {status}.', 'success')
            log_action('toggle_email_confirmation', 'EmailConfirmationSetting', setting.id,
                       f'Email confirmation {"enabled" if setting.enabled else "disabled"}')

        elif action == 'save_settings':
            setting.token_expiry_hours = int(request.form.get('token_expiry_hours', 48))
            setting.max_resends = int(request.form.get('max_resends', 5))
            setting.email_subject = request.form.get('email_subject', '').strip() or 'Conferma il tuo indirizzo email - SONACIP'
            setting.updated_by = current_user.id
            db.session.commit()
            flash('Impostazioni salvate.', 'success')
            log_action('update_email_confirmation', 'EmailConfirmationSetting', setting.id, 'Updated settings')

        elif action == 'confirm_all_existing':
            count = User.query.filter_by(email_confirmed=False).update({'email_confirmed': True})
            db.session.commit()
            flash(f'{count} utenti confermati manualmente.', 'success')
            log_action('confirm_all_users', 'User', 0, f'Bulk confirmed {count} users')

        elif action == 'confirm_user':
            user_id = request.form.get('user_id', type=int)
            if user_id:
                user = db.session.get(User, user_id)
                if user:
                    user.email_confirmed = True
                    user.email_confirm_token = None
                    db.session.commit()
                    flash(f'Utente {user.email} confermato.', 'success')
                    log_action('confirm_user_email', 'User', user.id, f'Manually confirmed {user.email}')

        return redirect(url_for('admin.email_confirmation_settings'))

    total_users = User.query.count()
    confirmed_users = User.query.filter_by(email_confirmed=True).count()
    unconfirmed_users = User.query.filter_by(email_confirmed=False).count()
    pending_users = User.query.filter_by(email_confirmed=False).order_by(User.created_at.desc()).limit(50).all()
    smtp = SmtpSetting.query.first()
    smtp_configured = smtp and smtp.enabled

    return render_template('admin/email_confirmation_settings.html',
                           setting=setting,
                           total_users=total_users,
                           confirmed_users=confirmed_users,
                           unconfirmed_users=unconfirmed_users,
                           pending_users=pending_users,
                           smtp_configured=smtp_configured)


@bp.route('/chat-monitor')
@login_required
@admin_required
def chat_monitor():
    page = request.args.get('page', 1, type=int)
    search_q = request.args.get('q', '').strip()
    user_filter = request.args.get('user_id', 0, type=int)

    user_a_expr = case(
        (Message.sender_id <= Message.recipient_id, Message.sender_id),
        else_=Message.recipient_id,
    )
    user_b_expr = case(
        (Message.sender_id <= Message.recipient_id, Message.recipient_id),
        else_=Message.sender_id,
    )

    total_messages = Message.query.count()
    total_conversations = db.session.query(
        user_a_expr,
        user_b_expr,
    ).distinct().count()
    active_chatters = db.session.query(func.count(func.distinct(Message.sender_id))).scalar() or 0
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_messages = Message.query.filter(Message.created_at >= today_start).count()

    conversations_q = db.session.query(
        user_a_expr.label('user_a'),
        user_b_expr.label('user_b'),
        func.count(Message.id).label('msg_count'),
        func.max(Message.created_at).label('last_activity')
    ).group_by('user_a', 'user_b').order_by(desc('last_activity'))

    if user_filter:
        conversations_q = conversations_q.filter(
            or_(Message.sender_id == user_filter, Message.recipient_id == user_filter)
        )

    count_subq = db.session.query(user_a_expr.label('ua'), user_b_expr.label('ub'))
    if user_filter:
        count_subq = count_subq.filter(
            or_(Message.sender_id == user_filter, Message.recipient_id == user_filter)
        )
    total_conv_count = count_subq.group_by('ua', 'ub').count()

    conversations_raw = conversations_q.limit(50).offset((page - 1) * 50).all()

    conversations = []
    for conv in conversations_raw:
        user_a = db.session.get(User, conv.user_a)
        user_b = db.session.get(User, conv.user_b)
        if user_a and user_b:
            conversations.append({
                'user_a': user_a,
                'user_b': user_b,
                'msg_count': conv.msg_count,
                'last_activity': conv.last_activity
            })

    return render_template('admin/chat_monitor.html',
                           total_messages=total_messages,
                           total_conversations=total_conversations,
                           active_chatters=active_chatters,
                           today_messages=today_messages,
                           conversations=conversations,
                           page=page,
                           total_pages=(total_conv_count + 49) // 50,
                           user_filter=user_filter,
                           search_q=search_q)


@bp.route('/chat-monitor/conversation/<int:user_a_id>/<int:user_b_id>')
@login_required
@admin_required
def chat_monitor_conversation(user_a_id, user_b_id):
    user_a = User.query.get_or_404(user_a_id)
    user_b = User.query.get_or_404(user_b_id)

    messages = Message.query.filter(
        or_(
            and_(Message.sender_id == user_a_id, Message.recipient_id == user_b_id),
            and_(Message.sender_id == user_b_id, Message.recipient_id == user_a_id)
        )
    ).order_by(Message.created_at.asc()).all()

    return render_template('admin/chat_monitor_conversation.html',
                           user_a=user_a, user_b=user_b, messages=messages)


@bp.route('/chat-monitor/delete-message/<int:message_id>', methods=['POST'])
@login_required
@admin_required
def chat_monitor_delete_message(message_id):
    msg = Message.query.get_or_404(message_id)
    sender_id = msg.sender_id
    recipient_id = msg.recipient_id
    db.session.delete(msg)
    db.session.commit()
    log_action('delete_message', 'Message', message_id, f'Admin deleted message between users {sender_id} and {recipient_id}')
    flash('Messaggio eliminato.', 'success')
    return redirect(url_for('admin.chat_monitor_conversation',
                            user_a_id=min(sender_id, recipient_id),
                            user_b_id=max(sender_id, recipient_id)))


@bp.route('/menu-order')
@login_required
@admin_required
def menu_order():
    menu_items = _get_sidebar_menu_config()
    main_items = [i for i in menu_items if i.get('section') == 'main']
    bottom_items = [i for i in menu_items if i.get('section') == 'bottom']
    return render_template('admin/menu_order.html', main_items=main_items, bottom_items=bottom_items)


@bp.route('/menu-order/save', methods=['POST'])
@login_required
@admin_required
def menu_order_save():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Dati non validi'}), 400

        valid_ids = {item['id'] for item in DEFAULT_SIDEBAR_MENU}
        fixed_ids = {item['id'] for item in DEFAULT_SIDEBAR_MENU if item.get('fixed')}
        default_sections = {item['id']: item['section'] for item in DEFAULT_SIDEBAR_MENU}

        order_list = []
        seen_ids = set()
        for item in data.get('items', []):
            item_id = item.get('id', '')
            if item_id not in valid_ids or item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            visible = item.get('visible', True)
            section = item.get('section', default_sections.get(item_id, 'main'))
            if item_id in fixed_ids:
                visible = True
            order_list.append({
                'id': item_id,
                'visible': visible,
                'section': section,
            })

        for default_item in DEFAULT_SIDEBAR_MENU:
            if default_item['id'] not in seen_ids:
                order_list.append({
                    'id': default_item['id'],
                    'visible': True,
                    'section': default_item['section'],
                })

        row = CustomizationKV.query.filter_by(scope='site', scope_key=None, key='sidebar.menu_order').first()
        if not row:
            row = CustomizationKV(scope='site', scope_key=None, key='sidebar.menu_order')
            db.session.add(row)
        row.set_value(order_list)
        row.updated_by = current_user.id
        row.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        log_action('update_menu_order', 'CustomizationKV', row.id, 'Updated sidebar menu order')
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/menu-order/reset', methods=['POST'])
@login_required
@admin_required
def menu_order_reset():
    row = CustomizationKV.query.filter_by(scope='site', scope_key=None, key='sidebar.menu_order').first()
    if row:
        db.session.delete(row)
        db.session.commit()
    log_action('reset_menu_order', 'CustomizationKV', 0, 'Reset sidebar menu order to default')
    flash('Ordine menu ripristinato ai valori predefiniti.', 'success')
    return redirect(url_for('admin.menu_order'))


# ============================================================================
# SYSTEM MODULES MANAGEMENT
# ============================================================================

@bp.route('/modules')
@login_required
@admin_required
def modules():
    """List all system modules"""
    modules_list = SystemModule.query.order_by(SystemModule.uploaded_at.desc()).all()
    return render_template('admin/modules.html', modules=modules_list)


@bp.route('/modules/upload', methods=['GET', 'POST'])
@login_required
@admin_required
def module_upload():
    """Upload a new system module"""
    form = ModuleUploadForm()
    
    if form.validate_on_submit():
        try:
            # Get the uploaded file
            module_file = form.module_file.data
            if not module_file:
                flash('Nessun file selezionato.', 'danger')
                return redirect(url_for('admin.module_upload'))
            
            # Secure the filename
            from werkzeug.utils import secure_filename
            filename = secure_filename(module_file.filename)
            
            # Create aggiornamento directory if it doesn't exist
            upload_dir = os.path.join(current_app.root_path, '..', 'aggiornamento')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save the file
            filepath = os.path.join(upload_dir, filename)
            module_file.save(filepath)
            
            # Create database record
            module = SystemModule(
                name=form.name.data,
                version=form.version.data,
                filename=filename,
                description=form.description.data,
                uploaded_by=current_user.id,
                enabled=False
            )
            
            db.session.add(module)
            db.session.commit()
            
            log_action('upload_module', 'SystemModule', module.id, f'Uploaded module {module.name} v{module.version}')
            flash(f'Modulo {module.name} v{module.version} caricato con successo!', 'success')
            return redirect(url_for('admin.modules'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error uploading module: {e}')
            flash(f'Errore durante il caricamento del modulo: {str(e)}', 'danger')
            return redirect(url_for('admin.module_upload'))
    
    return render_template('admin/module_upload.html', form=form)


@bp.route('/modules/<int:module_id>/toggle', methods=['POST'])
@login_required
@admin_required
def module_toggle(module_id):
    """Enable or disable a module"""
    module = SystemModule.query.get_or_404(module_id)
    
    try:
        module.enabled = not module.enabled
        if module.enabled:
            module.enabled_at = datetime.now(timezone.utc)
            module.disabled_at = None
            action_msg = f'Enabled module {module.name} v{module.version}'
            flash_msg = f'Modulo {module.name} attivato con successo!'
        else:
            module.disabled_at = datetime.now(timezone.utc)
            action_msg = f'Disabled module {module.name} v{module.version}'
            flash_msg = f'Modulo {module.name} disattivato con successo!'
        
        db.session.commit()
        log_action('toggle_module', 'SystemModule', module.id, action_msg)
        flash(flash_msg, 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error toggling module: {e}')
        flash(f'Errore durante la modifica dello stato del modulo: {str(e)}', 'danger')
    
    return redirect(url_for('admin.modules'))


@bp.route('/modules/<int:module_id>/delete', methods=['POST'])
@login_required
@admin_required
def module_delete(module_id):
    """Delete a module"""
    module = SystemModule.query.get_or_404(module_id)
    
    try:
        # Delete the file from disk
        upload_dir = os.path.join(current_app.root_path, '..', 'aggiornamento')
        filepath = os.path.join(upload_dir, module.filename)
        
        if os.path.exists(filepath):
            os.remove(filepath)
        
        # Delete the database record
        module_name = module.name
        module_version = module.version
        db.session.delete(module)
        db.session.commit()
        
        log_action('delete_module', 'SystemModule', module_id, f'Deleted module {module_name} v{module_version}')
        flash(f'Modulo {module_name} eliminato con successo!', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting module: {e}')
        flash(f'Errore durante l\'eliminazione del modulo: {str(e)}', 'danger')
    
    return redirect(url_for('admin.modules'))


@bp.route('/modules/<int:module_id>/download')
@login_required
@admin_required
def module_download(module_id):
    """Download a module file"""
    module = SystemModule.query.get_or_404(module_id)
    
    try:
        upload_dir = os.path.join(current_app.root_path, '..', 'aggiornamento')
        filepath = os.path.join(upload_dir, module.filename)
        
        if not os.path.exists(filepath):
            flash('File del modulo non trovato.', 'danger')
            return redirect(url_for('admin.modules'))
        
        from flask import send_file
        return send_file(
            filepath,
            as_attachment=True,
            download_name=module.filename
        )
        
    except Exception as e:
        current_app.logger.error(f'Error downloading module: {e}')
        flash(f'Errore durante il download del modulo: {str(e)}', 'danger')
        return redirect(url_for('admin.modules'))


@bp.route('/restart-site', methods=['POST'])
@login_required
@admin_required
def restart_site():
    """Restart the site by clearing caches and touching the WSGI file."""
    try:
        # Clear application cache
        cache = get_cache()
        cache.clear()

        # Touch wsgi.py to trigger a reload when running under Gunicorn/uWSGI
        wsgi_path = os.path.join(current_app.root_path, '..', 'wsgi.py')
        wsgi_path = os.path.abspath(wsgi_path)
        if os.path.exists(wsgi_path):
            os.utime(wsgi_path, None)

        log_action('restart_site', entity_type='system', details='Site restart triggered by super admin')
        flash('Riavvio del sito eseguito con successo. Le cache sono state svuotate.', 'success')
    except Exception as e:
        current_app.logger.error(f'Error restarting site: {e}')
        flash(f'Errore durante il riavvio del sito: {str(e)}', 'danger')

    return redirect(url_for('admin.dashboard'))

