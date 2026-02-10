import re


def _extract_url_for_endpoints(template_source: str) -> set[str]:
    """
    Extract endpoints used as string literals in url_for('endpoint', ...).

    We intentionally only check string-literal usage to avoid false positives
    for dynamic expressions.
    """
    # url_for('blueprint.endpoint' ...)
    pat = re.compile(r"""url_for\(\s*['"]([a-zA-Z0-9_.-]+)['"]""")
    return set(pat.findall(template_source or ""))


def test_all_templates_reference_valid_endpoints():
    """
    Prevent regressions like BuildError due to wrong endpoint names in templates.

    This is a fast, static integrity check: any endpoint referenced via
    `url_for('...')` must exist in the Flask app.
    """
    from app import create_app

    app = create_app("testing")
    endpoints = set(app.view_functions.keys())

    # Jinja loader can list all templates from app + blueprints.
    names = app.jinja_loader.list_templates()  # type: ignore[attr-defined]
    missing: dict[str, set[str]] = {}

    for name in names:
        try:
            src, _, _ = app.jinja_loader.get_source(app.jinja_env, name)  # type: ignore[attr-defined]
        except Exception:
            continue

        used = _extract_url_for_endpoints(src)
        # Ignore common non-app endpoints
        used.discard("static")

        bad = {ep for ep in used if ep not in endpoints}
        if bad:
            missing[name] = bad

    assert not missing, f"Templates reference missing endpoints: {missing}"

