from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import stripe
from flask import current_app

from app import db
from app.models import Payment, Plan, Subscription


def stripe_enabled() -> bool:
    return bool(current_app.config.get("STRIPE_SECRET_KEY"))


def _init_stripe() -> None:
    stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")


def _get_price_id(plan: Plan, billing_cycle: str) -> str | None:
    if billing_cycle == "yearly":
        return plan.stripe_price_yearly_id
    return plan.stripe_price_monthly_id


def create_checkout_session(subscription: Subscription, plan: Plan, billing_cycle: str, success_url: str, cancel_url: str) -> str:
    _init_stripe()
    price_id = _get_price_id(plan, billing_cycle)
    if not price_id:
        raise ValueError("Piano non configurato per Stripe (price_id mancante).")

    metadata = {
        "subscription_id": str(subscription.id),
        "plan_id": str(plan.id),
        "billing_cycle": billing_cycle,
        "society_id": str(subscription.society_id or ""),
        "user_id": str(subscription.user_id or ""),
    }

    sess = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        allow_promotion_codes=False,  # coupons are handled internally today
        client_reference_id=str(subscription.id),
        metadata=metadata,
        subscription_data={"metadata": metadata},
    )
    return sess.url  # type: ignore[attr-defined]


def create_billing_portal_session(customer_id: str, return_url: str) -> str:
    _init_stripe()
    portal = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
    return portal.url  # type: ignore[attr-defined]


def _upsert_payment_from_invoice(invoice: Any, status: str, subscription: Subscription | None) -> None:
    """
    Create/update a Payment row from Stripe invoice.
    transaction_id is the invoice id.
    """
    inv_id = getattr(invoice, "id", None) or invoice.get("id")
    amount_paid = getattr(invoice, "amount_paid", None)
    currency = getattr(invoice, "currency", None) or "eur"
    created = getattr(invoice, "created", None)
    created_dt = datetime.utcfromtimestamp(created) if created else datetime.utcnow()

    if amount_paid is None:
        # fallback to total
        amount_paid = getattr(invoice, "total", 0) or 0

    amount_eur = round(float(amount_paid) / 100.0, 2)

    existing = Payment.query.filter_by(transaction_id=inv_id).first()
    if not existing:
        p = Payment(
            user_id=(subscription.user_id if subscription else None),
            society_id=(subscription.society_id if subscription else None),
            subscription_id=(subscription.id if subscription else None),
            amount=amount_eur,
            currency=currency.upper(),
            status=status,
            payment_method="stripe",
            payment_date=created_dt,
            description="Stripe invoice",
            transaction_id=inv_id,
            gateway="stripe",
        )
        p.payment_metadata = json.dumps({"invoice": invoice})
        db.session.add(p)
        return

    existing.status = status
    existing.gateway = "stripe"
    existing.payment_method = "stripe"
    existing.payment_metadata = json.dumps({"invoice": invoice})
    db.session.add(existing)


def apply_subscription_from_webhook(stripe_sub: Any, subscription: Subscription) -> None:
    subscription.stripe_customer_id = getattr(stripe_sub, "customer", None) or stripe_sub.get("customer")
    subscription.stripe_subscription_id = getattr(stripe_sub, "id", None) or stripe_sub.get("id")
    subscription.cancel_at_period_end = bool(getattr(stripe_sub, "cancel_at_period_end", False) or stripe_sub.get("cancel_at_period_end", False))

    period_end = None
    try:
        pe = getattr(stripe_sub, "current_period_end", None) or stripe_sub.get("current_period_end")
        if pe:
            period_end = datetime.utcfromtimestamp(int(pe))
    except Exception:
        period_end = None
    subscription.current_period_end = period_end
    subscription.next_billing_date = period_end


def handle_stripe_event(event: Any) -> None:
    """
    Mutates DB based on Stripe webhook events.
    Idempotency relies on unique Payment.transaction_id for invoices and
    stable Subscription.stripe_subscription_id mapping.
    """
    etype = event["type"]
    obj = event["data"]["object"]

    # Checkout completion: activate the subscription row
    if etype == "checkout.session.completed":
        session_obj = obj
        sub_id = session_obj.get("subscription")
        client_ref = session_obj.get("client_reference_id")
        if not client_ref:
            return
        local_sub = Subscription.query.get(int(client_ref))
        if not local_sub:
            return
        # pull subscription from Stripe to get customer + period_end
        _init_stripe()
        stripe_sub = stripe.Subscription.retrieve(sub_id) if sub_id else None
        if stripe_sub:
            apply_subscription_from_webhook(stripe_sub, local_sub)
        local_sub.status = "active"
        local_sub.start_date = datetime.utcnow()
        db.session.add(local_sub)
        db.session.commit()
        return

    # Invoice succeeded: ensure payment recorded + subscription active
    if etype in ("invoice.paid", "invoice.payment_succeeded"):
        invoice = obj
        stripe_sub_id = invoice.get("subscription")
        local_sub = Subscription.query.filter_by(stripe_subscription_id=stripe_sub_id).first() if stripe_sub_id else None
        if local_sub:
            local_sub.status = "active"
            try:
                _init_stripe()
                stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
                apply_subscription_from_webhook(stripe_sub, local_sub)
            except Exception:
                pass
            db.session.add(local_sub)
        _upsert_payment_from_invoice(invoice, status="completed", subscription=local_sub)
        db.session.commit()
        return

    # Invoice failed: mark subscription past_due (dunning starter)
    if etype == "invoice.payment_failed":
        invoice = obj
        stripe_sub_id = invoice.get("subscription")
        local_sub = Subscription.query.filter_by(stripe_subscription_id=stripe_sub_id).first() if stripe_sub_id else None
        if local_sub:
            local_sub.status = "past_due"
            db.session.add(local_sub)
        _upsert_payment_from_invoice(invoice, status="failed", subscription=local_sub)
        db.session.commit()
        return

    # Subscription deleted/canceled
    if etype == "customer.subscription.deleted":
        stripe_sub = obj
        stripe_sub_id = stripe_sub.get("id")
        local_sub = Subscription.query.filter_by(stripe_subscription_id=stripe_sub_id).first() if stripe_sub_id else None
        if local_sub:
            local_sub.status = "cancelled"
            local_sub.cancelled_at = datetime.utcnow()
            local_sub.auto_renew = False
            db.session.add(local_sub)
            db.session.commit()
        return

