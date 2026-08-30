"""Detail úlohy - kroky, riziká, AI spätná väzba, čas, zdieľanie, synchronizácia."""

from __future__ import annotations

from datetime import datetime, time as dtime, timedelta

import streamlit as st

from ai import orchestrator
from ai.base import normalize
from core import auth, notifications, recurrence, repo
from core.models import (ASSIGNEE_ROLES, CONTEXT_TAGS, ENERGY, IMPORTANCE_LABELS,
                         QUADRANTS, RISK_KINDS, STATUSES, URGENCY_LABELS,
                         fmt_duration, fmt_minutes, now_utc, parse_dt, quadrant)
from integrations import google_calendar, ics, microsoft_todo
from ui import icons, theme
from ui.components import badges, esc, goto, progress_bar


def render() -> None:
    task_id = st.session_state.get("nav_task_id")
    task = repo.get_task(task_id) if task_id else None
    if not task:
        st.warning("Úloha sa nenašla.")
        if st.button("Späť na dnešok", icon=icons.st("arrow_back")):
            goto("today")
        return

    _header(task)
    _next_step_panel(task)

    tabs = st.tabs(["Kroky", "Riziká a výzvy", "AI analýza", "Čas",
                    "Osoby a zdieľanie", "Synchronizácia", "Úprava"])
    with tabs[0]:
        _steps_tab(task)
    with tabs[1]:
        _risks_tab(task)
    with tabs[2]:
        _ai_tab(task)
    with tabs[3]:
        _time_tab(task)
    with tabs[4]:
        _people_tab(task)
    with tabs[5]:
        _sync_tab(task)
    with tabs[6]:
        _edit_tab(task)


# =============================================================================
#  Hlavička
# =============================================================================

def _header(task: dict) -> None:
    with st.container(key="act-taskhead"):
        back, toggle, status_col = st.columns([0.32, 0.16, 0.52])
        with back:
            if st.button("Späť", icon=icons.st("arrow_back"), key="task_back", use_container_width=True):
                goto("tasks")
        with toggle:
            theme.theme_button("task_theme")
        cols = [None, status_col]

    project = repo.get_project(task.get("project_id")) if task.get("project_id") else None
    if project:
        st.markdown(f'<div class="fp-muted">{esc(project.get("emoji"))} '
                    f'{esc(project.get("name"))}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="fp-topbar-title" style="margin:.25rem 0 .5rem;">'
                f'{esc(task.get("title"))}</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:.3rem;margin-bottom:.4rem;">'
                f'{badges(task)}</div>', unsafe_allow_html=True)

    if True:
        if task.get("recurrence_rule"):
            st.markdown(f'<div class="fp-muted">{icons.html(icons.RECURRING)} '
                        f'{recurrence.describe(task["recurrence_rule"])}'
                        f'</div>', unsafe_allow_html=True)
        if task.get("description"):
            st.markdown(f'<div class="fp-quote" style="margin-top:.5rem;">'
                        f'{esc(task["description"])}</div>', unsafe_allow_html=True)

    with cols[1]:
        status = st.selectbox("Stav", list(STATUSES.keys()),
                              index=list(STATUSES.keys()).index(task.get("status", "todo"))
                              if task.get("status") in STATUSES else 1,
                              format_func=lambda v: STATUSES[v], key="task_status")
        if status != task.get("status"):
            spawned = repo.set_status(task["id"], status)
            if spawned:
                st.toast(f"Ďalší výskyt naplánovaný na "
                         f"{parse_dt(spawned['due_at']).astimezone().strftime('%d.%m.%Y')}",
                         icon=":material/autorenew:")
            st.rerun()

        if task.get("archived_at"):
            if st.button("Obnoviť z archívu", use_container_width=True, key="task_unarchive"):
                repo.archive_task(task["id"], False)
                st.rerun()
        else:
            if st.button("Archivovať", icon=icons.st("inventory_2"), use_container_width=True, key="task_archive"):
                repo.archive_task(task["id"], True)
                st.toast("Presunuté do archívu.", icon=":material/inventory_2:")
                goto("today")


