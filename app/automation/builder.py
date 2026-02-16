"""
Visual Automation Builder
Provides a user-friendly interface for creating automation rules
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import AutomationRule
from app.utils import check_permission
import json

automation_builder = Blueprint('automation_builder', __name__, url_prefix='/automation/builder')


@automation_builder.route('/')
@login_required
def index():
    """Automation builder dashboard"""
    if not check_permission(current_user, 'admin', 'manage_automations'):
        flash('You do not have permission to manage automations.', 'danger')
        return redirect(url_for('main.index'))
    
    rules = AutomationRule.query.filter_by(created_by=current_user.id).order_by(
        AutomationRule.created_at.desc()
    ).all()
    
    return render_template('automation/builder/index.html', rules=rules)


@automation_builder.route('/create')
@login_required
def create():
    """Visual automation rule builder"""
    if not check_permission(current_user, 'admin', 'manage_automations'):
        flash('You do not have permission to create automations.', 'danger')
        return redirect(url_for('main.index'))
    
    return render_template('automation/builder/create.html')


@automation_builder.route('/edit/<int:rule_id>')
@login_required
def edit(rule_id):
    """Edit existing automation rule"""
    rule = AutomationRule.query.get_or_404(rule_id)
    
    if not check_permission(current_user, 'admin', 'manage_automations') and rule.created_by != current_user.id:
        flash('You do not have permission to edit this automation.', 'danger')
        return redirect(url_for('automation_builder.index'))
    
    return render_template('automation/builder/edit.html', rule=rule)


@automation_builder.route('/api/event-types')
@login_required
def get_event_types():
    """Get available event types for triggers"""
    event_types = [
        {'value': 'user.registered', 'label': 'User Registered', 'category': 'Users'},
        {'value': 'user.login', 'label': 'User Login', 'category': 'Users'},
        {'value': 'user.profile_updated', 'label': 'User Profile Updated', 'category': 'Users'},
        
        {'value': 'event.created', 'label': 'Event Created', 'category': 'Events'},
        {'value': 'event.updated', 'label': 'Event Updated', 'category': 'Events'},
        {'value': 'event.upcoming', 'label': 'Event Upcoming', 'category': 'Events'},
        {'value': 'event.athlete_invited', 'label': 'Athlete Invited to Event', 'category': 'Events'},
        {'value': 'event.athlete_accepted', 'label': 'Athlete Accepted Event', 'category': 'Events'},
        {'value': 'event.athlete_rejected', 'label': 'Athlete Rejected Event', 'category': 'Events'},
        
        {'value': 'post.created', 'label': 'Post Created', 'category': 'Social'},
        {'value': 'post.liked', 'label': 'Post Liked', 'category': 'Social'},
        {'value': 'post.commented', 'label': 'Post Commented', 'category': 'Social'},
        {'value': 'user.followed', 'label': 'User Followed', 'category': 'Social'},
        
        {'value': 'payment.received', 'label': 'Payment Received', 'category': 'Payments'},
        {'value': 'payment.failed', 'label': 'Payment Failed', 'category': 'Payments'},
        {'value': 'subscription.created', 'label': 'Subscription Created', 'category': 'Payments'},
        {'value': 'subscription.cancelled', 'label': 'Subscription Cancelled', 'category': 'Payments'},
        
        {'value': 'tournament.created', 'label': 'Tournament Created', 'category': 'Tournaments'},
        {'value': 'match.scheduled', 'label': 'Match Scheduled', 'category': 'Tournaments'},
        {'value': 'match.completed', 'label': 'Match Completed', 'category': 'Tournaments'},
        
        {'value': 'crm.contact_created', 'label': 'Contact Created', 'category': 'CRM'},
        {'value': 'crm.opportunity_created', 'label': 'Opportunity Created', 'category': 'CRM'},
        {'value': 'crm.opportunity_won', 'label': 'Opportunity Won', 'category': 'CRM'},
        {'value': 'crm.opportunity_lost', 'label': 'Opportunity Lost', 'category': 'CRM'},
        
        {'value': 'task.created', 'label': 'Task Created', 'category': 'Tasks'},
        {'value': 'task.completed', 'label': 'Task Completed', 'category': 'Tasks'},
        {'value': 'task.overdue', 'label': 'Task Overdue', 'category': 'Tasks'},
    ]
    
    return jsonify(event_types)


@automation_builder.route('/api/action-types')
@login_required
def get_action_types():
    """Get available action types"""
    action_types = [
        {
            'value': 'notify',
            'label': 'Send Notification',
            'icon': 'bell',
            'fields': [
                {'name': 'user_id', 'type': 'user_select', 'label': 'Recipient', 'required': True},
                {'name': 'title', 'type': 'text', 'label': 'Title', 'required': True},
                {'name': 'message', 'type': 'textarea', 'label': 'Message', 'required': True},
                {'name': 'link', 'type': 'text', 'label': 'Link (optional)', 'required': False}
            ]
        },
        {
            'value': 'email',
            'label': 'Send Email',
            'icon': 'envelope',
            'fields': [
                {'name': 'recipient', 'type': 'email', 'label': 'Recipient Email', 'required': True},
                {'name': 'subject', 'type': 'text', 'label': 'Subject', 'required': True},
                {'name': 'body', 'type': 'textarea', 'label': 'Message', 'required': True},
                {'name': 'html', 'type': 'checkbox', 'label': 'HTML Format', 'required': False}
            ]
        },
        {
            'value': 'sms',
            'label': 'Send SMS',
            'icon': 'mobile',
            'fields': [
                {'name': 'phone', 'type': 'tel', 'label': 'Phone Number', 'required': True, 'placeholder': '+393331234567'},
                {'name': 'message', 'type': 'textarea', 'label': 'Message', 'required': True, 'maxlength': 160}
            ]
        },
        {
            'value': 'social_post',
            'label': 'Create Social Post',
            'icon': 'share',
            'fields': [
                {'name': 'content', 'type': 'textarea', 'label': 'Post Content', 'required': True},
                {'name': 'visibility', 'type': 'select', 'label': 'Visibility', 'options': ['public', 'followers', 'private'], 'required': True}
            ]
        },
        {
            'value': 'webhook',
            'label': 'Call Webhook',
            'icon': 'link',
            'fields': [
                {'name': 'url', 'type': 'url', 'label': 'Webhook URL', 'required': True},
                {'name': 'method', 'type': 'select', 'label': 'HTTP Method', 'options': ['POST', 'GET', 'PUT'], 'required': True},
                {'name': 'headers', 'type': 'json', 'label': 'Headers (JSON)', 'required': False}
            ]
        },
        {
            'value': 'task_create',
            'label': 'Create Task',
            'icon': 'check-square',
            'fields': [
                {'name': 'title', 'type': 'text', 'label': 'Task Title', 'required': True},
                {'name': 'description', 'type': 'textarea', 'label': 'Description', 'required': False},
                {'name': 'assignee_id', 'type': 'user_select', 'label': 'Assign To', 'required': False},
                {'name': 'due_date', 'type': 'date', 'label': 'Due Date', 'required': False}
            ]
        }
    ]
    
    return jsonify(action_types)


@automation_builder.route('/api/save', methods=['POST'])
@login_required
def save_rule():
    """Save automation rule"""
    if not check_permission(current_user, 'admin', 'manage_automations'):
        return jsonify({'error': 'Permission denied'}), 403
    
    data = request.get_json()
    
    try:
        rule_id = data.get('id')
        if rule_id:
            rule = AutomationRule.query.get_or_404(rule_id)
            if rule.created_by != current_user.id and not check_permission(current_user, 'admin', 'access'):
                return jsonify({'error': 'Permission denied'}), 403
        else:
            rule = AutomationRule()
            rule.created_by = current_user.id
        
        rule.name = data.get('name')
        rule.event_type = data.get('event_type')
        rule.condition = data.get('condition')
        rule.actions = json.dumps(data.get('actions', []))
        rule.is_active = data.get('is_active', True)
        rule.max_retries = data.get('max_retries', 3)
        rule.retry_delay = data.get('retry_delay', 60)
        
        # Validate actions
        valid, error = rule.validate_actions()
        if not valid:
            return jsonify({'error': error}), 400
        
        db.session.add(rule)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'rule_id': rule.id,
            'message': 'Automation rule saved successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@automation_builder.route('/api/delete/<int:rule_id>', methods=['DELETE'])
@login_required
def delete_rule(rule_id):
    """Delete automation rule"""
    rule = AutomationRule.query.get_or_404(rule_id)
    
    if rule.created_by != current_user.id and not check_permission(current_user, 'admin', 'access'):
        return jsonify({'error': 'Permission denied'}), 403
    
    try:
        db.session.delete(rule)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Automation rule deleted'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@automation_builder.route('/api/toggle/<int:rule_id>', methods=['POST'])
@login_required
def toggle_rule(rule_id):
    """Toggle automation rule active status"""
    rule = AutomationRule.query.get_or_404(rule_id)
    
    if rule.created_by != current_user.id and not check_permission(current_user, 'admin', 'access'):
        return jsonify({'error': 'Permission denied'}), 403
    
    try:
        rule.is_active = not rule.is_active
        db.session.commit()
        return jsonify({
            'success': True,
            'is_active': rule.is_active,
            'message': f"Automation rule {'activated' if rule.is_active else 'deactivated'}"
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
