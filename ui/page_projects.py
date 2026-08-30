"""Projekty - prehľad, založenie, členovia, detail."""

from __future__ import annotations

import streamlit as st

from core import auth, repo
from core.models import fmt_minutes
from ui import icons, theme
from ui.components import esc, goto, progress_bar, task_list

EMOJIS = ["📁", "🚀", "💼", "📊", "🏠", "🎓", "💡", "🧾", "🛠️", "❤️"]


def render() -> None:
    project_id = st.session_state.get("nav_project_id")
    if project_id and st.session_state.get("page") == "project_detail":
        _detail(project_id)
        return
    _overview()


# =============================================================================
#  Prehľad
# =============================================================================

def _overview() -> None:
    theme.topbar("Projekty", "väčšie celky")

    with st.expander("Nový projekt", icon=icons.st("add")):
        with st.form("new_project_form", clear_on_submit=True):
            cols = st.columns([1, 5])
            emoji = cols[0].selectbox("Ikona", EMOJIS, label_visibility="collapsed",
                                      key="np_emoji")
            name = cols[1].text_input("Názov projektu *", label_visibility="collapsed",
                                      placeholder="Názov projektu", key="np_name")
            description = st.text_area("Popis / cieľ projektu", height=80, key="np_desc")
            if st.form_submit_button("Vytvoriť", type="primary") and name.strip():
                project = repo.create_project(name, description, emoji)
                st.toast("Projekt vytvorený.", icon=":material/folder_open:")
                goto("project_detail", project_id=project["id"])

    projects = repo.list_projects()
    if not projects:
        st.info("Zatiaľ žiadne projekty. Úlohy môžu existovať aj bez projektu.")
        return

    for project in projects:
        tasks = repo.list_tasks(project_id=project["id"])
        done_tasks = [t for t in repo.list_tasks(project_id=project["id"],
                                                 statuses=["done"]) if not t.get("archived_at")]
        total_minutes = sum(int(t.get("estimated_minutes") or 0) for t in tasks)
        overdue = repo.dashboard_snapshot()["overdue"]
        overdue_here = [t for t in overdue if t.get("project_id") == project["id"]]

        with st.container(border=True):
            cols = st.columns([6, 2])
            with cols[0]:
                st.markdown(f'<div class="fp-card-title">{esc(project.get("emoji"))} '
                            f'{esc(project.get("name"))}</div>'
                            f'<div class="fp-card-sub">{esc(project.get("description") or "")}'
                            f'</div>', unsafe_allow_html=True)
                badges = (f'<span class="fp-badge fp-q2">{len(tasks)} aktívnych</span>'
                          f'<span class="fp-badge fp-time">{icons.html(icons.TIME)} '
                          f'{fmt_minutes(total_minutes)}</span>')
                if overdue_here:
                    badges += (f'<span class="fp-badge fp-q1">{icons.html(icons.RISK)} '
                               f'{len(overdue_here)} '
                               f'po termíne</span>')
                st.markdown(f'<div style="margin-top:8px;">{badges}</div>',
                            unsafe_allow_html=True)
                total = len(tasks) + len(done_tasks)
                if total:
                    st.markdown(progress_bar(len(done_tasks), total).replace("Kroky", "Úlohy"),
                                unsafe_allow_html=True)
            if cols[1].button("Otvoriť", key=f"proj_open_{project['id']}",
                              use_container_width=True):
                goto("project_detail", project_id=project["id"])


# =============================================================================
#  Detail
# =============================================================================

def _detail(project_id: str) -> None:
    project = repo.get_project(project_id)
    if not project:
        st.warning("Projekt sa nenašiel.")
        if st.button("Späť", icon=icons.st("arrow_back")):
            goto("projects")
        return

    with st.container(key="act-projhead"):
        back, toggle = st.columns([0.72, 0.28])
        with back:
            if st.button("Späť na projekty", icon=icons.st("arrow_back"), key="proj_back", use_container_width=True):
                goto("projects")
        with toggle:
            theme.theme_button("proj_theme")

    st.markdown(f"## {project.get('emoji', '📁')} {esc(project.get('name'))}")
    if project.get("description"):
        st.markdown(f'<div class="fp-quote">{esc(project["description"])}</div>',
                    unsafe_allow_html=True)

    tabs = st.tabs(["Úlohy", "Členovia", "Nastavenia projektu"])

    with tabs[0]:
        cols = st.columns([6, 2])
        if cols[1].button("Nová úloha v projekte", icon=icons.st("add"), type="primary",
                          use_container_width=True, key="proj_new_task"):
            st.session_state["nt_project"] = project_id
            goto("new_task")
        active = repo.list_tasks(project_id=project_id)
        done = [t for t in repo.list_tasks(project_id=project_id, statuses=["done"])]
        sub = st.tabs([f"Aktívne ({len(active)})", f"Hotové ({len(done)})"])
        with sub[0]:
            task_list(active, "pd", {project_id: project}, "V projekte nie sú aktívne úlohy.")
        with sub[1]:
            task_list(done, "pdd", {project_id: project}, "Zatiaľ nič dokončené.")

    with tabs[1]:
        people = {p["id"]: p for p in auth.list_people()}
        members = repo.project_members(project_id)
        st.markdown("#### Členovia projektu")
        if not members:
            st.info("Projekt zatiaľ nemá pridaných členov.")
        for member in members:
            profile = people.get(member.get("user_id"), {})
            st.markdown(f"- {profile.get('avatar_emoji', '🙂')} "
                        f"{esc(profile.get('full_name') or profile.get('email') or member.get('user_id'))} "
                        f"<span class='fp-badge fp-q4'>{esc(member.get('role'))}</span>",
                        unsafe_allow_html=True)

        member_ids = {m.get("user_id") for m in members}
        candidates = [pid for pid in people if pid not in member_ids]
        if candidates:
            with st.form("add_member_form", clear_on_submit=True):
                cols = st.columns([4, 2, 2])
                person = cols[0].selectbox(
                    "Pridať osobu", candidates,
                    format_func=lambda v: people[v].get("full_name") or people[v].get("email"))
                role = cols[1].selectbox("Rola", ["member", "viewer", "owner"])
                if cols[2].form_submit_button("Pridať", use_container_width=True):
                    repo.add_project_member(project_id, person, role)
                    st.rerun()

    with tabs[2]:
        with st.form("edit_project_form"):
            cols = st.columns([1, 5])
            emoji = cols[0].selectbox(
                "Ikona", EMOJIS,
                index=EMOJIS.index(project.get("emoji")) if project.get("emoji") in EMOJIS else 0)
            name = cols[1].text_input("Názov", value=project.get("name", ""))
            description = st.text_area("Popis", value=project.get("description") or "",
                                       height=90)
            if st.form_submit_button("Uložiť", icon=icons.st("save"), type="primary"):
                repo.update_project(project_id, {"name": name, "emoji": emoji,
                                                 "description": description})
                st.toast("Uložené.", icon=":material/save:")
                st.rerun()

        if project.get("archived_at"):
            if st.button("Obnoviť z archívu", key="proj_unarchive"):
                repo.archive_project(project_id, False)
                st.rerun()
        else:
            if st.button("Archivovať projekt", icon=icons.st("inventory_2"), key="proj_archive"):
                repo.archive_project(project_id, True)
                st.toast("Projekt archivovaný.", icon=":material/inventory_2:")
                goto("projects")
