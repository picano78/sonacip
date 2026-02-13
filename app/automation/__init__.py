"""
Automation module
Handles automated tasks, scheduling, and background jobs
"""
from app.automation.tasks import celery

__all__ = ['celery']
