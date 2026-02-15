"""
Post Scheduling Utilities
Handle scheduled posts and publishing
"""
from datetime import datetime, timezone
from app import db
from app.models import Post
from app.notifications.utils import create_notification


def schedule_post(user_id, content, scheduled_for, **kwargs):
    """
    Create a scheduled post
    
    Args:
        user_id: User creating the post
        content: Post content
        scheduled_for: datetime when to publish
        **kwargs: Additional post fields (image, audience, etc.)
    """
    post = Post(
        user_id=user_id,
        content=content,
        is_scheduled=True,
        scheduled_for=scheduled_for,
        status='scheduled',
        **kwargs
    )
    
    db.session.add(post)
    db.session.commit()
    
    return post


def publish_scheduled_posts():
    """
    Publish all posts scheduled for now or earlier
    This should be called by a background task (Celery)
    """
    now = datetime.now(timezone.utc)
    
    scheduled_posts = Post.query.filter(
        Post.status == 'scheduled',
        Post.is_scheduled == True,
        Post.scheduled_for <= now
    ).all()
    
    published_count = 0
    
    for post in scheduled_posts:
        try:
            # Publish the post
            post.status = 'published'
            post.published_at = now
            
            # Process hashtags if the content has them
            from app.social.analytics import process_post_hashtags
            if '#' in post.content:
                process_post_hashtags(post)
            
            # Notify user that their post was published
            create_notification(
                user_id=post.user_id,
                title='Post Published',
                message=f'Your scheduled post has been published!',
                notification_type='info',
                link=f'/social/post/{post.id}'
            )
            
            published_count += 1
            
        except Exception as e:
            # Log error but continue with other posts
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error publishing post {post.id}: {str(e)}", exc_info=True)
            continue
    
    if published_count > 0:
        db.session.commit()
    
    return published_count


def get_scheduled_posts(user_id):
    """Get all scheduled posts for a user"""
    return Post.query.filter_by(
        user_id=user_id,
        status='scheduled',
        is_scheduled=True
    ).order_by(Post.scheduled_for).all()


def cancel_scheduled_post(post_id, user_id):
    """Cancel a scheduled post"""
    post = Post.query.get(post_id)
    
    if not post or post.user_id != user_id:
        return False
    
    if post.status != 'scheduled':
        return False
    
    # Change to draft or delete
    post.status = 'draft'
    post.is_scheduled = False
    post.scheduled_for = None
    
    db.session.commit()
    return True


def reschedule_post(post_id, new_datetime, user_id):
    """Reschedule a post to a new time"""
    post = Post.query.get(post_id)
    
    if not post or post.user_id != user_id:
        return False
    
    if post.status != 'scheduled':
        return False
    
    post.scheduled_for = new_datetime
    db.session.commit()
    
    return True


def get_best_posting_times(user_id, limit=5):
    """
    Analyze user's past posts to suggest best posting times
    Based on engagement rates at different times
    """
    from sqlalchemy import func, extract
    
    # Get posts with good engagement
    posts = Post.query.filter_by(user_id=user_id).filter(
        Post.views_count > 0
    ).all()
    
    if not posts:
        # Return default suggested times
        return [
            {'hour': 9, 'day_of_week': 1, 'avg_engagement': 0},  # Monday 9 AM
            {'hour': 12, 'day_of_week': 3, 'avg_engagement': 0},  # Wednesday noon
            {'hour': 18, 'day_of_week': 5, 'avg_engagement': 0},  # Friday 6 PM
        ]
    
    # Group by hour and day of week
    time_performance = {}
    
    for post in posts:
        hour = post.created_at.hour
        day_of_week = post.created_at.weekday()
        key = (hour, day_of_week)
        
        if key not in time_performance:
            time_performance[key] = []
        
        time_performance[key].append(post.engagement_rate)
    
    # Calculate average engagement for each time slot
    results = []
    for (hour, day_of_week), engagement_rates in time_performance.items():
        avg_engagement = sum(engagement_rates) / len(engagement_rates)
        results.append({
            'hour': hour,
            'day_of_week': day_of_week,
            'avg_engagement': avg_engagement,
            'post_count': len(engagement_rates)
        })
    
    # Sort by engagement and return top times
    results.sort(key=lambda x: x['avg_engagement'], reverse=True)
    
    return results[:limit]
