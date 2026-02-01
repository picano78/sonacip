"""
Idempotent database seeding for production.

This is intentionally deterministic: safe to run multiple times.
"""
from __future__ import annotations

from datetime import datetime


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
                    created_at=datetime.utcnow(),
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
        if not Plan.query.filter_by(slug="free").first():
            db.session.add(
                Plan(
                    name="Free",
                    slug="free",
                    description="Piano gratuito",
                    price_monthly=0,
                    price_yearly=0,
                    currency="EUR",
                    is_active=True,
                    is_featured=False,
                    display_order=0,
                    has_crm=False,
                    has_advanced_stats=False,
                    has_api_access=False,
                    has_white_label=False,
                    has_priority_support=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
            summary["plans_created"] += 1
        db.session.commit()

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
        if not SmtpSetting.query.first():
            db.session.add(SmtpSetting(enabled=False))
            summary["smtp_settings_created"] += 1
        db.session.commit()

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
        email = app.config.get("SUPERADMIN_EMAIL") or "admin@example.com"
        password = app.config.get("SUPERADMIN_PASSWORD")

        existing_admin = User.query.filter_by(email=email).first()
        if not existing_admin and password:
            role = Role.query.filter_by(name="super_admin").first()
            if not role:
                raise RuntimeError("Role super_admin missing even after seeding.")
            user = User(
                email=email,
                username="admin",
                first_name="Admin",
                last_name="SONACIP",
                is_active=True,
                is_verified=True,
                role_obj=role,
                role_legacy=role.name,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            summary["admin_created"] += 1

    return summary

