"""
Deprecated Gunicorn config.

Use `gunicorn.conf.py` as the single source of truth.
Kept for backwards compatibility with older deploy scripts.
"""

from gunicorn.conf import *  # noqa: F401,F403
