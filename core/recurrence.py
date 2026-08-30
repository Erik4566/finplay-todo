"""Opakujúce sa úlohy.

Podporená podmnožina iCalendar RRULE:
    FREQ=DAILY|WEEKLY|MONTHLY|YEARLY  (povinné)
    INTERVAL=<n>                      (nepovinné, default 1)
    BYDAY=MO,TU,...                   (len pre WEEKLY)
"""

from __future__ import annotations

from datetime import datetime, timedelta

from core.models import parse_dt

WEEKDAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
WEEKDAY_LABELS = {"MO": "Po", "TU": "Ut", "WE": "St", "TH": "Št",
                  "FR": "Pi", "SA": "So", "SU": "Ne"}

PRESETS = {
    "Neopakuje sa": "",
    "Každý deň": "FREQ=DAILY;INTERVAL=1",
    "Každý pracovný deň": "FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,TU,WE,TH,FR",
    "Každý týždeň": "FREQ=WEEKLY;INTERVAL=1",
    "Každé 2 týždne": "FREQ=WEEKLY;INTERVAL=2",
    "Každý mesiac": "FREQ=MONTHLY;INTERVAL=1",
    "Každý rok": "FREQ=YEARLY;INTERVAL=1",
}


def parse_rule(rule: str | None) -> dict:
    if not rule:
        return {}
    out: dict = {}
    for part in str(rule).split(";"):
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        key = key.strip().upper()
        value = value.strip().upper()
        if key == "INTERVAL":
            try:
                out["interval"] = max(1, int(value))
            except ValueError:
                out["interval"] = 1
        elif key == "FREQ":
            out["freq"] = value
        elif key == "BYDAY":
            out["byday"] = [d for d in value.split(",") if d in WEEKDAYS]
    return out if out.get("freq") else {}


def describe(rule: str | None) -> str:
    parsed = parse_rule(rule)
    if not parsed:
        return "Neopakuje sa"
    interval = parsed.get("interval", 1)
    freq = parsed["freq"]
    base = {
        "DAILY": "deň", "WEEKLY": "týždeň", "MONTHLY": "mesiac", "YEARLY": "rok",
    }.get(freq, freq.lower())
    text = f"Každý {base}" if interval == 1 else f"Každé {interval}. {base}"
    if parsed.get("byday"):
        days = ", ".join(WEEKDAY_LABELS[d] for d in parsed["byday"])
        text += f" ({days})"
    return text


def _add_months(dt: datetime, months: int) -> datetime:
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    # ošetrenie kratších mesiacov (31. → posledný deň mesiaca)
    day = dt.day
    while day > 28:
        try:
            return dt.replace(year=year, month=month, day=day)
        except ValueError:
            day -= 1
    return dt.replace(year=year, month=month, day=day)


def next_occurrence(rule: str | None, after: datetime | str | None) -> datetime | None:
    """Najbližší ďalší termín po zadanom dátume."""
    parsed = parse_rule(rule)
    base = parse_dt(after)
    if not parsed or not base:
        return None

    freq = parsed["freq"]
    interval = parsed.get("interval", 1)

    if freq == "DAILY":
        return base + timedelta(days=interval)

    if freq == "WEEKLY":
        byday = parsed.get("byday")
        if not byday:
            return base + timedelta(weeks=interval)
        wanted = sorted(WEEKDAYS.index(d) for d in byday)
        current = base.weekday()
        for day in wanted:
            if day > current:
                return base + timedelta(days=day - current)
        # ďalší týždeň (rešpektuje INTERVAL)
        days_ahead = 7 * interval - current + wanted[0]
        return base + timedelta(days=days_ahead)

    if freq == "MONTHLY":
        return _add_months(base, interval)

    if freq == "YEARLY":
        return _add_months(base, 12 * interval)

    return None
