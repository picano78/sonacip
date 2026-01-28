"""Automation execution utilities"""
import json
import time
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from flask import current_app
from app import db, mail
from app.models import Automation, AutomationRule, AutomationRun, Notification, User
from app.automation.validation import evaluate_condition, validate_action_schema
from flask_mail import Message


def execute_automations(trigger_type, society_id=None, payload=None):
    """Legacy automations (Automation model)."""
    if not trigger_type:
        return []

    query = Automation.query.filter_by(trigger_type=trigger_type, is_active=True)
    if society_id:
        query = query.filter_by(society_id=society_id)

    automations = query.all()
    executed = []

    for auto in automations:
        try:
            auto.execution_count = (auto.execution_count or 0) + 1
            auto.last_executed_at = datetime.utcnow()
            auto.success_count = (auto.success_count or 0) + 1
            executed.append(auto)
        except Exception as exc:
            auto.failure_count = (auto.failure_count or 0) + 1
            auto.last_error = str(exc)
            db.session.add(auto)
    if executed:
        db.session.commit()
    return executed


def execute_rules(event_type: str, payload: Dict[str, Any] = None):
    """Execute AutomationRule actions with audit in AutomationRun."""
    if not event_type:
        return []
    payload = payload or {}
    rules = AutomationRule.query.filter_by(event_type=event_type, is_active=True).all()
    executed_runs: List[AutomationRun] = []

    for rule in rules:
        # Check condition first
        try:
            if rule.condition and not evaluate_condition(rule.condition, payload):
                run = AutomationRun(
                    rule_id=rule.id,
                    status='skipped',
                    payload=json.dumps(payload),
                    completed_at=datetime.utcnow()
                )
                db.session.add(run)
                executed_runs.append(run)
                continue
        except Exception as exc:
            current_app.logger.error(
                f"Condition evaluation failed for rule {rule.id}: {exc}",
                extra={'rule_id': rule.id, 'event_type': event_type, 'error': str(exc)}
            )
            # Continue with execution on condition error
        
        run = AutomationRun(rule_id=rule.id, status='success', payload=json.dumps(payload))
        try:
            actions = json.loads(rule.actions) if rule.actions else []
        except Exception as exc:
            run.status = 'failed'
            run.error_message = f'Invalid JSON: {str(exc)}'
            run.completed_at = datetime.utcnow()
            db.session.add(run)
            executed_runs.append(run)
            current_app.logger.error(
                f"Invalid actions JSON for rule {rule.id}",
                extra={'rule_id': rule.id, 'error': str(exc)}
            )
            continue

        try:
            normalized_actions = actions if isinstance(actions, list) else [actions] if actions else []
            _apply_actions_with_retry(rule, normalized_actions, payload, run)
            run.completed_at = datetime.utcnow()
        except Exception as exc:
            run.status = 'failed'
            run.error_message = str(exc)
            run.completed_at = datetime.utcnow()
            current_app.logger.error(
                f"Action execution failed for rule {rule.id}: {exc}",
                extra={
                    'rule_id': rule.id,
                    'event_type': event_type,
                    'error': str(exc),
                    'traceback': traceback.format_exc()
                }
            )
        db.session.add(run)
        executed_runs.append(run)

    if executed_runs:
        db.session.commit()
    return executed_runs


def _apply_actions_with_retry(rule: AutomationRule, actions: List[Dict[str, Any]], 
                                payload: Dict[str, Any], run: AutomationRun):
    """Apply actions with exponential backoff retry logic."""
    max_retries = getattr(rule, 'max_retries', 3)
    base_delay = getattr(rule, 'retry_delay', 60)
    
    for attempt in range(max_retries + 1):
        try:
            _apply_actions(actions, payload)
            return  # Success
        except Exception as exc:
            if attempt < max_retries:
                # Calculate exponential backoff
                delay = base_delay * (2 ** attempt)
                run.retry_count = attempt + 1
                run.status = 'retrying'
                run.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
                run.error_message = f"Attempt {attempt + 1} failed: {str(exc)}"
                db.session.flush()
                
                current_app.logger.warning(
                    f"Rule {rule.id} action failed, retry {attempt + 1}/{max_retries} in {delay}s",
                    extra={
                        'rule_id': rule.id,
                        'attempt': attempt + 1,
                        'delay': delay,
                        'error': str(exc)
                    }
                )
                time.sleep(delay)
            else:
                # Max retries exhausted
                raise


