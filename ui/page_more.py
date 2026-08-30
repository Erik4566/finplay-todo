"""Viac - rozcestník pre menej časté obrazovky."""

from __future__ import annotations

import streamlit as st

from core import auth, config, feedback, repo
from core.models import fmt_duration, now_utc, parse_dt
from ui import icons, theme
from ui.components import esc, goto

ITEMS = [
    ("projects", icons.PROJECTS, "Projekty", "Zoskupenie úloh do väčších celkov"),
    ("archive", icons.ARCHIVE, "Archív", "Dokončené a odložené úlohy"),
    ("settings", icons.SETTINGS, "Nastavenia", "Integrácie, AI modely, e-mail, profil"),
    ("feedback", "campaign", "Spätná väzba", "Čo v appke nefunguje alebo zdržuje"),
]


def render() -> None:
    user = auth.current_user() or {}
    theme.topbar("Viac", user.get("full_name") or user.get("email", ""))

    _stats()

    for key, icon, label, hint in ITEMS:
        with st.container(key=f"act-more-{key}"):
            if st.button(f"**{label}**  \n{hint}", icon=icons.st(icon),
                         key=f"more_{key}",
                         use_container_width=True):
                goto(key)

    theme.divider()
    theme.appearance_controls()

    theme.divider()

    backend = "Supabase" if config.has_supabase() else "Lokálna databáza"
    st.markdown(f'<div class="fp-muted">Dáta: {backend}</div>', unsafe_allow_html=True)

    if st.button("Odhlásiť sa", icon=icons.st(icons.LOGOUT),
                 key="more_logout", use_container_width=True):
        auth.sign_out()
        st.rerun()


def _stats() -> None:
    snapshot = repo.dashboard_snapshot()
    done_today = 0
    tracked = 0
    today = now_utc().astimezone().date()

    for task in repo.list_tasks(statuses=["done"], include_archived=True):
        completed = parse_dt(task.get("completed_at"))
        if completed and completed.astimezone().date() == today:
            done_today += 1

    try:
        entries = repo._be().table("time_entries").eq("user_id", repo._uid()).all()
        for entry in entries:
            started = parse_dt(entry.get("started_at"))
            if started and started.astimezone().date() == today:
                if entry.get("duration_seconds"):
                    tracked += int(entry["duration_seconds"])
                elif not entry.get("ended_at"):
                    tracked += int((now_utc() - started).total_seconds())
    except Exception:
        pass

    columns = st.columns(3)
    columns[0].metric("Aktívne", len(snapshot["all"]))
    columns[1].metric("Dnes hotové", done_today)
    columns[2].metric("Čas dnes", fmt_duration(tracked))
