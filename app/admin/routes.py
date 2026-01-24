"""
Admin routes
"""
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_, func, desc
from app import db
from app.admin import bp
from app.admin.utils import admin_required
from app.admin.forms import UserEditForm, UserSearchForm, PrivacySettingsForm, AdsSettingsForm, SocialSettingsAdminForm, AppearanceSettingsForm, StorageSettingsForm
from app.automation.forms import AutomationRuleForm
from app.models import User, Post, Event, Notification, AuditLog, Backup, Comment, PrivacySetting, AdsSetting, Society, SocialSetting, AppearanceSetting, StorageSetting, AutomationRule, AutomationRun
from datetime import datetime, timedelta
from threading import Timer
import os
from app.cache import get_cache


@bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard with statistics"""
    cache = get_cache()

    def load_stats():
        return {
            'total_users': User.query.count(),
            'total_societies': Society.query.count(),
            'total_athletes': User.query.filter(User.role.in_(['atleta', 'athlete'])).count(),
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

    stats = cache.get('admin:stats') or load_stats()
    cache.set('admin:stats', stats, ttl=current_app.config.get('CACHE_DEFAULT_TTL', 300))
    
    # Recent users
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    
    # Recent activity logs
    recent_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(20).all()
    
    return render_template('admin/dashboard.html', 
                         stats=stats,
                         recent_users=recent_users,
                         recent_logs=recent_logs)


@bp.route('/reset', methods=['POST'])
@login_required
@admin_required
def reset_system():
    """Soft reset: clear caches and ask process to restart."""
    cache = get_cache()
    cache.clear()

    # Flush Redis if configured
    if current_app.config.get('REDIS_URL'):
        try:
            from app.cache import RedisBackedCache
            if isinstance(cache, RedisBackedCache):
                cache.clear()
        except Exception as exc:  # pragma: no cover
            current_app.logger.warning(f"Redis flush failed: {exc}")

    # Log the action
    log = AuditLog(
        user_id=current_user.id,
        action='admin_reset',
        entity_type='system',
        entity_id=None,
        details='Admin requested system reset',
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()

    # Schedule a gentle process exit to let the supervisor restart
    def _exit_process():
        current_app.logger.warning('Exiting process after admin reset request')
        os._exit(0)

    Timer(1.5, _exit_process).start()
    flash('Riavvio applicazione in corso. Riprova tra qualche secondo.', 'info')
    return redirect(url_for('admin.dashboard'))


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
        flash('Impostazioni privacy aggiornate.', 'success')
        return redirect(url_for('admin.privacy_settings'))
    
    return render_template('admin/privacy.html', form=form, settings=settings)


@bp.route('/storage', methods=['GET', 'POST'])
@login_required
@admin_required
def storage_settings():
    """Configurazione percorso e formato salvataggi media."""
    settings = StorageSetting.query.first()
    if not settings:
        settings = StorageSetting(
            storage_backend=current_app.config.get('STORAGE_BACKEND', 'local'),
            base_path=current_app.config.get('STORAGE_LOCAL_PATH') or current_app.config.get('UPLOAD_FOLDER'),
            preferred_image_format=current_app.config.get('MEDIA_PREFERRED_IMAGE_FORMAT', 'webp'),
            preferred_video_format=current_app.config.get('MEDIA_PREFERRED_VIDEO_FORMAT', 'mp4'),
            image_quality=current_app.config.get('MEDIA_IMAGE_QUALITY', 75)
        )
        db.session.add(settings)
        db.session.commit()

    form = StorageSettingsForm(obj=settings)
    if not form.base_path.data:
        form.base_path.data = settings.base_path or current_app.config.get('STORAGE_LOCAL_PATH')

    if form.validate_on_submit():
        settings.storage_backend = form.storage_backend.data
        settings.base_path = form.base_path.data
        settings.preferred_image_format = form.preferred_image_format.data or settings.preferred_image_format
        settings.preferred_video_format = form.preferred_video_format.data or settings.preferred_video_format
        try:
            settings.image_quality = int(form.image_quality.data) if form.image_quality.data else settings.image_quality
        except ValueError:
            flash('Qualità immagini non valida, lasciare vuoto per il default.', 'warning')
        try:
            settings.video_bitrate = int(form.video_bitrate.data) if form.video_bitrate.data else settings.video_bitrate
        except ValueError:
            flash('Bitrate video non valido, lasciare vuoto per il default.', 'warning')
        try:
            settings.video_max_width = int(form.video_max_width.data) if form.video_max_width.data else settings.video_max_width
        except ValueError:
            flash('Larghezza video non valida, lasciare vuoto per il default.', 'warning')
        try:
            settings.max_image_mb = int(form.max_image_mb.data) if form.max_image_mb.data else settings.max_image_mb
            settings.max_video_mb = int(form.max_video_mb.data) if form.max_video_mb.data else settings.max_video_mb
        except ValueError:
            flash('Limiti MB non validi, lasciare vuoto per il default.', 'warning')
        settings.updated_by = current_user.id
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Impostazioni storage aggiornate.', 'success')
        return redirect(url_for('admin.storage_settings'))

    return render_template('admin/storage_settings.html', form=form, settings=settings)


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


@bp.route('/social-settings', methods=['GET', 'POST'])
@login_required
@admin_required
def social_settings():
    settings = SocialSetting.query.first()
    if not settings:
        settings = SocialSetting()
        db.session.add(settings)
        db.session.commit()

    form = SocialSettingsAdminForm(obj=settings)
    if form.validate_on_submit():
        form.populate_obj(settings)
        settings.updated_by = current_user.id
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Impostazioni social aggiornate.', 'success')
        return redirect(url_for('admin.social_settings'))

    return render_template('admin/social_settings.html', form=form, settings=settings)


@bp.route('/appearance-settings', methods=['GET', 'POST'])
@login_required
@admin_required
def appearance_settings():
    settings = AppearanceSetting.query.filter_by(scope='global').first()
    if not settings:
        settings = AppearanceSetting(scope='global')
        db.session.add(settings)
        db.session.commit()

    form = AppearanceSettingsForm(obj=settings)
    if form.validate_on_submit():
        form.populate_obj(settings)
        settings.updated_by = current_user.id
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Tema globale aggiornato.', 'success')
        return redirect(url_for('admin.appearance_settings'))

    return render_template('admin/appearance_settings.html', form=form, settings=settings)


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
    # User statistics by role
    try:
        user_stats = db.session.query(
            User.role,
            func.count(User.id).label('count')
        ).group_by(User.role).all()
    except Exception as e:
        user_stats = []
        print(f"Error fetching user stats: {e}")
    
    # Activity statistics (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    try:
        activity_stats = {
            'new_users': User.query.filter(User.created_at >= thirty_days_ago).count(),
            'new_posts': Post.query.filter(Post.created_at >= thirty_days_ago).count(),
            'new_events': Event.query.filter(Event.created_at >= thirty_days_ago).count(),
            'new_comments': Comment.query.filter(Comment.created_at >= thirty_days_ago).count()
        }
    except Exception as e:
        activity_stats = {'new_users': 0, 'new_posts': 0, 'new_events': 0, 'new_comments': 0}
        print(f"Error fetching activity stats: {e}")
    
    # Top users by posts
    try:
        top_posters = db.session.query(
            User,
            func.count(Post.id).label('post_count')
        ).join(Post).group_by(User.id).order_by(desc('post_count')).limit(10).all()
    except Exception as e:
        top_posters = []
        print(f"Error fetching top posters: {e}")
    
    # Top societies by followers
    try:
        societies = Society.query.limit(10).all()
        top_societies = sorted(
            societies,
            key=lambda s: s.user.followers.count() if s.user else 0,
            reverse=True
        )[:10]
    except Exception as e:
        top_societies = []
        print(f"Error fetching societies: {e}")
    
    return render_template('admin/stats.html',
                         user_stats=user_stats,
                         activity_stats=activity_stats,
                         top_posters=top_posters,
                         top_societies=top_societies)


@bp.route('/analytics')
@login_required
@admin_required
def analytics():
    """Visual analytics for iscritti/classifiche/attività."""
    days = 14
    today = datetime.utcnow().date()

    # Daily signups for the chart
    signup_data = []
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        count = User.query.filter(func.date(User.created_at) == day).count()
        signup_data.append({'date': day.isoformat(), 'count': count})

    # Role distribution
    role_counts = db.session.query(User.role, func.count(User.id)).group_by(User.role).all()
    role_data = [{'role': r or 'non_definito', 'count': c} for r, c in role_counts]

    # Activity snapshot
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    activity_summary = {
        'posts': Post.query.filter(Post.created_at >= seven_days_ago).count(),
        'events': Event.query.filter(Event.created_at >= seven_days_ago).count(),
        'comments': Comment.query.filter(Comment.created_at >= seven_days_ago).count()
    }

    return render_template('admin/analytics.html',
                         signup_data=signup_data,
                         role_data=role_data,
                         activity_summary=activity_summary,
                         days=days)


@bp.route('/automations')
@login_required
@admin_required
def automation_rules():
    """List all automation rules."""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    rules = AutomationRule.query.order_by(AutomationRule.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get execution stats for each rule
    rule_stats = {}
    for rule in rules.items:
        runs = AutomationRun.query.filter_by(rule_id=rule.id).all()
        rule_stats[rule.id] = {
            'total': len(runs),
            'success': len([r for r in runs if r.status == 'success']),
            'failed': len([r for r in runs if r.status == 'failed']),
            'last_run': max([r.created_at for r in runs], default=None)
        }
    
    return render_template('admin/automation_rules.html', rules=rules, rule_stats=rule_stats)


@bp.route('/automations/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_automation_rule():
    """Create new automation rule."""
    form = AutomationRuleForm()
    
    if form.validate_on_submit():
        rule = AutomationRule(
            name=form.name.data,
            event_type=form.event_type.data,
            condition=form.condition.data or None,
            actions=form.actions.data,
            is_active=form.is_active.data,
            max_retries=form.max_retries.data,
            retry_delay=form.retry_delay.data,
            created_by=current_user.id
        )
        
        # Validate actions
        is_valid, error = rule.validate_actions()
        if not is_valid:
            flash(f'Errore validazione azioni: {error}', 'danger')
            return render_template('admin/automation_form.html', form=form, rule=None)
        
        db.session.add(rule)
        db.session.commit()
        
        # Log audit
        log = AuditLog(
            user_id=current_user.id,
            action='create_automation_rule',
            entity_type='AutomationRule',
            entity_id=rule.id,
            details=f'Created rule: {rule.name}',
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'Regola "{rule.name}" creata con successo.', 'success')
        return redirect(url_for('admin.automation_rules'))
    
    return render_template('admin/automation_form.html', form=form, rule=None)


@bp.route('/automations/<int:rule_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_automation_rule(rule_id):
    """Edit automation rule."""
    rule = AutomationRule.query.get_or_404(rule_id)
    form = AutomationRuleForm(obj=rule)
    
    if form.validate_on_submit():
        rule.name = form.name.data
        rule.event_type = form.event_type.data
        rule.condition = form.condition.data or None
        rule.actions = form.actions.data
        rule.is_active = form.is_active.data
        rule.max_retries = form.max_retries.data
        rule.retry_delay = form.retry_delay.data
        rule.updated_at = datetime.utcnow()
        
        # Validate actions
        is_valid, error = rule.validate_actions()
        if not is_valid:
            flash(f'Errore validazione azioni: {error}', 'danger')
            return render_template('admin/automation_form.html', form=form, rule=rule)
        
        db.session.commit()
        
        # Log audit
        log = AuditLog(
            user_id=current_user.id,
            action='edit_automation_rule',
            entity_type='AutomationRule',
            entity_id=rule.id,
            details=f'Updated rule: {rule.name}',
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'Regola "{rule.name}" aggiornata.', 'success')
        return redirect(url_for('admin.automation_rules'))
    
    return render_template('admin/automation_form.html', form=form, rule=rule)


@bp.route('/automations/<int:rule_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_automation_rule(rule_id):
    """Delete automation rule."""
    rule = AutomationRule.query.get_or_404(rule_id)
    rule_name = rule.name
    
    # Delete all runs first
    AutomationRun.query.filter_by(rule_id=rule.id).delete()
    
    db.session.delete(rule)
    db.session.commit()
    
    # Log audit
    log = AuditLog(
        user_id=current_user.id,
        action='delete_automation_rule',
        entity_type='AutomationRule',
        entity_id=rule_id,
        details=f'Deleted rule: {rule_name}',
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
    
    flash(f'Regola "{rule_name}" eliminata.', 'success')
    return redirect(url_for('admin.automation_rules'))


@bp.route('/automations/<int:rule_id>/runs')
@login_required
@admin_required
def automation_runs(rule_id):
    """View execution history for automation rule."""
    rule = AutomationRule.query.get_or_404(rule_id)
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    runs = AutomationRun.query.filter_by(rule_id=rule.id).order_by(
        AutomationRun.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('admin/automation_runs.html', rule=rule, runs=runs)
