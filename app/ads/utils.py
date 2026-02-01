"""Ad delivery utilities (selection + signed tokens)."""
from __future__ import annotations

import random
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from flask import current_app, request, session
from itsdangerous import BadSignature, URLSafeSerializer

from app import db
from app.models import AdCampaign, AdCreative, AdEvent


def _serializer() -> URLSafeSerializer:
    secret = current_app.config.get("SECRET_KEY") or current_app.secret_key
    return URLSafeSerializer(secret_key=secret, salt="sonacip-ads")


def make_token(creative: AdCreative, placement: str, society_id: int | None, user_id: int | None) -> str:
    payload = {
        "creative_id": creative.id,
        "campaign_id": creative.campaign_id,
        "placement": placement,
        "society_id": society_id,
        "user_id": user_id,
        "ts": int(datetime.utcnow().timestamp()),
    }
    return _serializer().dumps(payload)


def parse_token(token: str) -> dict | None:
    try:
        return _serializer().loads(token)
    except BadSignature:
        return None


def _is_safe_redirect(url: str) -> bool:
    try:
        p = urlparse(url)
        if p.scheme in ("http", "https"):
            return True
        # allow relative urls
        if not p.scheme and not p.netloc and url.startswith("/"):
            return True
        return False
    except Exception:
        return False


def _eligible_creatives(placement: str, society_id: int | None) -> list[AdCreative]:
    now = datetime.utcnow()
    q = (
        AdCreative.query.join(AdCampaign, AdCreative.campaign_id == AdCampaign.id)
        .filter(
            AdCreative.is_active == True,  # noqa: E712
            AdCreative.placement == placement,
            AdCampaign.is_active == True,  # noqa: E712
        )
    )
    # date window
    q = q.filter((AdCampaign.starts_at.is_(None)) | (AdCampaign.starts_at <= now))
    q = q.filter((AdCampaign.ends_at.is_(None)) | (AdCampaign.ends_at >= now))
    # scope
    if society_id:
        q = q.filter((AdCampaign.society_id.is_(None)) | (AdCampaign.society_id == society_id))
    else:
        # no scope -> global only
        q = q.filter(AdCampaign.society_id.is_(None))

    # caps
    q = q.filter((AdCampaign.max_impressions.is_(None)) | (AdCampaign.impressions_count < AdCampaign.max_impressions))
    q = q.filter((AdCampaign.max_clicks.is_(None)) | (AdCampaign.clicks_count < AdCampaign.max_clicks))
    return q.order_by(AdCreative.id.asc()).limit(200).all()


def choose_creative(placement: str, society_id: int | None, user_id: int | None) -> Optional[AdCreative]:
    """
    Pick an ad creative automatically.
    Autopilot (per campaign): Thompson sampling on CTR; fallback to weights.
    """
    creatives = _eligible_creatives(placement, society_id)
    if not creatives:
        return None

    # basic frequency capping per-session (avoid repeating)
    seen = set(session.get("ads_seen", {}).get(placement, [])) if session else set()

    # split by campaign autopilot flag (needs campaign)
    by_campaign = {}
    for c in creatives:
        by_campaign.setdefault(c.campaign_id, []).append(c)

    def _score(c: AdCreative) -> float:
        # Deprioritize recently-seen creatives
        penalty = 0.25 if c.id in seen else 1.0

        camp = c.campaign
        if camp and camp.autopilot:
            # Thompson sampling Beta(1+clicks, 1+impressions-clicks)
            imp = int(c.impressions_count or 0)
            clk = int(c.clicks_count or 0)
            a = 1 + max(0, clk)
            b = 1 + max(0, imp - clk)
            sample = random.betavariate(a, b)
            return sample * penalty

        w = max(1, int(c.weight or 1))
        # convert weight into pseudo probability with small random jitter
        return (w / 100.0) * random.random() * penalty

    best = max(creatives, key=_score)

    # track in session
    try:
        ads_seen = session.get("ads_seen", {})
        arr = list(ads_seen.get(placement, []))
        arr.append(best.id)
        arr = arr[-30:]
        ads_seen[placement] = arr
        session["ads_seen"] = ads_seen
    except Exception:
        pass

    try:
        best.last_served_at = datetime.utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()

    return best


def log_event(kind: str, creative: AdCreative, placement: str, society_id: int | None, user_id: int | None) -> None:
    ip = request.headers.get("X-Forwarded-For") or request.remote_addr
    ua = (request.headers.get("User-Agent") or "")[:300]
    db.session.add(
        AdEvent(
            kind=kind,
            campaign_id=creative.campaign_id,
            creative_id=creative.id,
            placement=placement,
            society_id=society_id,
            user_id=user_id,
            ip=(ip or "")[:80],
            user_agent=ua,
            created_at=datetime.utcnow(),
        )
    )

    # counters
    if kind == "impression":
        creative.impressions_count = (creative.impressions_count or 0) + 1
        creative.campaign.impressions_count = (creative.campaign.impressions_count or 0) + 1
    elif kind == "click":
        creative.clicks_count = (creative.clicks_count or 0) + 1
        creative.campaign.clicks_count = (creative.campaign.clicks_count or 0) + 1

    db.session.add(creative)
    db.session.add(creative.campaign)
    db.session.commit()

