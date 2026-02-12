"""
Idempotent database seeding for production.

This is intentionally deterministic: safe to run multiple times.
"""
from __future__ import annotations

from datetime import datetime, timezone


def seed_defaults(app) -> dict:
    """
    Seed baseline rows required for a working installation:
    - roles
    - permissions + assignments
    - plans (at least 'free')
    - global settings (appearance/privacy/social/storage/site)
    - default navbar config
    - dashboard templates
    - super admin user (from env)
    """
    from app import db
    from app.models import (
        AdsSetting,
        AdCampaign,
        AdCreative,
        AppearanceSetting,
        CustomizationKV,
        DashboardTemplate,
        Permission,
        Plan,
        PrivacySetting,
        Role,
        SiteCustomization,
        SocialSetting,
        SmtpSetting,
        EnterpriseSSOSetting,
        AutomationRule,
        StorageSetting,
        User,
    )

    summary: dict[str, int] = {
        "roles_created": 0,
        "permissions_created": 0,
        "plans_created": 0,
        "admin_created": 0,
        "settings_created": 0,
        "dashboard_templates_created": 0,
        "navbar_created": 0,
        "smtp_settings_created": 0,
        "automation_rules_created": 0,
    }

    with app.app_context():
        # ---------------------------------------------------------------------
        # Roles
        # ---------------------------------------------------------------------
        required_roles = {
            "super_admin": ("Super Admin", 100, "Amministratore principale con tutti i permessi"),
            "admin": ("Amministratore", 90, "Amministratore con permessi completi"),
            "moderator": ("Moderatore", 50, "Moderatore contenuti"),
            "society_admin": ("Admin Società", 45, "Amministratore società sportiva"),
            "societa": ("Società", 40, "Società sportiva"),
            "staff": ("Staff", 30, "Staff tecnico o dirigenziale"),
            "coach": ("Coach", 30, "Allenatore"),
            "atleta": ("Atleta", 20, "Atleta"),
            "athlete": ("Athlete", 20, "Atleta (alias)"),
            "appassionato": ("Appassionato", 10, "Utente appassionato"),
            "user": ("Utente", 10, "Utente standard"),
            "guest": ("Ospite", 1, "Utente ospite"),
        }
        for name, (display, level, description) in required_roles.items():
            if not Role.query.filter_by(name=name).first():
                db.session.add(
                    Role(
                        name=name,
                        display_name=display,
                        level=level,
                        is_system=True,
                        is_active=True,
                        description=description,
                    )
                )
                summary["roles_created"] += 1
        db.session.commit()

        # ---------------------------------------------------------------------
        # Permissions + Assignments
        # ---------------------------------------------------------------------
        # Keep a stable, minimal permission surface used by templates/routes.
        perm_defs = [
            ("admin:access", "admin", "access", "Accesso pannello admin"),
            ("social:comment", "social", "comment", "Interagire nel feed social"),
            ("social:post", "social", "post", "Pubblicare post"),
            ("events:view", "events", "view", "Vedere eventi"),
            ("events:create", "events", "create", "Creare eventi"),
            ("events:manage", "events", "manage", "Gestire eventi"),
            ("tournaments:view", "tournaments", "view", "Vedere tornei"),
            ("tournaments:manage", "tournaments", "manage", "Gestire tornei"),
            ("calendar:view", "calendar", "view", "Vedere calendario società"),
            ("calendar:manage", "calendar", "manage", "Gestire calendario società"),
            ("crm:access", "crm", "access", "Accedere al CRM"),
            ("crm:manage", "crm", "manage", "Gestire CRM"),
            ("tasks:manage", "tasks", "manage", "Gestire task e planner"),
            ("analytics:access", "analytics", "access", "Accedere alle analytics"),
            ("society:manage", "society", "manage", "Gestire società"),
            ("society:manage_staff", "society", "manage_staff", "Gestire staff/membri società"),
            ("users:edit", "users", "edit", "Gestire utenti"),
            ("users:view_all", "users", "view_all", "Vedere profili utenti"),
        ]

        perms: dict[str, Permission] = {}
        for name, resource, action, description in perm_defs:
            p = Permission.query.filter_by(name=name).first()
            if not p:
                p = Permission(
                    name=name,
                    resource=resource,
                    action=action,
                    description=description,
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                )
                db.session.add(p)
                db.session.flush()
                summary["permissions_created"] += 1
            perms[name] = p
        db.session.commit()

        # Assign permissions to roles (super admin is implicitly allowed, but keep consistent).
        role_super = Role.query.filter_by(name="super_admin").first()
        role_society = Role.query.filter_by(name="societa").first()
        role_society_admin = Role.query.filter_by(name="society_admin").first()
        role_staff = Role.query.filter_by(name="staff").first()
        role_coach = Role.query.filter_by(name="coach").first()
        role_user = Role.query.filter_by(name="appassionato").first()

        def _grant(role: Role | None, perm_names: list[str]) -> None:
            if not role:
                return
            existing = {p.name for p in role.permissions.all()}
            for n in perm_names:
                if n in existing:
                    continue
                role.permissions.append(perms[n])

        # Admin roles
        _grant(role_super, [p[0] for p in perm_defs])
        _grant(Role.query.filter_by(name="admin").first(), [p[0] for p in perm_defs])
        _grant(Role.query.filter_by(name="moderator").first(), ["social:comment"])

        # Society roles
        _grant(
            role_society,
            [
                "social:comment",
                "social:post",
                "events:view",
                "events:create",
                "events:manage",
                "tournaments:view",
                "tournaments:manage",
                "calendar:view",
                "calendar:manage",
                "crm:access",
                "crm:manage",
                "tasks:manage",
                "analytics:access",
                "society:manage",
                "society:manage_staff",
                "users:edit",
                "users:view_all",
            ],
        )
        _grant(
            role_society_admin,
            [
                "social:comment",
                "social:post",
                "events:view",
                "events:create",
                "events:manage",
                "tournaments:view",
                "tournaments:manage",
                "calendar:view",
                "calendar:manage",
                "crm:access",
                "crm:manage",
                "tasks:manage",
                "analytics:access",
                "society:manage",
                "society:manage_staff",
                "users:edit",
                "users:view_all",
            ],
        )
        _grant(role_staff, ["social:comment", "events:view", "tournaments:view", "calendar:view", "tasks:manage"])
        _grant(role_coach, ["social:comment", "events:view", "tournaments:view", "calendar:view", "tasks:manage"])
        _grant(role_user, ["social:comment"])

        db.session.commit()

        # ---------------------------------------------------------------------
        # Plans (needed by registration auto-attach)
        # ---------------------------------------------------------------------
        free_plan = Plan.query.filter_by(slug="free").first()
        if not free_plan:
            free_plan = Plan(
                name="Free",
                slug="free",
                description="Piano gratuito",
                price_monthly=0,
                price_yearly=0,
                currency="EUR",
                is_active=True,
                is_featured=False,
                display_order=0,
                # Keep CRM enabled so societies can operate out-of-the-box.
                has_crm=True,
                has_advanced_stats=False,
                has_api_access=False,
                has_white_label=False,
                has_priority_support=False,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.session.add(free_plan)
            summary["plans_created"] += 1
        else:
            # Ensure CRM is available out-of-the-box even on older DBs.
            if free_plan.has_crm is False:
                free_plan.has_crm = True
                free_plan.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        # ---------------------------------------------------------------------
        # Add-ons (feature-based upsells) - idempotent
        # ---------------------------------------------------------------------
        try:
            from app.models import AddOn

            default_addons = [
                {
                    "slug": "ads-self-serve",
                    "name": "Ads Self‑Serve",
                    "description": "Campagne sponsor gestibili dagli inserzionisti con report e budget.",
                    "feature_key": "ads_selfserve",
                    "price_one_time": 79.0,
                    "currency": "EUR",
                    "display_order": 20,
                },
                {
                    "slug": "analytics-pro",
                    "name": "Analytics Pro",
                    "description": "Analytics manageriali, KPI e suggerimenti automatici.",
                    "feature_key": "analytics_pro",
                    "price_one_time": 99.0,
                    "currency": "EUR",
                    "display_order": 30,
                },
                {
                    "slug": "enterprise-pack",
                    "name": "Enterprise Pack",
                    "description": "SSO, audit avanzato, SLA, compliance enterprise.",
                    "feature_key": "enterprise_pack",
                    "price_one_time": 199.0,
                    "currency": "EUR",
                    "display_order": 40,
                },
            ]
            for a in default_addons:
                row = AddOn.query.filter_by(slug=a["slug"]).first()
                if not row:
                    db.session.add(AddOn(**a))
            db.session.commit()
        except Exception:
            db.session.rollback()

        # ---------------------------------------------------------------------
        # Global settings singletons
        # ---------------------------------------------------------------------
        if not AppearanceSetting.query.filter_by(scope="global").first():
            db.session.add(AppearanceSetting(scope="global"))
            summary["settings_created"] += 1
        if not PrivacySetting.query.first():
            db.session.add(PrivacySetting())
            summary["settings_created"] += 1
        if not SocialSetting.query.first():
            db.session.add(SocialSetting())
            summary["settings_created"] += 1
        if not StorageSetting.query.first():
            db.session.add(StorageSetting())
            summary["settings_created"] += 1
        if not AdsSetting.query.first():
            db.session.add(AdsSetting())
            summary["settings_created"] += 1
        if not SiteCustomization.query.first():
            db.session.add(SiteCustomization())
            summary["settings_created"] += 1
        try:
            from app.models import PlatformFeeSetting
            if not PlatformFeeSetting.query.first():
                db.session.add(PlatformFeeSetting(take_rate_percent=5, min_fee_cents=0, currency="EUR"))
        except Exception:
            pass
        if not SmtpSetting.query.first():
            db.session.add(SmtpSetting(enabled=False))
            summary["smtp_settings_created"] += 1
        if not EnterpriseSSOSetting.query.first():
            db.session.add(EnterpriseSSOSetting(enabled=False, scopes='openid email profile'))
        db.session.commit()

        # ---------------------------------------------------------------------
        # Ads autopilot: default "house" campaign (idempotent)
        # ---------------------------------------------------------------------
        try:
            if not AdCampaign.query.first():
                camp = AdCampaign(
                    name="SONACIP - Promo Piani",
                    objective="traffic",
                    society_id=None,
                    is_active=True,
                    autopilot=True,
                    created_by=None,
                    created_at=datetime.now(timezone.utc),
                )
                db.session.add(camp)
                db.session.flush()
                db.session.add(
                    AdCreative(
                        campaign_id=camp.id,
                        placement="feed_inline",
                        headline="Sblocca funzionalità avanzate",
                        body="Passa a un piano superiore per CRM completo, automazioni e molto altro.",
                        image_url=None,
                        link_url="/subscription/plans",
                        cta_label="Vedi piani",
                        is_active=True,
                        weight=100,
                        created_by=None,
                        created_at=datetime.now(timezone.utc),
                    )
                )
                db.session.commit()
        except Exception:
            db.session.rollback()

        # ---------------------------------------------------------------------
        # Default automation rules (super admin can edit)
        # ---------------------------------------------------------------------
        import json as _json

        def _ensure_rule(event_type: str, name: str, actions: list[dict]) -> None:
            nonlocal summary
            if AutomationRule.query.filter_by(event_type=event_type).first():
                return
            db.session.add(
                AutomationRule(
                    name=name,
                    event_type=event_type,
                    condition="",
                    actions=_json.dumps(actions),
                    is_active=True,
                    max_retries=3,
                    retry_delay=60,
                    created_at=datetime.now(timezone.utc),
                )
            )
            db.session.commit()
            summary["automation_rules_created"] += 1

        _ensure_rule(
            "medical_certificate.expiring",
            "Certificato medico in scadenza (notify)",
            [
                {
                    "type": "notify",
                    "user_id": "{{ user_id }}",
                    "title": "Certificato medico in scadenza",
                    "message": "Il tuo certificato medico scade il {{ expires_on }} (tra {{ days_left }} giorni).",
                },
            ],
        )

        _ensure_rule(
            "fee.due",
            "Quota in scadenza (notify)",
            [
                {
                    "type": "notify",
                    "user_id": "{{ user_id }}",
                    "title": "Quota in scadenza",
                    "message": "Quota in scadenza il {{ due_on }}: €{{ amount_eur }}. {{ description }}",
                },
            ],
        )

        # ---------------------------------------------------------------------
        # Default navbar config (CustomizationKV)
        # ---------------------------------------------------------------------
        import json

        if not CustomizationKV.query.filter_by(scope="site", scope_key=None, key="navbar.links").first():
            default_links = [
                {"label": "Home", "endpoint": "social.feed", "icon": "bi-house-fill", "resource": "social", "action": "comment"},
                {"label": "Esplora", "endpoint": "social.explore", "icon": "bi-compass"},
                {"label": "Eventi", "endpoint": "events.index", "icon": "bi-calendar-event", "resource": "events", "action": "view"},
                {"label": "Tornei", "endpoint": "tournaments.list_tournaments", "icon": "bi-trophy", "resource": "tournaments", "action": "view"},
                {"label": "Calendario Società", "endpoint": "calendar.index", "icon": "bi-calendar3-range", "resource": "calendar", "action": "view"},
                {"label": "CRM", "endpoint": "crm.index", "icon": "bi-briefcase", "resource": "crm", "action": "access"},
                {"label": "Admin", "endpoint": "admin.dashboard", "icon": "bi-gear-fill", "resource": "admin", "action": "access"},
            ]
            db.session.add(
                CustomizationKV(
                    scope="site",
                    scope_key=None,
                    key="navbar.links",
                    value_json=json.dumps(default_links),
                )
            )
            db.session.commit()
            summary["navbar_created"] += 1

        # ---------------------------------------------------------------------
        # Dashboard templates
        # ---------------------------------------------------------------------
        if not DashboardTemplate.query.filter_by(role_name=None).first():
            db.session.add(
                DashboardTemplate(
                    role_name=None,
                    name="Default",
                    layout="grid",
                    widgets=json.dumps([{"type": "quick_links"}, {"type": "stats"}, {"type": "recent_notifications"}]),
                )
            )
            summary["dashboard_templates_created"] += 1
        db.session.commit()

        # ---------------------------------------------------------------------
        # Super admin user
        # ---------------------------------------------------------------------
        # Production requirement: do not rely on extra env vars.
        # If SUPERADMIN_* is not provided, default to the requested credentials.
        email = app.config.get("SUPERADMIN_EMAIL") or "picano78@gmail.com"
        password = app.config.get("SUPERADMIN_PASSWORD") or "Simone78"
        # Login form uses email, but we keep username aligned to avoid confusion in admin UI.
        username = email

        existing_admin = User.query.filter_by(email=email).first()
        if not existing_admin:
            role = Role.query.filter_by(name="super_admin").first()
            if not role:
                raise RuntimeError("Role super_admin missing even after seeding.")
            user = User(
                email=email,
                username=username,
                first_name="Simone",
                last_name="",
                is_active=True,
                is_verified=True,
                email_confirmed=True,
                role_obj=role,
                role_legacy=role.name,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            summary["admin_created"] += 1
        else:
            # Keep the seeded super admin consistent on re-runs (idempotent).
            changed = False
            try:
                role = Role.query.filter_by(name="super_admin").first()
                if role and existing_admin.role_id != role.id:
                    existing_admin.role_obj = role
                    existing_admin.role_legacy = role.name
                    changed = True
            except Exception:
                pass
            if existing_admin.username != username:
                existing_admin.username = username
                changed = True
            # Ensure email_confirmed is True for super admin
            if not getattr(existing_admin, 'email_confirmed', True):
                existing_admin.email_confirmed = True
                changed = True
            # If password is the default (no env override), ensure it matches.
            if not app.config.get("SUPERADMIN_PASSWORD"):
                try:
                    if not existing_admin.check_password(password):
                        existing_admin.set_password(password)
                        changed = True
                except Exception:
                    pass
            if changed:
                db.session.add(existing_admin)
                db.session.commit()

    return summary

