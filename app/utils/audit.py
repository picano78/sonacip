"""
Audit logging utilities for tracking planner and calendar changes
"""
from flask import request
import logging
from app import db
from app.models import AuditLog
from datetime import datetime, timezone
import json

logger = logging.getLogger(__name__)


def log_planner_change(user_id, society_id, action, entity_type, entity_id, details=None):
    """
    Log a change to field planner or calendar.
    
    Args:
        user_id: ID of user making the change
        society_id: ID of the society
        action: Action type (e.g., 'created', 'updated', 'deleted')
        entity_type: Type of entity (e.g., 'FieldPlannerEvent', 'SocietyCalendarEvent')
        entity_id: ID of the entity
        details: Optional dict or string with additional details
    """
    try:
        # Get IP address from request
        ip_address = request.remote_addr if request else None
        if request and request.headers.get('X-Forwarded-For'):
            ip_address = request.headers.get('X-Forwarded-For').split(',')[0].strip()
        
        # Convert details to JSON string if dict
        if isinstance(details, dict):
            details = json.dumps(details, ensure_ascii=False)
        
        audit_entry = AuditLog(
            user_id=user_id,
            society_id=society_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address,
            created_at=datetime.now(timezone.utc)
        )
        
        db.session.add(audit_entry)
        db.session.commit()
        
        return audit_entry
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error logging audit entry: {e}", exc_info=True)
        return None


def get_planner_changes(society_id, limit=100, entity_type=None):
    """
    Get recent planner changes for a society.
    
    Args:
        society_id: ID of the society
        limit: Maximum number of records to return
        entity_type: Optional filter by entity type
    
    Returns:
        List of AuditLog entries
    """
    try:
        query = AuditLog.query.filter(
            AuditLog.society_id == society_id,
            AuditLog.entity_type.in_(['FieldPlannerEvent', 'SocietyCalendarEvent'])
        )
        
        if entity_type:
            query = query.filter(AuditLog.entity_type == entity_type)
        
        return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    except Exception as e:
        logger.error(f"Error getting planner changes: {e}", exc_info=True)
        return []
