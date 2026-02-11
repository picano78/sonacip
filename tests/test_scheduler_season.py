from datetime import date, datetime


def test_season_end_for_before_august():
    from app.scheduler.season import season_end_for

    assert season_end_for(date(2026, 2, 10)) == date(2026, 7, 31)


def test_season_end_for_after_august():
    from app.scheduler.season import season_end_for

    assert season_end_for(date(2026, 8, 5)) == date(2027, 7, 31)


def test_iter_weekly_includes_last_week_before_end():
    from app.scheduler.season import iter_weekly

    start = datetime(2026, 8, 1, 10, 0, 0)
    end = datetime(2026, 8, 1, 12, 0, 0)
    season_end = date(2026, 8, 15)

    occ = list(iter_weekly(start, end, season_end))
    assert len(occ) == 3
    assert occ[0][0].date() == date(2026, 8, 1)
    assert occ[-1][0].date() == date(2026, 8, 15)

