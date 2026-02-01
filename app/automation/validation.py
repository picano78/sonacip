"""Automation validation and condition evaluation."""
import json
import re
from typing import Any, Dict, Tuple


def evaluate_condition(condition_str: str, payload: Dict[str, Any]) -> bool:
    """
    Evaluate automation condition against payload.
    
    Supports:
    - Simple equality: "status == 'completed'"
    - Numeric comparison: "score > 10"
    - Contains: "title contains 'urgent'"
    - JSON path: "user.role == 'admin'"
    
    Args:
        condition_str: Condition expression or JSON
        payload: Event payload data
        
    Returns:
        True if condition matches, False otherwise
    """
    if not condition_str or not condition_str.strip():
        return True  # No condition = always execute
    
    try:
        # Try parsing as JSON first for complex conditions
        condition = json.loads(condition_str)
        if isinstance(condition, dict):
            return _evaluate_json_condition(condition, payload)
    except (json.JSONDecodeError, ValueError):
        pass
    
    # Simple expression evaluation
    return _evaluate_simple_expression(condition_str, payload)


def _evaluate_json_condition(condition: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    """Evaluate JSON-based condition (AND/OR logic)."""
    if 'all' in condition:  # AND
        return all(_match_rule(rule, payload) for rule in condition['all'])
    if 'any' in condition:  # OR
        return any(_match_rule(rule, payload) for rule in condition['any'])
    if 'not' in condition:  # NOT
        return not _match_rule(condition['not'], payload)
    return _match_rule(condition, payload)


def _match_rule(rule: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    """Match a single rule against payload."""
    field = rule.get('field')
    operator = rule.get('op', '==')
    value = rule.get('value')
    
    if not field:
        return False
    
    actual = _get_nested_value(payload, field)
    
    if operator == '==':
        return actual == value
    elif operator == '!=':
        return actual != value
    elif operator == '>':
        return float(actual) > float(value)
    elif operator == '>=':
        return float(actual) >= float(value)
    elif operator == '<':
        return float(actual) < float(value)
    elif operator == '<=':
        return float(actual) <= float(value)
    elif operator == 'contains':
        return value in str(actual)
    elif operator == 'in':
        return actual in value
    return False


def _evaluate_simple_expression(expr: str, payload: Dict[str, Any]) -> bool:
    """Evaluate simple string expression like 'status == completed'."""
    # Match patterns like: field op value
    patterns = [
        (r'(\w+(?:\.\w+)*)\s*==\s*["\']([^"\']+)["\']', lambda m: _get_nested_value(payload, m.group(1)) == m.group(2)),
        (r'(\w+(?:\.\w+)*)\s*!=\s*["\']([^"\']+)["\']', lambda m: _get_nested_value(payload, m.group(1)) != m.group(2)),
        (r'(\w+(?:\.\w+)*)\s*>=\s*(\d+(?:\.\d+)?)', lambda m: float(_get_nested_value(payload, m.group(1)) or 0) >= float(m.group(2))),
        (r'(\w+(?:\.\w+)*)\s*<=\s*(\d+(?:\.\d+)?)', lambda m: float(_get_nested_value(payload, m.group(1)) or 0) <= float(m.group(2))),
        (r'(\w+(?:\.\w+)*)\s*>\s*(\d+(?:\.\d+)?)', lambda m: float(_get_nested_value(payload, m.group(1)) or 0) > float(m.group(2))),
        (r'(\w+(?:\.\w+)*)\s*<\s*(\d+(?:\.\d+)?)', lambda m: float(_get_nested_value(payload, m.group(1)) or 0) < float(m.group(2))),
        (r'(\w+(?:\.\w+)*)\s+contains\s+["\']([^"\']+)["\']', lambda m: m.group(2) in str(_get_nested_value(payload, m.group(1)) or '')),
    ]
    
    for pattern, evaluator in patterns:
        match = re.match(pattern, expr.strip(), re.IGNORECASE)
        if match:
            try:
                return evaluator(match)
            except (ValueError, TypeError, AttributeError):
                return False
    
    return False


def _get_nested_value(data: Dict[str, Any], path: str) -> Any:
    """Get nested value from dict using dot notation."""
    keys = path.split('.')
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value


def validate_action_schema(action: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate single action schema.
    
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(action, dict):
        return False, 'Action must be a dictionary'
    
    if 'type' not in action:
        return False, 'Action must have a type'
    
    atype = action['type']
    
    # Type-specific validation
    if atype == 'notify':
        if 'user_id' not in action:
            return False, 'notify action requires user_id'
        if not isinstance(action['user_id'], (int, str)):
            return False, 'notify user_id must be an integer or template string'
    
    elif atype == 'email':
        if 'user_id' not in action:
            return False, 'email action requires user_id'
        if not isinstance(action['user_id'], (int, str)):
            return False, 'email user_id must be an integer or template string'
        if 'subject' in action and not isinstance(action['subject'], str):
            return False, 'email subject must be a string'
    
    elif atype == 'social_post':
        if 'user_id' not in action:
            return False, 'social_post action requires user_id'
        if not isinstance(action['user_id'], (int, str)):
            return False, 'social_post user_id must be an integer or template string'
        if 'content' in action and not isinstance(action['content'], str):
            return False, 'social_post content must be a string'
    
    elif atype == 'webhook':
        if 'url' not in action:
            return False, 'webhook action requires url'
        if not isinstance(action['url'], str) or not action['url'].startswith(('http://', 'https://')):
            return False, 'webhook url must be a valid HTTP(S) URL'
    
    elif atype == 'task_create':
        if 'title' not in action:
            return False, 'task_create action requires title'
        if 'assigned_to' in action and not isinstance(action['assigned_to'], (int, str)):
            return False, 'task_create assigned_to must be an integer or template string'

    elif atype == 'whatsapp':
        if 'user_id' not in action:
            return False, 'whatsapp action requires user_id'
        if not isinstance(action['user_id'], (int, str)):
            return False, 'whatsapp user_id must be an integer or template string'
        if 'message' not in action:
            return False, 'whatsapp action requires message'
        if not isinstance(action['message'], str):
            return False, 'whatsapp message must be a string'
        if 'template_key' in action and action['template_key'] is not None and not isinstance(action['template_key'], str):
            return False, 'whatsapp template_key must be a string'
        if 'template_params' in action and action['template_params'] is not None and not isinstance(action['template_params'], (list, str)):
            return False, 'whatsapp template_params must be a list or comma-separated string'
    
    else:
        return False, f'Unknown action type: {atype}'
    
    return True, ''
