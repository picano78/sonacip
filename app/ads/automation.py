"""
Automated Advertising System
Handles ad rotation, targeting, and performance analytics
"""
from datetime import datetime, timezone, timedelta
from app import db
from app.models import AdCampaign, AdCreative, User
from sqlalchemy import func, case
import logging
import random

logger = logging.getLogger(__name__)


def rotate_ads_autopilot():
    """
    Automated task to manage ad campaign rotation based on performance
    Should be run hourly via cron or celery beat
    """
    try:
        # Find active campaigns with autopilot enabled
        campaigns = AdCampaign.query.filter(
            AdCampaign.is_active.is_(True),
            AdCampaign.autopilot.is_(True)
        ).all()
        
        updated_count = 0
        for campaign in campaigns:
            # Check budget
            if campaign.budget_cents and campaign.spend_cents >= campaign.budget_cents:
                campaign.is_active = False
                db.session.add(campaign)
                logger.info(f"Campaign {campaign.id} deactivated: budget exhausted")
                updated_count += 1
                continue
            
            # Check end date
            if campaign.ends_at and campaign.ends_at < datetime.now(timezone.utc):
                campaign.is_active = False
                db.session.add(campaign)
                logger.info(f"Campaign {campaign.id} deactivated: end date reached")
                updated_count += 1
                continue
            
            # Check max impressions/clicks
            from app.models import AdEvent
            
            if campaign.max_impressions:
                total_impressions = AdEvent.query.filter(
                    AdEvent.campaign_id == campaign.id,
                    AdEvent.event_type == 'impression'
                ).count()
                
                if total_impressions >= campaign.max_impressions:
                    campaign.is_active = False
                    db.session.add(campaign)
                    logger.info(f"Campaign {campaign.id} deactivated: max impressions reached")
                    updated_count += 1
                    continue
            
            if campaign.max_clicks:
                total_clicks = AdEvent.query.filter(
                    AdEvent.campaign_id == campaign.id,
                    AdEvent.event_type == 'click'
                ).count()
                
                if total_clicks >= campaign.max_clicks:
                    campaign.is_active = False
                    db.session.add(campaign)
                    logger.info(f"Campaign {campaign.id} deactivated: max clicks reached")
                    updated_count += 1
                    continue
        
        if updated_count > 0:
            db.session.commit()
            logger.info(f"Rotated {updated_count} ad campaigns")
        
        return updated_count
        
    except Exception as e:
        logger.error(f"Error rotating ads: {e}")
        db.session.rollback()
        return 0


def calculate_ad_performance():
    """
    Automated task to calculate ad performance metrics
    Should be run daily via cron or celery beat
    """
    try:
        from app.models import AdEvent
        
        # Get performance for each active campaign
        campaigns = AdCampaign.query.filter(
            AdCampaign.is_active.is_(True)
        ).all()
        
        performance_data = []
        
        for campaign in campaigns:
            # Count impressions and clicks
            impressions = AdEvent.query.filter(
                AdEvent.campaign_id == campaign.id,
                AdEvent.event_type == 'impression'
            ).count()
            
            clicks = AdEvent.query.filter(
                AdEvent.campaign_id == campaign.id,
                AdEvent.event_type == 'click'
            ).count()
            
            # Calculate CTR (Click-Through Rate)
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            
            # Calculate CPM (Cost Per Mille - cost per 1000 impressions)
            spend = (campaign.spend_cents or 0) / 100.0
            cpm = (spend / impressions * 1000) if impressions > 0 else 0
            
            # Calculate CPC (Cost Per Click)
            cpc = (spend / clicks) if clicks > 0 else 0
            
            performance = {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'impressions': impressions,
                'clicks': clicks,
                'ctr': round(ctr, 2),
                'spend': spend,
                'cpm': round(cpm, 2),
                'cpc': round(cpc, 2),
                'budget': (campaign.budget_cents or 0) / 100.0,
                'budget_used_percent': round(
                    (spend / ((campaign.budget_cents or 1) / 100.0) * 100), 2
                ) if campaign.budget_cents else 0
            }
            
            performance_data.append(performance)
        
        logger.info(f"Calculated performance for {len(performance_data)} campaigns")
        return performance_data
        
    except Exception as e:
        logger.error(f"Error calculating ad performance: {e}")
        return []


def optimize_ad_targeting():
    """
    Automated task to optimize ad targeting based on performance
    Should be run daily via cron or celery beat
    """
    try:
        from app.models import AdEvent
        
        campaigns = AdCampaign.query.filter(
            AdCampaign.is_active.is_(True),
            AdCampaign.autopilot.is_(True)
        ).all()
        
        optimized_count = 0
        
        for campaign in campaigns:
            # Get performance by placement
            placements = db.session.query(
                AdEvent.placement,
                func.sum(case((AdEvent.event_type == 'impression', 1), else_=0)).label('impressions'),
                func.sum(case((AdEvent.event_type == 'click', 1), else_=0)).label('clicks')
            ).filter(
                AdEvent.campaign_id == campaign.id
            ).group_by(AdEvent.placement).all()
            
            if not placements:
                continue
            
            # Find best performing placement
            best_placement = None
            best_ctr = 0
            
            for placement, impressions, clicks in placements:
                if impressions > 0:
                    ctr = (clicks / impressions) * 100
                    if ctr > best_ctr:
                        best_ctr = ctr
                        best_placement = placement
            
            # If we found a significantly better placement, update creatives
            if best_placement and best_ctr > 2.0:  # Minimum 2% CTR
                creatives = AdCreative.query.filter_by(campaign_id=campaign.id).all()
                for creative in creatives:
                    if creative.placement != best_placement:
                        # Could create new creative for best placement
                        # or adjust weights
                        creative.weight = max(10, creative.weight - 10)
                        db.session.add(creative)
                        optimized_count += 1
        
        if optimized_count > 0:
            db.session.commit()
            logger.info(f"Optimized targeting for {optimized_count} creatives")
        
        return optimized_count
        
    except Exception as e:
        logger.error(f"Error optimizing ad targeting: {e}")
        db.session.rollback()
        return 0


