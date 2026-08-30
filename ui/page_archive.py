"""Archív - hotové a odložené úlohy a projekty, mimo dohľadu ale dohľadateľné."""

from __future__ import annotations

import streamlit as st

from core import repo
from core.models import fmt_duration, fmt_minutes, parse_dt
from ui import icons, theme
from ui.components import esc, goto, task_list


def render() -> None:
    theme.topbar("Archív", "nič sa nestráca")
    st.markdown('<div class="fp-muted">Nič sa nestráca. Hotové a archivované veci sú tu — '
                'a nájdeš ich aj cez globálne vyhľadávanie.</div>', unsafe_allow_html=True)
    st.write("")

    projects_by_id = {p["id"]: p for p in repo.list_projects(include_archived=True)}

    done = [t for t in repo.list_tasks(statuses=["done"], include_archived=True)]
    archived = [t for t in repo.list_tasks(include_archived=True) if t.get("archived_at")]
    archived_ids = {t["id"] for t in archived}
    done = [t for t in done if t["id"] not in archived_ids]
    archived_projects = [p for p in repo.list_projects(include_archived=True)
                         if p.get("archived_at")]

    cols = st.columns(3)
    cols[0].metric("Dokončené úlohy", len(done))
    cols[1].metric("Archivované úlohy", len(archived))
    cols[2].metric("Archivované projekty", len(archived_projects))

    tabs = st.tabs([f"Dokončené ({len(done)})",
                    f"Archivované úlohy ({len(archived)})",
                    f"Archivované projekty ({len(archived_projects)})"])

    with tabs[0]:
        _completed_list(done, projects_by_id)

    with tabs[1]:
        if not archived:
            st.info("Archív úloh je prázdny.")
        for task in archived:
            cols = st.columns([7, 2])
            cols[0].markdown(f'{esc(task.get("title"))}  \n'
                             f'<span class="fp-muted">archivované '
                             f'{_stamp(task.get("archived_at"))}</span>',
                             unsafe_allow_html=True)
            if cols[1].button("Obnoviť", key=f"arch_restore_{task['id']}",
                              use_container_width=True):
                repo.archive_task(task["id"], False)
                st.rerun()

    with tabs[2]:
        if not archived_projects:
            st.info("Archív projektov je prázdny.")
        for project in archived_projects:
            cols = st.columns([7, 2])
            cols[0].markdown(f'{esc(project.get("emoji"))} **{esc(project.get("name"))}**  \n'
                             f'<span class="fp-muted">archivované '
                             f'{_stamp(project.get("archived_at"))}</span>',
                             unsafe_allow_html=True)
            if cols[1].button("Obnoviť", key=f"arch_proj_{project['id']}",
                              use_container_width=True):
                repo.archive_project(project["id"], False)
                st.rerun()


def _completed_list(tasks: list[dict], projects_by_id: dict) -> None:
    if not tasks:
        st.info("Zatiaľ nič dokončené. Aj to je informácia.")
        return
    for task in tasks[:80]:
        tracked = repo.tracked_seconds(task["id"])
        estimate = int(task.get("estimated_minutes") or 0)
        project = projects_by_id.get(task.get("project_id"))
        with st.container(border=True):
            cols = st.columns([7, 2])
            with cols[0]:
                line = f'{icons.html(icons.CHECK)} **{esc(task.get("title"))}**'
                if project:
                    line += f' <span class="fp-muted">· {esc(project.get("name"))}</span>'
                st.markdown(line, unsafe_allow_html=True)
                st.markdown(
                    f'<span class="fp-badge fp-q4">dokončené '
                    f'{_stamp(task.get("completed_at"))}</span>'
                    f'<span class="fp-badge fp-time">{icons.html(icons.TIME)} '
                    f'namerané {fmt_duration(tracked)}</span>'
                    + (f'<span class="fp-badge fp-ai">odhad {fmt_minutes(estimate)}</span>'
                       if estimate else ""),
                    unsafe_allow_html=True)
            with cols[1]:
                if st.button("Otvoriť", key=f"arch_open_{task['id']}",
                             use_container_width=True):
                    goto("task", task_id=task["id"])
                if st.button("Späť do práce", icon=icons.st("undo"), key=f"arch_reopen_{task['id']}",
                             use_container_width=True):
                    repo.set_status(task["id"], "todo")
                    st.rerun()


def _stamp(value) -> str:
    dt = parse_dt(value)
    return dt.astimezone().strftime("%d.%m.%Y %H:%M") if dt else "—"
