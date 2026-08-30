"""Opakovane použiteľné UI prvky - mobile first.

Riadok úlohy je navrhnutý podľa Todoistu: kruhové zaškrtávadlo vľavo,
názov ako dotyková plocha cez celú šírku, ponuka akcií vpravo,
pod tým jeden riadok s metadátami. Farebný prúžok vľavo nesie prioritu.
"""

from __future__ import annotations

import html

import streamlit as st

from core import repo
from ui import icons
from core.models import (ENERGY, QUADRANTS, fmt_due, fmt_duration, fmt_minutes,
                         now_utc, parse_dt, quadrant)


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


# =============================================================================
#  Navigácia
# =============================================================================

def goto(page: str, task_id: str | None = None, project_id: str | None = None) -> None:
    st.session_state["page"] = page
    if task_id is not None:
        st.session_state["nav_task_id"] = task_id
    if project_id is not None:
        st.session_state["nav_project_id"] = project_id
    st.rerun()


# =============================================================================
#  Odznaky
# =============================================================================

def priority_badge(task: dict) -> str:
    key = quadrant(task.get("importance", 3), task.get("urgency", 3))
    quad = QUADRANTS[key]
    return (f'<span class="fp-badge fp-{key.lower()}">{icons.html(quad["icon"])} '
            f'{quad["label"]}</span>')


def priority_marker(task: dict) -> str:
    """Neviditeľná značka - CSS podľa nej farbí ľavý prúžok karty."""
    key = quadrant(task.get("importance", 3), task.get("urgency", 3)).lower()
    return f'<span class="fp-pri-{key}" style="display:none"></span>'


def due_badge(task: dict, short: bool = False) -> str:
    text, state = fmt_due(task.get("due_at"))
    if state == "none":
        return ""
    icon = {"overdue": icons.DUE_OVERDUE, "today": icons.DUE_TODAY,
            "soon": icons.DUE_SOON}.get(state, icons.DUE_LATER)
    if short:
        text = text.split(" · ")[0] if state in ("later", "soon") else text
    return (f'<span class="fp-badge fp-due-{state}">{icons.html(icon)} '
            f'{esc(text)}</span>')


def estimate_badge(task: dict) -> str:
    return (f'<span class="fp-badge fp-time">{icons.html(icons.TIME)} '
            f'{fmt_minutes(task.get("estimated_minutes"))}</span>')


def context_badge(task: dict) -> str:
    if not task.get("context_tag"):
        return ""
    return (f'<span class="fp-badge fp-ctx">{icons.html(icons.CONTEXT)} '
            f'{esc(task["context_tag"])}</span>')


def energy_badge(task: dict) -> str:
    level = task.get("energy_level")
    if not level or level == "medium":
        return ""
    icon = icons.ENERGY_LOW if level == "low" else icons.ENERGY_HIGH
    return (f'<span class="fp-badge fp-q4">{icons.html(icon)} '
            f'{esc(ENERGY.get(level, level))}</span>')


def badges(task: dict) -> str:
    return "".join([priority_badge(task), due_badge(task), estimate_badge(task),
                    context_badge(task), energy_badge(task)])


def progress_bar(done: int, total: int, label: str = "Kroky") -> str:
    percent = int(100 * done / total) if total else 0
    return (f'<div class="fp-progress"><div style="width:{percent}%"></div></div>'
            f'<div class="fp-muted" style="margin-top:.25rem;">{label}: {done}/{total}</div>')


# =============================================================================
#  Riadok úlohy
# =============================================================================

def task_card(task: dict, key_prefix: str, project_name: str | None = None,
              show_actions: bool = True) -> None:
    task_id = task["id"]
    done_steps, total_steps = repo.step_progress(task_id)
    next_step = repo.next_step(task_id)
    is_done = task.get("status") == "done"

    running = st.session_state.get("running_timer")
    is_running = bool(running and running.get("task_id") == task_id)

    with st.container(key=f"row-{key_prefix}-{task_id}"):
        left, middle, right = st.columns([0.14, 0.71, 0.15])

        with left:
            with st.container(key=f"check-{key_prefix}-{task_id}"):
                if st.button("", icon=icons.st(icons.CHECK),
                             key=f"chk_{key_prefix}_{task_id}",
                             help="Hotovo" if not is_done else "Vrátiť do práce"):
                    if is_done:
                        repo.set_status(task_id, "todo")
                    else:
                        spawned = repo.set_status(task_id, "done")
                        st.session_state.pop("running_timer", None)
                        if spawned:
                            st.toast("Vytvorený ďalší výskyt.", icon=":material/autorenew:")
                    st.rerun()

        with middle:
            with st.container(key=f"title-{key_prefix}-{task_id}"):
                if st.button(task.get("title", ""), key=f"ttl_{key_prefix}_{task_id}",
                             type="tertiary", use_container_width=True):
                    goto("task", task_id=task_id)

        with right:
            if show_actions:
                with st.container(key=f"more-{key_prefix}-{task_id}"):
                    with st.popover("", icon=icons.st(icons.NAV_MORE),
                                    use_container_width=True):
                        if st.button("Otvoriť detail", icon=icons.st(icons.OPEN),
                                     key=f"op_{key_prefix}_{task_id}",
                                     use_container_width=True):
                            goto("task", task_id=task_id)
                        if is_running:
                            if st.button("Zastaviť čas", icon=icons.st(icons.STOP),
                                         key=f"stp_{key_prefix}_{task_id}",
                                         use_container_width=True):
                                repo.stop_running_timer()
                                st.session_state.pop("running_timer", None)
                                st.rerun()
                        else:
                            if st.button("Začať a merať", icon=icons.st(icons.PLAY),
                                         key=f"srt_{key_prefix}_{task_id}",
                                         use_container_width=True):
                                entry = repo.start_timer(
                                    task_id, next_step["id"] if next_step else None)
                                st.session_state["running_timer"] = entry
                                st.rerun()
                        if st.button("Archivovať", icon=icons.st(icons.ARCHIVE),
                                     key=f"arc_{key_prefix}_{task_id}",
                                     use_container_width=True):
                            repo.archive_task(task_id, True)
                            st.toast("Presunuté do archívu.", icon=":material/inventory_2:")
                            st.rerun()

        st.markdown(_meta_line(task, next_step, done_steps, total_steps,
                               project_name, is_done, is_running),
                    unsafe_allow_html=True)


