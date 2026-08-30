"""Nastavenia - integrácie, AI modely, e-mail, profil, stav systému."""

from __future__ import annotations

import streamlit as st

from ai import orchestrator
from core import auth, calendars, config, db, notifications, repo
from core.models import parse_dt
from datetime import date
from integrations import email_smtp, google_calendar, microsoft_todo
from ui import icons, theme
from ui.components import esc


def render() -> None:
    theme.topbar("Nastavenia")

    tabs = st.tabs(["Integrácie", "AI modely", "E-mail a upozornenia",
                    "Kalendár", "Profil", "Stav systému"])
    with tabs[0]:
        _integrations()
    with tabs[1]:
        _ai()
    with tabs[2]:
        _email()
    with tabs[3]:
        _calendar()
    with tabs[4]:
        _profile()
    with tabs[5]:
        _health()


# =============================================================================
#  Kalendár - krajina, sviatky, stav dát
# =============================================================================

def _calendar() -> None:
    codes = list(calendars.COUNTRIES.keys())
    current = st.session_state.get("ui_country", calendars.DEFAULT_COUNTRY)
    choice = st.selectbox(
        "Krajina", codes, index=codes.index(current) if current in codes else 0,
        format_func=lambda c: calendars.COUNTRIES[c]["label"], key="ui_country_select")
    if choice != current:
        st.session_state["ui_country"] = choice
        st.rerun()

    cfg = calendars.country_config(choice)
    year = date.today().year

    theme.section("Meniny")
    if calendars.has_namedays(choice):
        st.markdown(
            f'<span class="fp-badge fp-time">{icons.html(icons.CHECK)} '
            f'{esc(cfg["nameday_source"])}</span>', unsafe_allow_html=True)
        if cfg.get("nameday_url"):
            st.markdown(f'[Oficiálny zdroj]({cfg["nameday_url"]})')
        st.caption("Aktualizácia zo zdroja:  python tools/update_calendar.py")
    else:
        st.warning(f"Meniny nie sú k dispozícii — {cfg['nameday_source']}. "
                   f"Doplniť sa dajú do súboru `data/{cfg['nameday_file']}`.")

    theme.section("Sviatky")
    st.markdown(f"Počítané zo zákona: **{cfg['law']}** · "
                f"[úplné znenie]({cfg['law_url']})")
    if calendars.is_verified(year):
        st.markdown(
            f'<span class="fp-badge fp-time">{icons.html(icons.CHECK)} '
            f'Znenie overené pri zdroji do roku {calendars.VERIFIED_UNTIL}</span>',
            unsafe_allow_html=True)
    else:
        st.warning(f"Znenie zákona bolo naposledy overené pre rok "
                   f"{calendars.VERIFIED_UNTIL}. Odvtedy mohla vyjsť novela — "
                   f"over zoznam nižšie pri zdroji.")

    st.markdown('<div class="fp-muted">Pohyblivé sviatky sa počítajú z Veľkej noci, '
                'takže tabuľka platí pre ľubovoľný rok. Ručne treba doplniť len '
                'novely zákona.</div>', unsafe_allow_html=True)

    shown = st.selectbox("Rok", [year, year + 1, year + 2], key="cal_year")
    rows = []
    for day, info in sorted(calendars.holidays(shown, choice).items()):
        css = "fp-q1" if info["rest"] else "fp-q3"
        rows.append(
            f'<div class="fp-event">'
            f'<div class="fp-event-time">{day.strftime("%d.%m.")}</div>'
            f'<div class="fp-event-title">{esc(info["name"])}'
            f'<div style="margin-top:.15rem;"><span class="fp-badge {css}">'
            f'{esc(calendars.label_for(info, choice))}</span></div></div></div>')
    st.markdown("".join(rows), unsafe_allow_html=True)

    days_off = sum(1 for i in calendars.holidays(shown, choice).values() if i["rest"])
    st.caption(f"Spolu {len(calendars.holidays(shown, choice))} sviatkov, "
               f"z toho {days_off} dní pracovného pokoja.")


# =============================================================================
#  Integrácie
# =============================================================================

def _integrations() -> None:
    st.markdown("### Google Calendar")
    _oauth_block(
        provider="google",
        status=google_calendar.status(),
        auth_url_fn=google_calendar.auth_url,
        exchange_fn=google_calendar.exchange_code,
        disconnect_fn=google_calendar.disconnect,
        setup_hint=(
            "Google Cloud Console → APIs & Services → Credentials → "
            "OAuth client ID (Web application). Do *Authorized redirect URIs* pridaj "
            "`http://localhost:8501`. Zapni **Google Calendar API**. "
            "client_id a client_secret potom vlož do sekcie `[google]` v "
            "`.streamlit/secrets.toml`."),
    )

    st.markdown('<hr class="fp-divider">', unsafe_allow_html=True)
    st.markdown("### Microsoft To Do")
    _oauth_block(
        provider="microsoft",
        status=microsoft_todo.status(),
        auth_url_fn=microsoft_todo.auth_url,
        exchange_fn=microsoft_todo.exchange_code,
        disconnect_fn=microsoft_todo.disconnect,
        setup_hint=(
            "Azure Portal → App registrations → New registration. Redirect URI typu *Web*: "
            "`http://localhost:8501`. V *API permissions* pridaj delegované "
            "`Tasks.ReadWrite`, `User.Read`, `offline_access`. V *Certificates & secrets* "
            "vytvor client secret. Údaje vlož do sekcie `[microsoft]` v "
            "`.streamlit/secrets.toml`."),
    )