def _next_step_panel(task: dict) -> None:
    step = repo.next_step(task["id"])
    done, total = repo.step_progress(task["id"])
    running = repo.running_entry()
    is_running = bool(running and running.get("task_id") == task["id"])

    if step:
        st.markdown(
            f'<div class="fp-hero"><div class="fp-hero-kicker">Najbližší krok</div>'
            f'<div class="fp-hero-step">{esc(step["title"])}</div>'
            f'<div class="fp-hero-meta">{fmt_minutes(step.get("estimated_minutes"))}'
            + (f' · postup {done}/{total}' if total else '') + '</div></div>',
            unsafe_allow_html=True)
    elif total:
        st.success("Všetky kroky sú hotové. Môžeš úlohu uzavrieť.")
    else:
        st.warning("Táto úloha nemá rozklad na kroky. Doplň ich v záložke „Kroky“.")

    with st.container(key="act-task-main"):
        cols = st.columns(2)
    if cols[0].button("Zastaviť čas" if is_running else "Začať a merať",
                      icon=icons.st(icons.STOP if is_running else icons.PLAY),
                      type="primary", use_container_width=True, key="task_timer"):
        if is_running:
            repo.stop_running_timer()
            st.session_state.pop("running_timer", None)
        else:
            entry = repo.start_timer(task["id"], step["id"] if step else None)
            st.session_state["running_timer"] = entry
        st.rerun()

    if cols[1].button("Krok hotový", icon=icons.st("check"), use_container_width=True, disabled=step is None,
                      key="task_step_done"):
        repo.toggle_step(step["id"], True)
        st.rerun()

    with st.container(key="act-task-sec"):
        cols2 = st.columns(2)
    if cols2[0].button("Úloha hotová", icon=icons.st("check_circle"), use_container_width=True,
                       disabled=task.get("status") == "done", key="task_complete"):
        spawned = repo.set_status(task["id"], "done")
        st.session_state.pop("running_timer", None)
        if spawned:
            st.toast("Vytvorený ďalší výskyt opakujúcej sa úlohy.", icon=":material/autorenew:")
        st.rerun()

    if cols2[1].button("Text na kopírovanie", icon=icons.st("list_alt"), use_container_width=True, key="task_text"):
        st.session_state["task_show_text"] = not st.session_state.get("task_show_text", False)

    if st.session_state.get("task_show_text"):
        text = notifications.task_as_text(task, repo.list_steps(task["id"]),
                                          repo.list_risks(task["id"]))
        st.code(text, language=None)


# =============================================================================
#  Kroky
# =============================================================================

def _steps_tab(task: dict) -> None:
    steps = repo.list_steps(task["id"])
    done, total = repo.step_progress(task["id"])
    if total:
        st.markdown(progress_bar(done, total), unsafe_allow_html=True)
        st.write("")

    for index, step in enumerate(steps):
        cols = st.columns([0.6, 6, 1.4, 0.6, 0.6, 0.6])
        checked = cols[0].checkbox(" ", value=bool(step.get("is_done")),
                                   key=f"step_chk_{step['id']}", label_visibility="collapsed")
        if checked != bool(step.get("is_done")):
            repo.toggle_step(step["id"], checked)
            st.rerun()

        style = "opacity:.5;text-decoration:line-through;" if step.get("is_done") else ""
        cols[1].markdown(f'<div style="padding-top:6px;{style}">{esc(step["title"])}</div>',
                         unsafe_allow_html=True)
        cols[2].markdown(f'<div class="fp-muted" style="padding-top:8px;">'
                         f'{fmt_minutes(step.get("estimated_minutes"))}</div>',
                         unsafe_allow_html=True)
        if cols[3].button("", icon=icons.st("keyboard_arrow_up"), key=f"step_up_{step['id']}", disabled=index == 0,
                          help="Posunúť vyššie"):
            _swap(steps, index, index - 1)
            st.rerun()
        if cols[4].button("", icon=icons.st("keyboard_arrow_down"), key=f"step_dn_{step['id']}", disabled=index == len(steps) - 1,
                          help="Posunúť nižšie"):
            _swap(steps, index, index + 1)
            st.rerun()
        if cols[5].button("", icon=icons.st("close"), key=f"step_del_{step['id']}", help="Zmazať krok"):
            repo.delete_step(step["id"])
            st.rerun()

    st.markdown('<hr class="fp-divider">', unsafe_allow_html=True)
    with st.form("add_step_form", clear_on_submit=True):
        cols = st.columns([6, 1.6, 1.4])
        title = cols[0].text_input("Nový krok", label_visibility="collapsed",
                                   placeholder="Ďalší najmenší krok…")
        minutes = cols[1].number_input("min", min_value=1, max_value=480, value=10, step=5,
                                       label_visibility="collapsed")
        if cols[2].form_submit_button("Pridať", icon=icons.st("add"), use_container_width=True) and title.strip():
            repo.add_step(task["id"], title, int(minutes))
            st.rerun()


