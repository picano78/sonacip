"""
Marketplace routes
Sellable packages of templates/workflows.
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import MarketplacePackage, MarketplacePackageItem, MarketplacePurchase, Template, Payment
from app.utils import admin_required, check_permission, log_action
from app.subscription.stripe_utils import stripe_enabled, create_marketplace_checkout_session
from app.marketplace.utils import install_purchase


bp = Blueprint("marketplace", __name__, url_prefix="/marketplace")


@bp.route("/")
def index():
    packages = (
        MarketplacePackage.query.filter_by(is_active=True)
        .order_by(MarketplacePackage.display_order.asc(), MarketplacePackage.created_at.desc())
        .all()
    )
    return render_template("marketplace/index.html", packages=packages)


@bp.route("/<string:slug>")
def detail(slug: str):
    pkg = MarketplacePackage.query.filter_by(slug=slug).first_or_404()
    items = pkg.items.all()
    return render_template("marketplace/detail.html", package=pkg, items=items)


@bp.route("/buy/<int:package_id>", methods=["POST"])
@login_required
def buy(package_id: int):
    pkg = MarketplacePackage.query.get_or_404(package_id)
    if not pkg.is_active:
        flash("Pacchetto non disponibile.", "warning")
        return redirect(url_for("marketplace.index"))

    # Society-scoped purchase when operating as a society
    society = current_user.get_primary_society()
    scope_society_id = society.id if society else None

    existing = MarketplacePurchase.query.filter_by(
        package_id=pkg.id,
        society_id=scope_society_id,
        user_id=current_user.id,
    ).first()
    if existing and existing.status == "completed":
        flash("Pacchetto già acquistato.", "info")
        if not existing.installed_at:
            try:
                install_purchase(existing, actor_user_id=current_user.id)
            except Exception:
                pass
        return redirect(url_for("marketplace.my_purchases"))

    purchase = MarketplacePurchase(
        package_id=pkg.id,
        user_id=current_user.id,
        society_id=scope_society_id,
        status="pending" if (pkg.price_one_time or 0) > 0 else "completed",
        created_at=datetime.utcnow(),
    )
    db.session.add(purchase)
    db.session.commit()

    if (pkg.price_one_time or 0) <= 0:
        try:
            install_purchase(purchase, actor_user_id=current_user.id)
        except Exception:
            pass
        log_action("marketplace_purchase_free", "MarketplacePurchase", purchase.id, f"package={pkg.slug}")
        flash("Pacchetto aggiunto.", "success")
        return redirect(url_for("marketplace.my_purchases"))

    # Stripe one-time checkout if configured and package has stripe price id
    if stripe_enabled() and pkg.stripe_price_one_time_id:
        try:
            success_url = url_for("marketplace.my_purchases", _external=True) + "?success=1"
            cancel_url = url_for("marketplace.detail", slug=pkg.slug, _external=True)
            checkout_url = create_marketplace_checkout_session(
                purchase_id=purchase.id,
                stripe_price_one_time_id=pkg.stripe_price_one_time_id,
                success_url=success_url,
                cancel_url=cancel_url,
            )
            return redirect(checkout_url)
        except Exception as exc:
            flash(f"Stripe non disponibile: {exc}", "warning")

    # Local fallback payment
    payment = Payment(
        user_id=current_user.id,
        society_id=scope_society_id,
        subscription_id=None,
        amount=float(pkg.price_one_time or 0),
        currency=(pkg.currency or "EUR"),
        status="completed",
        payment_method="manual",
        payment_date=datetime.utcnow(),
        description=f"Marketplace: {pkg.name}",
        transaction_id=f"LOCAL_MKT_{pkg.id}_{datetime.utcnow().timestamp()}",
        gateway="local",
    )
    db.session.add(payment)
    db.session.flush()
    purchase.payment_id = payment.id
    purchase.status = "completed"
    db.session.add(purchase)
    db.session.commit()

    try:
        install_purchase(purchase, actor_user_id=current_user.id)
    except Exception:
        pass
    log_action("marketplace_purchase", "MarketplacePurchase", purchase.id, f"package={pkg.slug}")
    flash("Acquisto completato.", "success")
    return redirect(url_for("marketplace.my_purchases"))


@bp.route("/my")
@login_required
def my_purchases():
    society = current_user.get_primary_society()
    scope_society_id = society.id if society else None
    purchases = MarketplacePurchase.query.filter_by(user_id=current_user.id, society_id=scope_society_id).order_by(MarketplacePurchase.created_at.desc()).all()
    return render_template("marketplace/my.html", purchases=purchases)


@bp.route("/install/<int:purchase_id>", methods=["POST"])
@login_required
def install(purchase_id: int):
    purchase = MarketplacePurchase.query.get_or_404(purchase_id)
    society = current_user.get_primary_society()
    scope_society_id = society.id if society else None
    if purchase.user_id != current_user.id or purchase.society_id != scope_society_id:
        abort(403)
    if purchase.status != "completed":
        flash("Acquisto non completato.", "warning")
        return redirect(url_for("marketplace.my_purchases"))
    install_purchase(purchase, actor_user_id=current_user.id)
    flash("Pacchetto installato.", "success")
    return redirect(url_for("marketplace.my_purchases"))


# -----------------------
# Admin management
# -----------------------
@bp.route("/admin", methods=["GET", "POST"])
@login_required
@admin_required
def admin_packages():
    if request.method == "POST":
        slug = (request.form.get("slug") or "").strip().lower()
        name = (request.form.get("name") or "").strip()
        description = (request.form.get("description") or "").strip() or None
        currency = (request.form.get("currency") or "EUR").strip().upper()
        stripe_price_one_time_id = (request.form.get("stripe_price_one_time_id") or "").strip() or None
        template_ids_raw = (request.form.get("template_ids") or "").strip()
        try:
            price_one_time = float(request.form.get("price_one_time") or 0)
        except Exception:
            price_one_time = 0.0
        try:
            display_order = int(request.form.get("display_order") or 0)
        except Exception:
            display_order = 0

        if not slug or len(slug) < 3:
            flash("Slug non valido.", "danger")
            return redirect(url_for("marketplace.admin_packages"))
        if not name:
            flash("Nome richiesto.", "danger")
            return redirect(url_for("marketplace.admin_packages"))
        if MarketplacePackage.query.filter_by(slug=slug).first():
            flash("Slug già esistente.", "danger")
            return redirect(url_for("marketplace.admin_packages"))

        pkg = MarketplacePackage(
            slug=slug,
            name=name,
            description=description,
            price_one_time=price_one_time,
            currency=currency,
            stripe_price_one_time_id=stripe_price_one_time_id,
            is_active=True,
            display_order=display_order,
            created_by=current_user.id,
            created_at=datetime.utcnow(),
        )
        db.session.add(pkg)
        db.session.flush()

        ids = []
        for part in template_ids_raw.replace("\n", ",").split(","):
            p = part.strip()
            if not p:
                continue
            try:
                ids.append(int(p))
            except Exception:
                continue
        ids = list(dict.fromkeys(ids))
        if ids:
            templates = Template.query.filter(Template.id.in_(ids)).all()
            for t in templates:
                db.session.add(MarketplacePackageItem(package_id=pkg.id, template_id=t.id, created_at=datetime.utcnow()))

        db.session.commit()
        log_action("marketplace_package_create", "MarketplacePackage", pkg.id, f"slug={slug}")
        flash("Pacchetto creato.", "success")
        return redirect(url_for("marketplace.admin_packages"))

    packages = MarketplacePackage.query.order_by(MarketplacePackage.display_order.asc(), MarketplacePackage.created_at.desc()).all()
    templates = Template.query.order_by(Template.created_at.desc()).limit(200).all()
    return render_template("marketplace/admin_packages.html", packages=packages, templates=templates)


@bp.route("/admin/<int:package_id>/toggle", methods=["POST"])
@login_required
@admin_required
def admin_toggle(package_id: int):
    pkg = MarketplacePackage.query.get_or_404(package_id)
    pkg.is_active = not bool(pkg.is_active)
    db.session.commit()
    log_action("marketplace_package_toggle", "MarketplacePackage", pkg.id, f"active={pkg.is_active}")
    flash("Pacchetto aggiornato.", "success")
    return redirect(url_for("marketplace.admin_packages"))

