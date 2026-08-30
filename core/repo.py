"""Repozitár - všetky operácie nad dátami na jednom mieste."""

from __future__ import annotations

from datetime import datetime

from core import auth, db, recurrence
from core.models import (iso, now_utc, parse_dt, priority_score, quadrant)

ACTIVE_STATUSES = ["inbox", "todo", "in_progress", "blocked"]


def _be() -> db.Backend:
    return auth.backend()


def _uid() -> str:
    user = auth.current_user()
    if not user:
        raise RuntimeError("Nie je prihlásený používateľ.")
    return user["id"]


# =============================================================================
#  Projekty
# =============================================================================

def list_projects(include_archived: bool = False) -> list[dict]:
    q = _be().table("projects").order("created_at", desc=True)
    rows = q.all()
    if not include_archived:
        rows = [r for r in rows if not r.get("archived_at")]
    return rows


def get_project(project_id: str) -> dict | None:
    if not project_id:
        return None
    return _be().table("projects").eq("id", project_id).first()


def create_project(name: str, description: str = "", emoji: str = "📁",
                   color: str = "#4F46E5") -> dict:
    be, uid = _be(), _uid()
    project = be.insert("projects", {
        "id": db.new_id(), "owner_id": uid, "name": name.strip(),
        "description": description, "emoji": emoji, "color": color,
        "status": "active", "archived_at": None,
        "created_at": iso(now_utc()), "updated_at": iso(now_utc()),
    })
    try:
        be.insert("project_members", {"project_id": project["id"], "user_id": uid,
                                      "role": "owner", "created_at": iso(now_utc()),
                                      "id": db.new_id()})
    except Exception:
        pass  # v Supabase má tabuľka zložený primárny kľúč bez stĺpca id
    return project


def update_project(project_id: str, values: dict) -> None:
    values = dict(values)
    values["updated_at"] = iso(now_utc())
    _be().table("projects").eq("id", project_id).update(values)


def archive_project(project_id: str, archived: bool = True) -> None:
    update_project(project_id, {"archived_at": iso(now_utc()) if archived else None})


def project_members(project_id: str) -> list[dict]:
    return _be().table("project_members").eq("project_id", project_id).all()


def add_project_member(project_id: str, user_id: str, role: str = "member") -> None:
    be = _be()
    existing = be.table("project_members").eq("project_id", project_id).eq("user_id", user_id).first()
    if existing:
        return
    row = {"project_id": project_id, "user_id": user_id, "role": role,
           "created_at": iso(now_utc())}
    if be.kind == "local":
        row["id"] = db.new_id()
    be.insert("project_members", row)


# =============================================================================
#  Úlohy
# =============================================================================

def list_tasks(project_id: str | None = None, statuses: list[str] | None = None,
               include_archived: bool = False, assignee_id: str | None = None,
               limit: int | None = None) -> list[dict]:
    q = _be().table("tasks")
    if project_id:
        q = q.eq("project_id", project_id)
    if statuses:
        q = q.in_("status", statuses)
    rows = q.all()
    if not include_archived:
        rows = [r for r in rows if not r.get("archived_at")]
    if assignee_id:
        assigned = {a["task_id"] for a in _be().table("task_assignees")
                    .eq("user_id", assignee_id).all()}
        rows = [r for r in rows if r["id"] in assigned or r.get("owner_id") == assignee_id]
    rows.sort(key=priority_score, reverse=True)
    return rows[:limit] if limit else rows


def get_task(task_id: str) -> dict | None:
    if not task_id:
        return None
    return _be().table("tasks").eq("id", task_id).first()


