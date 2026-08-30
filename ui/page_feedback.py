"""Spätná väzba k aplikácii - zapíš trenie hneď, ako naň narazíš."""

from __future__ import annotations

import streamlit as st

from core import config, feedback
from core.models import parse_dt
from ui import icons, theme
from ui.components import esc

PAGE_LABELS = {
    "today": "Dnes", "tasks": "Úlohy", "new_task": "Nová úloha",
    "search": "Hľadať", "more": "Viac", "projects": "Projekty",
    "project_detail": "Detail projektu", "archive": "Archív",
    "settings": "Nastavenia", "task": "Detail úlohy", "feedback": "Spätná väzba",
}


def render() -> None:
    open_count = feedback.counts()["new"]
    theme.topbar("Spätná väzba",
                 f"{open_count} otvorených" if open_count else "všetko vybavené")

    st.markdown('<div class="fp-muted">Keď ťa v appke niečo zdrží alebo nahnevá, '
                'zapíš to hneď — o dva dni si už nespomenieš, čo to bolo. '
                'Screenshot povie viac než odsek textu.</div>',
                unsafe_allow_html=True)

    _form()
    theme.divider()
    _history()


# =============================================================================
#  Nový záznam
# =============================================================================

def _form() -> None:
    came_from = st.session_state.get("feedback_from") or "today"

    with st.form("feedback_form", clear_on_submit=True):
        kinds = list(feedback.KINDS.keys())
        kind = st.radio("O čo ide", kinds, horizontal=True,
                        format_func=lambda k: feedback.KINDS[k])

        message = st.text_area(
            "Popis", height=130,
            placeholder="Čo si robil, čo si čakal a čo sa stalo namiesto toho?")

        pages = list(PAGE_LABELS.keys())
        page = st.selectbox(
            "Kde to bolo", pages,
            index=pages.index(came_from) if came_from in pages else 0,
            format_func=lambda p: PAGE_LABELS.get(p, p))

        uploaded = st.file_uploader(
            f"Obrázky (max {feedback.MAX_IMAGES}) — screenshot z telefónu je ideálny",
            type=[s.lstrip(".") for s in sorted(feedback.ALLOWED_SUFFIXES)],
            accept_multiple_files=True)

        blocking = st.checkbox("Blokuje ma to — nedá sa pokračovať")

        submitted = st.form_submit_button(
            "Odoslať", icon=icons.st(icons.SEND), type="primary",
            use_container_width=True)

    if not submitted:
        return
    if not (message or "").strip():
        st.error("Napíš aspoň krátky popis.")
        return

    saved, rejected = [], []
    for item in (uploaded or [])[:feedback.MAX_IMAGES]:
        prepared = feedback.prepare_image(item)
        if prepared:
            saved.append(prepared)
        else:
            rejected.append(item.name)

    feedback.create(
        message=message, kind=kind, page=page, blocking=blocking, images=saved,
        extra_context={
            "tema": "tmavá" if theme.is_dark() else "svetlá",
            "schema": theme.current_scheme(),
            "velkost": theme.scale_name(),
            "krajina": st.session_state.get("ui_country", "SK"),
        })

    if rejected:
        st.warning("Niektoré prílohy sa nepodarilo uložiť (formát alebo veľkosť): "
                   + ", ".join(rejected))
    st.success("Zapísané. Vďaka — presne toto potrebujem, aby som to vedel opraviť.")
    st.rerun()


# =============================================================================
#  História
# =============================================================================

def _history() -> None:
    items = feedback.list_all()
    if not items:
        st.markdown('<div class="fp-muted" style="text-align:center;padding:1.5rem;">'
                    'Zatiaľ si nič nezapísal.</div>', unsafe_allow_html=True)
        return

    theme.section(f"Zapísané ({len(items)})")

    for item in items:
        stamp = parse_dt(item.get("created_at"))
        when = stamp.astimezone().strftime("%d.%m. %H:%M") if stamp else ""
        kind = item.get("kind", "friction")
        done = item.get("status") == "done"

        with st.container(key=f"row-fb-{item['id']}"):
            head, actions = st.columns([0.78, 0.22])
            with head:
                badges = (f'<span class="fp-badge fp-q4">'
                          f'{icons.html(feedback.KIND_ICONS.get(kind, "flag"))} '
                          f'{esc(feedback.KINDS.get(kind, kind))}</span>')
                if item.get("blocking"):
                    badges += ('<span class="fp-badge fp-q1">'
                               f'{icons.html(icons.RISK)} blokuje</span>')
                if done:
                    badges += ('<span class="fp-badge fp-time">'
                               f'{icons.html(icons.CHECK)} vybavené</span>')
                st.markdown(
                    f'<div style="opacity:{".55" if done else "1"}">'
                    f'{badges}<div style="margin-top:.4rem;">{esc(item.get("message"))}</div>'
                    f'<div class="fp-meta" style="margin-left:0;">{when}'
                    + (f' · {PAGE_LABELS.get(item.get("page"), item.get("page"))}'
                       if item.get("page") else "")
                    + '</div></div>', unsafe_allow_html=True)

            with actions:
                if not done:
                    if st.button("Vybavené", icon=icons.st(icons.CHECK),
                                 key=f"fb_done_{item['id']}", use_container_width=True):
                        feedback.set_status(item["id"], "done")
                        st.rerun()
                else:
                    if st.button("Znova otvoriť", key=f"fb_open_{item['id']}",
                                 use_container_width=True):
                        feedback.set_status(item["id"], "new")
                        st.rerun()
                if st.button("Zmazať", icon=icons.st(icons.DELETE),
                             key=f"fb_del_{item['id']}", use_container_width=True):
                    feedback.delete(item["id"])
                    st.rerun()

            images = feedback.images_of(item)
            if images:
                columns = st.columns(min(len(images), 3))
                for index, image in enumerate(images):
                    data = feedback.image_bytes(image)
                    if data:
                        columns[index % len(columns)].image(
                            data, use_container_width=True)

    theme.divider()
    _export(items)


def _export(items: list[dict]) -> None:
    theme.section("Podklad pre vývoj")
    st.markdown('<div class="fp-muted">Celý zoznam ako text — dá sa vložiť do chatu '
                'a poslať aj s odkazmi na prílohy.</div>', unsafe_allow_html=True)

    only_open = st.checkbox("Len otvorené", value=True, key="fb_only_open")
    text = feedback.as_markdown(only_open=only_open)

    with st.expander("Zobraziť text"):
        st.code(text, language="markdown")

    left, right = st.columns(2)
    left.download_button(
        "Prehľad (.md)", data=text, file_name="finplay-spatna-vazba.md",
        mime="text/markdown", icon=icons.st(icons.DOWNLOAD),
        use_container_width=True, key="fb_download_md")
    right.download_button(
        "Aj s prílohami (.zip)", data=feedback.as_zip(only_open),
        file_name="finplay-spatna-vazba.zip", mime="application/zip",
        icon=icons.st(icons.DOWNLOAD), use_container_width=True, key="fb_download_zip")
    st.caption(f"Obrázky sú uložené v databáze, takže fungujú aj z telefónu "
               f"a po nasadení. Verzia appky {config.APP_VERSION}.")