def _oauth_block(provider: str, status: dict, auth_url_fn, exchange_fn,
                 disconnect_fn, setup_hint: str) -> None:
    if not status["configured"]:
        st.warning("**Mock režim** — integrácia je pripravená, ale chýbajú prihlasovacie "
                   "údaje. Úlohy sa neodosielajú, len sa logujú; export .ics funguje vždy.")
        with st.expander("Ako to zapnúť"):
            st.markdown(setup_hint)
        return

    if status["connected"]:
        cols = st.columns([6, 2])
        cols[0].success(f"Pripojené: {status.get('email') or 'účet'}")
        expires = parse_dt(status.get("expires_at"))
        if expires:
            cols[0].markdown(f'<div class="fp-muted">Token platí do '
                             f'{expires.astimezone().strftime("%d.%m.%Y %H:%M")}</div>',
                             unsafe_allow_html=True)
        if cols[1].button("Odpojiť", key=f"disc_{provider}", use_container_width=True):
            disconnect_fn()
            st.rerun()
        return

    st.info("Účet ešte nie je pripojený.")
    if st.button("1 · Získať prihlasovací odkaz", key=f"authurl_{provider}"):
        url, message = auth_url_fn()
        st.session_state[f"authurl_{provider}"] = url
        st.session_state[f"authmsg_{provider}"] = message

    url = st.session_state.get(f"authurl_{provider}")
    message = st.session_state.get(f"authmsg_{provider}")
    if url:
        st.markdown(f"[Otvoriť prihlásenie]({url})")
        st.caption(message or "")
        code = st.text_input("2 · Vlož sem kód (alebo celú návratovú URL)",
                             key=f"authcode_{provider}")
        if st.button("3 · Dokončiť pripojenie", key=f"authdone_{provider}",
                     type="primary", disabled=not code.strip()):
            ok, result = exchange_fn(code)
            (st.success if ok else st.error)(result)
            if ok:
                st.rerun()
    elif message:
        st.error(message)


# =============================================================================
#  AI
# =============================================================================

def _ai() -> None:
    st.markdown("### Napojené modely")
    st.markdown('<div class="fp-muted">Kľúče sa nastavujú v `.streamlit/secrets.toml` '
                '(sekcie `[ai.anthropic]`, `[ai.gemini]`, `[ai.openai]`) alebo cez '
                'premenné prostredia.</div>', unsafe_allow_html=True)
    st.write("")

    for item in orchestrator.provider_status():
        with st.container(border=True):
            cols = st.columns([5, 3, 2])
            cols[0].markdown(f"**{item['icon']} {item['label']}**  \n"
                             f"<span class='fp-muted'>model: {esc(item['model'])}</span>",
                             unsafe_allow_html=True)
            if item["configured"]:
                cols[1].markdown(f'<span class="fp-badge fp-time">'
                                 f'{icons.html(icons.CHECK)} Kľúč nastavený</span>',
                                 unsafe_allow_html=True)
                if cols[2].button("Otestovať", key=f"ai_test_{item['name']}",
                                  use_container_width=True):
                    with st.spinner("Testujem…"):
                        result = orchestrator.suggest_steps(
                            "Testovacia úloha: napísať krátky e-mail klientovi",
                            provider=item["name"])
                    if result.ok:
                        st.success(f"Model odpovedal za {result.latency_ms} ms.")
                    else:
                        st.error(result.error or "Model neodpovedal.")
            else:
                cols[1].markdown(f'<span class="fp-badge fp-q4">'
                                 f'{icons.html(icons.DEMO)} Bez kľúča</span>',
                                 unsafe_allow_html=True)

    if not any(p["configured"] for p in orchestrator.provider_status()):
        st.info("Zatiaľ nie je nastavený žiadny kľúč — analýzy bežia v demo režime "
                "(heuristiky, nie skutočný model).")


# =============================================================================
#  E-mail
# =============================================================================

