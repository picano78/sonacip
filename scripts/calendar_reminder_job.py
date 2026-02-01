#!/usr/bin/env python3
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone


def _parse_kinds(value: str) -> list[str]:
    kinds = []
    for part in (value or "").split(","):
        p = part.strip()
        if not p:
            continue
        kinds.append(p)
    return kinds or ["24h", "1h"]


def main() -> int:
    """
    Calendar reminder job (idempotent).

    Env:
    - CALENDAR_REMINDER_KINDS="24h,1h"
    - CALENDAR_REMINDER_WINDOW_MINUTES="15"
    """
    from app import create_app, db
    from app.models import (
        Notification,
        SocietyCalendarEvent,
        SocietyCalendarReminderSent,
    )

    kinds = _parse_kinds(os.environ.get("CALENDAR_REMINDER_KINDS", "24h,1h"))
    window_minutes = int(os.environ.get("CALENDAR_REMINDER_WINDOW_MINUTES", "15"))

    now = datetime.now(timezone.utc)
    window = timedelta(minutes=window_minutes)

    app = create_app()
    with app.app_context():
        sent = 0
        for kind in kinds:
            if kind.endswith("h"):
                hours = int(kind[:-1])
                target_start = now + timedelta(hours=hours)
                target_end = target_start + window
            else:
                # Unknown kind; skip
                continue

            # Events starting in [target_start, target_end)
            events = (
                SocietyCalendarEvent.query.filter(
                    SocietyCalendarEvent.start_datetime >= target_start.replace(tzinfo=None),
                    SocietyCalendarEvent.start_datetime < target_end.replace(tzinfo=None),
                )
                .order_by(SocietyCalendarEvent.start_datetime.asc())
                .all()
            )

            for ev in events:
                recipients = []
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
                    sent += 1

            db.session.commit()

        print(f"calendar_reminders_sent={sent}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

