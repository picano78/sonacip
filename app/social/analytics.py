"""
Social Analytics Utilities
Track and calculate social media metrics
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, desc
from app import db
from app.models import Post, PostAnalytics, UserSocialStats, Hashtag, Comment, User
import json


def track_post_view(post_id, user_id=None):
    """Track a post view"""
    post = db.session.get(Post, post_id)
    if not post:
        return False
    
    # Increment post views
    post.views_count += 1
    
    # Get or create today's analytics
    today = datetime.now(timezone.utc).date()
    analytics = PostAnalytics.query.filter_by(
        post_id=post_id,
        date=today
    ).first()
    
    if not analytics:
        analytics = PostAnalytics(
            post_id=post_id,
            date=today,
            views=1,
            unique_views=1 if user_id else 0
        )
        db.session.add(analytics)
    else:
        analytics.views += 1
        if user_id:
            analytics.unique_views += 1
    
    db.session.commit()
    return True


def get_trending_hashtags(limit=10, days=7):
    """Get trending hashtags from the last N days"""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    trending = Hashtag.query.filter(
        Hashtag.last_used_at >= cutoff_date
    ).order_by(desc(Hashtag.use_count)).limit(limit).all()
    
    return trending


def get_user_social_analytics(user_id, days=30):
    """Get comprehensive social analytics for a user"""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get user's posts
    posts = Post.query.filter_by(user_id=user_id).filter(
        Post.created_at >= cutoff_date
    ).all()
    
    if not posts:
        return {
            'posts_count': 0,
            'total_views': 0,
            'total_likes': 0,
            'total_comments': 0,
            'total_shares': 0,
            'avg_engagement_rate': 0.0,
            'best_performing_post': None
        }
    
    total_views = sum(p.views_count for p in posts)
    total_likes = sum(p.likes_count for p in posts)
    total_comments = sum(p.comments_count for p in posts)
    total_shares = sum(p.shares_count for p in posts)
    
    # Calculate average engagement rate
    engagement_rates = [p.engagement_rate for p in posts if p.views_count > 0]
    avg_engagement = sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0.0
    
    # Find best performing post
    best_post = max(posts, key=lambda p: p.engagement_rate) if posts else None
    
    return {
        'posts_count': len(posts),
        'total_views': total_views,
        'total_likes': total_likes,
        'total_comments': total_comments,
        'total_shares': total_shares,
        'avg_engagement_rate': avg_engagement,
        'best_performing_post': best_post
    }


def update_user_social_stats(user_id):
    """Update aggregated social stats for a user"""
    stats = UserSocialStats.query.filter_by(user_id=user_id).first()
    
    if not stats:
        stats = UserSocialStats(user_id=user_id)
        db.session.add(stats)
    
    # Count posts
    stats.posts_count = Post.query.filter_by(user_id=user_id).count()
    
    # Aggregate engagement
    posts = Post.query.filter_by(user_id=user_id).all()
    stats.total_likes_received = sum(p.likes_count for p in posts)
    stats.total_comments_received = sum(p.comments_count for p in posts)
    stats.total_shares_received = sum(p.shares_count for p in posts)
    stats.total_views = sum(p.views_count for p in posts)
    
    # Calculate average engagement
    engagement_rates = [p.engagement_rate for p in posts if p.views_count > 0]
    stats.avg_engagement_rate = sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0.0
    
    # Find most popular post
    if posts:
        most_popular = max(posts, key=lambda p: p.engagement_rate)
        stats.most_popular_post_id = most_popular.id
    
    # Update last post time
    latest_post = Post.query.filter_by(user_id=user_id).order_by(
        desc(Post.created_at)
    ).first()
    if latest_post:
        stats.last_post_at = latest_post.created_at
    
    # Count followers/following
    user = db.session.get(User, user_id)
    if user:
        stats.followers_count = user.followers.count()
        stats.following_count = user.following.count()
    
    stats.last_updated = datetime.now(timezone.utc)
    db.session.commit()
    
    return stats


def get_post_performance_metrics(post_id):
    """Get detailed performance metrics for a post"""
    post = db.session.get(Post, post_id)
    if not post:
        return None
    
    # Get analytics over time
    analytics = PostAnalytics.query.filter_by(post_id=post_id).order_by(
        PostAnalytics.date
    ).all()
    
    daily_data = [{
        'date': a.date.isoformat(),
        'views': a.views,
        'likes': a.likes,
        'comments': a.comments,
        'shares': a.shares
    } for a in analytics]
    
    return {
        'post_id': post_id,
        'total_views': post.views_count,
        'total_likes': post.likes_count,
        'total_comments': post.comments_count,
        'total_shares': post.shares_count,
        'engagement_rate': post.engagement_rate,
        'daily_data': daily_data,
        'hashtags': post.extract_hashtags() if hasattr(post, 'extract_hashtags') else []
    }


def process_post_hashtags(post):
    """Extract and process hashtags from a post"""
    hashtags = post.extract_hashtags()
    
    for tag in hashtags:
        tag_lower = tag.lower()
        hashtag = Hashtag.query.filter_by(tag=tag_lower).first()
        
        if not hashtag:
            hashtag = Hashtag(tag=tag_lower, use_count=1)
            db.session.add(hashtag)
        else:
            hashtag.use_count += 1
            hashtag.last_used_at = datetime.now(timezone.utc)
        
        db.session.flush()
        
        # Link post to hashtag
        # Check if relationship already exists
        from app.models import post_hashtags
        existing = db.session.query(post_hashtags).filter_by(
            post_id=post.id,
            hashtag_id=hashtag.id
        ).first()
        
        if not existing:
            db.session.execute(
                post_hashtags.insert().values(
                    post_id=post.id,
                    hashtag_id=hashtag.id
                )
            )
    
    db.session.commit()


def get_hashtag_posts(hashtag, limit=50):
    """Get posts for a specific hashtag"""
    hashtag_obj = Hashtag.query.filter_by(tag=hashtag.lower()).first()
    if not hashtag_obj:
        return []
    
    # Query posts with this hashtag
    from app.models import post_hashtags
    post_ids = db.session.query(post_hashtags.c.post_id).filter_by(
        hashtag_id=hashtag_obj.id
    ).all()
    
    post_ids = [pid[0] for pid in post_ids]
    
    posts = Post.query.filter(Post.id.in_(post_ids)).order_by(
        desc(Post.created_at)
    ).limit(limit).all()
    
    return posts


def get_feed_analytics(user_id, days=7):
    """Get analytics for user's feed activity"""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Posts from user
    user_posts = Post.query.filter_by(user_id=user_id).filter(
        Post.created_at >= cutoff_date
    ).count()
    
    # Posts user engaged with
    user = db.session.get(User, user_id)
    if not user:
        return {}
    
    liked_posts = user.liked_posts.filter(
        Post.created_at >= cutoff_date
    ).count()
    
    comments_made = Comment.query.filter_by(user_id=user_id).join(Post).filter(
        Post.created_at >= cutoff_date
    ).count()
    
    return {
        'period_days': days,
        'posts_created': user_posts,
        'posts_liked': liked_posts,
        'comments_made': comments_made,
        'total_activity': user_posts + liked_posts + comments_made
    }
