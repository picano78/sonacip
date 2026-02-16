"""
Test suite to verify that the application does not return HTTP 500 errors.

This test ensures that all routes in the SONACIP application are functioning
properly and do not return internal server errors (HTTP 500).
"""
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
    Comprehensive smoke test: verify no GET route returns HTTP 500 errors.

    We accept 200/3xx/4xx as "non-crash" outcomes because many routes require
    auth, CSRF, or real DB data. The goal is to ensure no internal server errors.
    
    Test coverage:
    - All registered GET routes
    - Routes with and without parameters
    - Skip complex routes (UUID, etc.) that need specific data
    """
    from app import create_app, db

    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        db.create_all()

    with app.test_client() as client:
        failures: list[tuple[str, int, str]] = []
        tested_routes = 0
        skipped_routes = 0
        
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
                    skipped_routes += 1
                    continue
                try:
                    from flask import url_for

                    with app.test_request_context():
                        path = url_for(rule.endpoint, **values)
                except Exception:
                    skipped_routes += 1
                    continue
            else:
                path = rule.rule

            resp = client.get(path, follow_redirects=False)
            tested_routes += 1
            
            if resp.status_code >= 500:
                failures.append((path, resp.status_code, rule.endpoint))

        # Print summary for debugging
        print(f"\n✅ 500 Error Test Summary:")
        print(f"   Routes tested: {tested_routes}")
        print(f"   Routes skipped: {skipped_routes}")
        print(f"   Routes with 500 errors: {len(failures)}")
        
        if failures:
            print("\n❌ Failed routes:")
            for path, status, endpoint in failures[:30]:
                print(f"   - {path} ({endpoint}): HTTP {status}")

        assert not failures, f"GET routes returning 5xx errors: {failures[:30]}"


def test_post_routes_do_not_return_500():
    """
    Test POST routes to ensure they don't crash with 500 errors.
    
    POST routes will likely return 4xx errors (auth required, CSRF, validation),
    but they should never return 500 errors which indicate server-side bugs.
    
    This test verifies the application handles POST requests gracefully even when
    they're invalid/unauthorized.
    """
    from app import create_app, db

    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = False  # Disable CSRF for testing

    with app.app_context():
        db.create_all()

    with app.test_client() as client:
        failures: list[tuple[str, int, str]] = []
        tested_routes = 0
        skipped_routes = 0
        
        for rule in app.url_map.iter_rules():
            if "POST" not in rule.methods:
                continue
            if rule.endpoint == "static":
                continue
            
            # Skip websockets / internal rules
            if rule.rule.startswith("/static"):
                continue

            # Build path with sample values for parameterized routes
            if rule.arguments:
                values = {}
                for a in rule.arguments:
                    conv = rule._converters.get(a)  # type: ignore[attr-defined]
                    conv_name = getattr(conv, "__class__", type("x", (), {})).__name__.lower() if conv else ""
                    if "integer" in conv_name or "int" in conv_name:
                        values[a] = 1
                    elif "float" in conv_name:
                        values[a] = 1.0
                    elif "uuid" in conv_name:
                        # Skip UUID routes
                        values = None
                        break
                    else:
                        values[a] = "test"
                if values is None:
                    skipped_routes += 1
                    continue
                try:
                    from flask import url_for
                    with app.test_request_context():
                        path = url_for(rule.endpoint, **values)
                except Exception:
                    skipped_routes += 1
                    continue
            else:
                path = rule.rule

            # POST with minimal data to check for crashes
            resp = client.post(path, data={}, follow_redirects=False)
            tested_routes += 1
            
            if resp.status_code >= 500:
                failures.append((path, resp.status_code, rule.endpoint))

        # Print summary
        print(f"\n✅ POST Routes 500 Error Test Summary:")
        print(f"   Routes tested: {tested_routes}")
        print(f"   Routes skipped: {skipped_routes}")
        print(f"   Routes with 500 errors: {len(failures)}")
        
        if failures:
            print("\n❌ Failed routes:")
            for path, status, endpoint in failures[:30]:
                print(f"   - {path} ({endpoint}): HTTP {status}")

        assert not failures, f"POST routes returning 5xx errors: {failures[:30]}"