def _swap(steps: list[dict], first: int, second: int) -> None:
    repo.update_step(steps[first]["id"], {"position": second})
    repo.update_step(steps[second]["id"], {"position": first})


# =============================================================================
#  Riziká a výzvy
# =============================================================================

def _risks_tab(task: dict) -> None:
    st.markdown('<div class="fp-muted">Priestor na to, čo sa môže pokaziť (riziká) '
                'a čo bude ťažké (výzvy). Zápis rizika je polovica jeho riešenia.</div>',
                unsafe_allow_html=True)
    st.write("")

    risks = repo.list_risks(task["id"])
    if not risks:
        st.info("Zatiaľ nič. Skús AI analýzu — navrhne riziká za teba.")

    for risk in risks:
        with st.container(border=True):
            cols = st.columns([7, 1])
            with cols[0]:
                source = (icons.html(icons.AI) + " "
                          + esc(risk.get("source_model") or "AI")
                          if risk.get("source") == "ai"
                          else icons.html(icons.PERSON) + " ručne")
                st.markdown(
                    f'{icons.html(icons.RISK if risk.get("kind") == "risk" else icons.CHALLENGE)} '
                    f'**{RISK_KINDS.get(risk.get("kind"), "Riziko")} · '
                    f'{esc(risk.get("title"))}**  \n'
                    f'<span class="fp-badge fp-ai">závažnosť {risk.get("severity")}/5</span>'
                    f'<span class="fp-badge fp-ai">pravdepodobnosť {risk.get("likelihood")}/5</span>'
                    f'<span class="fp-badge fp-q4">{source}</span>',
                    unsafe_allow_html=True)
                if risk.get("description"):
                    st.markdown(f'<div class="fp-quote" style="margin-top:8px;">'
                                f'{esc(risk["description"])}</div>', unsafe_allow_html=True)
                if risk.get("mitigation"):
                    st.markdown(f'<div style="margin-top:8px;color:#047857;">'
                                f'{icons.html(icons.CHECK)} {esc(risk["mitigation"])}'
                                f'</div>', unsafe_allow_html=True)
            if cols[1].button("", icon=icons.st("close"), key=f"risk_del_{risk['id']}"):
                repo.delete_risk(risk["id"])
                st.rerun()

    st.markdown('<hr class="fp-divider">', unsafe_allow_html=True)
    with st.expander("Pridať riziko alebo výzvu", icon=icons.st("add")):
        with st.form("add_risk_form", clear_on_submit=True):
            kind = st.radio("Typ", list(RISK_KINDS.keys()),
                            format_func=lambda v: RISK_KINDS[v], horizontal=True)
            title = st.text_input("Názov *", placeholder="Čo konkrétne hrozí?")
            description = st.text_area("Popis", height=80)
            cols = st.columns(2)
            severity = cols[0].select_slider("Závažnosť", [1, 2, 3, 4, 5], value=3)
            likelihood = cols[1].select_slider("Pravdepodobnosť", [1, 2, 3, 4, 5], value=3)
            mitigation = st.text_area("Ako to zmierniť", height=70)
            if st.form_submit_button("Uložiť", type="primary") and title.strip():
                repo.add_risk(task["id"], kind=kind, title=title, description=description,
                              severity=severity, likelihood=likelihood,
                              mitigation=mitigation, source="human")
                st.rerun()


