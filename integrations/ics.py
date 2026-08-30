"""Export úloh do .ics (iCalendar) - univerzálny import do ľubovoľného kalendára."""

from __future__ import annotations

from datetime import timedelta

from core.models import now_utc, parse_dt


def _stamp(dt) -> str:
    dt = parse_dt(dt) or now_utc()
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _escape(text) -> str:
    text = "" if text is None else str(text)
    return (text.replace("\\", "\\\\").replace(";", "\\;")
                .replace(",", "\\,").replace("\n", "\\n"))


def _fold(line: str) -> str:
    """iCalendar povoľuje max 75 oktetov na riadok."""
    if len(line) <= 73:
        return line
    chunks = [line[:73]]
    rest = line[73:]
    while rest:
        chunks.append(" " + rest[:72])
        rest = rest[72:]
    return "\r\n".join(chunks)


def task_to_event(task: dict, steps: list[dict] | None = None) -> list[str]:
    start = parse_dt(task.get("due_at")) or parse_dt(task.get("start_at")) or now_utc()
    minutes = int(task.get("estimated_minutes") or 30)
    end = start + timedelta(minutes=max(15, minutes))

    description_parts = []
    if task.get("description"):
        description_parts.append(task["description"])
    if steps:
        description_parts.append("Kroky:")
        for index, step in enumerate(steps, 1):
            mark = "x" if step.get("is_done") else " "
            description_parts.append(f"{index}. [{mark}] {step['title']} "
                                     f"({step.get('estimated_minutes', 0)} min)")
    description_parts.append(
        f"Dôležitosť {task.get('importance', 3)}/5 · urgentnosť {task.get('urgency', 3)}/5")

    lines = [
        "BEGIN:VEVENT",
        f"UID:{task['id']}@finplay-todo",
        f"DTSTAMP:{_stamp(now_utc())}",
        f"DTSTART:{_stamp(start)}",
        f"DTEND:{_stamp(end)}",
        f"SUMMARY:{_escape(task.get('title', 'Úloha'))}",
        f"DESCRIPTION:{_escape(chr(10).join(description_parts))}",
        f"STATUS:{'COMPLETED' if task.get('status') == 'done' else 'CONFIRMED'}",
    ]
    if task.get("recurrence_rule"):
        lines.append(f"RRULE:{task['recurrence_rule']}")
    lines += [
        "BEGIN:VALARM",
        "TRIGGER:-PT30M",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{_escape(task.get('title', 'Úloha'))}",
        "END:VALARM",
        "END:VEVENT",
    ]
    return lines


def build_calendar(tasks: list[dict], steps_by_task: dict[str, list[dict]] | None = None) -> str:
    steps_by_task = steps_by_task or {}
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//FinPlay ToDo//SK",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for task in tasks:
        lines += task_to_event(task, steps_by_task.get(task["id"]))
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