def create_task(*, title: str, description: str = "", project_id: str | None = None,
                importance: int = 3, urgency: int = 3, estimated_minutes: int = 30,
                due_at: datetime | None = None, status: str = "todo",
                energy_level: str = "medium", context_tag: str | None = None,
                recurrence_rule: str | None = None,
                steps: list[dict] | None = None,
                assignees: list[dict] | None = None,
                recurrence_parent: str | None = None) -> dict:
    be, uid = _be(), _uid()
    task_id = db.new_id()
    task = be.insert("tasks", {
        "id": task_id,
        "project_id": project_id or None,
        "owner_id": uid,
        "title": title.strip(),
        "description": description or "",
        "importance": int(importance),
        "urgency": int(urgency),
        "priority_label": quadrant(importance, urgency),
        "status": status,
        "energy_level": energy_level,
        "context_tag": context_tag,
        "estimated_minutes": int(estimated_minutes or 0),
        "due_at": iso(due_at) if due_at else None,
        "start_at": None,
        "completed_at": None,
        "archived_at": None,
        "recurrence_rule": recurrence_rule or None,
        "recurrence_parent": recurrence_parent,
        "google_event_id": None,
        "ms_todo_task_id": None,
        "position": 0,
        "created_at": iso(now_utc()),
        "updated_at": iso(now_utc()),
    })

    for index, step in enumerate(steps or []):
        add_step(task_id, step.get("title", ""), step.get("estimated_minutes", 10), index)

    for person in assignees or []:
        add_assignee(task_id, user_id=person.get("user_id"), email=person.get("email"),
                     role=person.get("role", "responsible"))
    return task


def update_task(task_id: str, values: dict) -> None:
    values = dict(values)
    if "importance" in values or "urgency" in values:
        task = get_task(task_id) or {}
        importance = values.get("importance", task.get("importance", 3))
        urgency = values.get("urgency", task.get("urgency", 3))
        values["priority_label"] = quadrant(importance, urgency)
    values["updated_at"] = iso(now_utc())
    _be().table("tasks").eq("id", task_id).update(values)


def set_status(task_id: str, status: str) -> dict | None:
    """Zmena stavu. Pri 'done' rieši opakovanie a vytvorí ďalší výskyt."""
    if status != "done":
        update_task(task_id, {"status": status, "completed_at": None})
        return None

    task = get_task(task_id)
    update_task(task_id, {"status": "done", "completed_at": iso(now_utc())})
    stop_running_timer(task_id)
    if not task:
        return None
    return _spawn_next_occurrence(task)


def _spawn_next_occurrence(task: dict) -> dict | None:
    rule = task.get("recurrence_rule")
    if not rule:
        return None
    base = parse_dt(task.get("due_at")) or now_utc()
    next_due = recurrence.next_occurrence(rule, base)
    if not next_due:
        return None

    steps = [{"title": s["title"], "estimated_minutes": s.get("estimated_minutes", 10)}
             for s in list_steps(task["id"])]
    people = [{"user_id": a.get("user_id"), "email": a.get("email"),
               "role": a.get("role", "responsible")} for a in list_assignees(task["id"])]

    return create_task(
        title=task["title"], description=task.get("description", ""),
        project_id=task.get("project_id"), importance=task.get("importance", 3),
        urgency=task.get("urgency", 3),
        estimated_minutes=task.get("estimated_minutes", 30),
        due_at=next_due, status="todo", energy_level=task.get("energy_level", "medium"),
        context_tag=task.get("context_tag"), recurrence_rule=rule,
        steps=steps, assignees=people,
        recurrence_parent=task.get("recurrence_parent") or task["id"],
    )


def archive_task(task_id: str, archived: bool = True) -> None:
    update_task(task_id, {"archived_at": iso(now_utc()) if archived else None})


def delete_task(task_id: str) -> None:
    be = _be()
    for table in ("task_steps", "task_assignees", "task_risks", "ai_feedback",
                  "time_entries", "reminders", "task_shares"):
        try:
            be.table(table).eq("task_id", task_id).delete()
        except Exception:
            pass
    be.table("tasks").eq("id", task_id).delete()


# =============================================================================
#  Kroky
# =============================================================================

def list_steps(task_id: str) -> list[dict]:
    rows = _be().table("task_steps").eq("task_id", task_id).all()
    rows.sort(key=lambda s: (s.get("position") or 0, s.get("created_at") or ""))
    return rows