# =============================================================================
#  AI analýza
# =============================================================================

def _ai_tab(task: dict) -> None:
    available = orchestrator.available_providers()
    meta = orchestrator.PROVIDER_META

    st.markdown('<div class="fp-muted">Viac modelov naraz = viac uhlov pohľadu. '
                'Výstupy sa ukladajú, takže ich vieš neskôr porovnať.</div>',
                unsafe_allow_html=True)

    cols = st.columns([4, 3, 2])
    chosen = cols[0].multiselect(
        "Modely", available, default=available,
        format_func=lambda v: f"{meta[v]['icon']} {meta[v]['label']}", key="ai_models")
    question = cols[1].text_input("Doplňujúca otázka (nepovinné)",
                                  placeholder="Napr. Na čo si mám dať pozor pri klientovi?",
                                  key="ai_question")
    run = cols[2].button("Spustiť analýzu", icon=icons.st("auto_awesome"), type="primary", use_container_width=True,
                         disabled=not chosen, key="ai_run")

    if st.session_state.pop("task_autorun_ai", False) and available:
        chosen = chosen or available
        run = True

    if run:
        with st.spinner(f"Pýtam sa modelov: {', '.join(meta[c]['label'] for c in chosen)}…"):
            results = orchestrator.analyze_task(task["id"], chosen, question)
        st.session_state["ai_last_results"] = results
        st.rerun()

    results = st.session_state.get("ai_last_results")
    if results:
        _render_results(task, results)

    st.markdown('<hr class="fp-divider">', unsafe_allow_html=True)
    _render_history(task)


def _render_results(task: dict, results) -> None:
    meta = orchestrator.PROVIDER_META
    columns = st.columns(len(results))
    for column, result in zip(columns, results):
        with column:
            info = meta.get(result.provider,
                            {"icon": icons.AI, "label": result.provider})
            st.markdown(f'<div class="fp-ai-head">{icons.html(info["icon"])} {info["label"]} '
                        f'<span class="fp-muted">{esc(result.model or "")}</span></div>',
                        unsafe_allow_html=True)
            if not result.ok:
                st.error(result.error or "Model neodpovedal.")
                continue

            payload = normalize(result.payload)
            st.markdown(f'<div class="fp-quote">{esc(payload["summary"])}</div>',
                        unsafe_allow_html=True)
            if payload["first_action"]:
                st.markdown(f"**Prvá akcia:** {esc(payload['first_action'])}")
            if payload["feedback"]:
                st.markdown(f'<div class="fp-muted" style="margin-top:8px;">'
                            f'{icons.html(icons.AI)} {esc(payload["feedback"])}</div>',
                            unsafe_allow_html=True)

            if payload["missing_steps"]:
                with st.expander(f"Chýbajúce kroky ({len(payload['missing_steps'])})",
                                 expanded=True):
                    for item in payload["missing_steps"]:
                        st.markdown(f"- **{esc(item.get('title'))}** "
                                    f"<span class='fp-muted'>· "
                                    f"{item.get('estimated_minutes', 10)} min</span>",
                                    unsafe_allow_html=True)
                    if st.button("Prevziať kroky", key=f"ai_apply_steps_{result.provider}",
                                 use_container_width=True):
                        count = orchestrator.apply_steps(task["id"], payload["missing_steps"])
                        st.toast(f"Pridaných {count} krokov.", icon=":material/format_list_numbered:")
                        st.rerun()

            risk_count = len(payload["risks"]) + len(payload["challenges"])
            if risk_count:
                with st.expander(f"Riziká a výzvy ({risk_count})", expanded=True):
                    for item in payload["risks"]:
                        st.markdown(f"- **{esc(item.get('title'))}** "
                                    f"<span class='fp-muted'>· {item.get('severity')}/5 × "
                                    f"{item.get('likelihood')}/5</span>",
                                    unsafe_allow_html=True)
                    for item in payload["challenges"]:
                        st.markdown(f"- **{esc(item.get('title'))}**")
                    if st.button("Prevziať do úlohy", key=f"ai_apply_risks_{result.provider}",
                                 use_container_width=True):
                        count = orchestrator.apply_risks(task["id"], result)
                        st.toast(f"Pridaných {count} položiek.", icon=":material/warning:")
                        st.rerun()

            if payload["adhd_tips"]:
                with st.expander("ADHD tipy"):
                    for tip in payload["adhd_tips"]:
                        st.markdown(f"- {esc(tip)}")

            st.markdown(
                f'<div class="fp-muted">Odhad modelu: '
                f'{fmt_minutes(payload["estimated_minutes_total"])} · '
                f'istota {payload["confidence"]}/5'
                + (f' · {result.latency_ms} ms' if result.latency_ms else '') + '</div>',
                unsafe_allow_html=True)