def _meta_line(task: dict, next_step, done_steps: int, total_steps: int,
               project_name: str | None, is_done: bool, is_running: bool) -> str:
    parts: list[str] = [priority_marker(task)]
    if is_done:
        parts.append('<span class="fp-done" style="display:none"></span>')

    if is_running:
        parts.append(f'<span class="fp-badge fp-time">{icons.html(icons.PLAY)} beží</span>')

    if next_step and not is_done:
        parts.append(f'<span class="fp-meta-next">{icons.html(icons.NEXT_STEP)} '
                     f'{esc(next_step["title"])}</span>')
    elif total_steps and not is_done:
        parts.append(f'<span>{icons.html(icons.DONE_ALL)} všetky kroky hotové</span>')
    elif not total_steps:
        parts.append(f'<span class="fp-badge fp-due-today">'
                     f'{icons.html(icons.RISK)} bez krokov</span>')

    parts.append(due_badge(task, short=True))
    parts.append(estimate_badge(task))
    if total_steps:
        parts.append(f'<span>{done_steps}/{total_steps}</span>')
    parts.append(context_badge(task))
    if project_name:
        parts.append(f'<span>· {esc(project_name)}</span>')

    return f'<div class="fp-meta">{"".join(p for p in parts if p)}</div>'


def task_list(tasks: list[dict], key_prefix: str, projects_by_id: dict | None = None,
              empty_text: str = "Nič tu nie je. To je v poriadku.") -> None:
    if not tasks:
        st.markdown(f'<div class="fp-muted" style="padding:1.4rem .2rem;text-align:center;">'
                    f'{esc(empty_text)}</div>', unsafe_allow_html=True)
        return
    projects_by_id = projects_by_id or {}
    for task in tasks:
        project = projects_by_id.get(task.get("project_id"))
        name = f"{project.get('emoji', '')} {project.get('name', '')}" if project else None
        task_card(task, key_prefix, name)


# =============================================================================
#  Bežiaci časovač
# =============================================================================

def running_timer_bar() -> None:
    entry = st.session_state.get("running_timer") or repo.running_entry()
    if not entry:
        return
    st.session_state["running_timer"] = entry
    task = repo.get_task(entry["task_id"])
    if not task:
        st.session_state.pop("running_timer", None)
        return

    started = parse_dt(entry.get("started_at")) or now_utc()
    elapsed = int((now_utc() - started).total_seconds())

    with st.container(key="act-timerbar"):
        left, right = st.columns([0.66, 0.34])
        left.markdown(
            f'<div class="fp-timer">{icons.html(icons.TIME)} {esc(task["title"][:34])} · '
            f'{fmt_duration(elapsed)}</div>', unsafe_allow_html=True)
        if right.button("Zastaviť", icon=icons.st(icons.STOP),
                        key="timer_stop_global", use_container_width=True):
            repo.stop_running_timer()
            st.session_state.pop("running_timer", None)
            st.rerun()


# =============================================================================
#  Prázdny stav
# =============================================================================

def empty_state(title: str, hint: str, button_label: str | None = None,
                page: str | None = None) -> None:
    st.markdown(
        f'<div style="text-align:center;padding:2rem .5rem 1rem;">'
        f'<div style="font-size:1.15rem;font-weight:700;">{esc(title)}</div>'
        f'<div class="fp-muted" style="margin-top:.35rem;">{esc(hint)}</div></div>',
        unsafe_allow_html=True)
    if button_label and page:
        if st.button(button_label, type="primary", use_container_width=True):
            goto(page)
