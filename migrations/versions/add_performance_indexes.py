"""
Database performance indexes migration
Add indexes for frequently queried columns to improve performance
"""

from alembic import op
import sqlalchemy as sa


def upgrade():
    """Add performance indexes"""
    
    # Social feed performance indexes
    op.create_index('idx_post_created_at_desc', 'post', [sa.text('created_at DESC')])
    op.create_index('idx_post_author_created', 'post', ['author_id', sa.text('created_at DESC')])
    
    # User followers indexes
    op.create_index('idx_followers_followed', 'followers', ['followed_id', 'created_at'])
    op.create_index('idx_followers_follower', 'followers', ['follower_id', 'created_at'])
    
    # Notification indexes
    op.create_index('idx_notification_user_unread', 'notification', ['user_id', 'is_read', sa.text('created_at DESC')])
    
    # Automation indexes
    op.create_index('idx_automation_rule_event_active', 'automation_rule', ['event_type', 'is_active'])
    op.create_index('idx_automation_run_retry', 'automation_run', ['status', 'next_retry_at'])
    
    # Event indexes
    op.create_index('idx_event_society_date', 'event', ['society_id', 'event_date'])
    op.create_index('idx_event_date_status', 'event', ['event_date', 'status'])
    
    # Society calendar indexes
    op.create_index('idx_society_calendar_event_date', 'society_calendar_event', ['event_date', 'society_id'])
    op.create_index('idx_society_calendar_attendance_event', 'society_calendar_attendance', ['event_id', 'status'])
    
    # CRM indexes
    op.create_index('idx_contact_society_created', 'contact', ['society_id', sa.text('created_at DESC')])
    op.create_index('idx_opportunity_status_value', 'opportunity', ['status', 'value'])
    
    # Message indexes
    op.create_index('idx_message_conversation', 'message', ['sender_id', 'recipient_id', sa.text('created_at DESC')])
    op.create_index('idx_message_recipient_unread', 'message', ['recipient_id', 'is_read', sa.text('created_at DESC')])
    
    # Comment indexes
    op.create_index('idx_comment_post_created', 'comment', ['post_id', sa.text('created_at DESC')])
    
    # Audit log indexes
    op.create_index('idx_audit_log_user_action', 'audit_log', ['user_id', 'action', sa.text('created_at DESC')])
    op.create_index('idx_audit_log_created', 'audit_log', [sa.text('created_at DESC')])


def downgrade():
    """Remove performance indexes"""
    
    # Social feed indexes
    op.drop_index('idx_post_created_at_desc', 'post')
    op.drop_index('idx_post_author_created', 'post')
    
    # User followers indexes
    op.drop_index('idx_followers_followed', 'followers')
    op.drop_index('idx_followers_follower', 'followers')
    
    # Notification indexes
    op.drop_index('idx_notification_user_unread', 'notification')
    
    # Automation indexes
    op.drop_index('idx_automation_rule_event_active', 'automation_rule')
    op.drop_index('idx_automation_run_retry', 'automation_run')
    
    # Event indexes
    op.drop_index('idx_event_society_date', 'event')
    op.drop_index('idx_event_date_status', 'event')
    
    # Society calendar indexes
    op.drop_index('idx_society_calendar_event_date', 'society_calendar_event')
    op.drop_index('idx_society_calendar_attendance_event', 'society_calendar_attendance')
    
    # CRM indexes
    op.drop_index('idx_contact_society_created', 'contact')
    op.drop_index('idx_opportunity_status_value', 'opportunity')
    
    # Message indexes
    op.drop_index('idx_message_conversation', 'message')
    op.drop_index('idx_message_recipient_unread', 'message')
    
    # Comment indexes
    op.drop_index('idx_comment_post_created', 'comment')
    
    # Audit log indexes
    op.drop_index('idx_audit_log_user_action', 'audit_log')
    op.drop_index('idx_audit_log_created', 'audit_log')
