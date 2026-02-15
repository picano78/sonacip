"""
Profile Enhancement Utilities
Verification, analytics, and custom fields
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, desc
from app import db
from app.models import User, ProfileVerification, ProfileAnalytics, CustomProfileField

logger = logging.getLogger(__name__)


def track_profile_view(profile_user_id, viewer_id=None, source='direct'):
    """Track a profile view for analytics"""
    user = User.query.get(profile_user_id)
    if not user:
        return False
    
    today = datetime.now(timezone.utc).date()
    
    # Get or create today's analytics
    analytics = ProfileAnalytics.query.filter_by(
        user_id=profile_user_id,
        date=today
    ).first()
    
    if not analytics:
        analytics = ProfileAnalytics(
            user_id=profile_user_id,
            date=today,
            profile_views=1,
            unique_viewers=1 if viewer_id else 0
        )
        # Initialize view sources
        sources = {source: 1}
        analytics.view_sources = json.dumps(sources)
        db.session.add(analytics)
    else:
        analytics.profile_views += 1
        if viewer_id:
            analytics.unique_viewers += 1
        
        # Update sources
        try:
            sources = json.loads(analytics.view_sources) if analytics.view_sources else {}
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(f"Failed to parse view sources JSON: {e}")
            sources = {}
        
        sources[source] = sources.get(source, 0) + 1
        analytics.view_sources = json.dumps(sources)
    
    db.session.commit()
    return True


def get_profile_analytics(user_id, days=30):
    """Get profile analytics for the last N days"""
    cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=days)
    
    analytics = ProfileAnalytics.query.filter(
        ProfileAnalytics.user_id == user_id,
        ProfileAnalytics.date >= cutoff_date
    ).order_by(ProfileAnalytics.date).all()
    
    if not analytics:
        return {
            'total_views': 0,
            'unique_viewers': 0,
            'new_followers': 0,
            'lost_followers': 0,
            'avg_daily_views': 0,
            'daily_data': []
        }
    
    total_views = sum(a.profile_views for a in analytics)
    unique_viewers = sum(a.unique_viewers for a in analytics)
    new_followers = sum(a.new_followers for a in analytics)
    lost_followers = sum(a.lost_followers for a in analytics)
    
    daily_data = [{
        'date': a.date.isoformat(),
        'views': a.profile_views,
        'unique_viewers': a.unique_viewers,
        'new_followers': a.new_followers
    } for a in analytics]
    
    return {
        'total_views': total_views,
        'unique_viewers': unique_viewers,
        'new_followers': new_followers,
        'lost_followers': lost_followers,
        'net_followers': new_followers - lost_followers,
        'avg_daily_views': total_views / len(analytics) if analytics else 0,
        'daily_data': daily_data
    }


def calculate_profile_completion(user):
    """Calculate profile completion percentage"""
    total_fields = 15
    completed_fields = 0
    
    # Basic fields
    if user.first_name:
        completed_fields += 1
    if user.last_name:
        completed_fields += 1
    if user.email:
        completed_fields += 1
    if user.phone:
        completed_fields += 1
    if user.bio:
        completed_fields += 1
    if user.avatar:
        completed_fields += 1
    if user.cover_photo:
        completed_fields += 1
    if user.city:
        completed_fields += 1
    
    # Role-specific fields
    if user.role == 'society_admin':
        if user.company_name:
            completed_fields += 1
        if user.vat_number or user.fiscal_code:
            completed_fields += 1
        if user.website:
            completed_fields += 1
    elif user.role == 'athlete':
        if user.birth_date:
            completed_fields += 1
        if user.sport:
            completed_fields += 1
    
    # Social connections
    followers_count = user.followers.count() if hasattr(user, 'followers') else 0
    following_count = user.followed.count() if hasattr(user, 'followed') else 0
    
    if followers_count > 0:
        completed_fields += 1
    if following_count > 0:
        completed_fields += 1
    
    # Posts
    posts_count = user.posts.count() if hasattr(user, 'posts') else 0
    if posts_count > 0:
        completed_fields += 1
    
    completion_percentage = (completed_fields / total_fields) * 100
    
    return {
        'percentage': round(completion_percentage, 1),
        'completed_fields': completed_fields,
        'total_fields': total_fields,
        'missing_fields': get_missing_profile_fields(user)
    }


def get_missing_profile_fields(user):
    """Get list of missing profile fields"""
    missing = []
    
    if not user.first_name:
        missing.append('first_name')
    if not user.last_name:
        missing.append('last_name')
    if not user.phone:
        missing.append('phone')
    if not user.bio:
        missing.append('bio')
    if not user.avatar:
        missing.append('avatar')
    if not user.cover_photo:
        missing.append('cover_photo')
    if not user.city:
        missing.append('city')
    
    return missing


def request_verification(user_id, verification_type, documents, notes=''):
    """Submit a profile verification request"""
    # Check if already has verification request
    existing = ProfileVerification.query.filter_by(user_id=user_id).first()
    
    if existing and existing.status == 'pending':
        return {'success': False, 'error': 'Verification request already pending'}
    
    if existing:
        # Update existing request
        verification = existing
        verification.status = 'pending'
    else:
        # Create new request
        verification = ProfileVerification(
            user_id=user_id,
            verification_type=verification_type
        )
        db.session.add(verification)
    
    # Update documents
    if len(documents) > 0:
        verification.document_1_path = documents[0]
    if len(documents) > 1:
        verification.document_2_path = documents[1]
    if len(documents) > 2:
        verification.document_3_path = documents[2]
    
    verification.applicant_notes = notes
    verification.submitted_at = datetime.now(timezone.utc)
    
    db.session.commit()
    
    return {'success': True, 'verification_id': verification.id}


def approve_verification(verification_id, reviewer_id, badge_type='blue_check', notes=''):
    """Approve a verification request"""
    verification = ProfileVerification.query.get(verification_id)
    if not verification:
        return {'success': False, 'error': 'Verification not found'}
    
    verification.status = 'approved'
    verification.reviewed_at = datetime.now(timezone.utc)
    verification.reviewed_by = reviewer_id
    verification.reviewer_notes = notes
    verification.badge_type = badge_type
    
    # Update user verification status
    user = verification.user
    user.is_verified = True
    
    db.session.commit()
    
    return {'success': True, 'message': 'Verification approved'}


def reject_verification(verification_id, reviewer_id, reason):
    """Reject a verification request"""
    verification = ProfileVerification.query.get(verification_id)
    if not verification:
        return {'success': False, 'error': 'Verification not found'}
    
    verification.status = 'rejected'
    verification.reviewed_at = datetime.now(timezone.utc)
    verification.reviewed_by = reviewer_id
    verification.rejection_reason = reason
    
    db.session.commit()
    
    return {'success': True, 'message': 'Verification rejected'}


def add_custom_field(user_id, field_name, field_value, field_type='text', category='personal', is_visible=True):
    """Add a custom field to user profile"""
    field = CustomProfileField(
        user_id=user_id,
        field_name=field_name,
        field_value=field_value,
        field_type=field_type,
        category=category,
        is_visible=is_visible
    )
    
    db.session.add(field)
    db.session.commit()
    
    return field


def update_custom_field(field_id, **kwargs):
    """Update a custom profile field"""
    field = CustomProfileField.query.get(field_id)
    if not field:
        return None
    
    for key, value in kwargs.items():
        if hasattr(field, key):
            setattr(field, key, value)
    
    db.session.commit()
    return field


def delete_custom_field(field_id, user_id):
    """Delete a custom profile field"""
    field = CustomProfileField.query.get(field_id)
    if not field or field.user_id != user_id:
        return False
    
    db.session.delete(field)
    db.session.commit()
    return True


def export_profile_data(user_id):
    """Export user profile data (GDPR compliance)"""
    user = User.query.get(user_id)
    if not user:
        return None
    
    data = {
        'profile': {
            'email': user.email,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone': user.phone,
            'bio': user.bio,
            'city': user.city,
            'created_at': user.created_at.isoformat() if user.created_at else None,
        },
        'statistics': {
            'posts_count': user.posts.count() if hasattr(user, 'posts') else 0,
            'followers_count': user.followers.count() if hasattr(user, 'followers') else 0,
            'following_count': user.followed.count() if hasattr(user, 'followed') else 0,
        },
        'custom_fields': [],
        'verification': None
    }
    
    # Add custom fields
    custom_fields = CustomProfileField.query.filter_by(user_id=user_id).all()
    for field in custom_fields:
        data['custom_fields'].append({
            'name': field.field_name,
            'value': field.field_value,
            'type': field.field_type,
            'category': field.category
        })
    
    # Add verification status
    verification = ProfileVerification.query.filter_by(user_id=user_id).first()
    if verification:
        data['verification'] = {
            'type': verification.verification_type,
            'status': verification.status,
            'badge_type': verification.badge_type,
            'submitted_at': verification.submitted_at.isoformat() if verification.submitted_at else None
        }
    
    return data


def get_profile_suggestions(user):
    """Get suggestions to improve profile"""
    suggestions = []
    
    # Check completion
    completion = calculate_profile_completion(user)
    
    if completion['percentage'] < 80:
        suggestions.append({
            'type': 'completion',
            'priority': 'high',
            'message': f"Your profile is {completion['percentage']}% complete. Complete it to increase visibility!"
        })
    
    # Check verification
    if not user.is_verified:
        verification = ProfileVerification.query.filter_by(user_id=user.id).first()
        if not verification or verification.status == 'rejected':
            suggestions.append({
                'type': 'verification',
                'priority': 'medium',
                'message': "Get verified to build trust and credibility!"
            })
    
    # Check social connections
    if hasattr(user, 'followers'):
        followers_count = user.followers.count()
        if followers_count < 10:
            suggestions.append({
                'type': 'social',
                'priority': 'medium',
                'message': "Connect with more people to expand your network!"
            })
    
    # Check content
    if hasattr(user, 'posts'):
        posts_count = user.posts.count()
        if posts_count == 0:
            suggestions.append({
                'type': 'content',
                'priority': 'high',
                'message': "Share your first post to engage with the community!"
            })
    
    return suggestions
