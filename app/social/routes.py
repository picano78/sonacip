"""
Social routes
Profiles, feed, posts, follows, likes, comments
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from sqlalchemy import or_
from app import db, limiter
from app.social.forms import PostForm, CommentForm, ProfileEditForm, SearchForm, PromotePostForm
from app.social.society_forms import SocietyInviteForm
from app.social.utils import save_picture
from app.social.feed_ranking import get_connection_ids, score_feed_posts
from app.models import (
    User,
    Post,
    Comment,
    Notification,
    AuditLog,
    AddOn,
    AddOnEntitlement,
    AdsSetting,
    Payment,
    SocialSetting,
    SocietyCalendarEvent,
    SocietyHealthSnapshot,
    SocietySuggestionDismissal,
    TournamentMatch,
    SocietyInvite,
    SocietyMembership,
    UserOnboardingStep,
    Opportunity,
    Permission,
    SocietyRolePermission,
    Career,
    Education,
    Skill,
    SkillEndorsement,
    Connection,
    BroadcastMessage,
    BroadcastRecipient,
    Message,
    SmtpSetting,
)
from app.cache import get_cache
from app.utils import permission_required, check_permission, get_active_society_id
from app.utils import log_action
from datetime import datetime, timedelta, timezone
import os
from app.ads.utils import choose_creative, make_token

bp = Blueprint('social', __name__, url_prefix='/social')


@bp.route('/feed')
@login_required
@permission_required('social', 'comment')
def _build_feed_page(user, page, per_page, settings, admin_access, scope_id, cache, cache_ttl):
    cache_key = f"feed:{user.id}:p{page}:pp{per_page}"
    cached_ids = cache.get(cache_key)

    followed_ids = set()
    try:
        followed_ids = {u.id for u in user.followed.all()}
    except Exception:
        followed_ids = set()

    friend_ids = get_connection_ids(user)
    friend_ids -= followed_ids
    if user.id in friend_ids:
        friend_ids.remove(user.id)

    def is_visible(p: Post) -> bool:
        if admin_access:
            return True
        if p.user_id == user.id:
            return True
        if (p.audience or 'public') == 'public':
            return True
        if (p.audience or '') == 'direct' and p.target_user_id == user.id:
            return True
        if (p.audience or '') == 'society' and scope_id and p.society_id == scope_id:
            return True
        if (p.audience or '') == 'followers' and p.user_id in followed_ids:
            return True
        return False

    if cached_ids is None:
        start = (page - 1) * per_page
        fetch_limit = per_page * 5 + start
        now = datetime.utcnow()

        promoted = Post.query.filter(
            Post.is_promoted == True,
            Post.promotion_ends_at.isnot(None),
            Post.promotion_ends_at > now
        ).options(joinedload(Post.author)).order_by(Post.created_at.desc()).limit(per_page * 2).all()

        combined = []
        seen = set()

        def _extend_posts(query):
            try:
                rows = (query.options(joinedload(Post.author))
                        .order_by(Post.created_at.desc())
                        .limit(fetch_limit)
                        .all())
            except Exception:
                rows = []
            for p in rows:
                if p.id not in seen:
                    combined.append(p)
                    seen.add(p.id)

        for p in promoted:
            if p.id not in seen:
                combined.append(p)
                seen.add(p.id)

        base_ids = followed_ids | friend_ids | {user.id}
        _extend_posts(Post.query.filter(Post.user_id.in_(base_ids)))
        _extend_posts(Post.query.filter(~Post.user_id.in_(base_ids)))

        combined = [p for p in combined if is_visible(p)]
        sorted_posts = score_feed_posts(combined, user, followed_ids, friend_ids, settings)
        total = len(sorted_posts)
        end = start + per_page
        page_ids = [p.id for p in sorted_posts[start:end]] if start < total else []
        cache.set(cache_key, {'ids': page_ids, 'total': total}, ttl=cache_ttl)
    else:
        page_ids = cached_ids.get('ids', [])
        total = cached_ids.get('total', 0)

    if page_ids:
        posts_map = {p.id: p for p in Post.query.filter(Post.id.in_(page_ids)).options(joinedload(Post.author)).all()}
        posts = [posts_map[i] for i in page_ids if i in posts_map]
    else:
        posts = []

    return posts, total


def feed():
    """Main social feed"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    cache_ttl = current_app.config.get('CACHE_DEFAULT_TTL', 120)
    cache = get_cache()

    settings = SocialSetting.query.first()
    if settings and not settings.feed_enabled and not check_permission(current_user, 'admin', 'access'):
        flash('Il feed sociale è disabilitato dall\'amministratore.', 'warning')
        return redirect(url_for('main.dashboard'))
    
    admin_access = check_permission(current_user, 'admin', 'access')
    scope_id = get_active_society_id(current_user)
    posts, total = _build_feed_page(current_user, page, per_page, settings, admin_access, scope_id, cache, cache_ttl)

    # Autopilot banners (Facebook-like): pick creatives for placements.
    ad = None
    ad_token = None
    sidebar_ad = None
    sidebar_ad_token = None
    try:
        ad = choose_creative("feed_inline", society_id=scope_id, user_id=current_user.id)
        if ad:
            ad_token = make_token(ad, "feed_inline", society_id=scope_id, user_id=current_user.id)
    except Exception:
        ad = None
        ad_token = None
    try:
        sidebar_ad = choose_creative("sidebar_card", society_id=scope_id, user_id=current_user.id)
        if sidebar_ad:
            sidebar_ad_token = make_token(sidebar_ad, "sidebar_card", society_id=scope_id, user_id=current_user.id)
    except Exception:
        sidebar_ad = None
        sidebar_ad_token = None

    # Update promotion views and disable expired ones (no-op if empty)
    if posts:
        for p in posts:
            if p.is_promoted:
                if p.promotion_ends_at and p.promotion_ends_at < datetime.utcnow():
                    p.is_promoted = False
                else:
                    p.promotion_views = (p.promotion_views or 0) + 1
                    if p.promotion_views_target and p.promotion_views >= p.promotion_views_target:
                        p.is_promoted = False
        db.session.commit()

    # Fake pagination object
    class SimplePagination:
        def __init__(self, page, per_page, total):
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1
            self.next_num = page + 1
        def iter_pages(self):
            return range(1, self.pages + 1)

    pagination = SimplePagination(page, per_page, total)
    
    # Post form
    form = PostForm()
    
    return render_template('social/feed.html',
                         posts=posts,
                         pagination=pagination,
                         form=form,
                         ad=ad,
                         ad_token=ad_token,
                         sidebar_ad=sidebar_ad,
                         sidebar_ad_token=sidebar_ad_token)


