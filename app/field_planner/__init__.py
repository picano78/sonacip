"""Field Planner Module - Field/Facility occupancy management"""
from flask import Blueprint, redirect

NEW_PREFIX = '/field_planner'
LEGACY_PREFIX = '/field-planner'

bp = Blueprint('field_planner', __name__, url_prefix=NEW_PREFIX)


def _legacy_root_redirect():
    return redirect(f'{NEW_PREFIX}/', code=302)


def _legacy_subpath_redirect(subpath: str):
    return redirect(f'{NEW_PREFIX}/{subpath}', code=302)


# Backward compatibility: support legacy hyphenated prefix without breaking links
legacy_bp = Blueprint('field_planner_legacy', __name__, url_prefix=LEGACY_PREFIX)
legacy_bp.add_url_rule('/', 'legacy_root', _legacy_root_redirect)
legacy_bp.add_url_rule('/<path:subpath>', 'legacy_redirect', _legacy_subpath_redirect)

from app.field_planner import routes