def _render_history(task: dict) -> None:
    history = repo.list_ai_feedback(task["id"])
    st.markdown(f"#### História AI výstupov ({len(history)})")
    if not history:
        st.info("Zatiaľ žiadna uložená analýza.")
        return
    meta = orchestrator.PROVIDER_META
    for item in history[:15]:
        info = meta.get(item.get("provider"),
                        {"icon": icons.AI, "label": item.get("provider")})
        stamp = parse_dt(item.get("created_at"))
        label = (f"{info['label']} · "
                 f"{stamp.astimezone().strftime('%d.%m.%Y %H:%M') if stamp else ''}")
        with st.expander(label):
            if item.get("error"):
                st.error(item["error"])
            payload = normalize(item.get("payload"))
            if payload["summary"]:
                st.markdown(esc(payload["summary"]))
            if payload["feedback"]:
                st.markdown(f'<div class="fp-muted">{icons.html(icons.AI)} '
                            f'{esc(payload["feedback"])}</div>',
                            unsafe_allow_html=True)
            if item.get("raw_text"):
                with st.expander("Surová odpoveď"):
                    st.code(item["raw_text"][:6000], language="json")
            if st.button("Zmazať záznam", key=f"ai_del_{item['id']}"):
                repo.delete_ai_feedback(item["id"])
                st.rerun()


# =============================================================================
#  Čas
# =============================================================================

def _time_tab(task: dict) -> None:
    tracked = repo.tracked_seconds(task["id"])
    estimate = int(task.get("estimated_minutes") or 0) * 60

    cols = st.columns(3)
    cols[0].metric("Nameraný čas", fmt_duration(tracked))
    cols[1].metric("Odhad", fmt_minutes(task.get("estimated_minutes")))
    if estimate:
        delta = tracked - estimate
        cols[2].metric("Rozdiel", fmt_duration(abs(delta)),
                       delta=("nad odhad" if delta > 0 else "pod odhad"),
                       delta_color="inverse" if delta > 0 else "normal")

    entries = repo.time_entries(task["id"])
    if not entries:
        st.info("Zatiaľ nič nameraného. Časovač spustíš tlačidlom hore.")
        return

    st.markdown("#### Záznamy")
    for entry in entries[:30]:
        started = parse_dt(entry.get("started_at"))
        duration = entry.get("duration_seconds")
        running = " · **beží**" if not entry.get("ended_at") else ""
        st.markdown(
            f'- {started.astimezone().strftime("%d.%m.%Y %H:%M") if started else "?"} · '
            f'{fmt_duration(duration) if duration else "—"}{running}')


# =============================================================================
#  Osoby, zdieľanie, pripomienky
# =============================================================================

