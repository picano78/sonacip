#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import json
from datetime import date, datetime, timedelta, timezone


def _parse_kinds(value: str) -> list[str]:
    kinds: list[str] = []
    for part in (value or "").split(","):
        p = part.strip()
        if not p:
            continue
        kinds.append(p)
    return kinds or ["24h", "1h"]


def _parse_int(value: str | None, default: int) -> int:
    try:
        return int(str(value))
    except Exception:
        return default


def _truthy(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    v = value.strip().lower()
    return v in ("1", "true", "yes", "y", "on", "enabled")


def main() -> int:
    """
    Unified maintenance job (idempotent by design).

    Runs:
    - calendar reminders (every 15 minutes; idempotent via SocietyCalendarReminderSent)
    - compliance reminders (safe to run more often; idempotent via *ReminderSent tables)

    Env:
    - RUN_CALENDAR_REMINDERS=true|false
    - RUN_COMPLIANCE=true|false
    - CALENDAR_REMINDER_KINDS="24h,1h"
    - CALENDAR_REMINDER_WINDOW_MINUTES="15"
    - CERT_EXPIRY_DAYS="14"
    - FEE_DUE_DAYS="7"
    - RUN_RETENTION=true|false
    """
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if root not in sys.path:
        sys.path.insert(0, root)

    from app import create_app, db
    from app.automation.utils import execute_rules
    from app.models import (
        AdEvent,
        MedicalCertificate,
        MedicalCertificateReminderSent,
        Notification,
        Opportunity,
        Post,
        Society,
        SocietyCalendarEvent,
        SocietyCalendarReminderSent,
        SocietyFee,
        SocietyFeeReminderSent,
        SocietyHealthSnapshot,
        SocietyMembership,
    )

    run_calendar = _truthy(os.environ.get("RUN_CALENDAR_REMINDERS"), True)
    run_compliance = _truthy(os.environ.get("RUN_COMPLIANCE"), True)
    run_retention = _truthy(os.environ.get("RUN_RETENTION"), True)

    calendar_kinds = _parse_kinds(os.environ.get("CALENDAR_REMINDER_KINDS", "24h,1h"))
    window_minutes = _parse_int(os.environ.get("CALENDAR_REMINDER_WINDOW_MINUTES"), 15)

    cert_days = _parse_int(os.environ.get("CERT_EXPIRY_DAYS"), 14)
    fee_days = _parse_int(os.environ.get("FEE_DUE_DAYS"), 7)

    now_utc = datetime.now(timezone.utc)
    today = date.today()

    app = create_app()
    with app.app_context():
        calendar_sent = 0
        compliance_sent = 0
        compliance_updated = 0
        health_created = 0
        ads_events_deleted = 0

        # --------------------------------------------------------------
        # Calendar reminders
        # --------------------------------------------------------------
        if run_calendar:
            window = timedelta(minutes=window_minutes)
            for kind in calendar_kinds:
                if not kind.endswith("h"):
                    continue
                try:
                    hours = int(kind[:-1])
                except Exception:
                    continue
                target_start = now_utc + timedelta(hours=hours)
                target_end = target_start + window

                events = (
                    SocietyCalendarEvent.query.filter(
                        SocietyCalendarEvent.start_datetime >= target_start.replace(tzinfo=None),
                        SocietyCalendarEvent.start_datetime < target_end.replace(tzinfo=None),
                    )
                    .order_by(SocietyCalendarEvent.start_datetime.asc())
                    .all()
                )

                for ev in events:
                    try:
                        recipients = ev.staff_members.all() + ev.athletes.all()
                    except Exception:
                        recipients = []

                    for u in recipients:
                        exists = SocietyCalendarReminderSent.query.filter_by(
                            event_id=ev.id, user_id=u.id, kind=kind
                        ).first()
                        if exists:
                            continue

                        db.session.add(
                            Notification(
                                user_id=u.id,
                                title=f"Promemoria evento ({kind})",
                                message=f'{ev.title} - {ev.start_datetime.strftime("%d/%m/%Y %H:%M")}',
                                notification_type="calendar",
                                link=f"/scheduler/calendar/{ev.id}",
                            )
                        )
                        db.session.add(
                            SocietyCalendarReminderSent(
                                event_id=ev.id,
                                user_id=u.id,
                                kind=kind,
                                sent_at=datetime.utcnow(),
                            )
                        )
                        calendar_sent += 1

                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()

        # --------------------------------------------------------------
        # Compliance: normalize status + reminders
        # --------------------------------------------------------------
        if run_compliance:
            # Auto-expire certificates
            try:
                expired = (
                    MedicalCertificate.query.filter(
                        MedicalCertificate.status == "valid",
                        MedicalCertificate.expires_on < today,
                    ).all()
                )
                for c in expired:
                    c.status = "expired"
                    compliance_updated += 1
                if compliance_updated:
                    db.session.commit()
            except Exception:
                db.session.rollback()

            # Expiry reminders
            cert_cutoff = today + timedelta(days=cert_days)
            certs = (
                MedicalCertificate.query.filter(
                    MedicalCertificate.status == "valid",
                    MedicalCertificate.expires_on >= today,
                    MedicalCertificate.expires_on <= cert_cutoff,
                )
                .order_by(MedicalCertificate.expires_on.asc())
                .all()
            )
            for c in certs:
                kind = f"{cert_days}d"
                already = MedicalCertificateReminderSent.query.filter_by(
                    certificate_id=c.id, user_id=c.user_id, kind=kind
                ).first()
                if already:
                    continue
                payload = {
                    "society_id": c.society_id,
                    "user_id": c.user_id,
                    "certificate_id": c.id,
                    "expires_on": c.expires_on.isoformat(),
                    "days_left": (c.expires_on - today).days,
                    "kind": kind,
                }
                execute_rules("medical_certificate.expiring", payload=payload)
                db.session.add(
                    MedicalCertificateReminderSent(
                        certificate_id=c.id,
                        user_id=c.user_id,
                        kind=kind,
                        sent_at=datetime.utcnow(),
                    )
                )
                try:
                    db.session.commit()
                    compliance_sent += 1
                except Exception:
                    db.session.rollback()

            # Fee reminders
            fee_cutoff = today + timedelta(days=fee_days)
            fees = (
                SocietyFee.query.filter(
                    SocietyFee.status == "pending",
                    SocietyFee.due_on >= today,
                    SocietyFee.due_on <= fee_cutoff,
                )
                .order_by(SocietyFee.due_on.asc())
                .all()
            )
            for f in fees:
                kind = f"{fee_days}d"
                already = SocietyFeeReminderSent.query.filter_by(
                    fee_id=f.id, user_id=f.user_id, kind=kind
                ).first()
                if already:
                    continue
                payload = {
                    "society_id": f.society_id,
                    "user_id": f.user_id,
                    "fee_id": f.id,
                    "due_on": f.due_on.isoformat(),
                    "amount_cents": f.amount_cents,
                    "amount_eur": round((f.amount_cents or 0) / 100.0, 2),
                    "currency": f.currency,
                    "description": f.description or "",
                    "days_left": (f.due_on - today).days,
                    "kind": kind,
                }
                execute_rules("fee.due", payload=payload)
                db.session.add(
                    SocietyFeeReminderSent(
                        fee_id=f.id,
                        user_id=f.user_id,
                        kind=kind,
                        sent_at=datetime.utcnow(),
                    )
                )
                try:
                    db.session.commit()
                    compliance_sent += 1
                except Exception:
                    db.session.rollback()

        # --------------------------------------------------------------
        # Retention: weekly health snapshot per society
        # --------------------------------------------------------------
        if run_retention:
            try:
                week_key = datetime.utcnow().strftime("%G-W%V")  # ISO week
                cutoff_dt = datetime.utcnow() - timedelta(days=7)
                societies = Society.query.all()

                for s in societies:
                    exists = SocietyHealthSnapshot.query.filter_by(society_id=s.id, week_key=week_key).first()
                    if exists:
                        continue

                    members_active = SocietyMembership.query.filter_by(society_id=s.id, status='active').count()
                    posts_7d = Post.query.filter(Post.society_id == s.id, Post.created_at >= cutoff_dt).count()
                    events_7d = SocietyCalendarEvent.query.filter(SocietyCalendarEvent.society_id == s.id, SocietyCalendarEvent.created_at >= cutoff_dt).count()
                    opps_7d = Opportunity.query.filter(Opportunity.society_id == s.id, Opportunity.created_at >= cutoff_dt).count()

                    # Simple adoption score 0-100
                    score = 20
                    score += min(20, posts_7d * 5)
                    score += min(20, events_7d * 5)
                    score += min(20, opps_7d * 5)
                    score += min(20, int(members_active / 5) * 5)
                    score = max(0, min(100, int(score)))

                    details = {
                        "members_active": members_active,
                        "posts_7d": posts_7d,
                        "events_7d": events_7d,
                        "opportunities_7d": opps_7d,
                    }

                    db.session.add(
                        SocietyHealthSnapshot(
                            society_id=s.id,
                            week_key=week_key,
                            score=score,
                            details=json.dumps(details),
                            created_at=datetime.utcnow(),
                        )
                    )
                    health_created += 1

                if health_created:
                    db.session.commit()
            except Exception:
                db.session.rollback()

        # --------------------------------------------------------------
        # Ads maintenance (retention): delete old ad events
        # --------------------------------------------------------------
        try:
            cutoff = datetime.utcnow() - timedelta(days=90)
            ads_events_deleted = AdEvent.query.filter(AdEvent.created_at < cutoff).delete()
            db.session.commit()
        except Exception:
            db.session.rollback()

        print(
            "maintenance "
            f"calendar_reminders_sent={calendar_sent} "
            f"compliance_status_updated={compliance_updated} "
            f"compliance_reminders_sent={compliance_sent} "
            f"health_snapshots_created={health_created} "
            f"ads_events_deleted={ads_events_deleted}"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