@bp.route('/feed/posts')
@login_required
@permission_required('social', 'comment')
def feed_posts():
    """Return partial post cards for infinite scroll (AJAX)"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    cache_ttl = current_app.config.get('CACHE_DEFAULT_TTL', 120)
    cache = get_cache()
    settings = SocialSetting.query.first()
    admin_access = check_permission(current_user, 'admin', 'access')
    scope_id = get_active_society_id(current_user)
    posts, _total = _build_feed_page(current_user, page, per_page, settings, admin_access, scope_id, cache, cache_ttl)

    if not posts:
        return ''

    return render_template('social/feed_partial.html', posts=posts)


@bp.route('/feed/updates')
@login_required
@permission_required('social', 'comment')
def feed_updates():
    """Return newest posts after a timestamp (AJAX polling)."""
    since_raw = (request.args.get('since') or '').strip()
    if not since_raw:
        return ''

    if since_raw.endswith('Z'):
        since_raw = since_raw[:-1] + '+00:00'

    try:
        since_dt = datetime.fromisoformat(since_raw)
        if since_dt.tzinfo is not None:
            since_dt = since_dt.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return ''

    settings = SocialSetting.query.first()
    admin_access = check_permission(current_user, 'admin', 'access')
    scope_id = get_active_society_id(current_user)
    followed_ids = set()
    try:
        followed_ids = {u.id for u in current_user.followed.all()}
    except Exception:
        followed_ids = set()
    friend_ids = get_connection_ids(current_user)
    friend_ids -= followed_ids
    if current_user.id in friend_ids:
        friend_ids.remove(current_user.id)

    def is_visible(p: Post) -> bool:
        if admin_access:
            return True
        if p.user_id == current_user.id:
            return True
        if (p.audience or 'public') == 'public':
            return True
        if (p.audience or '') == 'direct' and p.target_user_id == current_user.id:
            return True
        if (p.audience or '') == 'society' and scope_id and p.society_id == scope_id:
            return True
        if (p.audience or '') == 'followers' and p.user_id in followed_ids:
            return True
        return False

    try:
        posts = (Post.query
                 .filter(Post.created_at > since_dt)
                 .options(joinedload(Post.author))
                 .all())
    except Exception:
        posts = []

    posts = [p for p in posts if is_visible(p)]
    posts = score_feed_posts(posts, current_user, followed_ids, friend_ids, settings)
    posts = posts[:20]

    if not posts:
        return ''

    return render_template('social/feed_partial.html', posts=posts)


@bp.route('/post/create', methods=['POST'])
@login_required
@permission_required('social', 'post')
@limiter.limit("10 per minute")
def create_post():
    """Create a new post"""
    form = PostForm()
    settings = SocialSetting.query.first()
    if settings and not settings.feed_enabled and not check_permission(current_user, 'admin', 'access'):
        flash('Pubblicazione disabilitata dall\'amministratore.', 'warning')
        return redirect(url_for('social.feed'))
    
    if form.validate_on_submit():
        has_media_file = form.image.data and hasattr(form.image.data, 'filename') and form.image.data.filename
        if has_media_file and settings:
            fname = (form.image.data.filename or '').lower()
            is_video = fname.endswith(('.mp4', '.mov', '.avi', '.webm', '.mkv'))
            is_photo = not is_video
            if is_photo and not getattr(settings, 'allow_photos', True):
                flash('La pubblicazione di foto è stata disabilitata dall\'amministratore.', 'warning')
                return redirect(url_for('social.feed'))
            if is_video and not getattr(settings, 'allow_videos', True):
                flash('La pubblicazione di video è stata disabilitata dall\'amministratore.', 'warning')
                return redirect(url_for('social.feed'))

        audience = 'public' if form.is_public.data else 'followers'
        society_id = None
        if current_user.is_society():
            audience = 'public' if form.is_public.data else 'society'
            try:
                society_id = get_active_society_id(current_user)
            except Exception:
                society_id = None

        post = Post(
            user_id=current_user.id,
            content=form.content.data,
            is_public=form.is_public.data,
            audience=audience,
            society_id=society_id,
            post_type='official' if current_user.is_society() else 'personal',
        )
        
        if form.image.data:
            image_file = save_picture(form.image.data, folder='posts', size=(800, 800))
            post.image = image_file
        
        db.session.add(post)
        db.session.commit()

        try:
            log_action(
                'post_create',
                'Post',
                post.id,
                f'post_type={post.post_type} audience={post.audience}',
                society_id=post.society_id,
            )
        except Exception:
            pass
        
        flash('Post pubblicato!', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{error}', 'danger')
    
    return redirect(url_for('social.feed'))


@bp.route('/post/<int:post_id>')
@login_required
@permission_required('social', 'comment')
def view_post(post_id):
    """View single post with comments"""
    post = Post.query.get_or_404(post_id)
    form = CommentForm()
    
    return render_template('social/view_post.html', post=post, form=form)


@bp.route('/post/<int:post_id>/promote', methods=['GET', 'POST'])
@login_required
@permission_required('social', 'post')
def promote_post(post_id):
    """Promote a post with paid insertion (simulated payment)"""
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id and not check_permission(current_user, 'admin', 'access'):
        flash('Puoi sponsorizzare solo i tuoi post.', 'danger')
        return redirect(url_for('social.view_post', post_id=post_id))

    def _safe_float(value, default):
        try:
            return float(value)
        except Exception:
            return float(default)

    def _safe_int(value, default):
        try:
            return int(value)
        except Exception:
            return int(default)

    try:
        settings = AdsSetting.query.first()
        if not settings:
            settings = AdsSetting()
            db.session.add(settings)
            db.session.commit()
    except Exception:
        db.session.rollback()
        if current_app:
            current_app.logger.exception('Ads settings load failed')
        flash('Impossibile caricare le impostazioni sponsorizzazione.', 'danger')
        return redirect(url_for('social.view_post', post_id=post_id))

    price_per_day = _safe_float(settings.price_per_day, 5.0)
    price_per_thousand_views = _safe_float(settings.price_per_thousand_views, 2.0)
    default_duration = _safe_int(settings.default_duration_days, 7)
    default_views = _safe_int(settings.default_views, 500)

    form = PromotePostForm()
    if form.validate_on_submit():
        duration = _safe_int(form.duration_days.data, default_duration)
        views = _safe_int(form.views.data, default_views)
        cost = price_per_day * duration + (price_per_thousand_views / 1000.0) * views

        # Simulate payment success
        try:
            payment = Payment(
                user_id=current_user.id,
                amount=cost,
                currency='EUR',
                status='completed',
                payment_method='manual',
                description=f'Promozione post {post.id}'
            )
            db.session.add(payment)

            post.is_promoted = True
            post.promotion_starts_at = datetime.utcnow()
            post.promotion_ends_at = datetime.utcnow() + timedelta(days=duration)
            post.promotion_views_target = views
            post.promotion_amount = cost
            post.promotion_views = 0

            db.session.commit()
        except Exception:
            db.session.rollback()
            if current_app:
                current_app.logger.exception('Promote post failed')
            flash('Impossibile attivare la sponsorizzazione in questo momento.', 'danger')
            return redirect(url_for('social.view_post', post_id=post_id))

        flash(f'Post sponsorizzato! Costo €{cost:.2f}', 'success')
        return redirect(url_for('social.view_post', post_id=post_id))

    # Prefill defaults
    if not form.duration_days.data:
        form.duration_days.data = default_duration
    if not form.views.data:
        form.views.data = default_views

    cost_preview = price_per_day * (form.duration_days.data or default_duration) + \
        (price_per_thousand_views / 1000.0) * (form.views.data or default_views)

    return render_template('social/promote.html', form=form, post=post, settings=settings, cost_preview=cost_preview)


@bp.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
@permission_required('social', 'comment')
def like_post(post_id):
    """Like/unlike a post (supports HTMX)"""
    post = Post.query.get_or_404(post_id)
    
    if post.is_liked_by(current_user):
        # Unlike
        post.liked_by.remove(current_user)
        post.likes_count = max(0, post.likes_count - 1)
        liked = False
    else:
        # Like
        post.liked_by.append(current_user)
        post.likes_count += 1
        liked = True
        
        # Create notification for post author
        if post.user_id != current_user.id:
            notification = Notification(
                user_id=post.user_id,
                title='Nuovo like',
                message=f'{current_user.get_full_name()} ha messo mi piace al tuo post',
                notification_type='social',
                link=url_for('social.view_post', post_id=post.id)
            )
            db.session.add(notification)
    
    db.session.commit()
    
    # HTMX Response
    if 'HX-Request' in request.headers:
        btn_class = 'btn-primary' if liked else 'btn-outline-primary'
        icon_class = 'bi-heart-fill' if liked else 'bi-heart'
        
        button_html = f"""
        <button class="btn btn-sm {btn_class}"
                hx-post="{url_for('social.like_post', post_id=post.id)}"
                hx-swap="outerHTML"
                hx-target="this">
            <i class="bi {icon_class}"></i>
            <span>{post.likes_count}</span>
        </button>
        """
        return button_html
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'liked': liked,
            'likes_count': post.likes_count
        })
    
    return redirect(request.referrer or url_for('social.feed'))


@bp.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
@permission_required('social', 'comment')
def comment_post(post_id):
    """Add comment to post"""
    post = Post.query.get_or_404(post_id)
    form = CommentForm()
    
    if form.validate_on_submit():
        comment = Comment(
            post_id=post.id,
            user_id=current_user.id,
            content=form.content.data
        )
        db.session.add(comment)
        
        # Update post comments count
        post.comments_count += 1
        
        # Create notification for post author
        if post.user_id != current_user.id:
            notification = Notification(
                user_id=post.user_id,
                title='Nuovo commento',
                message=f'{current_user.get_full_name()} ha commentato il tuo post',
                notification_type='social',
                link=url_for('social.view_post', post_id=post.id)
            )
            db.session.add(notification)
        
        db.session.commit()
        flash('Commento aggiunto!', 'success')
    
    return redirect(url_for('social.view_post', post_id=post_id))


@bp.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
@permission_required('social', 'post')
def delete_post(post_id):
    """Delete own post"""
    post = Post.query.get_or_404(post_id)
    
    # Check ownership or admin
    if post.user_id != current_user.id and not check_permission(current_user, 'admin', 'access'):
        flash('Non puoi eliminare questo post.', 'danger')
        return redirect(url_for('social.feed'))
    
    db.session.delete(post)
    db.session.commit()
    
    flash('Post eliminato.', 'success')
    return redirect(url_for('social.feed'))


@bp.route('/profile/<int:user_id>')
@login_required
def profile(user_id):
    """View user/society profile"""
    user = User.query.get_or_404(user_id)
    
    if user.is_admin() and current_user.id != user.id:
        flash('Questo profilo non è disponibile.', 'warning')
        return redirect(url_for('social.feed'))
    
    # Get user's posts
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    posts_query = Post.query.filter_by(user_id=user.id).order_by(Post.created_at.desc())
    pagination = posts_query.paginate(page=page, per_page=per_page, error_out=False)
    posts = pagination.items
    
    # Statistics
    stats = {
        'posts_count': Post.query.filter_by(user_id=user.id).count(),
        'followers_count': user.followers.count(),
        'following_count': user.followed.count()
    }
    
    # Check if current user follows this user
    is_following = current_user.is_following(user) if current_user.is_authenticated else False

    active_sid = None
    try:
        active_sid = get_active_society_id(current_user)
    except Exception:
        active_sid = None
    
    careers = Career.query.filter_by(user_id=user.id).order_by(Career.start_date.desc()).all()
    educations = Education.query.filter_by(user_id=user.id).order_by(Education.start_year.desc()).all()
    user_skills = Skill.query.filter_by(user_id=user.id).order_by(Skill.endorsement_count.desc()).all()
    
    connections_count = Connection.query.filter(
        ((Connection.requester_id == user.id) | (Connection.addressee_id == user.id)),
        Connection.status == 'accepted'
    ).count()
    
    connection_status = None
    if current_user.is_authenticated and current_user.id != user.id:
        conn = Connection.query.filter(
            ((Connection.requester_id == current_user.id) & (Connection.addressee_id == user.id)) |
            ((Connection.requester_id == user.id) & (Connection.addressee_id == current_user.id))
        ).first()
        if conn:
            if conn.status == 'accepted':
                connection_status = 'connected'
            elif conn.status == 'pending':
                connection_status = 'pending_sent' if conn.requester_id == current_user.id else 'pending_received'
    
    pending_connections = []
    if current_user.is_authenticated and current_user.id == user.id:
        pending_connections = Connection.query.filter_by(addressee_id=user.id, status='pending').all()
    
    return render_template('social/profile.html',
                         user=user,
                         posts=posts,
                         pagination=pagination,
                         stats=stats,
                         is_following=is_following,
                         active_society_id=active_sid,
                         careers=careers,
                         educations=educations,
                         user_skills=user_skills,
                         connections_count=connections_count,
                         connection_status=connection_status,
                         pending_connections=pending_connections)


@bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit own profile"""
    form = ProfileEditForm(obj=current_user)
    
    if form.validate_on_submit():
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.phone = form.phone.data
        current_user.bio = form.bio.data
        current_user.language = form.language.data
        
        if current_user.is_society():
            current_user.website = form.website.data
        
        # Handle avatar upload
        if form.avatar.data:
            avatar_file = save_picture(form.avatar.data, folder='avatars', size=(300, 300))
            current_user.avatar = avatar_file
        
        # Handle cover photo upload
        if form.cover_photo.data:
            cover_file = save_picture(form.cover_photo.data, folder='covers', size=(1200, 400))
            current_user.cover_photo = cover_file
        
        current_user.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash('Profilo aggiornato!', 'success')
        return redirect(url_for('social.profile', user_id=current_user.id))
    
    return render_template('social/edit_profile.html', form=form)


