"""Field Planner Module - Field/Facility occupancy management"""
from flask import Blueprint, redirect, request

NEW_PREFIX = '/field_planner'
LEGACY_PREFIX = '/field-planner'

bp = Blueprint('field_planner', __name__, url_prefix=NEW_PREFIX)


def _legacy_root_redirect():
    code = 307 if request.method != 'GET' else 302
    return redirect(f'{NEW_PREFIX}/', code=code)


def _legacy_subpath_redirect(subpath: str):
    code = 307 if request.method != 'GET' else 302
    return redirect(f'{NEW_PREFIX}/{subpath}', code=code)


_ALL_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']

# Backward compatibility: support legacy hyphenated prefix without breaking links
legacy_bp = Blueprint('field_planner_legacy', __name__, url_prefix=LEGACY_PREFIX)
legacy_bp.add_url_rule('/', 'legacy_root', _legacy_root_redirect, methods=_ALL_METHODS)
legacy_bp.add_url_rule('/<path:subpath>', 'legacy_redirect', _legacy_subpath_redirect, methods=_ALL_METHODS)

from app.field_planner import routes
