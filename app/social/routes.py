"""
Social routes
Profiles, feed, posts, follows, likes, comments
"""
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_, desc
from app import db
from app.social import bp
from app.social.forms import PostForm, CommentForm, ProfileEditForm, SearchForm
from app.social.utils import save_picture
from app.models import User, Post, Comment, Notification, AuditLog
from datetime import datetime
import os


@bp.route('/feed')
@login_required
def feed():
    """Main social feed"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get posts from followed users + own posts
    try:
        posts_query = current_user.get_feed_posts()
        pagination = posts_query.paginate(page=page, per_page=per_page, error_out=False)
        posts = pagination.items
    except Exception as e:
        print(f"Error loading feed: {e}")
        # Fallback to own posts only
        posts_query = Post.query.filter_by(user_id=current_user.id)
        pagination = posts_query.paginate(page=page, per_page=per_page, error_out=False)
        posts = pagination.items
    
    # Post form
    form = PostForm()
    
    return render_template('social/feed.html',
                         posts=posts,
                         pagination=pagination,
                         form=form)


@bp.route('/post/create', methods=['POST'])
@login_required
def create_post():
    """Create a new post"""
    form = PostForm()
    
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
def view_post(post_id):
    """View single post with comments"""
    post = Post.query.get_or_404(post_id)
    form = CommentForm()
    
    return render_template('social/view_post.html', post=post, form=form)


@bp.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    """Like/unlike a post"""
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
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'liked': liked,
            'likes_count': post.likes_count
        })
    
    return redirect(request.referrer or url_for('social.feed'))


@bp.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
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
def delete_post(post_id):
    """Delete own post"""
    post = Post.query.get_or_404(post_id)
    
    # Check ownership or admin
    if post.user_id != current_user.id and not current_user.is_admin():
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
    if not current_user.is_society():
        flash('Accesso riservato alle società.', 'warning')
        return redirect(url_for('social.feed'))
    
    # Get society's staff and athletes
    staff = User.query.filter_by(
        role='staff',
        society_id=current_user.id
    ).all()
    
    athletes = User.query.filter_by(
        role='atleta',
        athlete_society_id=current_user.id
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
    societies = User.query.filter_by(role='societa', is_active=True).all()
    societies = sorted(societies, key=lambda u: u.followers.count(), reverse=True)[:20]
    
    # Get recent posts
    recent_posts = Post.query.filter_by(is_public=True).order_by(
        Post.created_at.desc()
    ).limit(10).all()
    
    return render_template('social/explore.html',
                         societies=societies,
                         recent_posts=recent_posts)
