"""Ads delivery and tracking routes."""
from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import AdCampaign, AdCreative
from app.ads.utils import parse_token, log_event, _is_safe_redirect
from app.subscription.stripe_utils import stripe_enabled, create_ads_topup_checkout_session

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


@bp.route("/selfserve")
@login_required
def selfserve():
    """Self-serve sponsor ads dashboard (requires add-on feature)."""
    if not current_user.has_feature("ads_selfserve"):
        flash("Questa funzionalità richiede Ads Self‑Serve.", "warning")
        return redirect(url_for("subscription.addons"))
    camps = AdCampaign.query.filter_by(is_self_serve=True, advertiser_user_id=current_user.id).order_by(AdCampaign.created_at.desc()).all()
    return render_template("ads/selfserve.html", campaigns=camps)


@bp.route("/selfserve/new", methods=["POST"])
@login_required
def selfserve_new():
    if not current_user.has_feature("ads_selfserve"):
        flash("Questa funzionalità richiede Ads Self‑Serve.", "warning")
        return redirect(url_for("subscription.addons"))

    name = (request.form.get("name") or "").strip() or "Campagna"
    placement = (request.form.get("placement") or "feed_inline").strip()
    link_url = (request.form.get("link_url") or "/").strip()
    headline = (request.form.get("headline") or "").strip() or None
    body = (request.form.get("body") or "").strip() or None
    try:
        budget_eur = float((request.form.get("budget_eur") or "0").replace(",", "."))
    except Exception:
        budget_eur = 0.0
    budget_cents = int(round(max(0.0, budget_eur) * 100))

    camp = AdCampaign(
        name=name,
        objective="traffic",
        society_id=None,
        is_active=True,
        starts_at=datetime.now(timezone.utc),
        ends_at=None,
        max_impressions=None,
        max_clicks=None,
        autopilot=True,
        is_self_serve=True,
        advertiser_user_id=current_user.id,
        budget_cents=budget_cents,
        spend_cents=0,
        created_by=current_user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.session.add(camp)
    db.session.flush()
    db.session.add(
        AdCreative(
            campaign_id=camp.id,
            placement=placement,
            headline=headline,
            body=body,
            image_url=None,
            link_url=link_url,
            cta_label="Scopri di più",
            is_active=True,
            weight=100,
            created_by=current_user.id,
            created_at=datetime.now(timezone.utc),
        )
    )
    db.session.commit()
    flash("Campagna creata.", "success")
    return redirect(url_for("ads.selfserve"))


@bp.route("/selfserve/<int:campaign_id>/topup", methods=["POST"])
@login_required
def selfserve_topup(campaign_id: int):
    if not current_user.has_feature("ads_selfserve"):
        flash("Questa funzionalità richiede Ads Self‑Serve.", "warning")
        return redirect(url_for("subscription.addons"))
    camp = AdCampaign.query.get_or_404(campaign_id)
    if camp.advertiser_user_id != current_user.id:
        abort(403)

    try:
        amount_eur = float((request.form.get("amount_eur") or "0").replace(",", "."))
    except Exception:
        amount_eur = 0.0
    amount_cents = int(round(max(0.0, amount_eur) * 100))
    if amount_cents <= 0:
        flash("Importo non valido.", "danger")
        return redirect(url_for("ads.selfserve"))

    if stripe_enabled():
        try:
            success_url = url_for("ads.selfserve", _external=True) + "?topup=1"
            cancel_url = url_for("ads.selfserve", _external=True)
            checkout_url = create_ads_topup_checkout_session(campaign=camp, amount_cents=amount_cents, success_url=success_url, cancel_url=cancel_url)
            return redirect(checkout_url)
        except Exception as exc:
            flash(f"Stripe non disponibile: {exc}", "warning")

    # Local fallback: add budget immediately
    camp.budget_cents = int(camp.budget_cents or 0) + amount_cents
    db.session.add(camp)
    db.session.commit()
    flash("Budget aggiornato.", "success")
    return redirect(url_for("ads.selfserve"))

