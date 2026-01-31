"""
Legacy entrypoint kept for compatibility.

Production entrypoint MUST be `wsgi:app`.
This module intentionally remains runnable by Gunicorn as `run:app` if needed.
"""

from app import create_app

app = create_app()
