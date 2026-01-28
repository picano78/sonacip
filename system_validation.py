#!/usr/bin/env python
"""SONACIP system validation for production readiness."""
from __future__ import annotations

import os
import sys
from typing import Iterable

from app import create_app, db
from sqlalchemy import text


MIN_PYTHON = (3, 10)
EXPECTED_BLUEPRINTS = {
    'main', 'auth', 'admin', 'crm', 'events', 'social', 'backup',
    'notifications', 'analytics', 'messages', 'tournaments',
    'tasks', 'scheduler', 'subscription'
}


def print_header(title: str) -> None:
    print('\n' + '=' * 70)
    print(f'  {title}')
    print('=' * 70)


def check_python_version() -> bool:
    print_header('PYTHON VERSION')
    current = sys.version_info[:3]
    print(f'  Detected Python: {current[0]}.{current[1]}.{current[2]}')
    if current < MIN_PYTHON:
        print('  ✗ Python version is too old')
        return False
    print('  ✓ Python version OK')
    return True


def check_venv() -> bool:
    print_header('VIRTUAL ENVIRONMENT')
    in_venv = sys.prefix != getattr(sys, 'base_prefix', sys.prefix)
    if in_venv:
        print('  ✓ Running inside virtual environment')
        return True
    print('  ✗ Not running inside virtual environment')
    return False


def check_gunicorn_import() -> bool:
    print_header('GUNICORN IMPORT')
    try:
        import gunicorn  # noqa: F401
        print('  ✓ Gunicorn import OK')
        return True
    except Exception as exc:
        print(f'  ✗ Gunicorn import failed: {exc}')
        return False


def check_wsgi_import() -> bool:
    print_header('WSGI IMPORT')
    try:
        from wsgi import app as wsgi_app  # noqa: F401
        print('  ✓ WSGI app import OK')
        return True
    except Exception as exc:
        print(f'  ✗ WSGI import failed: {exc}')
        return False


def check_database_connection(app) -> bool:
    print_header('DATABASE CONNECTION')
    try:
        with app.app_context():
            db.session.execute(text('SELECT 1'))
        print('  ✓ Database connection OK')
        return True
    except Exception as exc:
        print(f'  ✗ Database connection failed: {exc}')
        return False


def check_blueprints(app) -> bool:
    print_header('BLUEPRINT REGISTRATION')
    registered = set(app.blueprints.keys())
    missing = sorted(EXPECTED_BLUEPRINTS - registered)
    if missing:
        print(f'  ✗ Missing blueprints: {", ".join(missing)}')
        return False
    print(f'  ✓ Blueprints registered: {len(registered)}')
    return True


def run_checks(checks: Iterable) -> int:
    passed = 0
    failed = 0
    for check in checks:
        try:
            if check():
                passed += 1
            else:
                failed += 1
        except Exception as exc:
            failed += 1
            print(f'  ✗ Check failed with exception: {exc}')

    print_header('VALIDATION SUMMARY')
    print(f'  Total Checks: {passed + failed}')
    print(f'  ✓ Passed: {passed}')
    print(f'  ✗ Failed: {failed}')
    return 0 if failed == 0 else 1


def main() -> int:
    print('\n')
    print('╔' + '═' * 68 + '╗')
    print('║' + ' ' * 20 + 'SONACIP VALIDATION SUITE' + ' ' * 24 + '║')
    print('╚' + '═' * 68 + '╝')

    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False

    return run_checks([
        check_python_version,
        check_venv,
        check_gunicorn_import,
        check_wsgi_import,
        lambda: check_database_connection(app),
        lambda: check_blueprints(app),
    ])


if __name__ == '__main__':
    sys.exit(main())