def _apply_actions(actions: List[Dict[str, Any]], payload: Dict[str, Any]):
    """Apply automation actions with validation."""
    for action in actions:
        # Validate action schema
        is_valid, error = validate_action_schema(action)
        if not is_valid:
            raise ValueError(f"Invalid action: {error}")
        
        atype = action.get('type') if isinstance(action, dict) else None
        if atype == 'notify':
            _action_notify(action, payload)
        elif atype == 'email':
            _action_email(action, payload)
        elif atype == 'social_post':
            _action_social_post(action, payload)
        elif atype == 'webhook':
            _action_webhook(action, payload)
        elif atype == 'task_create':
            _action_task_create(action, payload)


def _action_notify(action: Dict[str, Any], payload: Dict[str, Any]):
    user_id = action.get('user_id')
    if not user_id:
        return
    notification = Notification(
        user_id=user_id,
        title=action.get('title') or 'Automazione',
        message=action.get('message') or str(payload),
        notification_type='automation'
    )
    db.session.add(notification)


def _action_email(action: Dict[str, Any], payload: Dict[str, Any]):
    to_user_id = action.get('user_id')
    subject = action.get('subject') or 'Automazione'
    body = action.get('body') or json.dumps(payload)
    if not to_user_id:
        return
    user = User.query.get(to_user_id)
    if not user or not user.email:
        return
    try:
        msg = Message(subject=subject, recipients=[user.email], body=body)
        mail.send(msg)
    except Exception as exc:
        current_app.logger.warning(f"Invio email automazione fallito: {exc}")
        raise


def _action_social_post(action: Dict[str, Any], payload: Dict[str, Any]):
    from app.models import Post
    user_id = action.get('user_id')
    content = action.get('content') or f"Aggiornamento automatico: {payload}"
    if not user_id:
        return
    user = User.query.get(user_id)
    if not user:
        return
    post = Post(user_id=user.id, content=content, is_public=True)
    db.session.add(post)


def _action_webhook(action: Dict[str, Any], payload: Dict[str, Any]):
    """Send webhook HTTP request."""
    import requests
    url = action.get('url')
    method = action.get('method', 'POST').upper()
    headers = action.get('headers', {})
    timeout = action.get('timeout', 30)
    
    headers.setdefault('Content-Type', 'application/json')
    headers.setdefault('User-Agent', 'SONACIP-Automation/1.0')
    
    try:
        if method == 'POST':
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
        elif method == 'GET':
            response = requests.get(url, params=payload, headers=headers, timeout=timeout)
        else:
            raise ValueError(f"Unsupported webhook method: {method}")
        
        response.raise_for_status()
        current_app.logger.info(
            f"Webhook sent successfully to {url}",
            extra={'url': url, 'status': response.status_code}
        )
    except requests.RequestException as exc:
        current_app.logger.error(
            f"Webhook failed to {url}: {exc}",
            extra={'url': url, 'error': str(exc)}
        )
        raise


def _action_task_create(action: Dict[str, Any], payload: Dict[str, Any]):
    """Create a task from automation."""
    from app.models import Task
    
    task = Task(
        title=action.get('title'),
        description=action.get('description', ''),
        assigned_to=action.get('assigned_to'),
        status=action.get('status', 'todo'),
        priority=action.get('priority', 'medium'),
        due_date=action.get('due_date'),
        created_by=action.get('created_by'),
        project_id=action.get('project_id')
    )
    db.session.add(task)
    current_app.logger.info(
        f"Task created via automation: {task.title}",
        extra={'task_title': task.title, 'assigned_to': task.assigned_to}
    )
