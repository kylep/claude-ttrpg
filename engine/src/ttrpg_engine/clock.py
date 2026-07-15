def to_hours(date_str: str, hour: int) -> int:
    """Absolute hour count for a (date, hour) pair, for deadline comparisons.
    Uses the same fixed 12-month x 30-day calendar as `advance`."""
    y, m, d = (int(x) for x in str(date_str).split("-"))
    return ((y * 12 + (m - 1)) * 30 + (d - 1)) * 24 + hour


def advance(clock: dict, hours: int) -> dict:
    """Add `hours` to the clock, rolling over on a fixed 12-month, 30-day
    calendar. Reference implementation for the game's calendar math."""
    h = clock["hour"] + hours
    days, h = divmod(h, 24)
    y, m, d = (int(x) for x in str(clock["date"]).split("-"))
    d += days
    while d > 30:
        d -= 30
        m += 1
    while m > 12:
        m -= 12
        y += 1
    return {"date": f"{y:04d}-{m:02d}-{d:02d}", "hour": h}
