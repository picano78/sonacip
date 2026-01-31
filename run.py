"""Deprecated entry point. Use wsgi:app for Gunicorn."""

raise RuntimeError(
    "Deprecated entry point. Use 'wsgi:app' as the Gunicorn entrypoint."
)

if __name__ == "__main__":
    raise RuntimeError("Deprecated. Use 'wsgi:app' as the Gunicorn entrypoint.")