def select_ad_for_placement(placement, society_id=None, user=None):
    """
    Smart ad selection algorithm based on targeting and performance
    
    Args:
        placement: Ad placement location (e.g., 'feed_inline', 'sidebar', 'banner')
        society_id: Optional society ID for targeted ads
        user: Optional user object for personalized targeting
    
    Returns:
        AdCreative object or None
    """
    try:
        # Build query for active creatives in this placement
        query = AdCreative.query.join(AdCampaign).filter(
            AdCampaign.is_active.is_(True),
            AdCreative.is_active.is_(True),
            AdCreative.placement == placement
        )
        
        # Society targeting
        if society_id:
            query = query.filter(
                db.or_(
                    AdCampaign.society_id == society_id,
                    AdCampaign.society_id == None  # General ads
                )
            )
        else:
            # Only general ads if no society context
            query = query.filter(AdCampaign.society_id == None)
        
        # Check budget constraints
        query = query.filter(
            db.or_(
                AdCampaign.budget_cents == None,
                AdCampaign.spend_cents < AdCampaign.budget_cents
            )
        )
        
        # Get all eligible creatives
        creatives = query.all()
        
        if not creatives:
            return None
        
        # Weight-based selection
        total_weight = sum(c.weight or 100 for c in creatives)
        if total_weight == 0:
            return random.choice(creatives)
        
        # Random selection based on weights
        rand = random.uniform(0, total_weight)
        current = 0
        
        for creative in creatives:
            current += (creative.weight or 100)
            if rand <= current:
                return creative
        
        return creatives[0]  # Fallback
        
    except Exception as e:
        logger.error(f"Error selecting ad: {e}")
        return None


def generate_ad_report(campaign_id, start_date=None, end_date=None):
    """
    Generate detailed performance report for a campaign
    
    Args:
        campaign_id: Campaign ID
        start_date: Optional start date for report
        end_date: Optional end date for report
    
    Returns:
        dict with performance metrics
    """
    try:
        from app.models import AdEvent
        
        campaign = AdCampaign.query.get(campaign_id)
        if not campaign:
            return None
        
        # Build query with date filters
        query = AdEvent.query.filter(AdEvent.campaign_id == campaign_id)
        
        if start_date:
            query = query.filter(AdEvent.timestamp >= start_date)
        if end_date:
            query = query.filter(AdEvent.timestamp <= end_date)
        
        # Count events by type
        impressions = query.filter(AdEvent.event_type == 'impression').count()
        clicks = query.filter(AdEvent.event_type == 'click').count()
        
        # Performance by placement
        by_placement = db.session.query(
            AdEvent.placement,
            func.sum(case((AdEvent.event_type == 'impression', 1), else_=0)).label('impressions'),
            func.sum(case((AdEvent.event_type == 'click', 1), else_=0)).label('clicks')
        ).filter(
            AdEvent.campaign_id == campaign_id
        )
        
        if start_date:
            by_placement = by_placement.filter(AdEvent.timestamp >= start_date)
        if end_date:
            by_placement = by_placement.filter(AdEvent.timestamp <= end_date)
        
        by_placement = by_placement.group_by(AdEvent.placement).all()
        
        # Calculate metrics
        spend = (campaign.spend_cents or 0) / 100.0
        ctr = (clicks / impressions * 100) if impressions > 0 else 0
        cpm = (spend / impressions * 1000) if impressions > 0 else 0
        cpc = (spend / clicks) if clicks > 0 else 0
        
        report = {
            'campaign_id': campaign.id,
            'campaign_name': campaign.name,
            'date_range': {
                'start': start_date.isoformat() if start_date else None,
                'end': end_date.isoformat() if end_date else None
            },
            'totals': {
                'impressions': impressions,
                'clicks': clicks,
                'spend': spend,
                'budget': (campaign.budget_cents or 0) / 100.0
            },
            'metrics': {
                'ctr': round(ctr, 2),
                'cpm': round(cpm, 2),
                'cpc': round(cpc, 2)
            },
            'by_placement': [
                {
                    'placement': p,
                    'impressions': i,
                    'clicks': c,
                    'ctr': round((c / i * 100) if i > 0 else 0, 2)
                }
                for p, i, c in by_placement
            ]
        }
        
        return report
        
    except Exception as e:
        logger.error(f"Error generating ad report: {e}")
        return None
