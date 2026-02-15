"""
Marketplace routes
- User listings (annunci di vendita) – Facebook Marketplace style
- Listing promotions (boost / in evidenza) – Subito.it style
- Admin packages (internal marketplace for templates/workflows)
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from PIL import Image

from app import db
from app.models import (
    MarketplacePackage, MarketplacePackageItem, MarketplacePurchase,
    MarketplaceListing, Template, Payment,
    PromotionTier, ListingPromotion, PlatformPaymentSetting
)
from app.utils import admin_required, check_permission, log_action
from app.subscription.stripe_utils import stripe_enabled, create_marketplace_checkout_session
from app.marketplace.utils import install_purchase

LISTING_EXPIRY_DAYS = 30


bp = Blueprint("marketplace", __name__, url_prefix="/marketplace")

ALLOWED_IMAGE_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def _allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXT


def _save_listing_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    if not _allowed_image(file_storage.filename):
        return None
    upload_dir = os.path.join(current_app.config.get('UPLOAD_FOLDER', os.path.join(current_app.root_path, '..', 'uploads')), 'marketplace')
    os.makedirs(upload_dir, exist_ok=True)
    ext = file_storage.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(upload_dir, unique_name)
    try:
        img = Image.open(file_storage)
        if img.mode in ('RGBA', 'LA'):
            img = img.convert('RGB')
        img.thumbnail((600, 600))
        img.save(filepath, quality=50, optimize=True)
    except Exception:
        file_storage.seek(0)
        file_storage.save(filepath)
    return f"marketplace/{unique_name}"


def _delete_listing_image(relative_path):
    try:
        upload_base = os.path.join(current_app.config.get('UPLOAD_FOLDER', os.path.join(current_app.root_path, '..', 'uploads')))
        full_path = os.path.join(upload_base, relative_path)
        if os.path.exists(full_path):
            os.remove(full_path)
    except Exception:
        pass


def _expire_old_listings():
    now = datetime.now(timezone.utc)
    expired = MarketplaceListing.query.filter(
        MarketplaceListing.status == 'active',
        MarketplaceListing.expires_at.isnot(None),
        MarketplaceListing.expires_at <= now
    ).all()
    for listing in expired:
        if listing.image_1:
            _delete_listing_image(listing.image_1)
        if listing.image_2:
            _delete_listing_image(listing.image_2)
        if listing.image_3:
            _delete_listing_image(listing.image_3)
        if listing.image_4:
            _delete_listing_image(listing.image_4)
        db.session.delete(listing)
    if expired:
        db.session.commit()

    promo_expired = MarketplaceListing.query.filter(
        MarketplaceListing.is_promoted == True,
        MarketplaceListing.promotion_expires_at.isnot(None),
        MarketplaceListing.promotion_expires_at <= now
    ).all()
    for listing in promo_expired:
        listing.is_promoted = False
        listing.promotion_expires_at = None
    if promo_expired:
        db.session.commit()


def _seed_default_promotion_tiers():
    if PromotionTier.query.count() == 0:
        defaults = [
            PromotionTier(name='In Evidenza 7 giorni', slug='evidenza_7', description='Il tuo annuncio in cima per 7 giorni',
                          duration_days=7, price=2.99, icon='bi-star', color='#ff9800', display_order=1),
            PromotionTier(name='In Evidenza 14 giorni', slug='evidenza_14', description='Il tuo annuncio in cima per 14 giorni',
                          duration_days=14, price=4.99, icon='bi-star-fill', color='#f57c00', display_order=2),
            PromotionTier(name='In Evidenza 30 giorni', slug='evidenza_30', description='Il tuo annuncio in cima per 30 giorni',
                          duration_days=30, price=7.99, icon='bi-stars', color='#e65100', display_order=3),
        ]
        for t in defaults:
            db.session.add(t)
        db.session.commit()


@bp.before_request
def _check_expired():
    _expire_old_listings()


@bp.route("/")
@login_required
def index():

    category = request.args.get('category', '')
    search_q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    query = MarketplaceListing.query.filter_by(status='active')

    if category:
        query = query.filter_by(category=category)
    if search_q:
        query = query.filter(
            db.or_(
                MarketplaceListing.title.ilike(f'%{search_q}%'),
                MarketplaceListing.description.ilike(f'%{search_q}%'),
                MarketplaceListing.location.ilike(f'%{search_q}%'),
            )
        )

    query = query.order_by(
        MarketplaceListing.is_promoted.desc(),
        MarketplaceListing.created_at.desc()
    )
    pagination = query.paginate(page=page, per_page=12, error_out=False)
    listings = pagination.items

    categories = MarketplaceListing.CATEGORIES

    return render_template(
        "marketplace/listings.html",
        listings=listings,
        pagination=pagination,
        categories=categories,
        current_category=category,
        search_q=search_q,
    )


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create_listing():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        category = request.form.get("category", "altro")
        condition = request.form.get("condition", "usato")
        location = (request.form.get("location") or "").strip()

        try:
            price = float(request.form.get("price") or 0)
        except (ValueError, TypeError):
            price = 0.0

        if not title or len(title) < 3:
            flash("Il titolo deve avere almeno 3 caratteri.", "danger")
            return redirect(url_for("marketplace.create_listing"))

        if price < 0:
            flash("Il prezzo non può essere negativo.", "danger")
            return redirect(url_for("marketplace.create_listing"))

        images = {}
        for i in range(1, 5):
            f = request.files.get(f"image_{i}")
            if f and f.filename:
                saved = _save_listing_image(f)
                if saved:
                    images[f"image_{i}"] = saved

        listing = MarketplaceListing(
            user_id=current_user.id,
            title=title,
            description=description,
            price=price,
            category=category,
            condition=condition,
            location=location,
            image_1=images.get("image_1"),
            image_2=images.get("image_2"),
            image_3=images.get("image_3"),
            image_4=images.get("image_4"),
            expires_at=datetime.now(timezone.utc) + timedelta(days=LISTING_EXPIRY_DAYS),
        )
        db.session.add(listing)
        db.session.commit()
        log_action("marketplace_listing_create", "MarketplaceListing", listing.id, f"title={title}")
        flash("Annuncio pubblicato! Resterà visibile per 30 giorni, poi verrà cancellato automaticamente.", "success")
        return redirect(url_for("marketplace.listing_detail", listing_id=listing.id))

    categories = MarketplaceListing.CATEGORIES
    conditions = MarketplaceListing.CONDITIONS
    return render_template("marketplace/create_listing.html", categories=categories, conditions=conditions)


@bp.route("/listing/<int:listing_id>")
@login_required
def listing_detail(listing_id):
    listing = MarketplaceListing.query.get_or_404(listing_id)
    if listing.status != 'active' and listing.user_id != current_user.id and not getattr(current_user, 'is_super_admin', False):
        abort(404)
    if listing.user_id != current_user.id:
        listing.views_count = (listing.views_count or 0) + 1
        db.session.commit()

    seller_listings = MarketplaceListing.query.filter(
        MarketplaceListing.user_id == listing.user_id,
        MarketplaceListing.id != listing.id,
        MarketplaceListing.status == 'active'
    ).order_by(MarketplaceListing.created_at.desc()).limit(4).all()

    similar = MarketplaceListing.query.filter(
        MarketplaceListing.category == listing.category,
        MarketplaceListing.id != listing.id,
        MarketplaceListing.status == 'active'
    ).order_by(MarketplaceListing.created_at.desc()).limit(4).all()

    return render_template(
        "marketplace/listing_detail.html",
        listing=listing,
        seller_listings=seller_listings,
        similar=similar,
    )


@bp.route("/listing/<int:listing_id>/edit", methods=["GET", "POST"])
@login_required
def edit_listing(listing_id):
    listing = MarketplaceListing.query.get_or_404(listing_id)
    if listing.user_id != current_user.id and not getattr(current_user, 'is_super_admin', False):
        abort(403)

    if request.method == "POST":
        listing.title = (request.form.get("title") or listing.title).strip()
        listing.description = (request.form.get("description") or "").strip()
        listing.category = request.form.get("category", listing.category)
        listing.condition = request.form.get("condition", listing.condition)
        listing.location = (request.form.get("location") or "").strip()

        try:
            listing.price = float(request.form.get("price") or 0)
        except (ValueError, TypeError):
            pass

        for i in range(1, 5):
            f = request.files.get(f"image_{i}")
            if f and f.filename:
                saved = _save_listing_image(f)
                if saved:
                    setattr(listing, f"image_{i}", saved)
            if request.form.get(f"remove_image_{i}"):
                setattr(listing, f"image_{i}", None)

        new_status = request.form.get("status")
        if new_status in ('active', 'sold', 'paused'):
            listing.status = new_status

        db.session.commit()
        flash("Annuncio aggiornato.", "success")
        return redirect(url_for("marketplace.listing_detail", listing_id=listing.id))

    categories = MarketplaceListing.CATEGORIES
    conditions = MarketplaceListing.CONDITIONS
    return render_template("marketplace/edit_listing.html", listing=listing, categories=categories, conditions=conditions)


@bp.route("/listing/<int:listing_id>/delete", methods=["POST"])
@login_required
def delete_listing(listing_id):
    listing = MarketplaceListing.query.get_or_404(listing_id)
    if listing.user_id != current_user.id and not getattr(current_user, 'is_super_admin', False):
        abort(403)
    db.session.delete(listing)
    db.session.commit()
    log_action("marketplace_listing_delete", "MarketplaceListing", listing_id, f"title={listing.title}")
    flash("Annuncio eliminato.", "success")
    return redirect(url_for("marketplace.my_listings"))


@bp.route("/listing/<int:listing_id>/sold", methods=["POST"])
@login_required
def mark_sold(listing_id):
    listing = MarketplaceListing.query.get_or_404(listing_id)
    if listing.user_id != current_user.id:
        abort(403)
    listing.status = 'sold'
    db.session.commit()
    flash("Annuncio contrassegnato come venduto.", "success")
    return redirect(url_for("marketplace.my_listings"))


@bp.route("/listing/<int:listing_id>/renew", methods=["POST"])
@login_required
def renew_listing(listing_id):
    listing = MarketplaceListing.query.get_or_404(listing_id)
    if listing.user_id != current_user.id:
        abort(403)
    if listing.status == 'expired':
        listing.status = 'active'
    listing.expires_at = datetime.now(timezone.utc) + timedelta(days=LISTING_EXPIRY_DAYS)
    db.session.commit()
    flash("Annuncio rinnovato per altri 60 giorni.", "success")
    return redirect(url_for("marketplace.my_listings"))


@bp.route("/my-listings")
@login_required
def my_listings():
    status_filter = request.args.get('status', '')
    query = MarketplaceListing.query.filter_by(user_id=current_user.id)
    if status_filter:
        query = query.filter_by(status=status_filter)
    listings = query.order_by(MarketplaceListing.created_at.desc()).all()
    return render_template("marketplace/my_listings.html", listings=listings, status_filter=status_filter)


# =============================================================
# Promotions / In Evidenza (Subito.it style)
# =============================================================

@bp.route("/listing/<int:listing_id>/promote")
@login_required
def promote_listing(listing_id):
    listing = MarketplaceListing.query.get_or_404(listing_id)
    if listing.user_id != current_user.id:
        abort(403)
    if listing.status != 'active':
        flash("Solo gli annunci attivi possono essere messi in evidenza.", "warning")
        return redirect(url_for("marketplace.listing_detail", listing_id=listing_id))

    _seed_default_promotion_tiers()
    tiers = PromotionTier.query.filter_by(is_active=True).order_by(PromotionTier.display_order.asc()).all()

    return render_template("marketplace/promote_listing.html", listing=listing, tiers=tiers)


@bp.route("/listing/<int:listing_id>/promote/<int:tier_id>", methods=["POST"])
@login_required
def pay_promotion(listing_id, tier_id):
    listing = MarketplaceListing.query.get_or_404(listing_id)
    if listing.user_id != current_user.id:
        abort(403)
    if listing.status != 'active':
        flash("Solo gli annunci attivi possono essere messi in evidenza.", "warning")
        return redirect(url_for("marketplace.listing_detail", listing_id=listing_id))

    tier = PromotionTier.query.get_or_404(tier_id)
    if not tier.is_active:
        flash("Piano promozione non disponibile.", "warning")
        return redirect(url_for("marketplace.promote_listing", listing_id=listing_id))

    promotion = ListingPromotion(
        listing_id=listing.id,
        tier_id=tier.id,
        user_id=current_user.id,
        status='pending',
        amount_paid=tier.price,
        currency=tier.currency or 'EUR',
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(promotion)
    db.session.commit()

    if stripe_enabled() and tier.stripe_price_id:
        try:
            from app.subscription.stripe_utils import _init_stripe
            import stripe as stripe_lib
            _init_stripe()
            success_url = url_for("marketplace.promotion_success", promotion_id=promotion.id, _external=True)
            cancel_url = url_for("marketplace.promote_listing", listing_id=listing.id, _external=True)
            sess = stripe_lib.checkout.Session.create(
                mode="payment",
                line_items=[{"price": tier.stripe_price_id, "quantity": 1}],
                success_url=success_url,
                cancel_url=cancel_url,
                allow_promotion_codes=False,
                metadata={
                    "listing_promotion_id": str(promotion.id),
                    "listing_id": str(listing.id),
                    "tier_id": str(tier.id),
                    "user_id": str(current_user.id),
                },
            )
            return redirect(sess.url)
        except Exception as exc:
            current_app.logger.warning(f"Stripe promotion checkout failed: {exc}")

    _activate_promotion(promotion)
    log_action("listing_promotion_activate", "ListingPromotion", promotion.id,
               f"listing={listing.id} tier={tier.slug}")
    flash(f"Annuncio messo in evidenza per {tier.duration_days} giorni!", "success")
    return redirect(url_for("marketplace.listing_detail", listing_id=listing.id))


@bp.route("/promotion/<int:promotion_id>/success")
@login_required
def promotion_success(promotion_id):
    promotion = ListingPromotion.query.get_or_404(promotion_id)
    if promotion.user_id != current_user.id:
        abort(403)
    if promotion.status == 'pending':
        _activate_promotion(promotion)
    flash("Pagamento completato! Il tuo annuncio è ora in evidenza.", "success")
    return redirect(url_for("marketplace.listing_detail", listing_id=promotion.listing_id))


def _activate_promotion(promotion):
    now = datetime.now(timezone.utc)
    tier = db.session.get(PromotionTier, promotion.tier_id)
    duration = tier.duration_days if tier else 7

    promotion.status = 'active'
    promotion.starts_at = now
    promotion.ends_at = now + timedelta(days=duration)

    if not promotion.payment_id:
        payment = Payment(
            user_id=promotion.user_id,
            amount=float(promotion.amount_paid or 0),
            currency=(promotion.currency or 'EUR'),
            status='completed',
            payment_method='local',
            payment_date=now,
            description=f"Promozione annuncio #{promotion.listing_id}",
            transaction_id=f"PROMO_{promotion.id}_{now.timestamp()}",
            gateway='local',
        )
        db.session.add(payment)
        db.session.flush()
        promotion.payment_id = payment.id

    listing = db.session.get(MarketplaceListing, promotion.listing_id)
    if listing:
        listing.is_promoted = True
        listing.promotion_expires_at = promotion.ends_at
        if listing.expires_at and listing.expires_at < promotion.ends_at:
            listing.expires_at = promotion.ends_at + timedelta(days=7)

    db.session.commit()


# =============================================================
# Legacy: Admin Packages (templates/workflows marketplace)
# =============================================================
@bp.route("/packages")
def packages_index():
    packages = (
        MarketplacePackage.query.filter_by(is_active=True)
        .order_by(MarketplacePackage.display_order.asc(), MarketplacePackage.created_at.desc())
        .all()
    )
    return render_template("marketplace/index.html", packages=packages)


@bp.route("/packages/<string:slug>")
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
        return redirect(url_for("marketplace.packages_index"))

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
        created_at=datetime.now(timezone.utc),
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

    payment = Payment(
        user_id=current_user.id,
        society_id=scope_society_id,
        subscription_id=None,
        amount=float(pkg.price_one_time or 0),
        currency=(pkg.currency or "EUR"),
        status="completed",
        payment_method="manual",
        payment_date=datetime.now(timezone.utc),
        description=f"Marketplace: {pkg.name}",
        transaction_id=f"LOCAL_MKT_{pkg.id}_{datetime.now(timezone.utc).timestamp()}",
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
    # Show all purchases made by the user, regardless of society
    purchases = MarketplacePurchase.query.filter_by(user_id=current_user.id).order_by(MarketplacePurchase.created_at.desc()).all()
    return render_template("marketplace/my.html", purchases=purchases)


@bp.route("/install/<int:purchase_id>", methods=["POST"])
@login_required
def install(purchase_id: int):
    purchase = MarketplacePurchase.query.get_or_404(purchase_id)
    # Verify that the purchase belongs to the current user
    if purchase.user_id != current_user.id:
        abort(403)
    
    # If purchase is for a society, verify user can manage that society
    if purchase.society_id:
        if not check_permission('society_admin', purchase.society_id, current_user.id):
            flash("Non hai i permessi per installare questo pacchetto per la società specificata.", "danger")
            return redirect(url_for("marketplace.my_purchases"))
    
    if purchase.status != "completed":
        flash("Acquisto non completato.", "warning")
        return redirect(url_for("marketplace.my_purchases"))
    install_purchase(purchase, actor_user_id=current_user.id)
    flash("Pacchetto installato.", "success")
    return redirect(url_for("marketplace.my_purchases"))


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
            created_at=datetime.now(timezone.utc),
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
                db.session.add(MarketplacePackageItem(package_id=pkg.id, template_id=t.id, created_at=datetime.now(timezone.utc)))

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
