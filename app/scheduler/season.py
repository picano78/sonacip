"""Season helpers for weekly bookings (Aug 1 -> Jul 31)."""

from __future__ import annotations

from datetime import date, datetime, timedelta


def season_end_for(d: date) -> date:
    """
    Season is Aug 1 -> Jul 31.
    Given a date, return the season end date (Jul 31) for the season containing it.
    """
    year = d.year
    aug1 = date(year, 8, 1)
    if d >= aug1:
        return date(year + 1, 7, 31)
    return date(year, 7, 31)


def iter_weekly(start_dt: datetime, end_dt: datetime, season_end_date: date):
    """
    Yield (start_dt, end_dt) weekly until season_end_date (inclusive).
    """
    dur = end_dt - start_dt
    cur = start_dt
    while cur.date() <= season_end_date:
        yield cur, cur + dur
        cur = cur + timedelta(days=7)