@bp.route('/profile/avatar', methods=['POST'])
@login_required
def upload_avatar():
    """Upload avatar image directly from profile page"""
    if 'avatar' not in request.files:
        flash('Nessun file selezionato.', 'warning')
        return redirect(url_for('social.profile', user_id=current_user.id))
    
    file = request.files['avatar']
    if file.filename == '':
        flash('Nessun file selezionato.', 'warning')
        return redirect(url_for('social.profile', user_id=current_user.id))
    
    if file:
        avatar_file = save_picture(file, folder='avatars', size=(300, 300))
        current_user.avatar = avatar_file
        current_user.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Immagine profilo aggiornata!', 'success')
    
    return redirect(url_for('social.profile', user_id=current_user.id))


@bp.route('/follow/<int:user_id>', methods=['POST'])
@login_required
def follow(user_id):
    """Follow a user/society"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('Non puoi seguire te stesso.', 'warning')
        return redirect(url_for('social.profile', user_id=user_id))
    
    if current_user.is_following(user):
        flash('Stai già seguendo questo utente.', 'info')
    else:
        current_user.follow(user)
        db.session.commit()
        
        # Create notification
        notification = Notification(
            user_id=user.id,
            title='Nuovo follower',
            message=f'{current_user.get_full_name()} ha iniziato a seguirti',
            notification_type='social',
            link=url_for('social.profile', user_id=current_user.id)
        )
        db.session.add(notification)
        db.session.commit()
        
        flash(f'Ora segui {user.get_full_name()}!', 'success')
    
    return redirect(request.referrer or url_for('social.profile', user_id=user_id))


@bp.route('/unfollow/<int:user_id>', methods=['POST'])
@login_required
def unfollow(user_id):
    """Unfollow a user/society"""
    user = User.query.get_or_404(user_id)
    
    if not current_user.is_following(user):
        flash('Non stai seguendo questo utente.', 'info')
    else:
        current_user.unfollow(user)
        db.session.commit()
        flash(f'Hai smesso di seguire {user.get_full_name()}.', 'success')
    
    return redirect(request.referrer or url_for('social.profile', user_id=user_id))


@bp.route('/followers/<int:user_id>')
@login_required
def followers(user_id):
    """View user's followers"""
    user = User.query.get_or_404(user_id)
    
    page = request.args.get('page', 1, type=int)
    per_page = 30
    
    pagination = user.followers.paginate(page=page, per_page=per_page, error_out=False)
    followers = pagination.items
    
    return render_template('social/followers.html',
                         user=user,
                         followers=followers,
                         pagination=pagination)


@bp.route('/following/<int:user_id>')
@login_required
def following(user_id):
    """View users that this user follows"""
    user = User.query.get_or_404(user_id)
    
    page = request.args.get('page', 1, type=int)
    per_page = 30
    
    pagination = user.followed.paginate(page=page, per_page=per_page, error_out=False)
    following = pagination.items
    
    return render_template('social/following.html',
                         user=user,
                         following=following,
                         pagination=pagination)


