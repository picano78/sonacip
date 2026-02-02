from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import stripe
from flask import current_app

from app import db
from app.models import (
    AddOn,
    AddOnEntitlement,
    MarketplacePurchase,
    Payment,
    Plan,
    PlatformFeeSetting,
    PlatformTransaction,
    SocietyFee,
    AdCampaign,
    Subscription,
)


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


def create_addon_checkout_session(addon: AddOn, *, user_id: int | None, society_id: int | None, success_url: str, cancel_url: str) -> str:
    """
    One-time payment checkout session to purchase an add-on.
    Requires addon.stripe_price_one_time_id.
    """
    _init_stripe()
    if not addon.stripe_price_one_time_id:
        raise ValueError("Add-on non configurato per Stripe (stripe_price_one_time_id mancante).")

    metadata = {
        "addon_id": str(addon.id),
        "feature_key": str(addon.feature_key),
        "society_id": str(society_id or ""),
        "user_id": str(user_id or ""),
    }
    sess = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{"price": addon.stripe_price_one_time_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        allow_promotion_codes=False,
        metadata=metadata,
    )
    return sess.url  # type: ignore[attr-defined]


def create_marketplace_checkout_session(*, purchase_id: int, stripe_price_one_time_id: str, success_url: str, cancel_url: str) -> str:
    """
    One-time payment checkout session for marketplace packages.
    """
    _init_stripe()
    if not stripe_price_one_time_id:
        raise ValueError("Pacchetto non configurato per Stripe (stripe_price_one_time_id mancante).")
    metadata = {"marketplace_purchase_id": str(purchase_id)}
    sess = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{"price": stripe_price_one_time_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        allow_promotion_codes=False,
        metadata=metadata,
    )
    return sess.url  # type: ignore[attr-defined]


def create_fee_checkout_session(fee: SocietyFee, *, success_url: str, cancel_url: str) -> str:
    """
    One-time payment checkout for a SocietyFee (dynamic amount via price_data).
    """
    _init_stripe()
    amount_cents = int(fee.amount_cents or 0)
    if amount_cents <= 0:
        raise ValueError("Importo quota non valido.")
    currency = (fee.currency or "EUR").lower()
    metadata = {
        "fee_id": str(fee.id),
        "society_id": str(fee.society_id or ""),
        "user_id": str(fee.user_id or ""),
    }
    sess = stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": currency,
                    "unit_amount": amount_cents,
                    "product_data": {
                        "name": f"Quota società (#{fee.id})",
                        "description": fee.description or "Quota",
                    },
                },
                "quantity": 1,
            }
        ],
        success_url=success_url,
        cancel_url=cancel_url,
        allow_promotion_codes=False,
        metadata=metadata,
    )
    return sess.url  # type: ignore[attr-defined]


def create_ads_topup_checkout_session(*, campaign: AdCampaign, amount_cents: int, success_url: str, cancel_url: str) -> str:
    """One-time payment to add budget to an ad campaign (self-serve)."""
    _init_stripe()
    if amount_cents <= 0:
        raise ValueError("Importo non valido.")
    metadata = {
        "ad_campaign_id": str(campaign.id),
        "society_id": str(campaign.society_id or ""),
        "user_id": str(campaign.advertiser_user_id or campaign.created_by or ""),
    }
    sess = stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "eur",
                    "unit_amount": int(amount_cents),
                    "product_data": {"name": f"Budget Ads (campagna #{campaign.id})"},
                },
                "quantity": 1,
            }
        ],
        success_url=success_url,
        cancel_url=cancel_url,
        allow_promotion_codes=False,
        metadata=metadata,
    )
    return sess.url  # type: ignore[attr-defined]


def _take_rate_for_amount(amount_eur: float) -> tuple[float, float]:
    """Return (platform_fee_eur, net_eur)."""
    settings = PlatformFeeSetting.query.first()
    pct = int(settings.take_rate_percent or 0) if settings else 0
    min_cents = int(settings.min_fee_cents or 0) if settings else 0
    gross_cents = int(round(float(amount_eur) * 100))
    fee_cents = int(round((gross_cents * max(0, pct)) / 100.0))
    fee_cents = max(fee_cents, max(0, min_cents))
    fee_cents = min(fee_cents, gross_cents)
    platform_fee = round(fee_cents / 100.0, 2)
    net = round((gross_cents - fee_cents) / 100.0, 2)
    return platform_fee, net

