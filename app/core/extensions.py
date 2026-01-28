"""Backwards-compatible extension imports.

Use extensions from app/__init__.py as the single source of truth.
"""
from app import db, migrate, login_manager, mail, csrf, limiter

__all__ = [
	'db',
	'migrate',
	'login_manager',
	'mail',
	'csrf',
	'limiter',
]