def _people_tab(task: dict) -> None:
    people = {p["id"]: p for p in auth.list_people()}
    assignees = repo.list_assignees(task["id"])

    st.markdown("#### Priradené osoby")
    if not assignees:
        st.info("Úloha nie je nikomu priradená.")
    for item in assignees:
        cols = st.columns([6, 1])
        profile = people.get(item.get("user_id"))
        label = (f"{profile.get('avatar_emoji', '🙂')} "
                 f"{profile.get('full_name') or profile.get('email')}") if profile \
            else f"{item.get('email')}"
        cols[0].markdown(f"{label} <span class='fp-badge fp-q4'>"
                         f"{ASSIGNEE_ROLES.get(item.get('role'), item.get('role'))}</span>",
                         unsafe_allow_html=True)
        if cols[1].button("", icon=icons.st("close"), key=f"assignee_del_{item['id']}"):
            repo.remove_assignee(item["id"])
            st.rerun()

    with st.form("add_assignee_form", clear_on_submit=True):
        cols = st.columns([3, 3, 2])
        person = cols[0].selectbox("Osoba s účtom", [None] + list(people.keys()),
                                   format_func=lambda v: "(vybrať)" if v is None else
                                   people[v].get("full_name") or people[v].get("email"))
        email = cols[1].text_input("alebo e-mail")
        role = cols[2].selectbox("Rola", list(ASSIGNEE_ROLES.keys()),
                                 format_func=lambda v: ASSIGNEE_ROLES[v])
        if st.form_submit_button("Priradiť") and (person or email.strip()):
            repo.add_assignee(task["id"], user_id=person, email=email or None, role=role)
            st.rerun()

    st.markdown('<hr class="fp-divider">', unsafe_allow_html=True)

    # ---------------- zdieľanie ----------------
    st.markdown("#### Zdieľať e-mailom")
    default_recipients = ", ".join(repo.assignee_emails(task["id"], people))
    recipients = st.text_area("Príjemcovia (oddelení čiarkou)", value=default_recipients,
                              height=68, key="share_recipients")
    note = st.text_area("Odkaz v e-maile", height=80, key="share_note",
                        placeholder="Ahoj, posielam ti túto úlohu aj s rozkladom na kroky…")
    cols = st.columns([2, 5])
    if cols[0].button("Odoslať", icon=icons.st("mail"), type="primary", use_container_width=True,
                      key="share_send"):
        ok, message = notifications.share_task(
            task["id"], [r.strip() for r in recipients.split(",")], note)
        (st.success if ok else st.error)(message)

    shares = repo.list_shares(task["id"])
    if shares:
        with st.expander(f"História zdieľania ({len(shares)})"):
            for share in shares[:20]:
                stamp = parse_dt(share.get("created_at"))
                icon = icons.html(icons.CHECK if share.get("status") == "sent"
                                  else icons.CLOSE)
                st.markdown(f"{icon} {esc(share.get('recipient_email'))} · "
                            f"{stamp.astimezone().strftime('%d.%m.%Y %H:%M') if stamp else ''}"
                            + (f" · {esc(share.get('error'))}" if share.get("error") else ""))

    st.markdown('<hr class="fp-divider">', unsafe_allow_html=True)

    # ---------------- pripomienky ----------------
    st.markdown("#### Pripomienky")
    for reminder in repo.list_reminders(task["id"]):
        cols = st.columns([6, 1])
        when = parse_dt(reminder.get("remind_at"))
        state = "odoslané" if reminder.get("sent_at") else \
            ("zavreté" if reminder.get("dismissed_at") else "čaká")
        cols[0].markdown(f"{icons.html(icons.BELL)} "
                         f"{when.astimezone().strftime('%d.%m.%Y %H:%M') if when else '?'} · "
                         f"{'e-mail' if reminder.get('channel') == 'email' else 'v appke'} · "
                         f"<span class='fp-muted'>{state}</span>", unsafe_allow_html=True)
        if cols[1].button("", icon=icons.st("close"), key=f"rem_del_{reminder['id']}"):
            repo.delete_reminder(reminder["id"])
            st.rerun()

    with st.form("add_reminder_form", clear_on_submit=True):
        cols = st.columns([2, 2, 2, 2])
        date = cols[0].date_input("Dátum", value=now_utc().astimezone().date())
        clock = cols[1].time_input("Čas", value=dtime(9, 0))
        channel = cols[2].selectbox("Kanál", ["app", "email"],
                                    format_func=lambda v: "V aplikácii" if v == "app"
                                    else "E-mail")
        message = cols[3].text_input("Text")
        if st.form_submit_button("Pridať pripomienku"):
            repo.create_reminder(task["id"], datetime.combine(date, clock).astimezone(),
                                 channel, message)
            st.rerun()


