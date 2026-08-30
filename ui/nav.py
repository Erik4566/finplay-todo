"""Spodná navigačná lišta - hlavný navigačný prvok aplikácie.

Vzor: Todoist / TickTick / Things - päť cieľov v dosahu palca, prostredný
je zvýraznená akcia „pridať". Lišta je fixná, takže je dostupná odvšadiaľ.
"""

from __future__ import annotations

import streamlit as st

from ui import icons

# (kľúč stránky, ikona, popis)
# Material ikony su monochromaticke - dedia farbu, takze aktivny stav
# sa da odlisit farbou. Emoji to nedokazu (a "..." Streamlit ani neprijme).
TABS = [
    ("today", icons.NAV_TODAY, "Dnes"),
    ("tasks", icons.NAV_TASKS, "Úlohy"),
    ("new_task", icons.NAV_ADD, "Pridať"),
    ("search", icons.NAV_SEARCH, "Hľadať"),
    ("more", icons.NAV_MORE, "Viac"),
]

# stránky, ktoré v lište zvýraznia daný cieľ
BELONGS_TO = {
    "task": "tasks",
    "feedback": "more",
    "project_detail": "more",
    "projects": "more",
    "archive": "more",
    "settings": "more",
}


def active_tab(page: str) -> str:
    return BELONGS_TO.get(page, page)


def render(current_page: str) -> None:
    active = active_tab(current_page)

    with st.container(key="bottomnav"):
        columns = st.columns(len(TABS), gap="small")
        for column, (key, icon, label) in zip(columns, TABS):
            wrapper_key = "navadd" if key == "new_task" else f"navitem_{key}"
            with column:
                with st.container(key=wrapper_key):
                    clicked = st.button(
                        label,
                        icon=icons.st(icon),
                        key=f"nav_{key}",
                        use_container_width=True,
                        type="primary" if key == active else "secondary",
                    )
            if clicked and current_page != key:
                st.session_state["page"] = key
                st.rerun()
