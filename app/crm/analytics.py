"""
CRM Analytics and Lead Scoring Utilities
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, desc, and_, or_
from app import db
from app.models import Contact, Opportunity, CRMActivity, LeadScoringRule, ContactSegment

logger = logging.getLogger(__name__)


def calculate_lead_score(contact):
    """
    Calculate lead score for a contact based on scoring rules
    """
    if not contact.society_id:
        return 0
    
    # Get active scoring rules for society
    rules = LeadScoringRule.query.filter_by(
        society_id=contact.society_id,
        is_active=True
    ).all()
    
    total_score = 0
    
    for rule in rules:
        # Evaluate rule
        if evaluate_scoring_rule(contact, rule):
            total_score += rule.points
    
    # Cap score between 0-100
    total_score = max(0, min(100, total_score))
    
    # Update contact
    contact.score = total_score
    contact.score_updated_at = datetime.now(timezone.utc)
    
    # Update engagement level based on score
    if total_score >= 70:
        contact.engagement_level = 'hot'
    elif total_score >= 40:
        contact.engagement_level = 'warm'
    else:
        contact.engagement_level = 'cold'
    
    db.session.commit()
    
    return total_score


def evaluate_scoring_rule(contact, rule):
    """Evaluate if a contact matches a scoring rule"""
    attribute_value = getattr(contact, rule.attribute, None)
    
    if attribute_value is None:
        return False
    
    # Convert to string for comparison
    attribute_value = str(attribute_value)
    rule_value = str(rule.value) if rule.value else ""
    
    if rule.operator == 'equals':
        return attribute_value == rule_value
    elif rule.operator == 'contains':
        return rule_value.lower() in attribute_value.lower()
    elif rule.operator == 'greater_than':
        try:
            return float(attribute_value) > float(rule_value)
        except (ValueError, TypeError) as e:
            logger.debug(f"Cannot compare values as numbers: {e}")
            return False
    elif rule.operator == 'less_than':
        try:
            return float(attribute_value) < float(rule_value)
        except (ValueError, TypeError) as e:
            logger.debug(f"Cannot compare values as numbers: {e}")
            return False
    elif rule.operator == 'not_equals':
        return attribute_value != rule_value
    
    return False


def recalculate_all_scores(society_id):
    """Recalculate lead scores for all contacts in a society"""
    contacts = Contact.query.filter_by(society_id=society_id).all()
    
    updated_count = 0
    for contact in contacts:
        calculate_lead_score(contact)
        updated_count += 1
    
    return updated_count


def get_contact_activity_summary(contact_id):
    """Get activity summary for a contact"""
    activities = CRMActivity.query.filter_by(contact_id=contact_id).all()
    
    summary = {
        'total_activities': len(activities),
        'calls': sum(1 for a in activities if a.activity_type == 'call'),
        'emails': sum(1 for a in activities if a.activity_type == 'email'),
        'meetings': sum(1 for a in activities if a.activity_type == 'meeting'),
        'notes': sum(1 for a in activities if a.activity_type == 'note'),
        'completed': sum(1 for a in activities if a.completed),
        'pending': sum(1 for a in activities if not a.completed),
        'last_activity': max((a.activity_date for a in activities), default=None)
    }
    
    return summary


def get_pipeline_forecast(society_id, period_months=3):
    """
    Get sales pipeline forecast for next N months
    """
    cutoff_date = datetime.now().date() + timedelta(days=period_months * 30)
    
    opportunities = Opportunity.query.filter(
        Opportunity.society_id == society_id,
        Opportunity.stage.in_(['prospecting', 'qualification', 'proposal', 'negotiation']),
        Opportunity.expected_close_date <= cutoff_date
    ).all()
    
    forecast = {
        'total_opportunities': len(opportunities),
        'total_value': 0.0,
        'weighted_value': 0.0,
        'by_stage': {},
        'by_month': {}
    }
    
    for opp in opportunities:
        # Parse value
        try:
            value = float(opp.value) if opp.value else 0.0
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid opportunity value '{opp.value}': {e}")
            value = 0.0
        
        # Parse probability
        try:
            prob = float(opp.probability) / 100 if opp.probability else 0.5
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid opportunity probability '{opp.probability}': {e}")
            prob = 0.5
        
        weighted = value * prob
        
        forecast['total_value'] += value
        forecast['weighted_value'] += weighted
        
        # Group by stage
        stage = opp.stage or 'unknown'
        if stage not in forecast['by_stage']:
            forecast['by_stage'][stage] = {'count': 0, 'value': 0.0, 'weighted': 0.0}
        
        forecast['by_stage'][stage]['count'] += 1
        forecast['by_stage'][stage]['value'] += value
        forecast['by_stage'][stage]['weighted'] += weighted
        
        # Group by month
        if opp.expected_close_date:
            month_key = opp.expected_close_date.strftime('%Y-%m')
            if month_key not in forecast['by_month']:
                forecast['by_month'][month_key] = {'count': 0, 'value': 0.0, 'weighted': 0.0}
            
            forecast['by_month'][month_key]['count'] += 1
            forecast['by_month'][month_key]['value'] += value
            forecast['by_month'][month_key]['weighted'] += weighted
    
    return forecast


def get_conversion_funnel(society_id, days=30):
    """Get contact conversion funnel metrics"""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    contacts = Contact.query.filter(
        Contact.society_id == society_id,
        Contact.created_at >= cutoff_date
    ).all()
    
    funnel = {
        'new': sum(1 for c in contacts if c.status == 'new'),
        'contacted': sum(1 for c in contacts if c.status == 'contacted'),
        'interested': sum(1 for c in contacts if c.status == 'interested'),
        'converted': sum(1 for c in contacts if c.status == 'converted'),
        'lost': sum(1 for c in contacts if c.status == 'lost'),
        'total': len(contacts)
    }
    
    # Calculate conversion rates
    if funnel['total'] > 0:
        funnel['contact_rate'] = (funnel['contacted'] / funnel['total']) * 100
        funnel['interest_rate'] = (funnel['interested'] / funnel['total']) * 100
        funnel['conversion_rate'] = (funnel['converted'] / funnel['total']) * 100
    else:
        funnel['contact_rate'] = 0
        funnel['interest_rate'] = 0
        funnel['conversion_rate'] = 0
    
    return funnel


def segment_contacts(segment):
    """
    Get contacts matching a segment's criteria
    """
    try:
        criteria = json.loads(segment.criteria)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.error(f"Failed to parse segment criteria JSON: {e}", exc_info=True)
        return []
    
    query = Contact.query.filter_by(society_id=segment.society_id)
    
    # Apply filters
    for filter_item in criteria.get('filters', []):
        field = filter_item.get('field')
        operator = filter_item.get('operator')
        value = filter_item.get('value')
        
        if not field or not operator:
            continue
        
        # Build filter based on operator
        if operator == 'equals':
            query = query.filter(getattr(Contact, field) == value)
        elif operator == 'contains':
            query = query.filter(getattr(Contact, field).ilike(f'%{value}%'))
        elif operator == 'in':
            if isinstance(value, list):
                query = query.filter(getattr(Contact, field).in_(value))
    
    contacts = query.all()
    
    # Update segment count
    segment.contact_count = len(contacts)
    segment.last_calculated_at = datetime.now(timezone.utc)
    db.session.commit()
    
    return contacts


def get_crm_dashboard_stats(society_id):
    """Get comprehensive CRM dashboard statistics"""
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    
    # Contact stats
    total_contacts = Contact.query.filter_by(society_id=society_id).count()
    new_contacts_30d = Contact.query.filter(
        Contact.society_id == society_id,
        Contact.created_at >= thirty_days_ago
    ).count()
    
    hot_leads = Contact.query.filter_by(
        society_id=society_id,
        engagement_level='hot'
    ).count()
    
    # Opportunity stats
    total_opportunities = Opportunity.query.filter_by(society_id=society_id).count()
    
    open_opportunities = Opportunity.query.filter(
        Opportunity.society_id == society_id,
        Opportunity.stage.in_(['prospecting', 'qualification', 'proposal', 'negotiation'])
    ).all()
    
    total_pipeline_value = sum(
        float(opp.value) if opp.value else 0.0 
        for opp in open_opportunities
    )
    
    won_opportunities = Opportunity.query.filter_by(
        society_id=society_id,
        stage='closed_won'
    ).count()
    
    # Activity stats
    activities_30d = CRMActivity.query.join(Contact).filter(
        Contact.society_id == society_id,
        CRMActivity.created_at >= thirty_days_ago
    ).count()
    
    pending_activities = CRMActivity.query.join(Contact).filter(
        Contact.society_id == society_id,
        CRMActivity.completed == False
    ).count()
    
    return {
        'contacts': {
            'total': total_contacts,
            'new_30d': new_contacts_30d,
            'hot_leads': hot_leads
        },
        'opportunities': {
            'total': total_opportunities,
            'open': len(open_opportunities),
            'won': won_opportunities,
            'pipeline_value': total_pipeline_value
        },
        'activities': {
            'last_30d': activities_30d,
            'pending': pending_activities
        }
    }


def get_top_performing_sources(society_id, limit=5):
    """Get top sources for contacts/conversions"""
    sources = db.session.query(
        Contact.source,
        func.count(Contact.id).label('count'),
        func.sum(func.case([(Contact.status == 'converted', 1)], else_=0)).label('conversions')
    ).filter(
        Contact.society_id == society_id,
        Contact.source != None
    ).group_by(Contact.source).order_by(desc('count')).limit(limit).all()
    
    results = []
    for source, count, conversions in sources:
        conversion_rate = (conversions / count * 100) if count > 0 else 0
        results.append({
            'source': source,
            'count': count,
            'conversions': conversions,
            'conversion_rate': conversion_rate
        })
    
    return results
