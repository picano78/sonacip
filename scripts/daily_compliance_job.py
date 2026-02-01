#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta


def _parse_days(value: str, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def main() -> int:
    # Ensure project root on path when executed as script.
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if root not in sys.path:
        sys.path.insert(0, root)

    from app import create_app, db
    from app.automation.utils import execute_rules
    from app.models import (
        MedicalCertificate,
        MedicalCertificateReminderSent,
        SocietyFee,
        SocietyFeeReminderSent,
    )

    # Windows (days before due/expiry)
    cert_days = _parse_days(os.environ.get("CERT_EXPIRY_DAYS", "14"), 14)
    fee_days = _parse_days(os.environ.get("FEE_DUE_DAYS", "7"), 7)

    today = date.today()

    app = create_app()
    with app.app_context():
        sent = 0

        # ------------------------------------------------------------------
        # Medical certificate expiry reminders
        # ------------------------------------------------------------------
        cert_cutoff = today + timedelta(days=cert_days)
        certs = (
            MedicalCertificate.query.filter(
                MedicalCertificate.status == 'valid',
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
            db.session.add(MedicalCertificateReminderSent(certificate_id=c.id, user_id=c.user_id, kind=kind, sent_at=datetime.utcnow()))
            db.session.commit()
            sent += 1

        # ------------------------------------------------------------------
        # Society fee due reminders
        # ------------------------------------------------------------------
        fee_cutoff = today + timedelta(days=fee_days)
        fees = (
            SocietyFee.query.filter(
                SocietyFee.status == 'pending',
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
            db.session.add(SocietyFeeReminderSent(fee_id=f.id, user_id=f.user_id, kind=kind, sent_at=datetime.utcnow()))
            db.session.commit()
            sent += 1

        print(f"compliance_reminders_sent={sent}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

