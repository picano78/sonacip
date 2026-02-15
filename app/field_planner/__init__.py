"""Field Planner Module - Field/Facility occupancy management"""
from flask import Blueprint, redirect

bp = Blueprint('field_planner', __name__, url_prefix='/field_planner')


def _legacy_root_redirect():
    return redirect('/field_planner/', code=302)


def _legacy_subpath_redirect(subpath: str):
    return redirect(f'/field_planner/{subpath}', code=302)


# Backward compatibility: support legacy hyphenated prefix without breaking links
legacy_bp = Blueprint('field_planner_legacy', __name__, url_prefix='/field-planner')
legacy_bp.add_url_rule('/', 'legacy_root', _legacy_root_redirect)
legacy_bp.add_url_rule('/<path:subpath>', 'legacy_redirect', _legacy_subpath_redirect)

from app.field_planner import routes
