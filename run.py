"""Deprecated entry point. Use wsgi:app for Gunicorn."""

from wsgi import app

if __name__ == "__main__":
    raise RuntimeError("Deprecated. Use 'wsgi:app' as the Gunicorn entrypoint.")