@bp.route('/search')
@login_required
def search():
    """Search for users and societies"""
    form = SearchForm(request.args, meta={'csrf': False})
    
    page = request.args.get('page', 1, type=int)
    per_page = 30
    
    query = form.query.data or ''
    
    if query:
        search = f"%{query}%"
        users_query = User.query.filter(
            or_(
                User.username.ilike(search),
                User.first_name.ilike(search),
                User.last_name.ilike(search),
                User.company_name.ilike(search)
            )
        ).filter_by(is_active=True)
    else:
        users_query = User.query.filter_by(is_active=True)
    
    from app.models import Role
    super_admin_role = Role.query.filter_by(name='super_admin').first()
    if super_admin_role and not current_user.is_admin():
        users_query = users_query.filter(User.role_id != super_admin_role.id)
    
    pagination = users_query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    users = pagination.items
    
    return render_template('social/search.html',
                         users=users,
                         pagination=pagination,
                         form=form,
                         query=query)


@bp.route('/society/dashboard')
@login_required
def society_dashboard():
    """Dashboard for societies"""
    if not check_permission(current_user, 'society', 'manage'):
        flash('Accesso riservato alle società.', 'warning')
        return redirect(url_for('social.feed'))
    society = current_user.get_primary_society()
    if not society:
        flash('Profilo società non trovato.', 'warning')
        return redirect(url_for('social.feed'))
    
    # Get society's staff and athletes (canonical: SocietyMembership)
    try:
        staff_memberships = (
            SocietyMembership.query.filter_by(society_id=society.id, status='active')
            .filter(SocietyMembership.role_name.in_(['staff', 'coach', 'dirigente']))
            .options(joinedload(SocietyMembership.user))
            .all()
        )
        athlete_memberships = (
            SocietyMembership.query.filter_by(society_id=society.id, status='active')
            .filter(SocietyMembership.role_name.in_(['atleta', 'athlete']))
            .options(joinedload(SocietyMembership.user))
            .all()
        )
        staff = [m.user for m in staff_memberships if m.user]
        athletes = [m.user for m in athlete_memberships if m.user]
    except Exception:
        staff = []
        athletes = []
    
    # Get society's events
    from app.models import Event
    events = Event.query.filter_by(
        creator_id=current_user.id
    ).order_by(Event.start_date.desc()).limit(10).all()
    
    # Statistics
    stats = {
        'followers_count': current_user.followers.count(),
        'staff_count': len(staff),
        'athletes_count': len(athletes),
        'events_count': Event.query.filter_by(creator_id=current_user.id).count(),
        'posts_count': Post.query.filter_by(user_id=current_user.id).count()
    }
    
    # Pending invites
    invites = SocietyInvite.query.filter_by(society_id=society.id, status='pending').order_by(SocietyInvite.created_at.desc()).all()
    # Memberships (canonical)
    memberships = SocietyMembership.query.filter_by(society_id=society.id, status='active').order_by(SocietyMembership.created_at.desc()).all()

    # Audit logs scoped to this society
    recent_audit = AuditLog.query.filter_by(society_id=society.id).order_by(AuditLog.created_at.desc()).limit(20).all()

    # Retention / onboarding / next-best-actions
    health = SocietyHealthSnapshot.query.filter_by(society_id=society.id).order_by(SocietyHealthSnapshot.created_at.desc()).first()

    dismissed = SocietySuggestionDismissal.query.filter_by(society_id=society.id, user_id=current_user.id).all()
    dismissed_keys = {d.key for d in dismissed}

    member_count = SocietyMembership.query.filter_by(society_id=society.id, status='active').count()
    calendar_count = SocietyCalendarEvent.query.filter_by(society_id=society.id).count()
    society_posts_count = Post.query.filter_by(society_id=society.id).count()

    suggestions = []
    def _suggest(key: str, title: str, body: str, action_url: str | None = None):
        if key in dismissed_keys:
            return
        suggestions.append({"key": key, "title": title, "body": body, "action_url": action_url})

    if member_count < 5:
        _suggest("invite_members", "Invita membri", "Aggiungi staff/atleti per far partire il lavoro reale della società.", url_for('social.society_dashboard'))
    if calendar_count == 0:
        _suggest("create_calendar_event", "Crea il primo evento nel planner", "Il calendario è il cuore operativo: crea un allenamento o una partita.", url_for('calendar.create'))
    if member_count < 3:
        _suggest("add_crm_member", "Aggiungi membri al CRM", "Gestisci i membri della società con il nuovo modulo CRM.", url_for('crm.members'))
    if society_posts_count == 0:
        _suggest("publish_society_post", "Pubblica un comunicato", "Usa il social per comunicazioni ufficiali verso la società/atleti.", url_for('social.feed'))
    # Onboarding checklist (hybrid: some auto-detected, some manual)
    step_defs = [
        {"key": "invite_one_member", "label": "Invita almeno 1 membro", "auto": member_count >= 2},
        {"key": "create_one_calendar_event", "label": "Crea 1 evento nel calendario", "auto": calendar_count >= 1},
        {"key": "add_crm_members", "label": "Aggiungi membri al CRM", "auto": member_count >= 3},
        {"key": "publish_one_post", "label": "Pubblica 1 post/comunicato", "auto": society_posts_count >= 1},
        {"key": "review_permissions", "label": "Rivedi permessi ruoli", "auto": False},
    ]
    stored_steps = UserOnboardingStep.query.filter_by(society_id=society.id, user_id=current_user.id).all()
    stored_keys = {s.step_key for s in stored_steps}
    onboarding = []
    completed_count = 0
    for sd in step_defs:
        done = bool(sd["auto"]) or (sd["key"] in stored_keys)
        if done:
            completed_count += 1
        onboarding.append({"key": sd["key"], "label": sd["label"], "done": done, "manual": not bool(sd["auto"])})
    onboarding_progress = int((completed_count / max(1, len(step_defs))) * 100)

    invite_form = SocietyInviteForm()

    return render_template(
        'social/society_dashboard.html',
        staff=staff,
        athletes=athletes,
        events=events,
        stats=stats,
        invites=invites,
        memberships=memberships,
        recent_audit=recent_audit,
        invite_form=invite_form,
        health=health,
        suggestions=suggestions,
        onboarding=onboarding,
        onboarding_progress=onboarding_progress,
    )


