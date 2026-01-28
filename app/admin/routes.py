"""
Admin routes
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_, and_, func, desc
from app import db
from app.admin.utils import admin_required
from app.admin.forms import UserEditForm, UserSearchForm, PrivacySettingsForm, AdsSettingsForm
from app.models import User, Post, Event, Notification, AuditLog, Backup, Comment, PrivacySetting, AdsSetting, Society
from datetime import datetime, timedelta
import os

bp = Blueprint('admin', __name__)


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
