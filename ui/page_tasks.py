"""Zoznam úloh s filtrami - mobile first.

Filtre sú zbalené, aby na telefóne bolo hneď vidieť úlohy, nie ovládacie prvky.
"""

from __future__ import annotations

import streamlit as st

from core import auth, repo
from core.models import CONTEXT_TAGS, QUADRANTS, STATUSES, quadrant
from integrations import ics
from ui import icons, theme
from ui.components import running_timer_bar, task_list

SORTS = {
    "Priorita (odporúčané)": "priority",
    "Termín": "due",
    "Najkratšie najprv": "short",
    "Naposledy vytvorené": "created",
}

DEFAULT_STATUSES = ["inbox", "todo", "in_progress", "blocked"]


def render() -> None:
    projects = repo.list_projects(include_archived=True)
    projects_by_id = {p["id"]: p for p in projects}

    filters = _filters(projects, projects_by_id)

    tasks = repo.list_tasks(
        project_id=filters["project_id"],
        statuses=filters["statuses"] or None,
        assignee_id=auth.current_user()["id"] if filters["only_mine"] else None,
    )
    if filters["quadrants"]:
        tasks = [t for t in tasks
                 if quadrant(t.get("importance", 3), t.get("urgency", 3))
                 in filters["quadrants"]]
    if filters["context"]:
        tasks = [t for t in tasks if t.get("context_tag") == filters["context"]]
    if filters["only_undecomposed"]:
        tasks = [t for t in tasks if repo.step_progress(t["id"])[1] == 0]

    tasks = _sort(tasks, filters["sort"])

    theme.topbar("Úlohy", f"{len(tasks)} {'úloha' if len(tasks) == 1 else 'úloh'}")
    running_timer_bar()

    task_list(tasks, "tl", projects_by_id,
              "Žiadna úloha nesedí na tieto filtre. Skús ich uvoľniť.")

    if tasks:
        theme.divider()
        st.download_button(
            f"Exportovať do kalendára (.ics)",
            data=ics.build_calendar(tasks,
                                    {t["id"]: repo.list_steps(t["id"]) for t in tasks}),
            file_name="finplay-ulohy.ics", mime="text/calendar",
            use_container_width=True, key="tl_ics")


def _filters(projects: list[dict], projects_by_id: dict) -> dict:
    """Zbalený panel filtrov. Vracia normalizované hodnoty."""
    with st.expander("Filtre a zoradenie", icon=icons.st("filter_list")):
        project_options = ["(všetky)"] + [p["id"] for p in projects
                                          if not p.get("archived_at")]
        project_id = st.selectbox(
            "Projekt", project_options,
            format_func=lambda v: "(všetky)" if v == "(všetky)"
            else f"{projects_by_id[v].get('emoji', '📁')} {projects_by_id[v]['name']}",
            key="tl_project")

        statuses = st.multiselect(
            "Stav", list(STATUSES.keys()), default=DEFAULT_STATUSES,
            format_func=lambda v: STATUSES[v], key="tl_status")

        quadrants = st.multiselect(
            "Priorita", list(QUADRANTS.keys()),
            format_func=lambda v: QUADRANTS[v]["label"],
            key="tl_quadrant")

        context = st.selectbox("Kontext", ["(všetky)"] + CONTEXT_TAGS, key="tl_context")
        sort_label = st.selectbox("Zoradiť", list(SORTS.keys()), key="tl_sort")

        only_mine = st.checkbox("Len moje", value=False, key="tl_mine")
        only_undecomposed = st.checkbox(
            "Len bez rozkladu na kroky", value=False, key="tl_nosteps",
            help="Úlohy, ktoré ešte nemajú kroky — dobré miesto, kde upratať")

    return {
        "project_id": None if project_id == "(všetky)" else project_id,
        "statuses": statuses,
        "quadrants": quadrants,
        "context": None if context == "(všetky)" else context,
        "sort": SORTS[sort_label],
        "only_mine": only_mine,
        "only_undecomposed": only_undecomposed,
    }


def _sort(tasks: list[dict], mode: str) -> list[dict]:
    if mode == "due":
        return sorted(tasks, key=lambda t: (t.get("due_at") is None, t.get("due_at") or ""))
    if mode == "short":
        return sorted(tasks, key=lambda t: t.get("estimated_minutes") or 9999)
    if mode == "created":
        return sorted(tasks, key=lambda t: t.get("created_at") or "", reverse=True)
    return tasks  # už zoradené podľa priority v repo.list_tasks
