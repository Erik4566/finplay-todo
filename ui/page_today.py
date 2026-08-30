"""Dnes - hlavná obrazovka s funkciou „Najbližší krok" (mobile first)."""

from __future__ import annotations

import streamlit as st

from core import calendars, notifications, repo
from core.models import (CONTEXT_TAGS, ENERGY, fmt_duration, fmt_minutes,
                         now_utc, parse_dt)
from integrations import google_calendar
from ui import icons, theme
from ui.components import (badges, esc, goto, progress_bar, running_timer_bar,
                           task_list)

WEEKDAYS = ["pondelok", "utorok", "streda", "štvrtok", "piatok", "sobota", "nedeľa"]
MONTHS = ["januára", "februára", "marca", "apríla", "mája", "júna", "júla",
          "augusta", "septembra", "októbra", "novembra", "decembra"]


def _today_label() -> str:
    now = now_utc().astimezone()
    return f"{WEEKDAYS[now.weekday()]}, {now.day}. {MONTHS[now.month - 1]}"


def _skip(task_id: str) -> None:
    skipped = set(st.session_state.get("skipped_tasks", []))
    skipped.add(task_id)
    st.session_state["skipped_tasks"] = list(skipped)


def _pick(energy, minutes, context):
    skipped = set(st.session_state.get("skipped_tasks", []))
    candidates = [t for t in repo.list_tasks(statuses=["todo", "in_progress"])
                  if t["id"] not in skipped]
    if not candidates:
        st.session_state["skipped_tasks"] = []
        candidates = repo.list_tasks(statuses=["todo", "in_progress"])
    if not candidates:
        return None

    def matches(task):
        if energy and (task.get("energy_level") or "medium") != energy:
            return False
        if minutes and (task.get("estimated_minutes") or 0) > minutes:
            return False
        if context and task.get("context_tag") != context:
            return False
        return True

    filtered = [t for t in candidates if matches(t)]
    return (filtered or candidates)[0]


def render() -> None:
    theme.topbar("Dnes", _today_label())

    _day_context()
    running_timer_bar()
    _alerts()
    _hero()
    _calendar()

    theme.divider()
    _overview()


# =============================================================================
#  Kontext dňa - meniny a sviatky
# =============================================================================

def _day_context() -> None:
    ctx = calendars.today_context(country=st.session_state.get("ui_country", "SK"))
    chips = []

    if ctx["name_day"]:
        chips.append(f'<span class="fp-badge fp-q4">{icons.html(icons.NAMEDAY)} '
                     f'Meniny má <b>{esc(ctx["name_day"])}</b></span>')

    if ctx["holiday"]:
        # voľno vyzeráme inak než sviatok, v ktorý sa pracuje
        css = "fp-q1" if ctx["is_day_off"] else "fp-q3"
        chips.append(f'<span class="fp-badge {css}">{icons.html(icons.HOLIDAY)} '
                     f'{esc(ctx["holiday"])} · {esc(ctx["holiday_label"])}</span>')
    elif ctx["next_holiday"]:
        when = calendars.humanize_days(ctx["next_holiday_in_days"])
        css = "fp-q2" if ctx["next_holiday_in_days"] <= 7 else "fp-q4"
        chips.append(f'<span class="fp-badge {css}">{icons.html(icons.HOLIDAY)} '
                     f'{esc(ctx["next_holiday"])} · {when} '
                     f'<span style="opacity:.75">({esc(ctx["next_holiday_label"])})</span>'
                     f'</span>')

    if chips:
        st.markdown(f'<div class="fp-daystrip">{"".join(chips)}</div>',
                    unsafe_allow_html=True)


# =============================================================================
#  Dnešný kalendár (Google)
# =============================================================================