# =============================================================================
#  Synchronizácia
# =============================================================================

def _sync_tab(task: dict) -> None:
    steps = repo.list_steps(task["id"])

    google_status = google_calendar.status()
    ms_status = microsoft_todo.status()

    cols = st.columns(2)
    with cols[0]:
        with st.container(border=True):
            st.markdown("#### Google Calendar")
            _status_line(google_status)
            if task.get("google_event_id"):
                st.markdown(f'<div class="fp-muted">Napojená udalosť: '
                            f'{esc(task["google_event_id"][:18])}…</div>',
                            unsafe_allow_html=True)
            if st.button("Odoslať do kalendára", use_container_width=True, key="sync_google"):
                ok, message = google_calendar.push_task(task, steps)
                (st.success if ok else st.warning)(message)
            if task.get("google_event_id") and st.button(
                    "Odpojiť udalosť", use_container_width=True, key="sync_google_del"):
                ok, message = google_calendar.delete_event(task)
                (st.success if ok else st.warning)(message)

    with cols[1]:
        with st.container(border=True):
            st.markdown("#### Microsoft To Do")
            _status_line(ms_status)
            if task.get("ms_todo_task_id"):
                st.markdown(f'<div class="fp-muted">Napojená úloha: '
                            f'{esc(task["ms_todo_task_id"][:18])}…</div>',
                            unsafe_allow_html=True)
            if st.button("Odoslať do To Do", use_container_width=True, key="sync_ms"):
                ok, message = microsoft_todo.push_task(task, steps)
                (st.success if ok else st.warning)(message)
            if task.get("ms_todo_task_id") and st.button(
                    "Odpojiť úlohu", use_container_width=True, key="sync_ms_del"):
                ok, message = microsoft_todo.delete_task(task)
                (st.success if ok else st.warning)(message)

    st.markdown('<hr class="fp-divider">', unsafe_allow_html=True)
    st.markdown("#### Export do kalendára (.ics)")
    st.markdown('<div class="fp-muted">Funguje vždy, aj bez pripojených účtov — '
                'stiahni a importuj do ľubovoľného kalendára.</div>', unsafe_allow_html=True)
    st.download_button(
        "Stiahnuť .ics", data=ics.build_calendar([task], {task["id"]: steps}),
        file_name=f"{task['title'][:40].replace(' ', '_')}.ics",
        mime="text/calendar", key="sync_ics")

    log = [row for row in repo.recent_sync_log(50) if row.get("task_id") == task["id"]]
    if log:
        with st.expander(f"Log synchronizácie ({len(log)})"):
            for row in log[:20]:
                stamp = parse_dt(row.get("created_at"))
                icon = icons.html({"ok": icons.CHECK, "error": icons.CLOSE}
                                  .get(row.get("status"), icons.DEMO))
                st.markdown(f"{icon} {esc(row.get('provider'))} · "
                            f"{stamp.astimezone().strftime('%d.%m. %H:%M') if stamp else ''} · "
                            f"{esc(row.get('message'))}")


def _status_line(status: dict) -> None:
    if not status["configured"]:
        st.markdown(f'<span class="fp-badge fp-q4">{icons.html(icons.DEMO)} '
                    f'Mock režim</span> '
                    '<span class="fp-muted">chýbajú prihlasovacie údaje v secrets.toml</span>',
                    unsafe_allow_html=True)
    elif status["connected"]:
        st.markdown(f'<span class="fp-badge fp-time">{icons.html(icons.CHECK)} '
                    f'Pripojené</span> '
                    f'<span class="fp-muted">{esc(status.get("email") or "")}</span>',
                    unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="fp-badge fp-due-today">{icons.html(icons.RISK)} '
                    f'Nepripojený účet</span> '
                    '<span class="fp-muted">Nastavenia → Integrácie</span>',
                    unsafe_allow_html=True)


