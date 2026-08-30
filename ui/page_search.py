"""Globálne vyhľadávanie naprieč úlohami, krokmi, projektmi, rizikami a AI výstupmi."""

from __future__ import annotations

import streamlit as st

from core import repo
from core.models import parse_dt
from ui import icons, theme
from ui.components import esc, goto, task_list


def render() -> None:
    theme.topbar("Hľadať", "naprieč všetkým")

    st.session_state.setdefault("search_query", "")
    query = st.text_input(
        "Hľadať",
        placeholder="Názov úlohy, krok, riziko, projekt, text z AI analýzy…",
        key="search_query", label_visibility="collapsed")

    cols = st.columns([3, 7])
    include_archived = cols[0].checkbox("Vrátane archívu", value=True, key="search_archived")

    if len((query or "").strip()) < 2:
        st.info("Napíš aspoň dva znaky. Hľadá sa naprieč všetkým, čo v systéme je.")
        return

    results = repo.global_search(query, include_archived)
    projects_by_id = {p["id"]: p for p in repo.list_projects(include_archived=True)}

    total = sum(len(v) for v in results.values())
    st.markdown(f'<div class="fp-muted">Nájdených záznamov: <b>{total}</b></div>',
                unsafe_allow_html=True)

    tabs = st.tabs([
        f"Úlohy ({len(results['tasks'])})",
        f"Kroky ({len(results['steps'])})",
        f"Projekty ({len(results['projects'])})",
        f"Riziká ({len(results['risks'])})",
        f"AI výstupy ({len(results['ai'])})",
    ])

    with tabs[0]:
        task_list(results["tasks"], "sr", projects_by_id, "Žiadna úloha nesedí.")

    with tabs[1]:
        if not results["steps"]:
            st.info("Žiadny krok nesedí.")
        for step in results["steps"][:60]:
            task = repo.get_task(step["task_id"])
            cols = st.columns([7, 2])
            mark = icons.html(icons.CHECK if step.get("is_done")
                              else "radio_button_unchecked")
            cols[0].markdown(f'{mark} {esc(step["title"])}  \n'
                             f'<span class="fp-muted">v úlohe: '
                             f'{esc(task.get("title") if task else "?")}</span>',
                             unsafe_allow_html=True)
            if task and cols[1].button("Otvoriť", key=f"srch_step_{step['id']}",
                                       use_container_width=True):
                goto("task", task_id=task["id"])

    with tabs[2]:
        if not results["projects"]:
            st.info("Žiadny projekt nesedí.")
        for project in results["projects"]:
            cols = st.columns([7, 2])
            cols[0].markdown(f'**{esc(project.get("emoji"))} {esc(project.get("name"))}**  \n'
                             f'<span class="fp-muted">{esc(project.get("description") or "")}'
                             f'</span>', unsafe_allow_html=True)
            if cols[1].button("Otvoriť", key=f"srch_proj_{project['id']}",
                              use_container_width=True):
                goto("project_detail", project_id=project["id"])

    with tabs[3]:
        if not results["risks"]:
            st.info("Žiadne riziko nesedí.")
        for risk in results["risks"][:60]:
            task = repo.get_task(risk["task_id"])
            cols = st.columns([7, 2])
            cols[0].markdown(
                f'**{esc(risk.get("title"))}** '
                f'<span class="fp-badge fp-ai">{risk.get("severity")}/5 × '
                f'{risk.get("likelihood")}/5</span>  \n'
                f'<span class="fp-muted">v úlohe: {esc(task.get("title") if task else "?")}'
                f'</span>', unsafe_allow_html=True)
            if task and cols[1].button("Otvoriť", key=f"srch_risk_{risk['id']}",
                                       use_container_width=True):
                goto("task", task_id=task["id"])

    with tabs[4]:
        if not results["ai"]:
            st.info("Žiadny AI výstup nesedí.")
        for item in results["ai"][:40]:
            task = repo.get_task(item["task_id"])
            stamp = parse_dt(item.get("created_at"))
            with st.expander(f"{item.get('provider')} · "
                             f"{task.get('title') if task else '?'} · "
                             f"{stamp.astimezone().strftime('%d.%m.%Y') if stamp else ''}"):
                st.markdown(esc(item.get("summary") or "")[:1500])
                if task and st.button("Otvoriť úlohu", key=f"srch_ai_{item['id']}"):
                    goto("task", task_id=task["id"])