@bp.route('/society/audit/export.csv')
@login_required
def society_audit_export():
    """Enterprise: export society audit logs as CSV."""
    from flask import Response
    import io
    import csv

    if not check_permission(current_user, 'society', 'manage'):
        abort(403)
    if not current_user.has_feature('enterprise_pack'):
        flash('Questa funzione richiede Enterprise Pack.', 'warning')
        return redirect(url_for('subscription.addons'))
    society = current_user.get_primary_society()
    if not society:
        abort(404)

    logs = AuditLog.query.filter_by(society_id=society.id).order_by(AuditLog.created_at.desc()).limit(2000).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['created_at', 'user_id', 'action', 'entity_type', 'entity_id', 'details', 'ip'])
    for l in logs:
        w.writerow([
            l.created_at.isoformat() if l.created_at else '',
            l.user_id or '',
            l.action or '',
            l.entity_type or '',
            l.entity_id or '',
            (l.details or '').replace('\n', ' ')[:2000],
            l.ip_address or '',
        ])
    out = buf.getvalue()
    return Response(out, mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename="audit_society.csv"'})


@bp.route('/society/export-data')
@login_required
def society_export_data():
    """Society admin can download their own society data as CSV."""
    import csv as csv_mod
    import io as io_mod
    from flask import make_response as mk_resp
    from app.models import SocietyMembership, SocietyCalendarEvent, Event

    if not check_permission(current_user, 'society', 'manage'):
        flash('Accesso riservato alle società.', 'warning')
        return redirect(url_for('social.feed'))
    society = current_user.get_primary_society()
    if not society:
        flash('Società non trovata.', 'warning')
        return redirect(url_for('social.feed'))

    output = io_mod.StringIO()
    writer = csv_mod.writer(output)

    writer.writerow([f'=== DATI SOCIETÀ: {society.name} ==='])
    writer.writerow(['Campo', 'Valore'])
    writer.writerow(['Nome', society.name or ''])
    writer.writerow(['Email', getattr(society, 'email', '') or ''])
    writer.writerow(['Telefono', getattr(society, 'phone', '') or ''])
    writer.writerow(['Indirizzo', getattr(society, 'address', '') or ''])
    writer.writerow(['Città', getattr(society, 'city', '') or ''])
    writer.writerow(['Sport', getattr(society, 'sport', '') or ''])
    writer.writerow(['Codice Fiscale', getattr(society, 'fiscal_code', '') or ''])
    writer.writerow(['P.IVA', getattr(society, 'vat_number', '') or ''])
    writer.writerow([])

    writer.writerow(['=== MEMBRI ==='])
    writer.writerow(['ID', 'Nome', 'Email', 'Telefono', 'Ruolo Membro', 'Data Iscrizione'])
    members = SocietyMembership.query.filter_by(society_id=society.id, status='active').all()
    for m in members:
        user = User.query.get(m.user_id)
        if user:
            writer.writerow([
                user.id, user.get_full_name(), user.email,
                user.phone or '', getattr(m, 'role_name', '') or '',
                m.created_at.strftime('%Y-%m-%d') if m.created_at else ''
            ])
    writer.writerow([])

    writer.writerow(['=== EVENTI SOCIETÀ ==='])
    writer.writerow(['ID', 'Titolo', 'Data Inizio', 'Data Fine', 'Luogo'])
    cal_events = SocietyCalendarEvent.query.filter_by(society_id=society.id).order_by(SocietyCalendarEvent.id.desc()).all()
    for e in cal_events:
        writer.writerow([
            e.id, getattr(e, 'title', '') or '',
            e.start_time.strftime('%Y-%m-%d %H:%M') if getattr(e, 'start_time', None) else '',
            e.end_time.strftime('%Y-%m-%d %H:%M') if getattr(e, 'end_time', None) else '',
            getattr(e, 'location', '') or ''
        ])
    writer.writerow([])

    writer.writerow(['=== POST SOCIETÀ ==='])
    writer.writerow(['ID', 'Contenuto', 'Data', 'Like', 'Commenti'])
    posts = Post.query.filter_by(society_id=society.id).order_by(Post.created_at.desc()).limit(500).all()
    for p in posts:
        writer.writerow([
            p.id,
            (p.content or '')[:200].replace('\n', ' '),
            p.created_at.strftime('%Y-%m-%d %H:%M') if p.created_at else '',
            p.likes.count() if hasattr(p, 'likes') else 0,
            p.comments.count() if hasattr(p, 'comments') else 0,
        ])

    resp = mk_resp(output.getvalue())
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    safe_name = (society.name or 'societa').replace(' ', '_').lower()[:30]
    resp.headers['Content-Disposition'] = f'attachment; filename=dati_{safe_name}_{datetime.utcnow().strftime("%Y%m%d")}.csv'
    try:
        log_action('society_export_data', 'Society', society.id, f'Society exported own data')
    except Exception:
        pass
    return resp


@bp.route('/society/suggestions/<string:key>/dismiss', methods=['POST'])
@login_required
def society_dismiss_suggestion(key: str):
    if not check_permission(current_user, 'society', 'manage'):
        abort(403)
    society = current_user.get_primary_society()
    if not society:
        abort(404)
    key = (key or "").strip()
    if not key or len(key) > 120:
        return redirect(url_for('social.society_dashboard'))
    existing = SocietySuggestionDismissal.query.filter_by(society_id=society.id, user_id=current_user.id, key=key).first()
    if not existing:
        db.session.add(SocietySuggestionDismissal(society_id=society.id, user_id=current_user.id, key=key, dismissed_at=datetime.utcnow()))
        db.session.commit()
    return redirect(url_for('social.society_dashboard'))


@bp.route('/society/onboarding/<string:step_key>/complete', methods=['POST'])
@login_required
def society_onboarding_complete(step_key: str):
    if not check_permission(current_user, 'society', 'manage'):
        abort(403)
    society = current_user.get_primary_society()
    if not society:
        abort(404)
    step_key = (step_key or "").strip()
    if not step_key or len(step_key) > 80:
        return redirect(url_for('social.society_dashboard'))
    existing = UserOnboardingStep.query.filter_by(society_id=society.id, user_id=current_user.id, step_key=step_key).first()
    if not existing:
        db.session.add(UserOnboardingStep(society_id=society.id, user_id=current_user.id, step_key=step_key, completed_at=datetime.utcnow()))
        db.session.commit()
    return redirect(url_for('social.society_dashboard'))


@bp.route('/society/invite', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def society_invite():
    """Society invites a user to join with a specific role."""
    if not check_permission(current_user, 'society', 'manage'):
        flash('Accesso riservato alle società.', 'warning')
        return redirect(url_for('social.feed'))
    society = current_user.get_primary_society()
    if not society:
        flash('Profilo società non trovato.', 'warning')
        return redirect(url_for('social.feed'))

    form = SocietyInviteForm()
    if not form.validate_on_submit():
        flash('Dati invito non validi.', 'danger')
        return redirect(url_for('social.society_dashboard'))

    q = (form.user_query.data or '').strip()
    user = User.query.filter((User.email == q) | (User.username == q)).first()
    if not user:
        flash('Utente non trovato.', 'warning')
        return redirect(url_for('social.society_dashboard'))
    if user.id == current_user.id:
        flash('Non puoi invitare te stesso.', 'warning')
        return redirect(url_for('social.society_dashboard'))

    # Create invite
    existing = SocietyInvite.query.filter_by(society_id=society.id, invited_user_id=user.id, status='pending').first()
    if existing:
        flash('Invito già inviato (in attesa).', 'info')
        return redirect(url_for('social.society_dashboard'))

    inv = SocietyInvite(
        society_id=society.id,
        invited_user_id=user.id,
        invited_by=current_user.id,
        requested_role=form.requested_role.data,
        status='pending',
        note=form.note.data or None,
    )
    db.session.add(inv)

    notif = Notification(
        user_id=user.id,
        title='Invito da società',
        message=f'{current_user.get_full_name()} ti ha invitato come {form.requested_role.data}.',
        notification_type='system',
        link=url_for('social.my_invites'),
    )
    db.session.add(notif)
    db.session.commit()

    log_action('society_invite', 'SocietyInvite', inv.id, f'Invited {user.id} role={inv.requested_role}', society_id=society.id)
    flash('Invito inviato.', 'success')
    return redirect(url_for('social.society_dashboard'))


@bp.route('/society/permissions', methods=['GET', 'POST'])
@login_required
def society_permissions():
    """Manage society-scoped role permissions (view/edit powers per role)."""
    if not check_permission(current_user, 'society', 'manage'):
        flash('Accesso riservato alle società.', 'warning')
        return redirect(url_for('social.feed'))
    society = current_user.get_primary_society()
    if not society:
        flash('Profilo società non trovato.', 'warning')
        return redirect(url_for('social.feed'))

    managed_roles = ['dirigente', 'coach', 'staff', 'atleta']
    managed_perms = Permission.query.filter(
        Permission.resource.in_(['social', 'events', 'calendar', 'crm', 'tasks', 'tournaments', 'society', 'users'])
    ).order_by(Permission.resource.asc(), Permission.action.asc()).all()

    if request.method == 'POST':
        # Parse tri-state selects: inherit/allow/deny
        changed = 0
        for role_name in managed_roles:
            for perm in managed_perms:
                key = f"p__{role_name}__{perm.id}"
                if key not in request.form:
                    continue
                val = (request.form.get(key) or 'inherit').strip()
                row = SocietyRolePermission.query.filter_by(
                    society_id=society.id, role_name=role_name, permission_id=perm.id
                ).first()
                if val == 'inherit':
                    if row:
                        db.session.delete(row)
                        changed += 1
                    continue
                if val not in ('allow', 'deny'):
                    continue
                if not row:
                    row = SocietyRolePermission(
                        society_id=society.id,
                        role_name=role_name,
                        permission_id=perm.id,
                        effect=val,
                        created_by=current_user.id,
                    )
                    db.session.add(row)
                    changed += 1
                else:
                    if row.effect != val:
                        row.effect = val
                        changed += 1

        db.session.commit()
        log_action('society_permissions_update', 'Society', society.id, f'Changed={changed}', society_id=society.id)
        flash('Permessi aggiornati.', 'success')
        return redirect(url_for('social.society_permissions'))

    overrides = SocietyRolePermission.query.filter_by(society_id=society.id).all()
    override_map = {(o.role_name, o.permission_id): o.effect for o in overrides}

    return render_template(
        'social/society_permissions.html',
        society=society,
        roles=managed_roles,
        permissions=managed_perms,
        override_map=override_map,
    )


@bp.route('/society/members/<int:user_id>/set-role', methods=['POST'])
@login_required
def society_set_member_role(user_id):
    """Change a member role within the current society."""
    if not check_permission(current_user, 'society', 'manage_staff'):
        flash('Permesso negato.', 'danger')
        return redirect(url_for('social.society_dashboard'))
    society = current_user.get_primary_society()
    if not society:
        flash('Profilo società non trovato.', 'warning')
        return redirect(url_for('social.society_dashboard'))

    role_name = (request.form.get('role_name') or '').strip()
    if role_name not in ('atleta', 'coach', 'staff', 'dirigente'):
        flash('Ruolo non valido.', 'danger')
        return redirect(url_for('social.society_dashboard'))

    membership = SocietyMembership.query.filter_by(society_id=society.id, user_id=user_id, status='active').first()
    if not membership:
        flash('Membro non trovato.', 'warning')
        return redirect(url_for('social.society_dashboard'))

    member = User.query.get_or_404(user_id)
    membership.role_name = role_name
    membership.updated_by = current_user.id

    # Keep legacy linkages aligned for now (until full migration off legacy fields)
    if role_name == 'atleta':
        member.role = 'atleta'
        member.athlete_society_id = society.id
        member.society_id = None
        member.staff_role = None
    elif role_name == 'coach':
        member.role = 'coach'
        member.society_id = society.id
        member.athlete_society_id = None
        member.staff_role = 'coach'
    elif role_name == 'dirigente':
        member.role = 'staff'
        member.society_id = society.id
        member.athlete_society_id = None
        member.staff_role = 'dirigente'
    else:
        member.role = 'staff'
        member.society_id = society.id
        member.athlete_society_id = None
        member.staff_role = 'staff'

    db.session.commit()
    log_action('society_member_role_change', 'User', member.id, f'role={role_name}', society_id=society.id)
    flash('Ruolo aggiornato.', 'success')
    return redirect(url_for('social.society_dashboard'))


@bp.route('/society/members/<int:user_id>/remove', methods=['POST'])
@login_required
def society_remove_member(user_id):
    """Remove/deactivate a member from the current society."""
    if not check_permission(current_user, 'society', 'manage_staff'):
        flash('Permesso negato.', 'danger')
        return redirect(url_for('social.society_dashboard'))
    society = current_user.get_primary_society()
    if not society:
        flash('Profilo società non trovato.', 'warning')
        return redirect(url_for('social.society_dashboard'))

    membership = SocietyMembership.query.filter_by(society_id=society.id, user_id=user_id, status='active').first()
    if not membership:
        flash('Membro non trovato.', 'warning')
        return redirect(url_for('social.society_dashboard'))

    member = User.query.get_or_404(user_id)
    membership.status = 'inactive'
    membership.updated_by = current_user.id

    # Clear legacy links if they match this society
    if member.society_id == society.id:
        member.society_id = None
    if member.athlete_society_id == society.id:
        member.athlete_society_id = None
    member.staff_role = None

    # If the user has no other active memberships, revert to appassionato
    still_active = SocietyMembership.query.filter(
        SocietyMembership.user_id == member.id,
        SocietyMembership.status == 'active',
    ).count()
    if still_active == 0 and not member.is_society():
        member.role = 'appassionato'

    db.session.add(
        Notification(
            user_id=member.id,
            title='Rimozione da società',
            message=f'Sei stato rimosso dalla società {society.legal_name}.',
            notification_type='system',
            link=url_for('main.dashboard'),
        )
    )

    db.session.commit()
    log_action('society_member_remove', 'User', member.id, 'removed', society_id=society.id)
    flash('Membro rimosso.', 'success')
    return redirect(url_for('social.society_dashboard'))


@bp.route('/invites')
@login_required
def my_invites():
    """List invites received by the current user."""
    invites = SocietyInvite.query.filter_by(invited_user_id=current_user.id, status='pending').order_by(SocietyInvite.created_at.desc()).all()
    return render_template('social/invites.html', invites=invites)


@bp.route('/invites/<int:invite_id>/<string:action>', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def respond_invite(invite_id, action):
    """Accept/reject an invite."""
    inv = SocietyInvite.query.get_or_404(invite_id)
    if inv.invited_user_id != current_user.id:
        flash('Invito non valido.', 'danger')
        return redirect(url_for('social.my_invites'))

    if action not in ('accept', 'reject'):
        flash('Azione non valida.', 'danger')
        return redirect(url_for('social.my_invites'))

    if inv.status != 'pending':
        flash('Invito già gestito.', 'info')
        return redirect(url_for('social.my_invites'))

    society_id = inv.society_id

    if action == 'reject':
        inv.status = 'rejected'
        inv.responded_at = datetime.utcnow()
        db.session.commit()
        log_action('society_invite_reject', 'SocietyInvite', inv.id, f'Rejected invite role={inv.requested_role}', society_id=society_id)
        flash('Invito rifiutato.', 'success')
        return redirect(url_for('social.my_invites'))

    # Accept: activate membership + update user role fields
    requested = inv.requested_role
    membership = SocietyMembership.query.filter_by(society_id=society_id, user_id=current_user.id).first()
    if not membership:
        membership = SocietyMembership(
            society_id=society_id,
            user_id=current_user.id,
            role_name=requested,
            status='active',
            created_by=inv.invited_by,
        )
        db.session.add(membership)
    else:
        membership.role_name = requested
        membership.status = 'active'
        membership.updated_by = inv.invited_by

    # Update the user's primary role + society linkage
    if requested == 'atleta':
        current_user.role = 'atleta'
        current_user.athlete_society_id = society_id
        current_user.society_id = None
        current_user.staff_role = None
    elif requested == 'coach':
        current_user.role = 'coach'
        current_user.society_id = society_id
        current_user.athlete_society_id = None
        current_user.staff_role = 'coach'
    elif requested == 'dirigente':
        current_user.role = 'staff'
        current_user.society_id = society_id
        current_user.athlete_society_id = None
        current_user.staff_role = 'dirigente'
    else:  # staff
        current_user.role = 'staff'
        current_user.society_id = society_id
        current_user.athlete_society_id = None
        current_user.staff_role = 'staff'

    inv.status = 'accepted'
    inv.responded_at = datetime.utcnow()
    db.session.commit()

    log_action('society_invite_accept', 'SocietyInvite', inv.id, f'Accepted invite role={requested}', society_id=society_id)
    flash('Invito accettato. Ruolo aggiornato.', 'success')
    return redirect(url_for('main.dashboard'))


@bp.route('/explore')
@login_required
def explore():
    """Explore page - discover societies and users"""
    # Get top societies by followers
    societies = User.query.filter(
        User.role.in_(['societa', 'society_admin']),
        User.is_active == True
    ).all()
    societies = sorted(societies, key=lambda u: u.followers.count(), reverse=True)[:20]
    
    # Get recent posts
    recent_posts = Post.query.filter_by(is_public=True).order_by(
        Post.created_at.desc()
    ).limit(10).all()
    
    return render_template('social/explore.html',
                         societies=societies,
                         recent_posts=recent_posts)


@bp.route('/career/add', methods=['GET', 'POST'])
@login_required
def add_career():
    """Add career experience"""
    if request.method == 'POST':
        career = Career(
            user_id=current_user.id,
            title=request.form.get('title'),
            company=request.form.get('company'),
            location=request.form.get('location'),
            employment_type=request.form.get('employment_type'),
            start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date(),
            end_date=datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date() if request.form.get('end_date') else None,
            is_current=bool(request.form.get('is_current')),
            description=request.form.get('description')
        )
        db.session.add(career)
        db.session.commit()
        flash('Esperienza aggiunta con successo!', 'success')
        return redirect(url_for('social.profile', user_id=current_user.id))
    return render_template('social/career_form.html', career=None)


@bp.route('/career/<int:career_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_career(career_id):
    """Edit career experience"""
    career = Career.query.get_or_404(career_id)
    if career.user_id != current_user.id:
        flash('Non autorizzato.', 'danger')
        return redirect(url_for('social.profile', user_id=current_user.id))
    
    if request.method == 'POST':
        career.title = request.form.get('title')
        career.company = request.form.get('company')
        career.location = request.form.get('location')
        career.employment_type = request.form.get('employment_type')
        career.start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        career.end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date() if request.form.get('end_date') else None
        career.is_current = bool(request.form.get('is_current'))
        career.description = request.form.get('description')
        db.session.commit()
        flash('Esperienza aggiornata!', 'success')
        return redirect(url_for('social.profile', user_id=current_user.id))
    return render_template('social/career_form.html', career=career)


@bp.route('/career/<int:career_id>/delete', methods=['POST'])
@login_required
def delete_career(career_id):
    """Delete career experience"""
    career = Career.query.get_or_404(career_id)
    if career.user_id != current_user.id:
        flash('Non autorizzato.', 'danger')
        return redirect(url_for('social.profile', user_id=current_user.id))
    
    db.session.delete(career)
    db.session.commit()
    flash('Esperienza eliminata.', 'success')
    return redirect(url_for('social.profile', user_id=current_user.id))


@bp.route('/education/add', methods=['GET', 'POST'])
@login_required
def add_education():
    """Add education"""
    if request.method == 'POST':
        edu = Education(
            user_id=current_user.id,
            school=request.form.get('school'),
            degree=request.form.get('degree'),
            field_of_study=request.form.get('field_of_study'),
            start_year=int(request.form.get('start_year')) if request.form.get('start_year') else None,
            end_year=int(request.form.get('end_year')) if request.form.get('end_year') else None,
            description=request.form.get('description')
        )
        db.session.add(edu)
        db.session.commit()
        flash('Formazione aggiunta con successo!', 'success')
        return redirect(url_for('social.profile', user_id=current_user.id))
    return render_template('social/education_form.html', education=None)


@bp.route('/education/<int:education_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_education(education_id):
    """Edit education"""
    edu = Education.query.get_or_404(education_id)
    if edu.user_id != current_user.id:
        flash('Non autorizzato.', 'danger')
        return redirect(url_for('social.profile', user_id=current_user.id))
    
    if request.method == 'POST':
        edu.school = request.form.get('school')
        edu.degree = request.form.get('degree')
        edu.field_of_study = request.form.get('field_of_study')
        edu.start_year = int(request.form.get('start_year')) if request.form.get('start_year') else None
        edu.end_year = int(request.form.get('end_year')) if request.form.get('end_year') else None
        edu.description = request.form.get('description')
        db.session.commit()
        flash('Formazione aggiornata!', 'success')
        return redirect(url_for('social.profile', user_id=current_user.id))
    return render_template('social/education_form.html', education=edu)


@bp.route('/education/<int:education_id>/delete', methods=['POST'])
@login_required
def delete_education(education_id):
    """Delete education"""
    edu = Education.query.get_or_404(education_id)
    if edu.user_id != current_user.id:
        flash('Non autorizzato.', 'danger')
        return redirect(url_for('social.profile', user_id=current_user.id))
    
    db.session.delete(edu)
    db.session.commit()
    flash('Formazione eliminata.', 'success')
    return redirect(url_for('social.profile', user_id=current_user.id))


@bp.route('/skill/add', methods=['GET', 'POST'])
@login_required
def add_skill():
    """Add skill"""
    if request.method == 'POST':
        skill = Skill(
            user_id=current_user.id,
            name=request.form.get('name'),
            category=request.form.get('category')
        )
        db.session.add(skill)
        db.session.commit()
        flash('Competenza aggiunta!', 'success')
        return redirect(url_for('social.profile', user_id=current_user.id))
    return render_template('social/skill_form.html')


@bp.route('/skill/<int:skill_id>/endorse', methods=['POST'])
@login_required
def endorse_skill(skill_id):
    """Endorse a skill"""
    skill = Skill.query.get_or_404(skill_id)
    if skill.user_id == current_user.id:
        flash('Non puoi confermare le tue competenze.', 'warning')
        return redirect(url_for('social.profile', user_id=skill.user_id))
    
    existing = SkillEndorsement.query.filter_by(skill_id=skill_id, endorsed_by_id=current_user.id).first()
    if existing:
        flash('Hai già confermato questa competenza.', 'info')
        return redirect(url_for('social.profile', user_id=skill.user_id))
    
    endorsement = SkillEndorsement(skill_id=skill_id, endorsed_by_id=current_user.id)
    skill.endorsement_count += 1
    db.session.add(endorsement)
    db.session.commit()
    flash('Competenza confermata!', 'success')
    return redirect(url_for('social.profile', user_id=skill.user_id))


@bp.route('/connection/send/<int:user_id>', methods=['POST'])
@login_required
def send_connection(user_id):
    """Send connection request"""
    if user_id == current_user.id:
        flash('Non puoi collegarti a te stesso.', 'warning')
        return redirect(url_for('social.profile', user_id=user_id))
    
    existing = Connection.query.filter(
        ((Connection.requester_id == current_user.id) & (Connection.addressee_id == user_id)) |
        ((Connection.requester_id == user_id) & (Connection.addressee_id == current_user.id))
    ).first()
    
    if existing:
        flash('Richiesta di collegamento già esistente.', 'info')
        return redirect(url_for('social.profile', user_id=user_id))
    
    conn = Connection(
        requester_id=current_user.id,
        addressee_id=user_id,
        status='pending'
    )
    db.session.add(conn)
    
    notif = Notification(
        user_id=user_id,
        type='connection_request',
        title='Nuova richiesta di collegamento',
        message=f'{current_user.get_full_name()} vuole collegarsi con te',
        link=url_for('social.profile', user_id=current_user.id)
    )
    db.session.add(notif)
    db.session.commit()
    
    flash('Richiesta di collegamento inviata!', 'success')
    return redirect(url_for('social.profile', user_id=user_id))


@bp.route('/connection/accept/<int:user_id>', methods=['POST'])
@login_required
def accept_connection(user_id):
    """Accept connection request"""
    conn = Connection.query.filter_by(requester_id=user_id, addressee_id=current_user.id, status='pending').first()
    if not conn:
        flash('Richiesta non trovata.', 'warning')
        return redirect(url_for('social.profile', user_id=current_user.id))
    
    conn.status = 'accepted'
    conn.updated_at = datetime.utcnow()
    
    notif = Notification(
        user_id=user_id,
        type='connection_accepted',
        title='Collegamento accettato',
        message=f'{current_user.get_full_name()} ha accettato la tua richiesta di collegamento',
        link=url_for('social.profile', user_id=current_user.id)
    )
    db.session.add(notif)
    db.session.commit()
    
    flash('Collegamento accettato!', 'success')
    return redirect(url_for('social.profile', user_id=current_user.id))


@bp.route('/connection/reject/<int:user_id>', methods=['POST'])
@login_required
def reject_connection(user_id):
    """Reject connection request"""
    conn = Connection.query.filter_by(requester_id=user_id, addressee_id=current_user.id, status='pending').first()
    if not conn:
        flash('Richiesta non trovata.', 'warning')
        return redirect(url_for('social.profile', user_id=current_user.id))
    
    conn.status = 'rejected'
    conn.updated_at = datetime.utcnow()
    db.session.commit()
    
    flash('Richiesta ignorata.', 'info')
    return redirect(url_for('social.profile', user_id=current_user.id))


@bp.route('/connections/<int:user_id>')
@login_required
def connections_list(user_id):
    """View user's connections"""
    user = User.query.get_or_404(user_id)
    connections = Connection.query.filter(
        ((Connection.requester_id == user.id) | (Connection.addressee_id == user.id)),
        Connection.status == 'accepted'
    ).all()
    
    connected_users = []
    for conn in connections:
        if conn.requester_id == user.id:
            connected_user = User.query.get(conn.addressee_id)
        else:
            connected_user = User.query.get(conn.requester_id)
        if connected_user and not (connected_user.is_admin() and not current_user.is_admin()):
            connected_users.append(connected_user)
    
    return render_template('social/connections.html', user=user, connections=connected_users)


@bp.route('/user/<int:user_id>/posts')
@login_required
def user_posts(user_id):
    """View all posts from a user"""
    user = User.query.get_or_404(user_id)
    page = request.args.get('page', 1, type=int)
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('social/user_posts.html', user=user, posts=posts.items, pagination=posts)


@bp.route('/society/broadcasts')
@login_required
def society_broadcasts():
    if not check_permission(current_user, 'society', 'manage'):
        flash('Accesso riservato alle società.', 'warning')
        return redirect(url_for('social.feed'))
    society = current_user.get_primary_society()
    if not society:
        flash('Profilo società non trovato.', 'warning')
        return redirect(url_for('social.feed'))

    page = request.args.get('page', 1, type=int)
    pagination = BroadcastMessage.query.filter_by(scope_type='society', society_id=society.id)\
        .order_by(BroadcastMessage.created_at.desc())\
        .paginate(page=page, per_page=20, error_out=False)
    total = BroadcastMessage.query.filter_by(scope_type='society', society_id=society.id).count()
    total_sent = BroadcastMessage.query.filter_by(scope_type='society', society_id=society.id, status='sent').count()

    member_count = SocietyMembership.query.filter_by(society_id=society.id, status='active').count()

    return render_template('social/society_broadcasts.html', broadcasts=pagination.items,
                           pagination=pagination, society=society,
                           total=total, total_sent=total_sent, member_count=member_count)


@bp.route('/society/broadcasts/compose', methods=['GET', 'POST'])
@login_required
def society_broadcast_compose():
    if not check_permission(current_user, 'society', 'manage'):
        flash('Accesso riservato alle società.', 'warning')
        return redirect(url_for('social.feed'))
    society = current_user.get_primary_society()
    if not society:
        flash('Profilo società non trovato.', 'warning')
        return redirect(url_for('social.feed'))

    membership_roles = ['atleta', 'coach', 'staff', 'dirigente', 'appassionato']

    if request.method == 'POST':
        subject = (request.form.get('subject') or '').strip()
        body = (request.form.get('body') or '').strip()
        selected_roles = request.form.getlist('target_roles')
        send_email = bool(request.form.get('send_email'))

        if not subject or not body:
            flash('Oggetto e messaggio sono obbligatori.', 'danger')
            return render_template('social/society_broadcast_compose.html',
                                   society=society, membership_roles=membership_roles,
                                   subject=subject, body=body, selected_roles=selected_roles)

        broadcast = BroadcastMessage(
            sender_id=current_user.id,
            scope_type='society',
            society_id=society.id,
            subject=subject,
            body=body,
            target_roles=','.join(selected_roles) if selected_roles else None,
            send_email=send_email,
            status='draft',
        )
        db.session.add(broadcast)
        db.session.flush()

        members_query = SocietyMembership.query.filter_by(society_id=society.id, status='active')
        if selected_roles:
            members_query = members_query.filter(SocietyMembership.role_name.in_(selected_roles))
        memberships = members_query.all()

        count = 0
        target_users = []
        for m in memberships:
            if m.user_id == current_user.id:
                continue
            user = User.query.get(m.user_id)
            if not user or not user.is_active or user.is_banned:
                continue
            msg = Message(
                sender_id=current_user.id,
                recipient_id=user.id,
                subject=f"[{society.legal_name}] {subject}",
                body=body,
                is_read=False,
            )
            db.session.add(msg)
            db.session.flush()
            recipient = BroadcastRecipient(
                broadcast_id=broadcast.id,
                user_id=user.id,
                message_id=msg.id,
                delivery_status='sent',
                sent_at=datetime.utcnow(),
            )
            db.session.add(recipient)
            target_users.append(user)
            count += 1

        broadcast.total_recipients = count
        broadcast.status = 'sent'
        broadcast.sent_at = datetime.utcnow()
        db.session.commit()

        if send_email:
            _send_society_broadcast_emails(broadcast, target_users, society)

        log_action('send_society_broadcast', 'BroadcastMessage', broadcast.id,
                   f'society={society.id} recipients={count} roles={selected_roles}',
                   society_id=society.id)
        flash(f'Comunicazione inviata a {count} membri.', 'success')
        return redirect(url_for('social.society_broadcast_detail', broadcast_id=broadcast.id))

    return render_template('social/society_broadcast_compose.html',
                           society=society, membership_roles=membership_roles,
                           subject='', body='', selected_roles=[])


@bp.route('/society/broadcasts/<int:broadcast_id>')
@login_required
def society_broadcast_detail(broadcast_id):
    if not check_permission(current_user, 'society', 'manage'):
        flash('Accesso riservato alle società.', 'warning')
        return redirect(url_for('social.feed'))
    society = current_user.get_primary_society()
    if not society:
        flash('Profilo società non trovato.', 'warning')
        return redirect(url_for('social.feed'))

    broadcast = BroadcastMessage.query.filter_by(id=broadcast_id, society_id=society.id).first_or_404()
    page = request.args.get('page', 1, type=int)
    recipients_page = broadcast.recipients.join(User, BroadcastRecipient.user_id == User.id)\
        .add_entity(User).paginate(page=page, per_page=50, error_out=False)

    read_count = BroadcastRecipient.query.filter_by(broadcast_id=broadcast.id)\
        .join(Message, BroadcastRecipient.message_id == Message.id)\
        .filter(Message.is_read == True).count()

    return render_template('social/society_broadcast_detail.html', broadcast=broadcast,
                           society=society, recipients_page=recipients_page, read_count=read_count)


@bp.route('/society/broadcasts/<int:broadcast_id>/delete', methods=['POST'])
@login_required
def society_broadcast_delete(broadcast_id):
    if not check_permission(current_user, 'society', 'manage'):
        flash('Accesso riservato alle società.', 'warning')
        return redirect(url_for('social.feed'))
    society = current_user.get_primary_society()
    if not society:
        return redirect(url_for('social.feed'))
    broadcast = BroadcastMessage.query.filter_by(id=broadcast_id, society_id=society.id).first_or_404()
    db.session.delete(broadcast)
    db.session.commit()
    flash('Comunicazione eliminata.', 'success')
    return redirect(url_for('social.society_broadcasts'))


def _send_society_broadcast_emails(broadcast, users, society):
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
            msg['Subject'] = f"[{society.legal_name}] {broadcast.subject}"
            msg['From'] = smtp.default_sender or 'noreply@sonacip.it'
            msg['To'] = u.email
            text_body = broadcast.body
            html_body = f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
            <div style="background:#1877f2;color:#fff;padding:20px;border-radius:8px 8px 0 0;">
                <h2 style="margin:0;">{society.legal_name}</h2>
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
