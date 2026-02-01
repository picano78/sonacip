"""Ads delivery and tracking routes."""
from __future__ import annotations

from flask import Blueprint, abort, redirect
from flask_login import current_user

from app.models import AdCreative
from app.ads.utils import parse_token, log_event, _is_safe_redirect

bp = Blueprint("ads", __name__, url_prefix="/ads")


@bp.route("/i/<token>")
def impression(token: str):
    data = parse_token(token)
    if not data:
        return ("", 204)
    creative = AdCreative.query.get(data.get("creative_id"))
    if not creative or not creative.campaign:
        return ("", 204)
    try:
        log_event(
            "impression",
            creative,
            placement=str(data.get("placement") or ""),
            society_id=data.get("society_id"),
            user_id=(current_user.id if getattr(current_user, "is_authenticated", False) else None),
        )
    except Exception:
        # Never break page render because of ads.
        return ("", 204)
    return ("", 204)


@bp.route("/c/<token>")
def click(token: str):
    data = parse_token(token)
    if not data:
        abort(404)
    creative = AdCreative.query.get(data.get("creative_id"))
    if not creative or not creative.campaign:
        abort(404)
    try:
        log_event(
            "click",
            creative,
            placement=str(data.get("placement") or ""),
            society_id=data.get("society_id"),
            user_id=(current_user.id if getattr(current_user, "is_authenticated", False) else None),
        )
    except Exception:
        pass
    target = creative.link_url or "/"
    if not _is_safe_redirect(target):
        target = "/"
    return redirect(target)

