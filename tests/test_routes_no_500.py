from __future__ import annotations


def _build_sample_path(rule) -> str | None:
    """
    Build a sample URL path for a Flask Rule.
    - For required int params, use 1.
    - For required string params, use 'test'.
    If a rule uses a complex converter, skip it.
    """
    args = {}
    for arg in rule.arguments:
        conv = rule._converters.get(arg)  # type: ignore[attr-defined]
        conv_name = getattr(conv, "__class__", type("x", (), {})).__name__.lower() if conv else ""
        if "integer" in conv_name or "int" in conv_name:
            args[arg] = 1
        elif "uuid" in conv_name:
            # Skip UUID routes (need a valid uuid string)
            return None
        else:
            args[arg] = "test"
    try:
        return rule.rule.format(**{k: f"<{k}>" for k in args}) if False else None
    except Exception:
        return None


def test_get_routes_do_not_return_500():
    """
    Broad smoke test: for every GET route, a request should not crash with 500.

    We accept 200/3xx/4xx as "non-crash" outcomes because many routes require
    auth, CSRF, or real DB data.
    """
    from app import create_app, db

    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        db.create_all()

    with app.test_client() as client:
        failures: list[tuple[str, int]] = []
        for rule in app.url_map.iter_rules():
            if "GET" not in rule.methods:
                continue
            if rule.endpoint == "static":
                continue
            # Skip websockets / internal rules
            if rule.rule.startswith("/static"):
                continue

            # If route has parameters, call it with a best-effort sample.
            if rule.arguments:
                # Build a sample URL by replacing converters with dummy values.
                # We do this by using url_for, falling back to skip if build fails.
                values = {}
                for a in rule.arguments:
                    conv = rule._converters.get(a)  # type: ignore[attr-defined]
                    conv_name = getattr(conv, "__class__", type("x", (), {})).__name__.lower() if conv else ""
                    if "integer" in conv_name or "int" in conv_name:
                        values[a] = 1
                    elif "float" in conv_name:
                        values[a] = 1.0
                    elif "uuid" in conv_name:
                        # Skip UUID routes (need a valid UUID)
                        values = None
                        break
                    else:
                        values[a] = "test"
                if values is None:
                    continue
                try:
                    from flask import url_for

                    with app.test_request_context():
                        path = url_for(rule.endpoint, **values)
                except Exception:
                    continue
            else:
                path = rule.rule

            resp = client.get(path, follow_redirects=False)
            if resp.status_code >= 500:
                failures.append((path, resp.status_code))

        assert not failures, f"GET routes returning 5xx: {failures[:30]}"

