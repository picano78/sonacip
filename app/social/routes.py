"""
Social routes
Profiles, feed, posts, follows, likes, comments
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app import db
from app.social.forms import PostForm, CommentForm, ProfileEditForm, SearchForm, PromotePostForm
from app.social.utils import save_picture
from app.models import User, Post, Comment, Notification, AuditLog, AdsSetting, Payment, SocialSetting, TournamentMatch
from app.cache import get_cache
from app.utils import permission_required, check_permission
from datetime import datetime, timedelta
from datetime import datetime
import os

bp = Blueprint('social', __name__)


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
        total = posts_query.count() if 'posts_query' in locals() else len(sorted_posts)
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
                         form=form)


@bp.route('/post/create', methods=['POST'])
@login_required
@permission_required('social', 'post')
def create_post():
    """Create a new post"""
    form = PostForm()
    settings = SocialSetting.query.first()
    if settings and not settings.feed_enabled and not check_permission(current_user, 'admin', 'access'):
        flash('Pubblicazione disabilitata dall\'amministratore.', 'warning')
        return redirect(url_for('social.feed'))
    
    if form.validate_on_submit():
        post = Post(
            user_id=current_user.id,
            content=form.content.data,
            is_public=form.is_public.data
        )
        
        # Handle image upload
        if form.image.data:
            image_file = save_picture(form.image.data, folder='posts', size=(800, 800))
            post.image = image_file
        
        db.session.add(post)
        db.session.commit()
        
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
    
    return render_template('social/profile.html',
                         user=user,
                         posts=posts,
                         pagination=pagination,
                         stats=stats,
                         is_following=is_following)


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
    
    # Get society's staff and athletes
    staff = User.query.filter(
        User.role.in_(['staff', 'coach']),
        User.society_id == society.id
    ).all()

    athletes = User.query.filter(
        User.role.in_(['atleta', 'athlete']),
        User.athlete_society_id == society.id
    ).all()
    
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
    
    return render_template('social/society_dashboard.html',
                         staff=staff,
                         athletes=athletes,
                         events=events,
                         stats=stats)


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
