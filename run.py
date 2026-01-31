"""Deprecated entry point. Use wsgi:app for Gunicorn."""

if __name__ == "__main__":
    raise RuntimeError("Deprecated. Use 'wsgi:app' as the Gunicorn entrypoint.")
