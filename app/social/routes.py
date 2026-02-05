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
    WhatsappOptIn,
    UserOnboardingStep,
    Opportunity,
    Permission,
    SocietyRolePermission,
)
from app.cache import get_cache
from app.utils import permission_required, check_permission, get_active_society_id
from app.utils import log_action
from datetime import datetime, timedelta
import os
from app.ads.utils import choose_creative, make_token

bp = Blueprint('social', __name__, url_prefix='/social')


@bp.route('/feed')
@login_required
@permission_required('social', 'comment')
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
    
    cache_key = f"feed:{current_user.id}:p{page}"
    cached_ids = cache.get(cache_key)

    start = (page - 1) * per_page
    # Visibility scoping (athletes see only relevant communications)
    admin_access = check_permission(current_user, 'admin', 'access')
    scope_id = get_active_society_id(current_user)
    followed_ids = set()
    try:
        followed_ids = {u.id for u in current_user.followed.all()}
    except Exception:
        followed_ids = set()

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

    if cached_ids is None:
        # Get posts from followed users + own posts
        try:
            posts_query = current_user.get_feed_posts()
        except Exception as e:
            print(f"Error loading feed: {e}")
            posts_query = Post.query.filter_by(user_id=current_user.id)

        fetch_limit = per_page * 5 + start
        now = datetime.utcnow()
        promoted = Post.query.filter(
            Post.is_promoted == True,
            Post.promotion_ends_at.isnot(None),
            Post.promotion_ends_at > now
        ).order_by(Post.created_at.desc()).limit(per_page * 2).all()

        raw_posts = posts_query.order_by(Post.created_at.desc()).limit(fetch_limit).all()

        combined = []
        seen = set()
        for p in promoted + raw_posts:
            if p.id not in seen:
                combined.append(p)
                seen.add(p.id)
        # Apply visibility filter in-memory (keeps existing query behavior stable)
        combined = [p for p in combined if is_visible(p)]

    boosted_types = []
    muted_types = []
    if settings:
        try:
            import json
            boosted_types = json.loads(settings.boosted_types or '[]')
            muted_types = json.loads(settings.muted_types or '[]')
        except Exception:
            boosted_types = []
            muted_types = []

    def engagement_score(p):
        age_hours = max((datetime.utcnow() - p.created_at).total_seconds() / 3600, 0.1)
        recency = max(0, 48 - age_hours) / 48  # 0-1
        score = (p.likes_count * 2) + (p.comments_count * 3) + recency * 5
        if p.is_promoted and p.promotion_ends_at and p.promotion_ends_at > datetime.utcnow():
            score += 20
        # Governance: boost tournament/match/official posts
        if p.is_promoted and settings and settings.boost_official:
            score += 5
        # Priority tiers: official society content > tournaments/matches > automations > personal
        if p.author and p.author.is_society():
            score += 30
        if p.post_type and any(token in p.post_type for token in ['tournament', 'match']):
            score += 20
        if p.post_type and 'automation' in p.post_type:
            score += 10
        if boosted_types:
            for t in boosted_types:
                if t in (p.post_type or ''):
                    score += 5
        if muted_types:
            for t in muted_types:
                if t in (p.post_type or ''):
                    score -= 10
        return score
    if cached_ids is None:
        sorted_posts = sorted(combined, key=engagement_score, reverse=True)
        total = len(sorted_posts)
        end = start + per_page
        page_ids = [p.id for p in sorted_posts[start:end]] if start < len(sorted_posts) else []
        cache.set(cache_key, {'ids': page_ids, 'total': total}, ttl=cache_ttl)
    else:
        page_ids = cached_ids.get('ids', [])
        total = cached_ids.get('total', 0)

    if page_ids:
        posts_map = {p.id: p for p in Post.query.filter(Post.id.in_(page_ids)).options(joinedload(Post.author)).all()}
        posts = [posts_map[i] for i in page_ids if i in posts_map]
    else:
        posts = []

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
        # Map legacy `is_public` to explicit audience rules
        audience = 'public' if form.is_public.data else 'followers'
        society_id = None
        if current_user.is_society():
            audience = 'public' if form.is_public.data else 'society'
            # Scope posts to the Society entity, not the User id.
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
        
        # Handle image upload
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

    settings = AdsSetting.query.first()
    if not settings:
        settings = AdsSetting()
        db.session.add(settings)
        db.session.commit()

    form = PromotePostForm()
    if form.validate_on_submit():
        duration = form.duration_days.data
        views = form.views.data
        cost = settings.price_per_day * duration + (settings.price_per_thousand_views / 1000.0) * views

        # Simulate payment success
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
        flash(f'Post sponsorizzato! Costo €{cost:.2f}', 'success')
        return redirect(url_for('social.view_post', post_id=post_id))

    # Prefill defaults
    if not form.duration_days.data:
        form.duration_days.data = settings.default_duration_days
    if not form.views.data:
        form.views.data = settings.default_views

    cost_preview = settings.price_per_day * (form.duration_days.data or settings.default_duration_days) + \
        (settings.price_per_thousand_views / 1000.0) * (form.views.data or settings.default_views)

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

    whatsapp_opted_in = None
    active_sid = None
    try:
        active_sid = get_active_society_id(current_user)
    except Exception:
        active_sid = None
    if current_user.is_authenticated and current_user.id == user.id and active_sid:
        try:
            row = WhatsappOptIn.query.filter_by(society_id=active_sid, user_id=user.id).first()
            whatsapp_opted_in = bool(row.is_opted_in) if row else False
        except Exception:
            whatsapp_opted_in = None
    
    return render_template('social/profile.html',
                         user=user,
                         posts=posts,
                         pagination=pagination,
                         stats=stats,
                         is_following=is_following,
                         whatsapp_opted_in=whatsapp_opted_in,
                         active_society_id=active_sid)


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
        # Show all active users
        users_query = User.query.filter_by(is_active=True)
    
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
    opp_count = Opportunity.query.filter_by(society_id=society.id).count()
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
    if opp_count == 0:
        _suggest("create_crm_opportunity", "Apri la prima opportunità CRM", "Traccia sponsor/iscrizioni/reclutamento con una opportunità.", url_for('crm.new_opportunity'))
    if society_posts_count == 0:
        _suggest("publish_society_post", "Pubblica un comunicato", "Usa il social per comunicazioni ufficiali verso la società/atleti.", url_for('social.feed'))
    if not current_user.has_feature("whatsapp_pro"):
        _suggest("upsell_whatsapp_pro", "Attiva WhatsApp Pro", "Automazioni WhatsApp avanzate (template/opt-in) per aumentare retention e pagamenti.", url_for('subscription.addons'))

    # Onboarding checklist (hybrid: some auto-detected, some manual)
    step_defs = [
        {"key": "invite_one_member", "label": "Invita almeno 1 membro", "auto": member_count >= 2},
        {"key": "create_one_calendar_event", "label": "Crea 1 evento nel calendario", "auto": calendar_count >= 1},
        {"key": "create_one_crm_opportunity", "label": "Crea 1 opportunità CRM", "auto": opp_count >= 1},
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


@bp.route('/whatsapp/optin', methods=['POST'])
@login_required
def whatsapp_optin():
    """User opt-in to receive WhatsApp messages for the active society scope."""
    society_id = get_active_society_id(current_user)
    if not society_id:
        flash('Seleziona una società per attivare WhatsApp.', 'warning')
        return redirect(url_for('main.dashboard'))
    if not current_user.phone:
        flash('Imposta un numero di telefono nel profilo per attivare WhatsApp.', 'warning')
        return redirect(url_for('social.edit_profile'))
    row = WhatsappOptIn.query.filter_by(society_id=society_id, user_id=current_user.id).first()
    if not row:
        row = WhatsappOptIn(society_id=society_id, user_id=current_user.id)
        db.session.add(row)
    row.phone_number = current_user.phone
    row.is_opted_in = True
    row.opted_in_at = datetime.utcnow()
    row.opted_out_at = None
    row.source = 'user'
    db.session.commit()
    flash('WhatsApp attivato per questa società.', 'success')
    return redirect(url_for('social.profile', user_id=current_user.id))


@bp.route('/whatsapp/optout', methods=['POST'])
@login_required
def whatsapp_optout():
    """User opt-out from WhatsApp messages for the active society scope."""
    society_id = get_active_society_id(current_user)
    if not society_id:
        return redirect(url_for('main.dashboard'))
    row = WhatsappOptIn.query.filter_by(society_id=society_id, user_id=current_user.id).first()
    if not row:
        row = WhatsappOptIn(society_id=society_id, user_id=current_user.id, phone_number=current_user.phone)
        db.session.add(row)
    row.is_opted_in = False
    row.opted_out_at = datetime.utcnow()
    row.source = 'user'
    db.session.commit()
    flash('WhatsApp disattivato per questa società.', 'info')
    return redirect(url_for('social.profile', user_id=current_user.id))


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