def add_step(task_id: str, title: str, estimated_minutes: int = 10,
             position: int | None = None) -> dict:
    if not (title or "").strip():
        raise ValueError("Krok musí mať názov.")
    if position is None:
        position = len(list_steps(task_id))
    return _be().insert("task_steps", {
        "id": db.new_id(), "task_id": task_id, "position": position,
        "title": title.strip(), "estimated_minutes": int(estimated_minutes or 0),
        "is_done": False, "done_at": None, "created_at": iso(now_utc()),
    })


def toggle_step(step_id: str, done: bool) -> None:
    _be().table("task_steps").eq("id", step_id).update(
        {"is_done": bool(done), "done_at": iso(now_utc()) if done else None})


def update_step(step_id: str, values: dict) -> None:
    _be().table("task_steps").eq("id", step_id).update(values)


def delete_step(step_id: str) -> None:
    _be().table("task_steps").eq("id", step_id).delete()


def next_step(task_id: str) -> dict | None:
    """Prvý nedokončený krok - jadro funkcie 'Najbližší krok'."""
    for step in list_steps(task_id):
        if not step.get("is_done"):
            return step
    return None


def step_progress(task_id: str) -> tuple[int, int]:
    steps = list_steps(task_id)
    return sum(1 for s in steps if s.get("is_done")), len(steps)


# =============================================================================
#  Priradenie osôb
# =============================================================================

def list_assignees(task_id: str) -> list[dict]:
    return _be().table("task_assignees").eq("task_id", task_id).all()


def add_assignee(task_id: str, user_id: str | None = None, email: str | None = None,
                 role: str = "responsible") -> dict | None:
    if not user_id and not email:
        return None
    be = _be()
    for existing in list_assignees(task_id):
        if (user_id and existing.get("user_id") == user_id) or \
           (email and (existing.get("email") or "").lower() == email.lower()):
            return existing
    return be.insert("task_assignees", {
        "id": db.new_id(), "task_id": task_id, "user_id": user_id,
        "email": (email or "").strip().lower() or None, "role": role,
        "created_at": iso(now_utc()),
    })


def remove_assignee(assignee_id: str) -> None:
    _be().table("task_assignees").eq("id", assignee_id).delete()


def set_assignees(task_id: str, people: list[dict]) -> None:
    _be().table("task_assignees").eq("task_id", task_id).delete()
    for person in people:
        add_assignee(task_id, person.get("user_id"), person.get("email"),
                     person.get("role", "responsible"))


def assignee_emails(task_id: str, profiles_by_id: dict | None = None) -> list[str]:
    profiles_by_id = profiles_by_id or {p["id"]: p for p in auth.list_people()}
    emails = []
    for a in list_assignees(task_id):
        if a.get("email"):
            emails.append(a["email"])
        elif a.get("user_id") and a["user_id"] in profiles_by_id:
            emails.append(profiles_by_id[a["user_id"]]["email"])
    return sorted(set(emails))


# =============================================================================
#  Riziká a výzvy
# =============================================================================

def list_risks(task_id: str) -> list[dict]:
    rows = _be().table("task_risks").eq("task_id", task_id).all()
    rows.sort(key=lambda r: ((r.get("severity") or 0) * (r.get("likelihood") or 0)), reverse=True)
    return rows


def add_risk(task_id: str, *, kind: str = "risk", title: str, description: str = "",
             severity: int = 3, likelihood: int = 3, mitigation: str = "",
             source: str = "human", source_model: str | None = None) -> dict:
    return _be().insert("task_risks", {
        "id": db.new_id(), "task_id": task_id, "kind": kind, "title": title.strip(),
        "description": description, "severity": int(severity), "likelihood": int(likelihood),
        "mitigation": mitigation, "source": source, "source_model": source_model,
        "created_by": _uid(), "created_at": iso(now_utc()),
    })


def delete_risk(risk_id: str) -> None:
    _be().table("task_risks").eq("id", risk_id).delete()


# =============================================================================
#  AI spätná väzba
# =============================================================================

def list_ai_feedback(task_id: str) -> list[dict]:
    rows = _be().table("ai_feedback").eq("task_id", task_id).all()
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows


