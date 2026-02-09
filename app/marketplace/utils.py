from __future__ import annotations

from datetime import datetime, timezone

from app import db
from app.models import MarketplacePurchase, Template


def install_purchase(purchase: MarketplacePurchase, actor_user_id: int) -> None:
    """
    Clone templates from a purchased package into the buyer scope.
    Idempotent: does nothing if purchase.installed_at is already set.
    """
    if not purchase or purchase.installed_at:
        return
    now = datetime.now(timezone.utc)

    # Resolve target scope (society preferred, otherwise user-scoped templates)
    target_society_id = purchase.society_id

    items = purchase.package.items.all() if purchase.package else []
    for item in items:
        src = item.template
        if not src:
            continue
        cloned = Template(
            name=f"{src.name} (Marketplace)",
            description=src.description,
            template_type=src.template_type,
            content=src.content,
            created_by=actor_user_id,
            society_id=target_society_id,
            is_public=False,
            is_system=False,
            usage_count=0,
            created_at=now,
            updated_at=now,
        )
        db.session.add(cloned)

    purchase.installed_at = now
    db.session.add(purchase)
    db.session.commit()

