"""FinPlay ToDo - projektový manažér šitý na ADHD.

Spustenie:
    pip install -r requirements.txt
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="FinPlay ToDo", page_icon="🎯", layout="centered",
                   initial_sidebar_state="collapsed")

from core import auth, config, notifications  # noqa: E402
from ui import (nav, page_archive, page_feedback, page_more,  # noqa: E402
                page_new_task, page_projects, page_search, page_settings,
                page_task, page_tasks, page_today, theme)

PAGES = {
    "today": page_today.render,
    "tasks": page_tasks.render,
    "new_task": page_new_task.render,
    "search": page_search.render,
    "more": page_more.render,
    # dostupné cez „Viac" alebo z kariet úloh
    "projects": page_projects.render,
    "project_detail": page_projects.render,
    "archive": page_archive.render,
    "settings": page_settings.render,
    "task": page_task.render,
    "feedback": page_feedback.render,
}


# =============================================================================
#  Prihlásenie
# =============================================================================

def login_screen() -> None:
    spacer, toggle = st.columns([0.78, 0.22])
    with toggle:
        theme.theme_button("login_theme")

    st.markdown(
        '<div style="text-align:center;padding:1.6rem 0 1rem;">'
        '<div class="fp-login-logo">🎯</div>'
        '<div class="fp-login-title">FinPlay ToDo</div>'
        '<div class="fp-muted" style="margin-top:.4rem;">'
        'Nezapíše ti úlohu, kým nevieš, čím začneš.</div></div>',
        unsafe_allow_html=True)

    if not config.has_supabase():
        st.info("Beží lokálny režim — dáta zostávajú v tomto počítači. "
                "Vytvor si účet nižšie.")

    tab_login, tab_signup = st.tabs(["Prihlásenie", "Nový účet"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("E-mail", placeholder="ty@firma.sk")
            password = st.text_input("Heslo", type="password")
            if st.form_submit_button("Prihlásiť sa", type="primary",
                                     use_container_width=True):
                ok, message = auth.sign_in(email, password)
                if ok:
                    st.rerun()
                else:
                    st.error(message)

    with tab_signup:
        with st.form("signup_form"):
            full_name = st.text_input("Meno a priezvisko")
            email = st.text_input("E-mail", key="signup_email", placeholder="ty@firma.sk")
            password = st.text_input("Heslo (min. 8 znakov)", type="password",
                                     key="signup_password")
            if st.form_submit_button("Vytvoriť účet", type="primary",
                                     use_container_width=True):
                ok, message = auth.sign_up(email, password, full_name)
                if ok:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)


# =============================================================================
#  Hlavný beh
# =============================================================================

def main() -> None:
    theme.inject()

    if not auth.current_user():
        login_screen()
        return

    st.session_state.setdefault("page", "today")

    try:
        notifications.maybe_auto_send()
    except Exception:
        pass

    page = st.session_state.get("page", "today")
    # spätná väzba si pamätá, z ktorej obrazovky si prišiel - predvyplní pole "Kde"
    if page != "feedback":
        st.session_state["feedback_from"] = page
    PAGES.get(page, page_today.render)()

    nav.render(page)


main()