def add_ai_feedback(task_id: str, *, provider: str, model: str | None, kind: str,
                    summary: str | None, payload: dict | None, raw_text: str | None,
                    latency_ms: int | None = None, error: str | None = None) -> dict:
    return _be().insert("ai_feedback", {
        "id": db.new_id(), "task_id": task_id, "provider": provider, "model": model,
        "kind": kind, "summary": summary, "payload": payload, "raw_text": raw_text,
        "latency_ms": latency_ms, "error": error, "created_by": _uid(),
        "created_at": iso(now_utc()),
    })


def delete_ai_feedback(feedback_id: str) -> None:
    _be().table("ai_feedback").eq("id", feedback_id).delete()


# =============================================================================
#  Sledovanie času
# =============================================================================

def running_entry() -> dict | None:
    rows = _be().table("time_entries").eq("user_id", _uid()).is_null("ended_at").all()
    return rows[0] if rows else None


def start_timer(task_id: str, step_id: str | None = None) -> dict:
    stop_running_timer()
    entry = _be().insert("time_entries", {
        "id": db.new_id(), "task_id": task_id, "user_id": _uid(), "step_id": step_id,
        "started_at": iso(now_utc()), "ended_at": None, "duration_seconds": None,
        "note": None, "created_at": iso(now_utc()),
    })
    task = get_task(task_id)
    if task and task.get("status") in ("todo", "inbox"):
        update_task(task_id, {"status": "in_progress"})
    return entry


def stop_running_timer(task_id: str | None = None, note: str | None = None) -> dict | None:
    entry = running_entry()
    if not entry:
        return None
    if task_id and entry.get("task_id") != task_id:
        return None
    started = parse_dt(entry.get("started_at")) or now_utc()
    seconds = max(0, int((now_utc() - started).total_seconds()))
    _be().table("time_entries").eq("id", entry["id"]).update({
        "ended_at": iso(now_utc()), "duration_seconds": seconds, "note": note,
    })
    entry["duration_seconds"] = seconds
    return entry


def time_entries(task_id: str) -> list[dict]:
    rows = _be().table("time_entries").eq("task_id", task_id).all()
    rows.sort(key=lambda r: r.get("started_at") or "", reverse=True)
    return rows


def tracked_seconds(task_id: str) -> int:
    total = 0
    for entry in time_entries(task_id):
        if entry.get("duration_seconds"):
            total += int(entry["duration_seconds"])
        elif not entry.get("ended_at"):
            started = parse_dt(entry.get("started_at"))
            if started:
                total += int((now_utc() - started).total_seconds())
    return total


# =============================================================================
#  Upozornenia
# =============================================================================

def create_reminder(task_id: str, remind_at: datetime, channel: str = "app",
                    message: str = "") -> dict:
    return _be().insert("reminders", {
        "id": db.new_id(), "task_id": task_id, "user_id": _uid(),
        "remind_at": iso(remind_at), "channel": channel, "message": message,
        "sent_at": None, "dismissed_at": None, "created_at": iso(now_utc()),
    })


def list_reminders(task_id: str) -> list[dict]:
    rows = _be().table("reminders").eq("task_id", task_id).all()
    rows.sort(key=lambda r: r.get("remind_at") or "")
    return rows


def due_reminders() -> list[dict]:
    rows = _be().table("reminders").eq("user_id", _uid()).is_null("dismissed_at").all()
    now = iso(now_utc())
    return [r for r in rows if (r.get("remind_at") or "") <= now]


def mark_reminder_sent(reminder_id: str) -> None:
    _be().table("reminders").eq("id", reminder_id).update({"sent_at": iso(now_utc())})


def dismiss_reminder(reminder_id: str) -> None:
    _be().table("reminders").eq("id", reminder_id).update({"dismissed_at": iso(now_utc())})


def delete_reminder(reminder_id: str) -> None:
    _be().table("reminders").eq("id", reminder_id).delete()


# =============================================================================
#  Zdieľanie
# =============================================================================

def record_share(task_id: str, recipient_email: str, message: str,
                 status: str, error: str | None = None) -> dict:
    return _be().insert("task_shares", {
        "id": db.new_id(), "task_id": task_id, "shared_by": _uid(),
        "recipient_email": recipient_email, "message": message, "status": status,
        "error": error, "sent_at": iso(now_utc()) if status == "sent" else None,
        "created_at": iso(now_utc()),
    })


