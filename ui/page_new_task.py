"""Nová úloha - sprievodca, ktorý bez rozkladu na kroky nedovolí uložiť."""

from __future__ import annotations

import uuid
from datetime import datetime, time as dtime, timedelta

import streamlit as st

from ai import orchestrator
from ai.base import normalize
from core import auth, config, recurrence, repo
from core.models import (ASSIGNEE_ROLES, CONTEXT_TAGS, ENERGY, IMPORTANCE_LABELS,
                         QUADRANTS, URGENCY_LABELS, fmt_minutes, now_utc, quadrant)
from ui import icons, theme
from ui.components import esc, goto

MIN_STEPS = config.app_config()["min_steps"]


def _blank_step() -> dict:
    return {"uid": uuid.uuid4().hex[:8], "title": "", "minutes": 10}


def _init_state() -> None:
    st.session_state.setdefault("nt_steps", [_blank_step() for _ in range(MIN_STEPS)])
    st.session_state.setdefault("nt_ai_suggestion", None)


def _reset_state() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith("nt_"):
            del st.session_state[key]


def render() -> None:
    _init_state()
    theme.topbar("Nová úloha")
    st.markdown(
        '<div class="fp-muted">Systém úlohu neuloží, kým nevieš, čím začneš. '
        f'Minimum je {MIN_STEPS} kroky.</div>', unsafe_allow_html=True)

    _quick_capture()

    st.markdown('<hr class="fp-divider">', unsafe_allow_html=True)

    # ---------------------------------------------------------------- 1. Čo
    st.markdown("### 1 · Čo treba urobiť")
    title = st.text_input("Názov úlohy *", key="nt_title",
                          placeholder="Napr. Pripraviť ponuku pre klienta X")
    description = st.text_area(
        "Popis a definícia „hotovo“", key="nt_description", height=90,
        placeholder="Ako spoznáš, že je úloha naozaj dokončená?")

    projects = repo.list_projects()
    project_options = [None] + [p["id"] for p in projects]
    project_labels = {p["id"]: f"{p.get('emoji', '📁')} {p['name']}" for p in projects}
    project_id = st.selectbox(
        "Projekt", project_options,
        format_func=lambda v: "(bez projektu)" if v is None else project_labels.get(v, "?"),
        key="nt_project")

    # ------------------------------------------------------------- 2. Kroky
    st.markdown("### 2 · Rozklad na najmenšie kroky *")
    st.markdown(
        '<div class="fp-muted">Každý krok má byť taký malý, aby sa dal začať do dvoch minút '
        'bez ďalšieho rozmýšľania.</div>', unsafe_allow_html=True)

    _ai_step_helper(title, description)

    steps = st.session_state["nt_steps"]
    for index, step in enumerate(steps):
        uid = step.setdefault("uid", uuid.uuid4().hex[:8])
        cols = st.columns([6, 1.6, 0.8])
        step["title"] = cols[0].text_input(
            f"Krok {index + 1}", value=step.get("title", ""),
            key=f"nt_step_title_{uid}", label_visibility="collapsed",
            placeholder=f"Krok {index + 1} — konkrétna akcia")
        step["minutes"] = cols[1].number_input(
            "min", min_value=1, max_value=480, step=5,
            value=int(step.get("minutes", 10)),
            key=f"nt_step_min_{uid}", label_visibility="collapsed")
        if cols[2].button("", icon=icons.st("close"), key=f"nt_step_del_{uid}",
                          disabled=len(steps) <= 1, help="Odstrániť krok"):
            steps.pop(index)
            st.rerun()

    cols = st.columns([2, 6])
    if cols[0].button("Ďalší krok", icon=icons.st("add"), use_container_width=True):
        steps.append(_blank_step())
        st.rerun()

    filled = [s for s in steps if s.get("title", "").strip()]
    total_minutes = sum(int(s.get("minutes") or 0) for s in filled)
    if filled:
        cols[1].markdown(
            f'<div class="fp-muted" style="padding-top:8px;">Vyplnené kroky: '
            f'<b>{len(filled)}/{MIN_STEPS}</b> · súčet odhadov: '
            f'<b>{fmt_minutes(total_minutes)}</b></div>', unsafe_allow_html=True)

    # -------------------------------------------------------- 3. Priorita
    st.markdown("### 3 · Dôležitosť a urgentnosť *")
    cols = st.columns(2)
    importance = cols[0].select_slider(
        "Dôležitosť — posunie ma to k cieľu?", options=[1, 2, 3, 4, 5], value=3,
        format_func=lambda v: IMPORTANCE_LABELS[v], key="nt_importance")
    urgency = cols[1].select_slider(
        "Urgentnosť — ako veľmi to horí?", options=[1, 2, 3, 4, 5], value=3,
        format_func=lambda v: URGENCY_LABELS[v], key="nt_urgency")

    quad = QUADRANTS[quadrant(importance, urgency)]
    st.markdown(
        f'<div style="margin:-6px 0 10px;"><span class="fp-badge '
        f'fp-{quadrant(importance, urgency).lower()}">{icons.html(quad["icon"])} '
        f'{quad["label"]}</span>'
        f'</div>', unsafe_allow_html=True)

    # ----------------------------------------------------------- 4. Kto
    st.markdown("### 4 · Kto to urobí *")
    people = auth.list_people()
    people_labels = {p["id"]: f"{p.get('avatar_emoji', '🙂')} "
                              f"{p.get('full_name') or p.get('email')}" for p in people}
    selected_people = st.multiselect(
        "Osoby s účtom", options=list(people_labels.keys()),
        format_func=lambda v: people_labels.get(v, v),
        default=[auth.current_user()["id"]] if auth.current_user() and
        auth.current_user()["id"] in people_labels else [],
        key="nt_people")
    role = st.selectbox("Rola priradených osôb", list(ASSIGNEE_ROLES.keys()),
                        format_func=lambda v: ASSIGNEE_ROLES[v], key="nt_role")
    external = st.text_input(
        "Ďalšie osoby e-mailom (oddelené čiarkou)", key="nt_external",
        placeholder="kolega@firma.sk, externista@dodavatel.sk")

    # ---------------------------------------------------------- 5. Kedy
    st.markdown("### 5 · Kedy a v akom režime")
    cols = st.columns(3)
    has_due = cols[0].checkbox("Nastaviť termín", value=True, key="nt_has_due")
    due_date = cols[0].date_input(
        "Dátum", value=(now_utc() + timedelta(days=1)).astimezone().date(),
        key="nt_due_date", disabled=not has_due)
    due_time = cols[0].time_input("Čas", value=dtime(17, 0), key="nt_due_time",
                                  disabled=not has_due)
    estimate = cols[1].number_input(
        "Celkový odhad (min)", min_value=5, max_value=2400, step=5,
        value=max(5, total_minutes or 30), key="nt_estimate")
    energy = cols[1].selectbox("Potrebná energia", list(ENERGY.keys()), index=1,
                               format_func=lambda v: ENERGY[v], key="nt_energy")
    context = cols[2].selectbox("Kontext", ["(žiadny)"] + CONTEXT_TAGS, key="nt_context")
    repeat_label = cols[2].selectbox("Opakovanie", list(recurrence.PRESETS.keys()),
                                     key="nt_repeat")
    reminder_before = cols[2].selectbox(
        "Pripomienka", ["Bez pripomienky", "30 minút pred", "2 hodiny pred",
                        "1 deň pred"], key="nt_reminder")

    # -------------------------------------------------------- Uloženie
    st.markdown('<hr class="fp-divider">', unsafe_allow_html=True)

    problems = []
    if not title.strip():
        problems.append("Úloha potrebuje názov.")
    if len(filled) < MIN_STEPS:
        problems.append(f"Doplň aspoň {MIN_STEPS} kroky (teraz máš {len(filled)}).")
    if not selected_people and not external.strip():
        problems.append("Priraď úlohu aspoň jednej osobe.")

    if problems:
        st.warning("Ešte chýba:\n\n" + "\n".join(f"- {p}" for p in problems))

    cols = st.columns([2, 2, 4])
    save_and_analyze = cols[1].button("Uložiť a spustiť AI analýzu",
                                      use_container_width=True, disabled=bool(problems))
    save = cols[0].button("Uložiť úlohu", type="primary", use_container_width=True,
                          disabled=bool(problems))

    if save or save_and_analyze:
        due_at = None
        if has_due:
            due_at = datetime.combine(due_date, due_time).astimezone()

        assignees = [{"user_id": pid, "role": role} for pid in selected_people]
        for email in [e.strip() for e in external.split(",") if e.strip()]:
            assignees.append({"email": email, "role": role})

        task = repo.create_task(
            title=title, description=description, project_id=project_id,
            importance=importance, urgency=urgency, estimated_minutes=estimate,
            due_at=due_at, status="todo", energy_level=energy,
            context_tag=None if context == "(žiadny)" else context,
            recurrence_rule=recurrence.PRESETS[repeat_label] or None,
            steps=[{"title": s["title"], "estimated_minutes": s["minutes"]} for s in filled],
            assignees=assignees,
        )

        if due_at and reminder_before != "Bez pripomienky":
            delta = {"30 minút pred": timedelta(minutes=30),
                     "2 hodiny pred": timedelta(hours=2),
                     "1 deň pred": timedelta(days=1)}[reminder_before]
            repo.create_reminder(task["id"], due_at - delta, channel="app",
                                 message=f"Blíži sa termín: {title}")

        _reset_state()
        st.session_state["nt_just_created"] = task["id"]
        if save_and_analyze:
            st.session_state["task_autorun_ai"] = True
        goto("task", task_id=task["id"])