def _calendar() -> None:
    status = google_calendar.status()

    if not status["connected"]:
        if status["configured"]:
            with st.container(key="act-calhint"):
                st.markdown('<div class="fp-muted">Google Calendar nie je pripojený — '
                            'dnešné udalosti sa nedajú načítať.</div>',
                            unsafe_allow_html=True)
                if st.button("Pripojiť kalendár", icon=icons.st(icons.CALENDAR),
                             key="cal_connect", use_container_width=True):
                    goto("settings")
        return

    events = google_calendar.todays_events()
    label = f"Dnešný kalendár ({len(events)})" if events else "Dnešný kalendár — voľno"

    with st.expander(label, icon=icons.st(icons.CALENDAR), expanded=bool(events)):
        if not events:
            st.markdown('<div class="fp-muted">Na dnes nemáš v kalendári nič.</div>',
                        unsafe_allow_html=True)
            return
        rows = []
        for event in events:
            if event["all_day"]:
                when = "celý deň"
            else:
                start = event["start"].astimezone().strftime("%H:%M") if event["start"] else "?"
                end = event["end"].astimezone().strftime("%H:%M") if event["end"] else ""
                when = f"{start}\u2013{end}" if end else start
            place = (f'<div class="fp-event-place">{esc(event["location"])}</div>'
                     if event.get("location") else "")
            rows.append(f'<div class="fp-event">'
                        f'<div class="fp-event-time">{when}</div>'
                        f'<div class="fp-event-title">{esc(event["title"])}{place}</div>'
                        f'</div>')
        st.markdown("".join(rows), unsafe_allow_html=True)


# =============================================================================
#  Upozornenia
# =============================================================================

def _alerts() -> None:
    alerts = notifications.pending_alerts()
    if not alerts["reminders"] and not alerts["overdue"]:
        return

    for item in alerts["reminders"][:3]:
        task, reminder = item["task"], item["reminder"]
        st.markdown(
            f'<div class="fp-alert">{icons.html(icons.DUE_TODAY)} '
            f'<b>{esc(task["title"])}</b>'
            + (f'<br><span class="fp-muted">{esc(reminder.get("message"))}</span>'
               if reminder.get("message") else "") + "</div>",
            unsafe_allow_html=True)
        with st.container(key=f"act-rem-{reminder['id']}"):
            left, right = st.columns(2)
            if left.button("Otvoriť", key=f"rem_open_{reminder['id']}",
                           use_container_width=True):
                goto("task", task_id=task["id"])
            if right.button("Zavrieť", key=f"rem_dismiss_{reminder['id']}",
                            use_container_width=True):
                repo.dismiss_reminder(reminder["id"])
                st.rerun()

    if alerts["overdue"]:
        count = len(alerts["overdue"])
        st.markdown(
            f'<div class="fp-alert">{icons.html(icons.RISK)} <b>{count}</b> '
            f'{"úloha je" if count == 1 else "úloh je"} po termíne. '
            f'Nájdeš ich nižšie — stačí presunúť termín.</div>',
            unsafe_allow_html=True)


# =============================================================================
#  Najbližší krok
# =============================================================================