def list_shares(task_id: str) -> list[dict]:
    rows = _be().table("task_shares").eq("task_id", task_id).all()
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows


# =============================================================================
#  Napojené účty a log synchronizácie
# =============================================================================

def get_integration_account(provider: str) -> dict | None:
    return _be().table("integration_accounts").eq("user_id", _uid()) \
        .eq("provider", provider).first()


def save_integration_account(provider: str, values: dict) -> dict:
    be = _be()
    existing = get_integration_account(provider)
    values = dict(values)
    values["updated_at"] = iso(now_utc())
    if existing:
        be.table("integration_accounts").eq("id", existing["id"]).update(values)
        return {**existing, **values}
    values.update({"id": db.new_id(), "user_id": _uid(), "provider": provider,
                   "created_at": iso(now_utc())})
    return be.insert("integration_accounts", values)


def delete_integration_account(provider: str) -> None:
    _be().table("integration_accounts").eq("user_id", _uid()).eq("provider", provider).delete()


def log_sync(task_id: str | None, provider: str, status: str, message: str,
             external_id: str | None = None, direction: str = "push") -> None:
    try:
        _be().insert("sync_log", {
            "id": db.new_id(), "user_id": _uid(), "task_id": task_id, "provider": provider,
            "direction": direction, "external_id": external_id, "status": status,
            "message": message, "created_at": iso(now_utc()),
        })
    except Exception:
        pass


def recent_sync_log(limit: int = 25) -> list[dict]:
    rows = _be().table("sync_log").eq("user_id", _uid()).all()
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows[:limit]


# =============================================================================
#  Globálne vyhľadávanie
# =============================================================================

def global_search(query: str, include_archived: bool = True) -> dict:
    """Prehľadá úlohy, kroky, projekty, riziká a AI výstupy."""
    needle = (query or "").strip()
    if len(needle) < 2:
        return {"tasks": [], "steps": [], "projects": [], "risks": [], "ai": []}

    be = _be()
    tasks = be.table("tasks").search(["title", "description"], needle).all()
    if not include_archived:
        tasks = [t for t in tasks if not t.get("archived_at")]
    steps = be.table("task_steps").search(["title"], needle).all()
    projects = be.table("projects").search(["name", "description"], needle).all()
    risks = be.table("task_risks").search(["title", "description", "mitigation"], needle).all()
    ai = be.table("ai_feedback").search(["summary", "raw_text"], needle).all()

    tasks.sort(key=priority_score, reverse=True)
    return {"tasks": tasks, "steps": steps, "projects": projects,
            "risks": risks, "ai": ai}


# =============================================================================
#  Prehľadové dotazy
# =============================================================================

def dashboard_snapshot() -> dict:
    tasks = list_tasks(statuses=ACTIVE_STATUSES)
    now = now_utc()
    overdue, today, upcoming = [], [], []
    for task in tasks:
        due = parse_dt(task.get("due_at"))
        if not due:
            continue
        if due < now:
            overdue.append(task)
        elif (due - now).total_seconds() < 86_400:
            today.append(task)
        elif (due - now).days < 7:
            upcoming.append(task)
    return {"all": tasks, "overdue": overdue, "today": today, "upcoming": upcoming}


def pick_next_task(energy: str | None = None, max_minutes: int | None = None,
                   context: str | None = None) -> dict | None:
    """Vyberie jednu úlohu pre režim 'Najbližší krok'."""
    candidates = [t for t in list_tasks(statuses=["todo", "in_progress"])]
    if energy:
        candidates = [t for t in candidates if (t.get("energy_level") or "medium") == energy] \
                     or candidates
    if max_minutes:
        filtered = [t for t in candidates if (t.get("estimated_minutes") or 0) <= max_minutes]
        candidates = filtered or candidates
    if context:
        filtered = [t for t in candidates if t.get("context_tag") == context]
        candidates = filtered or candidates
    return candidates[0] if candidates else None