# =============================================================================
#  Rýchle zachytenie
# =============================================================================

def _quick_capture() -> None:
    with st.expander("Rýchle zachytenie do Inboxu (keď na sprievodcu teraz nemáš hlavu)", icon=icons.st("bolt")):
        st.markdown(
            '<div class="fp-muted">Úloha sa uloží do Inboxu s jediným krokom: '
            '„Rozložiť na kroky". Pravidlo rozkladu tým zostáva zachované — '
            'len sa odloží o pár minút.</div>', unsafe_allow_html=True)
        text = st.text_input("Čo ti prebehlo hlavou?", key="qc_title",
                             label_visibility="collapsed",
                             placeholder="Zapíš to sem a vráť sa k tomu neskôr…")
        if st.button("Uložiť do Inboxu", key="qc_save", disabled=not text.strip()):
            user = auth.current_user()
            task = repo.create_task(
                title=text.strip(), status="inbox", importance=3, urgency=3,
                estimated_minutes=15,
                steps=[{"title": "Rozložiť na kroky a doplniť detaily",
                        "estimated_minutes": 5}],
                assignees=[{"user_id": user["id"], "role": "responsible"}] if user else [],
            )
            st.session_state.pop("qc_title", None)
            st.toast("Uložené do Inboxu.", icon=":material/download:")
            goto("task", task_id=task["id"])