def _email() -> None:
    cfg = config.smtp_config()
    st.markdown("### SMTP")
    if cfg:
        st.success(f"Nastavené: {cfg['host']}:{cfg['port']} ako {cfg['from_email']}")
        recipient = st.text_input("Testovací e-mail",
                                  value=(auth.current_user() or {}).get("email", ""))
        if st.button("Poslať testovací e-mail", type="primary", disabled=not recipient):
            ok, message = email_smtp.send_email(
                recipient, "FinPlay ToDo — test",
                "<p>Toto je testovací e-mail z FinPlay ToDo. Ak ti prišiel, "
                "zdieľanie úloh aj upozornenia fungujú.</p>")
            (st.success if ok else st.error)(message)
    else:
        st.warning("SMTP nie je nastavené. Zdieľanie e-mailom a e-mailové upozornenia "
                   "sú vypnuté — úlohu vieš stále skopírovať ako text.")
        with st.expander("Ako to nastaviť"):
            st.markdown(
                "Do `.streamlit/secrets.toml` doplň sekciu `[smtp]`:\n\n"
                "```toml\n[smtp]\nhost = \"smtp.gmail.com\"\nport = 587\n"
                "username = \"ty@firma.sk\"\npassword = \"app-password\"\n"
                "from_email = \"ty@firma.sk\"\nuse_tls = true\n```\n\n"
                "Pri Gmaile potrebuješ **App Password** (dvojfaktor musí byť zapnutý), "
                "nie bežné heslo k účtu.")

    st.markdown('<hr class="fp-divider">', unsafe_allow_html=True)
    st.markdown("### Čakajúce upozornenia")
    alerts = notifications.pending_alerts()
    st.metric("Splatné pripomienky", len(alerts["reminders"]))
    if st.button("Odoslať čakajúce e-mailové pripomienky",
                 disabled=not email_smtp.is_configured()):
        sent, problems = notifications.send_due_reminder_emails()
        st.success(f"Odoslaných: {sent}")
        for problem in problems:
            st.error(problem)
    st.caption("Automatické odosielanie zapneš cez `auto_send_reminders = true` "
               "v sekcii `[app]`.")


# =============================================================================
#  Profil
# =============================================================================

def _profile() -> None:
    user = auth.current_user() or {}
    profile = repo._be().table("profiles").eq("id", user.get("id")).first() or {}

    with st.form("profile_form"):
        cols = st.columns([1, 5])
        emoji = cols[0].text_input("Ikona", value=profile.get("avatar_emoji") or "🙂",
                                   max_chars=2)
        full_name = cols[1].text_input("Meno", value=profile.get("full_name")
                                       or user.get("full_name") or "")
        st.text_input("E-mail", value=user.get("email", ""), disabled=True)
        timezone = st.text_input("Časové pásmo", value=profile.get("timezone")
                                 or config.app_config()["default_timezone"])
        if st.form_submit_button("Uložiť", icon=icons.st("save"), type="primary"):
            repo._be().table("profiles").eq("id", user["id"]).update({
                "avatar_emoji": emoji, "full_name": full_name, "timezone": timezone})
            st.session_state["auth_user"]["full_name"] = full_name
            st.toast("Profil uložený.", icon=":material/save:")
            st.rerun()

    st.markdown('<hr class="fp-divider">', unsafe_allow_html=True)
    if st.button("Odhlásiť sa"):
        auth.sign_out()
        st.rerun()


# =============================================================================
#  Stav systému
# =============================================================================

def _health() -> None:
    backend = repo._be()
    rows = [
        ("Databáza", "Supabase" if backend.kind == "supabase"
         else "Lokálna SQLite (finplay_local.db)",
         backend.kind == "supabase"),
        ("Prihlásenie", "Supabase Auth" if config.has_supabase() else "Lokálne účty",
         config.has_supabase()),
        ("Google Calendar", "Pripojené" if google_calendar.is_connected()
         else ("Nakonfigurované, nepripojené" if google_calendar.is_configured()
               else "Mock režim"), google_calendar.is_connected()),
        ("Microsoft To Do", "Pripojené" if microsoft_todo.is_connected()
         else ("Nakonfigurované, nepripojené" if microsoft_todo.is_configured()
               else "Mock režim"), microsoft_todo.is_connected()),
        ("SMTP", "Nastavené" if email_smtp.is_configured() else "Nenastavené",
         email_smtp.is_configured()),
    ]
    for provider in orchestrator.provider_status():
        rows.append((f"AI · {provider['label']}",
                     provider["model"] if provider["configured"] else "bez kľúča",
                     provider["configured"]))

    for label, value, ok in rows:
        cols = st.columns([3, 5, 1])
        cols[0].markdown(f"**{label}**")
        cols[1].markdown(f'<span class="fp-muted">{esc(value)}</span>',
                         unsafe_allow_html=True)
        cols[2].markdown(icons.html(icons.CHECK if ok else icons.DEMO),
                         unsafe_allow_html=True)

    if backend.kind != "supabase":
        st.markdown('<hr class="fp-divider">', unsafe_allow_html=True)
        st.info("Beží lokálna databáza. Na prepnutie na Supabase spusti `sql/schema.sql` "
                "v SQL editore projektu a doplň `[supabase]` do `.streamlit/secrets.toml`. "
                "Dáta z lokálneho režimu sa neprenášajú automaticky.")
        st.caption(f"Súbor databázy: {db.LOCAL_DB_PATH}")
