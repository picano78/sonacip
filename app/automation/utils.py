"""Automation execution utilities"""
from datetime import datetime
from app import db
from app.models import Automation


def execute_automations(trigger_type, society_id=None, payload=None):
    """Execute active automations matching a trigger.
    This is a lightweight placeholder that updates stats; extend actions as needed.
    """
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
            # Here you could parse auto.actions and perform them (webhooks, tasks, emails, etc.)
            executed.append(auto)
        except Exception as exc:
            auto.failure_count = (auto.failure_count or 0) + 1
            auto.last_error = str(exc)
            db.session.add(auto)
    if executed:
        db.session.commit()
    return executed
