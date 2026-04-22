"""Automation execution utilities"""
import json
import time
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from flask import current_app
from app import db, mail
from app.models import Automation, AutomationRule, AutomationRun, Notification, User
from app.automation.validation import evaluate_condition, validate_action_schema
from flask_mail import Message
from jinja2 import Template
from urllib.parse import urlparse
import ipaddress
import socket

# SSRF Protection
BLOCKED_SCHEMES = ['file', 'ftp', 'gopher', 'data', 'javascript']
BLOCKED_NETWORKS = [
    ipaddress.ip_network('127.0.0.0/8'),      # Localhost
    ipaddress.ip_network('10.0.0.0/8'),       # Private
    ipaddress.ip_network('172.16.0.0/12'),    # Private
    ipaddress.ip_network('192.168.0.0/16'),   # Private
    ipaddress.ip_network('169.254.0.0/16'),   # Link-local
    ipaddress.ip_network('::1/128'),          # IPv6 localhost
    ipaddress.ip_network('fc00::/7'),         # IPv6 private
    ipaddress.ip_network('fe80::/10'),        # IPv6 link-local
]


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
            auto.last_executed_at = datetime.now(timezone.utc)
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
    # Accept both legacy underscore and dot-separated event types.
    candidates = {event_type}
    candidates.add(event_type.replace('_', '.'))
    candidates.add(event_type.replace('.', '_'))
    rules = AutomationRule.query.filter(AutomationRule.event_type.in_(list(candidates)), AutomationRule.is_active == True).all()
    executed_runs: List[AutomationRun] = []

    for rule in rules:
        # Check condition first
        try:
            if rule.condition and not evaluate_condition(rule.condition, payload):
                run = AutomationRun(
                    rule_id=rule.id,
                    status='skipped',
                    payload=json.dumps(payload),
                    completed_at=datetime.now(timezone.utc)
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
            run.completed_at = datetime.now(timezone.utc)
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
            run.completed_at = datetime.now(timezone.utc)
        except Exception as exc:
            run.status = 'failed'
            run.error_message = str(exc)
            run.completed_at = datetime.now(timezone.utc)
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
                run.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
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


def _render_template(value: Any, payload: Dict[str, Any]) -> Any:
    """Render strings using either Jinja2 ({{ }}) or str.format ({key})."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    s = value
    try:
        if "{{" in s and "}}" in s:
            return Template(s).render(**payload)
    except Exception:
        # Fall back to .format
        pass
    try:
        class _SafeDict(dict):
            def __missing__(self, key):
                return "{" + key + "}"
        return s.format_map(_SafeDict(payload))
    except Exception:
        return s


def _resolve_int(value: Any, payload: Dict[str, Any]) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        rendered = _render_template(value, payload)
        try:
            return int(str(rendered).strip())
        except Exception:
            return None
    return None


def _action_notify(action: Dict[str, Any], payload: Dict[str, Any]):
    user_id = _resolve_int(action.get('user_id'), payload)
    if not user_id:
        return
    notification = Notification(
        user_id=user_id,
        title=_render_template(action.get('title') or 'Automazione', payload),
        message=_render_template(action.get('message') or str(payload), payload),
        notification_type='automation'
    )
    db.session.add(notification)


def _action_email(action: Dict[str, Any], payload: Dict[str, Any]):
    to_user_id = _resolve_int(action.get('user_id'), payload)
    subject = _render_template(action.get('subject') or 'Automazione', payload)
    body = _render_template(action.get('body') or json.dumps(payload), payload)
    if not to_user_id:
        return
    user = db.session.get(User, to_user_id)
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
    user_id = _resolve_int(action.get('user_id'), payload)
    content = _render_template(action.get('content') or f"Aggiornamento automatico: {payload}", payload)
    if not user_id:
        return
    user = db.session.get(User, user_id)
    if not user:
        return
    post = Post(user_id=user.id, content=content, is_public=True)
    db.session.add(post)


def _validate_webhook_url(url: str) -> None:
    """Validate webhook URL to prevent SSRF attacks."""
    if not url or not isinstance(url, str):
        raise ValueError("Invalid webhook URL")
    
    parsed = urlparse(url)
    
    # Check scheme
    if parsed.scheme.lower() in BLOCKED_SCHEMES:
        raise ValueError(f"Scheme '{parsed.scheme}' not allowed")
    
    if parsed.scheme.lower() not in ['http', 'https']:
        raise ValueError("Only HTTP/HTTPS allowed for webhooks")
    
    # Check hostname
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid hostname in webhook URL")
    
    # Prevent localhost/private IPs
    try:
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for info in addr_info:
            ip_str = info[4][0]
            try:
                ip = ipaddress.ip_address(ip_str.split('%')[0])  # Handle IPv6 scope
                for network in BLOCKED_NETWORKS:
                    if ip in network:
                        raise ValueError(f"Webhook URL resolves to blocked IP range: {ip}")
            except ValueError as e:
                if 'blocked' in str(e).lower():
                    raise
                continue
    except socket.gaierror as e:
        raise ValueError(f"Cannot resolve hostname '{hostname}': {e}")


def _action_webhook(action: Dict[str, Any], payload: Dict[str, Any]):
    """Send webhook HTTP request with SSRF protection."""
    import requests
    
    url = action.get('url')
    if not url:
        raise ValueError("Webhook URL required")
    
    # SECURITY: Validate URL before making request
    _validate_webhook_url(url)
    
    method = action.get('method', 'POST').upper()
    headers = action.get('headers', {})
    timeout = min(action.get('timeout', 30), 60)  # Max 60 seconds
    
    headers.setdefault('Content-Type', 'application/json')
    headers.setdefault('User-Agent', 'SONACIP-Automation/1.0')
    
    try:
        if method == 'POST':
            response = requests.post(url, json=payload, headers=headers, timeout=timeout, allow_redirects=False)
        elif method == 'GET':
            response = requests.get(url, params=payload, headers=headers, timeout=timeout, allow_redirects=False)
        else:
            raise ValueError(f"Unsupported webhook method: {method}")
        
        response.raise_for_status()
        current_app.logger.info(f"Webhook sent successfully", extra={'url': url, 'status': response.status_code})
    except requests.RequestException as exc:
        current_app.logger.error(f"Webhook failed: {exc}", extra={'url': url, 'error': str(exc)})
        raise


def _action_task_create(action: Dict[str, Any], payload: Dict[str, Any]):
    """Create a task from automation."""
    from app.models import Task
    
    task = Task(
        title=_render_template(action.get('title'), payload),
        description=_render_template(action.get('description', ''), payload),
        assigned_to=_resolve_int(action.get('assigned_to'), payload),
        status=action.get('status', 'todo'),
        priority=action.get('priority', 'medium'),
        due_date=action.get('due_date'),
        created_by=_resolve_int(action.get('created_by'), payload),
        project_id=_resolve_int(action.get('project_id'), payload),
    )
    db.session.add(task)
    current_app.logger.info(
        f"Task created via automation: {task.title}",
        extra={'task_title': task.title, 'assigned_to': task.assigned_to}
    )