# =============================================================================
#  AI pomoc pri rozklade
# =============================================================================

def _ai_step_helper(title: str, description: str) -> None:
    providers = orchestrator.available_providers()
    cols = st.columns([3, 3, 4])
    provider = cols[0].selectbox(
        "Model na návrh krokov", providers,
        format_func=lambda v: f"{orchestrator.PROVIDER_META[v]['icon']} "
                              f"{orchestrator.PROVIDER_META[v]['label']}",
        key="nt_ai_provider", label_visibility="collapsed")
    if cols[1].button("Navrhni kroky", icon=icons.st("auto_awesome"), use_container_width=True,
                      disabled=not title.strip(), key="nt_ai_btn"):
        with st.spinner("Rozkladám úlohu…"):
            result = orchestrator.suggest_steps(title, description, provider)
        st.session_state["nt_ai_suggestion"] = result

    result = st.session_state.get("nt_ai_suggestion")
    if not result:
        return
    if not result.ok:
        st.error(result.error or "Model neodpovedal.")
        return

    payload = normalize(result.payload)
    suggestions = payload["missing_steps"]
    if not suggestions:
        st.info("Model nenavrhol žiadne ďalšie kroky.")
        return

    with st.container(border=True):
        st.markdown(f"**Návrh od {orchestrator.PROVIDER_META[result.provider]['label']}**")
        if payload["summary"]:
            st.markdown(f'<div class="fp-quote">{esc(payload["summary"])}</div>',
                        unsafe_allow_html=True)
        for item in suggestions:
            st.markdown(f"- **{esc(item.get('title'))}** "
                        f"<span class='fp-muted'>· {item.get('estimated_minutes', 10)} min "
                        f"— {esc(item.get('why'))}</span>", unsafe_allow_html=True)
        cols = st.columns([2, 2, 4])
        if cols[0].button("Prevziať kroky", key="nt_ai_apply", type="primary",
                          use_container_width=True):
            current = [s for s in st.session_state["nt_steps"] if s.get("title", "").strip()]
            for item in suggestions:
                current.append({"uid": uuid.uuid4().hex[:8],
                                "title": item.get("title", ""),
                                "minutes": int(item.get("estimated_minutes") or 10)})
            st.session_state["nt_steps"] = current or st.session_state["nt_steps"]
            st.session_state["nt_ai_suggestion"] = None
            st.rerun()
        if cols[1].button("Zahodiť návrh", key="nt_ai_discard", use_container_width=True):
            st.session_state["nt_ai_suggestion"] = None
            st.rerun()