def _hero() -> None:
    with st.expander("Na čo mám teraz kapacitu", icon=icons.st("tune")):
        energy = st.selectbox(
            "Energia", ["(nezáleží)"] + list(ENERGY.keys()),
            format_func=lambda v: "(nezáleží)" if v == "(nezáleží)" else ENERGY[v],
            key="today_energy")
        minutes = st.selectbox(
            "Koľko mám času", ["(nezáleží)", 15, 30, 60, 120],
            format_func=lambda v: v if v == "(nezáleží)" else f"do {v} min",
            key="today_minutes")
        st.selectbox("Kontext", ["(nezáleží)"] + CONTEXT_TAGS, key="today_context")

    energy = None if st.session_state.get("today_energy") in (None, "(nezáleží)") \
        else st.session_state["today_energy"]
    minutes = None if st.session_state.get("today_minutes") in (None, "(nezáleží)") \
        else int(st.session_state["today_minutes"])
    context = None if st.session_state.get("today_context") in (None, "(nezáleží)") \
        else st.session_state["today_context"]

    task = _pick(energy, minutes, context)

    if not task:
        st.markdown(
            '<div class="fp-hero"><div class="fp-hero-kicker">Voľno</div>'
            '<div class="fp-hero-step">Nemáš žiadnu aktívnu úlohu.</div>'
            '<div class="fp-hero-meta">Buď je hotovo, alebo je čas niečo zapísať.</div>'
            '</div>', unsafe_allow_html=True)
        if st.button("Pridať úlohu", icon=icons.st("add"), type="primary", use_container_width=True):
            goto("new_task")
        return

    step = repo.next_step(task["id"])
    done, total = repo.step_progress(task["id"])
    step_title = step["title"] if step else "Doplň rozklad na kroky"
    step_time = fmt_minutes(step.get("estimated_minutes")) if step else "?"

    st.markdown(
        f'<div class="fp-hero">'
        f'<div class="fp-hero-kicker">Najbližší krok</div>'
        f'<div class="fp-hero-step">{esc(step_title)}</div>'
        f'<div class="fp-hero-task">v úlohe <b>{esc(task["title"])}</b></div>'
        f'<div style="margin-top:.6rem;display:flex;flex-wrap:wrap;gap:.3rem;">'
        f'{badges(task)}</div>'
        f'<div class="fp-hero-meta">Tento krok: <b>{step_time}</b>'
        + (f' · postup {done}/{total} krokov' if total else '') + '</div></div>',
        unsafe_allow_html=True)

    running = st.session_state.get("running_timer")
    is_running = bool(running and running.get("task_id") == task["id"])

    with st.container(key="act-hero-main"):
        left, right = st.columns(2)
        if left.button("Zastaviť" if is_running else "Začať teraz",
                       icon=icons.st(icons.STOP if is_running else icons.PLAY),
                       type="primary", use_container_width=True, key="hero_timer"):
            if is_running:
                repo.stop_running_timer()
                st.session_state.pop("running_timer", None)
            else:
                entry = repo.start_timer(task["id"], step["id"] if step else None)
                st.session_state["running_timer"] = entry
            st.rerun()

        if right.button("Krok hotový", icon=icons.st("check"), use_container_width=True,
                        disabled=step is None, key="hero_step_done"):
            repo.toggle_step(step["id"], True)
            if repo.next_step(task["id"]) is None:
                st.toast("Všetky kroky hotové — môžeš úlohu uzavrieť.", icon=":material/celebration:")
            st.rerun()

    with st.container(key="act-hero-sec"):
        left, right = st.columns(2)
        if left.button("Iná úloha", icon=icons.st("skip_next"), use_container_width=True, key="hero_skip"):
            _skip(task["id"])
            st.rerun()
        if right.button("Otvoriť detail", use_container_width=True, key="hero_open"):
            goto("task", task_id=task["id"])

    if total:
        st.markdown(progress_bar(done, total), unsafe_allow_html=True)


# =============================================================================
#  Prehľad
# =============================================================================

def _overview() -> None:
    snapshot = repo.dashboard_snapshot()
    projects_by_id = {p["id"]: p for p in repo.list_projects(include_archived=True)}

    columns = st.columns(3)
    columns[0].metric("Aktívne", len(snapshot["all"]))
    columns[1].metric("Po termíne", len(snapshot["overdue"]))
    columns[2].metric("Čas dnes", fmt_duration(_tracked_today()))

    tabs = st.tabs([f"Po termíne ({len(snapshot['overdue'])})",
                    f"Dnes ({len(snapshot['today'])})",
                    f"Týždeň ({len(snapshot['upcoming'])})",
                    f"Všetko ({len(snapshot['all'])})"])
    with tabs[0]:
        task_list(snapshot["overdue"], "ov", projects_by_id, "Nič po termíne. Naozaj.")
    with tabs[1]:
        task_list(snapshot["today"], "td", projects_by_id, "Na dnes nič nehorí.")
    with tabs[2]:
        task_list(snapshot["upcoming"], "wk", projects_by_id, "Tento týždeň zatiaľ nič.")
    with tabs[3]:
        task_list(snapshot["all"][:40], "all", projects_by_id, "Žiadne aktívne úlohy.")


def _tracked_today() -> int:
    total = 0
    today = now_utc().astimezone().date()
    try:
        entries = repo._be().table("time_entries").eq("user_id", repo._uid()).all()
    except Exception:
        return 0
    for entry in entries:
        started = parse_dt(entry.get("started_at"))
        if not started or started.astimezone().date() != today:
            continue
        if entry.get("duration_seconds"):
            total += int(entry["duration_seconds"])
        elif not entry.get("ended_at"):
            total += int((now_utc() - started).total_seconds())
    return total