def _upsert_payment_from_checkout_session(session_obj: Any, status: str, *, user_id: int | None, society_id: int | None) -> Payment:
    """
    Create/update a Payment row from Stripe checkout session (mode=payment).
    transaction_id uses payment_intent when available.
    """
    tx_id = session_obj.get("payment_intent") or session_obj.get("id")
    existing = Payment.query.filter_by(transaction_id=tx_id).first()

    amount_total = session_obj.get("amount_total") or 0
    currency = (session_obj.get("currency") or "eur").upper()
    created = session_obj.get("created")
    created_dt = datetime.utcfromtimestamp(created) if created else datetime.utcnow()
    amount_eur = round(float(amount_total) / 100.0, 2)

    payload = json.dumps({"checkout_session": session_obj})

    if user_id is None:
        raise ValueError("checkout.session senza user_id (metadata) - impossibile creare Payment.")

    if not existing:
        p = Payment(
            user_id=user_id,
            society_id=society_id,
            subscription_id=None,
            amount=amount_eur,
            currency=currency,
            status=status,
            payment_method="stripe",
            payment_date=created_dt,
            description="Stripe checkout (add-on)",
            transaction_id=tx_id,
            gateway="stripe",
        )
        p.payment_metadata = payload
        db.session.add(p)
        db.session.flush()
        return p

    existing.status = status
    existing.gateway = "stripe"
    existing.payment_method = "stripe"
    existing.payment_metadata = payload
    db.session.add(existing)
    db.session.flush()
    return existing

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

    # Checkout completion: activate the subscription row OR finalize add-on purchase
    if etype == "checkout.session.completed":
        session_obj = obj
        mode = session_obj.get("mode")

        # Add-on flow (one-time payment)
        if mode == "payment" and session_obj.get("metadata", {}).get("addon_id"):
            meta = session_obj.get("metadata") or {}
            addon_id = int(meta.get("addon_id"))
            user_id = int(meta.get("user_id")) if str(meta.get("user_id") or "").strip() else None
            society_id = int(meta.get("society_id")) if str(meta.get("society_id") or "").strip() else None

            addon = AddOn.query.get(addon_id)
            if not addon:
                return
            if user_id is None:
                return
            p = _upsert_payment_from_checkout_session(session_obj, status="completed", user_id=user_id, society_id=society_id)

            # Create entitlement (idempotent per payment_id)
            exists = AddOnEntitlement.query.filter_by(payment_id=p.id).first()
            if not exists:
                db.session.add(
                    AddOnEntitlement(
                        addon_id=addon.id,
                        feature_key=addon.feature_key,
                        user_id=user_id,
                        society_id=society_id,
                        payment_id=p.id,
                        status="active",
                        source="stripe",
                        start_date=datetime.utcnow(),
                        end_date=None,
                        created_at=datetime.utcnow(),
                    )
                )
            db.session.commit()
            return

        # Marketplace package flow (one-time payment)
        if mode == "payment" and session_obj.get("metadata", {}).get("marketplace_purchase_id"):
            meta = session_obj.get("metadata") or {}
            purchase_id = int(meta.get("marketplace_purchase_id"))
            purchase = MarketplacePurchase.query.get(purchase_id)
            if not purchase:
                return
            if purchase.status == "completed":
                return
            p = _upsert_payment_from_checkout_session(
                session_obj,
                status="completed",
                user_id=purchase.user_id,
                society_id=purchase.society_id,
            )
            purchase.payment_id = p.id
            purchase.status = "completed"
            db.session.add(purchase)
            db.session.commit()
            try:
                from app.marketplace.utils import install_purchase
                install_purchase(purchase, actor_user_id=purchase.user_id)
            except Exception:
                pass
            return

        # Society fee payment flow (one-time payment)
        if mode == "payment" and session_obj.get("metadata", {}).get("fee_id"):
            meta = session_obj.get("metadata") or {}
            fee_id = int(meta.get("fee_id"))
            fee = SocietyFee.query.get(fee_id)
            if not fee:
                return
            if fee.status == "paid":
                return
            p = _upsert_payment_from_checkout_session(
                session_obj,
                status="completed",
                user_id=fee.user_id,
                society_id=fee.society_id,
            )
            fee.status = "paid"
            fee.paid_at = datetime.utcnow()
            db.session.add(fee)

            gross = float(p.amount or 0)
            platform_fee, net = _take_rate_for_amount(gross)
            existing = PlatformTransaction.query.filter_by(entity_type="SocietyFee", entity_id=fee.id, payment_id=p.id).first()
            if not existing:
                db.session.add(
                    PlatformTransaction(
                        society_id=fee.society_id,
                        user_id=fee.user_id,
                        payment_id=p.id,
                        entity_type="SocietyFee",
                        entity_id=fee.id,
                        gross_amount=gross,
                        platform_fee_amount=platform_fee,
                        net_amount=net,
                        currency=(p.currency or "EUR"),
                        status="collected",
                        created_at=datetime.utcnow(),
                    )
                )
            db.session.commit()
            return

        # Ads top-up (self-serve)
        if mode == "payment" and session_obj.get("metadata", {}).get("ad_campaign_id"):
            meta = session_obj.get("metadata") or {}
            camp_id = int(meta.get("ad_campaign_id"))
            camp = AdCampaign.query.get(camp_id)
            if not camp:
                return
            p = _upsert_payment_from_checkout_session(
                session_obj,
                status="completed",
                user_id=(camp.advertiser_user_id or camp.created_by),
                society_id=camp.society_id,
            )
            # Increase budget by amount_total
            amount_total = session_obj.get("amount_total") or 0
            camp.budget_cents = int(camp.budget_cents or 0) + int(amount_total)
            db.session.add(camp)
            db.session.commit()
            return

        # Subscription flow
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

