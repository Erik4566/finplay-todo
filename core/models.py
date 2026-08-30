"""Doménové konštanty, priorita (Eisenhower) a pomocné formátovanie."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# --- Číselníky -----------------------------------------------------------------

STATUSES = {
    "inbox": "Inbox",
    "todo": "Na urobenie",
    "in_progress": "Robím",
    "blocked": "Zaseknuté",
    "done": "Hotové",
}

ENERGY = {
    "low": "Nízka energia",
    "medium": "Stredná energia",
    "high": "Vysoká energia",
}

ASSIGNEE_ROLES = {
    "responsible": "Zodpovedná osoba",
    "accountable": "Schvaľuje",
    "informed": "Len informovaná",
}

RISK_KINDS = {"risk": "Riziko", "challenge": "Výzva"}

CONTEXT_TAGS = ["@počítač", "@telefón", "@vonku", "@doma", "@kancelária", "@čakám", "@nákup"]

IMPORTANCE_LABELS = {
    1: "1 · Nepodstatné",
    2: "2 · Skôr vedľajšie",
    3: "3 · Bežné",
    4: "4 · Dôležité",
    5: "5 · Kľúčové",
}

URGENCY_LABELS = {
    1: "1 · Počká mesiace",
    2: "2 · Počká týždne",
    3: "3 · Tento týždeň",
    4: "4 · Do 48 hodín",
    5: "5 · Dnes / horí",
}

# --- Priorita ------------------------------------------------------------------

# `icon` sú názvy z Material Symbols (viď ui/icons.py), nie emoji.
QUADRANTS = {
    "Q1": {"label": "Q1 · Urob teraz", "icon": "local_fire_department", "color": "#DC2626"},
    "Q2": {"label": "Q2 · Naplánuj", "icon": "event_upcoming", "color": "#2563EB"},
    "Q3": {"label": "Q3 · Deleguj", "icon": "groups", "color": "#D97706"},
    "Q4": {"label": "Q4 · Nízka priorita", "icon": "keyboard_double_arrow_down",
           "color": "#6B7280"},
}


def quadrant(importance: int, urgency: int) -> str:
    """Eisenhowerov kvadrant z dôležitosti a urgentnosti (1-5)."""
    important = (importance or 3) >= 4
    urgent = (urgency or 3) >= 4
    if important and urgent:
        return "Q1"
    if important and not urgent:
        return "Q2"
    if not important and urgent:
        return "Q3"
    return "Q4"


def priority_score(task: dict) -> float:
    """Vyššie číslo = skôr na rade. Kombinuje kvadrant, termín a odhad času."""
    importance = task.get("importance") or 3
    urgency = task.get("urgency") or 3
    score = importance * 2.0 + urgency * 1.5

    due = parse_dt(task.get("due_at"))
    if due:
        hours_left = (due - now_utc()).total_seconds() / 3600
        if hours_left < 0:
            score += 12          # po termíne - hore
        elif hours_left < 24:
            score += 8
        elif hours_left < 72:
            score += 4
        elif hours_left < 168:
            score += 2

    if task.get("status") == "in_progress":
        score += 5               # rozrobené sa dokončuje prednostne
    if task.get("status") == "blocked":
        score -= 6

    est = task.get("estimated_minutes") or 30
    if est <= 15:
        score += 1.5             # rýchle výhry pre naštartovanie

    return score


# --- Čas -----------------------------------------------------------------------

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def parse_dt(value) -> datetime | None:
    """Tolerantný parser ISO reťazcov z Postgresu aj SQLite."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip().replace(" ", "T")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    # Postgres vracia mikrosekundy s rôznou dĺžkou
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        try:
            head, _, tail = text.partition(".")
            offset = ""
            for sign in ("+", "-"):
                idx = tail.find(sign)
                if idx > 0:
                    offset = tail[idx:]
                    break
            dt = datetime.fromisoformat(head + offset)
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def fmt_minutes(minutes) -> str:
    minutes = int(minutes or 0)
    if minutes < 60:
        return f"{minutes} min"
    hours, rest = divmod(minutes, 60)
    return f"{hours} h" if rest == 0 else f"{hours} h {rest} min"


def fmt_duration(seconds) -> str:
    seconds = int(seconds or 0)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def fmt_due(value) -> tuple[str, str]:
    """Vráti (text, stav) kde stav je overdue | today | soon | later | none."""
    due = parse_dt(value)
    if not due:
        return ("bez termínu", "none")
    delta = due - now_utc()
    local = due.astimezone()
    stamp = local.strftime("%d.%m. %H:%M")
    if delta.total_seconds() < 0:
        days = int(abs(delta.total_seconds()) // 86400)
        return (f"{stamp} · meškanie {days} d" if days else f"{stamp} · po termíne", "overdue")
    if delta < timedelta(hours=24):
        return (f"{stamp} · dnes/zajtra", "today")
    if delta < timedelta(days=7):
        return (f"{stamp} · o {delta.days + 1} d", "soon")
    return (stamp, "later")


def initials(name: str | None, email: str | None = None) -> str:
    source = (name or email or "?").strip()
    parts = [p for p in source.replace("@", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def person_label(profile: dict | None, fallback_email: str | None = None) -> str:
    if profile:
        return profile.get("full_name") or profile.get("email") or "Neznámy"
    return fallback_email or "Neznámy"
