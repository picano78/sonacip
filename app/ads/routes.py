"""Ads delivery and tracking routes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import AdCampaign, AdCreative, AdsSetting
from app.ads.utils import parse_token, log_event, _is_safe_redirect
from app.subscription.stripe_utils import stripe_enabled, create_ads_topup_checkout_session

bp = Blueprint("ads", __name__, url_prefix="/ads")

VALID_AUDIENCES = {'all', 'societies', 'users', 'athletes', 'coaches'}


@bp.route("/i/<token>")
def impression(token: str):
    data = parse_token(token)
    if not data:
        return ("", 204)
    creative = db.session.get(AdCreative, data.get("creative_id"))
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
    creative = db.session.get(AdCreative, data.get("creative_id"))
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


def _get_ads_settings():
    """Return AdsSetting row (create default if missing)."""
    settings = AdsSetting.query.first()
    if not settings:
        settings = AdsSetting()
        db.session.add(settings)
        db.session.commit()
    return settings


@bp.route("/selfserve")
@login_required
def selfserve():
    """Self-serve sponsor ads dashboard."""
    settings = _get_ads_settings()
    camps = AdCampaign.query.filter_by(
        is_self_serve=True, advertiser_user_id=current_user.id
    ).order_by(AdCampaign.created_at.desc()).all()
    return render_template("ads/selfserve.html", campaigns=camps, settings=settings)


@bp.route("/selfserve/new", methods=["POST"])
@login_required
def selfserve_new():
    settings = _get_ads_settings()

    name = (request.form.get("name") or "").strip() or "Campagna"
    placement = (request.form.get("placement") or "feed_inline").strip()
    link_url = (request.form.get("link_url") or "/").strip()
    headline = (request.form.get("headline") or "").strip() or None
    body = (request.form.get("body") or "").strip() or None

    # Audience targeting
    target_audience = (request.form.get("target_audience") or "all").strip()
    if target_audience not in VALID_AUDIENCES:
        target_audience = "all"

    # Duration (days) constrained by admin settings
    min_days = settings.min_duration_days or 1
    max_days = settings.max_duration_days or 90
    default_days = settings.default_duration_days or 7
    try:
        duration_days = int(request.form.get("duration_days") or default_days)
    except (ValueError, TypeError):
        duration_days = default_days
    duration_days = max(min_days, min(max_days, duration_days))

    now = datetime.now(timezone.utc)
    starts_at = now
    ends_at = now + timedelta(days=duration_days)

    # Calculate price: price_per_day * duration_days
    price_per_day = float(settings.price_per_day or 5.0)
    total_price_eur = round(price_per_day * duration_days, 2)
    budget_cents = int(round(total_price_eur * 100))

    # Handle image upload
    image_url = None
    image_file = request.files.get("image")
    if image_file and image_file.filename:
        try:
            from app.storage import save_image_light
            image_url = save_image_light(image_file, folder="ads")
        except Exception as exc:
            flash(f"Errore caricamento immagine: {exc}", "danger")
            return redirect(url_for("ads.selfserve"))

    camp = AdCampaign(
        name=name,
        objective="traffic",
        society_id=None,
        is_active=False,  # activated after payment
        starts_at=starts_at,
        ends_at=ends_at,
        target_audience=target_audience,
        payment_status="pending",
        max_impressions=None,
        max_clicks=None,
        autopilot=True,
        is_self_serve=True,
        advertiser_user_id=current_user.id,
        budget_cents=budget_cents,
        spend_cents=0,
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.session.add(camp)
    db.session.flush()
    db.session.add(
        AdCreative(
            campaign_id=camp.id,
            placement=placement,
            headline=headline,
            body=body,
            image_url=image_url,
            link_url=link_url,
            cta_label="Scopri di più",
            is_active=True,
            weight=100,
            created_by=current_user.id,
            created_at=now,
        )
    )
    db.session.commit()

    # Redirect to Stripe payment
    if stripe_enabled() and budget_cents > 0:
        try:
            success_url = url_for("ads.selfserve", _external=True) + "?paid=1"
            cancel_url = url_for("ads.selfserve", _external=True) + "?cancelled=1"
            checkout_url = create_ads_topup_checkout_session(
                campaign=camp,
                amount_cents=budget_cents,
                success_url=success_url,
                cancel_url=cancel_url,
            )
            return redirect(checkout_url)
        except Exception as exc:
            # Stripe unavailable – activate immediately as fallback
            camp.is_active = True
            camp.payment_status = "completed"
            db.session.commit()
            flash(f"Stripe non disponibile ({exc}). Campagna attivata.", "warning")
            return redirect(url_for("ads.selfserve"))

    # No Stripe / free campaign – activate immediately
    camp.is_active = True
    camp.payment_status = "completed"
    db.session.commit()
    flash("Campagna creata e attivata.", "success")
    return redirect(url_for("ads.selfserve"))


@bp.route("/selfserve/<int:campaign_id>/topup", methods=["POST"])
@login_required
def selfserve_topup(campaign_id: int):
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

