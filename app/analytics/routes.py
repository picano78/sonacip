"""
Analytics and Business Intelligence Routes
Power BI / Tableau level insights
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, desc, and_, or_
from app import db
from app.models import (
    Analytics, User, Post, Event, Contact, Opportunity,
    Task, Project, Subscription, Payment
)
from app.utils import admin_required, permission_required
from datetime import datetime, timedelta
import json

bp = Blueprint('analytics', __name__, url_prefix='/analytics')


@bp.route('/')
@login_required
@permission_required('analytics', 'access')
def dashboard():
    """Advanced analytics dashboard"""
    
    # Time range
    days = int(request.args.get('days', 30))
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # User analytics
    user_stats = get_user_analytics(start_date)
    
    # CRM analytics
    crm_stats = get_crm_analytics(start_date)
    
    # Social analytics
    social_stats = get_social_analytics(start_date)
    
    # Task/Project analytics
    task_stats = get_task_analytics(start_date)
    
    # Financial analytics
    financial_stats = get_financial_analytics(start_date)
    
    return render_template('analytics/dashboard.html',
                         user_stats=user_stats,
                         crm_stats=crm_stats,
                         social_stats=social_stats,
                         task_stats=task_stats,
                         financial_stats=financial_stats,
                         days=days)


@bp.route('/crm')
@login_required
@permission_required('analytics', 'access')
def crm_analytics():
    """CRM-specific analytics (Salesforce-level insights)"""
    
    # Sales pipeline
    pipeline_data = get_pipeline_analysis()
    
    # Sales forecast
    forecast_data = get_sales_forecast()
    
    # Conversion rates
    conversion_data = get_conversion_rates()
    
    # Top performers
    top_contacts = get_top_contacts()
    top_opportunities = get_top_opportunities()
    
    # Win/Loss analysis
    win_loss_data = get_win_loss_analysis()
    
    return render_template('analytics/crm.html',
                         pipeline=pipeline_data,
                         forecast=forecast_data,
                         conversion=conversion_data,
                         top_contacts=top_contacts,
                         top_opportunities=top_opportunities,
                         win_loss=win_loss_data)


@bp.route('/social')
@login_required
@permission_required('analytics', 'access')
def social_analytics():
    """Social network analytics (LinkedIn/Instagram Insights level)"""
    
    # Engagement metrics
    engagement = get_engagement_metrics()
    
    # Top posts
    top_posts = Post.query.filter(
        Post.created_at >= datetime.utcnow() - timedelta(days=30)
    ).order_by(desc(Post.likes_count)).limit(10).all()
    
    # User growth
    growth_data = get_user_growth_data()
    
    # Engagement trends
    trends = get_engagement_trends()
    
    return render_template('analytics/social.html',
                         engagement=engagement,
                         top_posts=top_posts,
                         growth=growth_data,
                         trends=trends)


@bp.route('/tasks')
@login_required
@permission_required('analytics', 'access')
def task_analytics():
    """Task and project analytics (Monday.com Insights level)"""
    
    # Project stats
    project_stats = get_project_stats()
    
    # Team performance
    team_performance = get_team_performance()
    
    # Task completion trends
    completion_trends = get_completion_trends()
    
    # Burndown chart data
    burndown_data = get_burndown_data()
    
    # Time tracking
    time_stats = get_time_tracking_stats()
    
    return render_template('analytics/tasks.html',
                         projects=project_stats,
                         team=team_performance,
                         trends=completion_trends,
                         burndown=burndown_data,
                         time=time_stats)


@bp.route('/export')
@login_required
@permission_required('analytics', 'access')
def export_data():
    """Export analytics data (CSV, Excel, PDF)"""
    export_type = request.args.get('type', 'csv')
    data_category = request.args.get('category', 'users')
    
    # Generate export based on category
    if data_category == 'users':
        data = export_user_data()
    elif data_category == 'crm':
        data = export_crm_data()
    elif data_category == 'social':
        data = export_social_data()
    elif data_category == 'tasks':
        data = export_task_data()
    else:
        flash('Invalid export category.', 'danger')
        return redirect(url_for('analytics.dashboard'))
    
    # Format and send file
    if export_type == 'csv':
        return send_csv_export(data, data_category)
    elif export_type == 'excel':
        return send_excel_export(data, data_category)
    elif export_type == 'pdf':
        return send_pdf_export(data, data_category)
    
    flash('Export completed!', 'success')
    return redirect(url_for('analytics.dashboard'))


# Analytics calculation functions

def get_user_analytics(start_date):
    """Calculate user-related analytics"""
    total_users = User.query.count()
    new_users = User.query.filter(User.created_at >= start_date).count()
    active_users = User.query.filter(User.last_seen >= start_date).count()
    
    # By role
    by_role = db.session.query(
        User.role,
        func.count(User.id)
    ).group_by(User.role).all()
    
    # Growth rate
    previous_period = datetime.utcnow() - timedelta(days=60)
    previous_users = User.query.filter(User.created_at < start_date, User.created_at >= previous_period).count()
    growth_rate = ((new_users - previous_users) / previous_users * 100) if previous_users > 0 else 0
    
    return {
        'total': total_users,
        'new': new_users,
        'active': active_users,
        'by_role': dict(by_role),
        'growth_rate': round(growth_rate, 2)
    }


def get_crm_analytics(start_date):
    """Calculate CRM analytics"""
    total_contacts = Contact.query.count()
    new_contacts = Contact.query.filter(Contact.created_at >= start_date).count()
    
    total_opportunities = Opportunity.query.count()
    won_opportunities = Opportunity.query.filter_by(stage='closed_won').count()
    lost_opportunities = Opportunity.query.filter_by(stage='closed_lost').count()
    
    # Pipeline value (opportunities not closed)
    pipeline_value = db.session.query(
        func.sum(Opportunity.weighted_value)
    ).filter(
        Opportunity.stage.notin_(['closed_won', 'closed_lost'])
    ).scalar() or 0
    
    # Win rate
    total_closed = won_opportunities + lost_opportunities
    win_rate = (won_opportunities / total_closed * 100) if total_closed > 0 else 0
    
    return {
        'total_contacts': total_contacts,
        'new_contacts': new_contacts,
        'total_opportunities': total_opportunities,
        'won': won_opportunities,
        'lost': lost_opportunities,
        'pipeline_value': round(pipeline_value, 2),
        'win_rate': round(win_rate, 2)
    }


def get_social_analytics(start_date):
    """Calculate social network analytics"""
    total_posts = Post.query.count()
    new_posts = Post.query.filter(Post.created_at >= start_date).count()
    
    # Engagement
    total_likes = db.session.query(func.count()).select_from(Post).filter(
        Post.created_at >= start_date
    ).scalar() or 0
    
    # Average engagement per post
    avg_engagement = total_likes / new_posts if new_posts > 0 else 0
    
    return {
        'total_posts': total_posts,
        'new_posts': new_posts,
        'total_likes': total_likes,
        'avg_engagement': round(avg_engagement, 2)
    }


def get_task_analytics(start_date):
    """Calculate task/project analytics"""
    total_tasks = Task.query.count()
    completed_tasks = Task.query.filter_by(status='done').count()
    overdue_tasks = Task.query.filter(
        Task.status != 'done',
        Task.due_date < datetime.utcnow()
    ).count()
    
    # Completion rate
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    total_projects = Project.query.count()
    active_projects = Project.query.filter_by(status='active').count()
    
    return {
        'total_tasks': total_tasks,
        'completed': completed_tasks,
        'overdue': overdue_tasks,
        'completion_rate': round(completion_rate, 2),
        'total_projects': total_projects,
        'active_projects': active_projects
    }


def get_financial_analytics(start_date):
    """Calculate financial analytics"""
    # Subscription revenue
    active_subscriptions = Subscription.query.filter_by(status='active').count()
    
    # Monthly recurring revenue (MRR)
    mrr = db.session.query(
        func.sum(Subscription.amount)
    ).filter(
        Subscription.status == 'active',
        Subscription.billing_cycle == 'monthly'
    ).scalar() or 0
    
    # Total revenue from payments
    total_revenue = db.session.query(
        func.sum(Payment.amount)
    ).filter(
        Payment.status == 'completed',
        Payment.created_at >= start_date
    ).scalar() or 0
    
    return {
        'active_subscriptions': active_subscriptions,
        'mrr': round(mrr, 2),
        'revenue': round(total_revenue, 2)
    }


def get_pipeline_analysis():
    """Analyze sales pipeline by stage"""
    pipeline = db.session.query(
        Opportunity.stage,
        func.count(Opportunity.id).label('count'),
        func.sum(Opportunity.weighted_value).label('total_value')
    ).filter(
        Opportunity.stage.notin_(['closed_won', 'closed_lost'])
    ).group_by(Opportunity.stage).all()
    
    return [
        {
            'stage': p[0],
            'count': p[1],
            'value': round(p[2] or 0, 2)
        }
        for p in pipeline
    ]


def get_sales_forecast():
    """Generate sales forecast"""
    # Get opportunities by forecast category
    forecast = db.session.query(
        Opportunity.forecast_category,
        func.sum(Opportunity.weighted_value)
    ).filter(
        Opportunity.stage.notin_(['closed_won', 'closed_lost'])
    ).group_by(Opportunity.forecast_category).all()
    
    return dict(forecast)


def get_conversion_rates():
    """Calculate conversion rates by stage"""
    stages = ['prospecting', 'qualification', 'proposal', 'negotiation']
    conversion = {}
    
    for i in range(len(stages) - 1):
        from_stage = stages[i]
        to_stage = stages[i + 1]
        
        from_count = Opportunity.query.filter_by(stage=from_stage).count()
        to_count = Opportunity.query.filter_by(stage=to_stage).count()
        
        rate = (to_count / from_count * 100) if from_count > 0 else 0
        conversion[f'{from_stage}_to_{to_stage}'] = round(rate, 2)
    
    return conversion


def get_top_contacts():
    """Get top-performing contacts"""
    # Contacts with most opportunities won
    return db.session.query(
        Contact,
        func.count(Opportunity.id).label('won_count')
    ).join(
        Opportunity
    ).filter(
        Opportunity.stage == 'closed_won'
    ).group_by(Contact.id).order_by(desc('won_count')).limit(10).all()


def get_top_opportunities():
    """Get highest-value opportunities"""
    return Opportunity.query.filter(
        Opportunity.stage.notin_(['closed_won', 'closed_lost'])
    ).order_by(desc(Opportunity.weighted_value)).limit(10).all()


def get_win_loss_analysis():
    """Analyze won vs lost opportunities"""
    total_won = Opportunity.query.filter_by(stage='closed_won').count()
    total_lost = Opportunity.query.filter_by(stage='closed_lost').count()
    
    won_value = db.session.query(
        func.sum(Opportunity.weighted_value)
    ).filter_by(stage='closed_won').scalar() or 0
    
    lost_value = db.session.query(
        func.sum(Opportunity.weighted_value)
    ).filter_by(stage='closed_lost').scalar() or 0
    
    return {
        'won_count': total_won,
        'lost_count': total_lost,
        'won_value': round(won_value, 2),
        'lost_value': round(lost_value, 2),
        'win_rate': round((total_won / (total_won + total_lost) * 100) if (total_won + total_lost) > 0 else 0, 2)
    }


# Additional helper functions
def get_engagement_metrics():
    """Calculate social engagement metrics"""
    return {}  # Placeholder


def get_user_growth_data():
    """Get user growth over time"""
    return {}  # Placeholder


def get_engagement_trends():
    """Get engagement trends"""
    return {}  # Placeholder


def get_project_stats():
    """Get project statistics"""
    return {}  # Placeholder


def get_team_performance():
    """Analyze team performance"""
    return {}  # Placeholder


def get_completion_trends():
    """Get task completion trends"""
    return {}  # Placeholder


def get_burndown_data():
    """Generate burndown chart data"""
    return {}  # Placeholder


def get_time_tracking_stats():
    """Get time tracking statistics"""
    return {}  # Placeholder


def export_user_data():
    """Export user data"""
    return {}  # Placeholder


def export_crm_data():
    """Export CRM data"""
    return {}  # Placeholder


def export_social_data():
    """Export social data"""
    return {}  # Placeholder


def export_task_data():
    """Export task data"""
    return {}  # Placeholder


def send_csv_export(data, category):
    """Send CSV export"""
    pass  # Placeholder


def send_excel_export(data, category):
    """Send Excel export"""
    pass  # Placeholder


def send_pdf_export(data, category):
    """Send PDF export"""
    pass  # Placeholder