# =============================================================================
#  Úprava
# =============================================================================

def _edit_tab(task: dict) -> None:
    with st.form("edit_task_form"):
        title = st.text_input("Názov", value=task.get("title", ""))
        description = st.text_area("Popis", value=task.get("description") or "", height=110)

        projects = repo.list_projects()
        options = [None] + [p["id"] for p in projects]
        labels = {p["id"]: f"{p.get('emoji', '📁')} {p['name']}" for p in projects}
        current = task.get("project_id")
        project_id = st.selectbox(
            "Projekt", options,
            index=options.index(current) if current in options else 0,
            format_func=lambda v: "(bez projektu)" if v is None else labels.get(v, "?"))

        cols = st.columns(2)
        importance = cols[0].select_slider(
            "Dôležitosť", [1, 2, 3, 4, 5], value=int(task.get("importance") or 3),
            format_func=lambda v: IMPORTANCE_LABELS[v])
        urgency = cols[1].select_slider(
            "Urgentnosť", [1, 2, 3, 4, 5], value=int(task.get("urgency") or 3),
            format_func=lambda v: URGENCY_LABELS[v])

        cols = st.columns(3)
        due = parse_dt(task.get("due_at"))
        has_due = cols[0].checkbox("Termín", value=bool(due))
        due_date = cols[0].date_input(
            "Dátum", value=due.astimezone().date() if due
            else (now_utc() + timedelta(days=1)).astimezone().date())
        due_time = cols[0].time_input(
            "Čas", value=due.astimezone().time() if due else dtime(17, 0))
        estimate = cols[1].number_input("Odhad (min)", min_value=5, max_value=2400, step=5,
                                        value=int(task.get("estimated_minutes") or 30))
        energy_keys = list(ENERGY.keys())
        energy = cols[1].selectbox(
            "Energia", energy_keys,
            index=energy_keys.index(task.get("energy_level") or "medium"),
            format_func=lambda v: ENERGY[v])
        context_options = ["(žiadny)"] + CONTEXT_TAGS
        context = cols[2].selectbox(
            "Kontext", context_options,
            index=context_options.index(task["context_tag"])
            if task.get("context_tag") in context_options else 0)
        preset_keys = list(recurrence.PRESETS.keys())
        current_rule = task.get("recurrence_rule") or ""
        preset_index = next((i for i, k in enumerate(preset_keys)
                             if recurrence.PRESETS[k] == current_rule), 0)
        repeat = cols[2].selectbox("Opakovanie", preset_keys, index=preset_index)

        if st.form_submit_button("Uložiť zmeny", icon=icons.st("save"), type="primary"):
            repo.update_task(task["id"], {
                "title": title.strip() or task["title"],
                "description": description,
                "project_id": project_id,
                "importance": importance,
                "urgency": urgency,
                "estimated_minutes": int(estimate),
                "due_at": (datetime.combine(due_date, due_time).astimezone().isoformat()
                           if has_due else None),
                "energy_level": energy,
                "context_tag": None if context == "(žiadny)" else context,
                "recurrence_rule": recurrence.PRESETS[repeat] or None,
            })
            st.toast("Uložené.", icon=":material/save:")
            st.rerun()

    st.markdown('<hr class="fp-divider">', unsafe_allow_html=True)
    with st.expander("Trvalé zmazanie úlohy", icon=icons.st("delete")):
        st.markdown('<div class="fp-muted">Zmaže úlohu vrátane krokov, rizík, AI výstupov '
                    'a nameraného času. Nedá sa vrátiť — zvyčajne stačí archivovať.</div>',
                    unsafe_allow_html=True)
        confirm = st.text_input("Napíš ZMAZAŤ na potvrdenie", key="delete_confirm")
        if st.button("Zmazať natrvalo", key="task_delete",
                     disabled=confirm.strip().upper() != "ZMAZAŤ"):
            repo.delete_task(task["id"])
            st.session_state.pop("delete_confirm", None)
            st.toast("Úloha zmazaná.", icon=":material/delete:")
            goto("today")
