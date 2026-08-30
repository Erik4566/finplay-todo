"""Upozornenia: splatné pripomienky, meškajúce úlohy, e-mailové odoslanie."""

from __future__ import annotations

from core import config, repo
from core.models import now_utc, parse_dt
from integrations import email_smtp


def pending_alerts() -> dict:
    """Všetko, čo si zaslúži pozornosť teraz."""
    snapshot = repo.dashboard_snapshot()
    reminders = []
    for reminder in repo.due_reminders():
        task = repo.get_task(reminder["task_id"])
        if task and not task.get("archived_at") and task.get("status") != "done":
            reminders.append({"reminder": reminder, "task": task})
    return {
        "reminders": reminders,
        "overdue": snapshot["overdue"],
        "today": snapshot["today"],
        "count": len(reminders) + len(snapshot["overdue"]),
    }


def send_due_reminder_emails(only_unsent: bool = True) -> tuple[int, list[str]]:
    """Odošle e-maily pre splatné pripomienky s kanálom 'email'."""
    if not email_smtp.is_configured():
        return 0, ["SMTP nie je nakonfigurované."]

    user = repo.auth.current_user() or {}
    sent, problems = 0, []
    for item in pending_alerts()["reminders"]:
        reminder, task = item["reminder"], item["task"]
        if reminder.get("channel") != "email":
            continue
        if only_unsent and reminder.get("sent_at"):
            continue
        recipients = repo.assignee_emails(task["id"]) or [user.get("email")]
        subject, html = email_smtp.render_reminder_email(task, reminder)
        ok, message = email_smtp.send_email([r for r in recipients if r], subject, html)
        if ok:
            repo.mark_reminder_sent(reminder["id"])
            sent += 1
        else:
            problems.append(f"{task.get('title')}: {message}")
    return sent, problems


def maybe_auto_send() -> None:
    """Automatické odoslanie, ak je zapnuté v konfigurácii."""
    if not config.app_config()["auto_send_reminders"]:
        return
    try:
        send_due_reminder_emails()
    except Exception:
        pass


def share_task(task_id: str, recipients: list[str], note: str = "") -> tuple[bool, str]:
    """Pošle úlohu e-mailom konkrétnym osobám a zaznamená to."""
    task = repo.get_task(task_id)
    if not task:
        return False, "Úloha neexistuje."

    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        return False, "Zadaj aspoň jedného príjemcu."

    steps = repo.list_steps(task_id)
    risks = repo.list_risks(task_id)
    project = repo.get_project(task.get("project_id")) if task.get("project_id") else None
    user = repo.auth.current_user() or {}
    sender = user.get("full_name") or user.get("email") or "FinPlay ToDo"

    subject, html = email_smtp.render_task_email(task, steps, risks, sender, note, project)

    if not email_smtp.is_configured():
        for recipient in recipients:
            repo.record_share(task_id, recipient, note, "failed", "SMTP nie je nakonfigurované.")
        return False, ("SMTP nie je nakonfigurované — e-mail sa neodoslal. "
                       "Doplň sekciu [smtp] v secrets.toml, alebo použi tlačidlo "
                       "„Kopírovať text úlohy“.")

    ok, message = email_smtp.send_email(recipients, subject, html)
    for recipient in recipients:
        repo.record_share(task_id, recipient, note, "sent" if ok else "failed",
                          None if ok else message)
    return ok, message


def task_as_text(task: dict, steps: list[dict], risks: list[dict]) -> str:
    """Plain-text podoba úlohy - na skopírovanie do chatu alebo mailu."""
    lines = [f"# {task.get('title', '')}"]
    if task.get("description"):
        lines.append(task["description"])
    lines.append(f"Dôležitosť {task.get('importance', 3)}/5 · "
                 f"urgentnosť {task.get('urgency', 3)}/5 · "
                 f"odhad {task.get('estimated_minutes', 0)} min")
    due = parse_dt(task.get("due_at"))
    if due:
        lines.append(f"Termín: {due.astimezone().strftime('%d.%m.%Y %H:%M')}")
    lines.append("")
    lines.append("Kroky:")
    for index, step in enumerate(steps, 1):
        mark = "x" if step.get("is_done") else " "
        lines.append(f"{index}. [{mark}] {step['title']} ({step.get('estimated_minutes', 0)} min)")
    if risks:
        lines.append("")
        lines.append("Riziká a výzvy:")
        for risk in risks:
            lines.append(f"- {risk.get('title')} "
                         f"(závažnosť {risk.get('severity')}/5, "
                         f"pravdepodobnosť {risk.get('likelihood')}/5)")
            if risk.get("mitigation"):
                lines.append(f"  Zmiernenie: {risk['mitigation']}")
    lines.append("")
    lines.append(f"— FinPlay ToDo, {now_utc().astimezone().strftime('%d.%m.%Y %H:%M')}")
    return "\n".join(lines)
