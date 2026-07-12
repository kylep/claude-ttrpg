def advance(clock: dict, hours: int) -> dict:
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
