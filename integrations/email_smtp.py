"""Odosielanie e-mailov cez SMTP - zdieľanie úloh a upozornenia."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from core import config
from core.models import QUADRANTS, fmt_due, fmt_minutes, quadrant


def is_configured() -> bool:
    return bool(config.smtp_config())


def send_email(to: str | list[str], subject: str, html: str,
               text: str | None = None) -> tuple[bool, str]:
    cfg = config.smtp_config()
    if not cfg:
        return False, "SMTP nie je nakonfigurované (sekcia [smtp] v secrets.toml)."

    recipients = [to] if isinstance(to, str) else list(to)
    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        return False, "Chýba príjemca."

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((cfg["from_name"], cfg["from_email"]))
    message["To"] = ", ".join(recipients)
    message.set_content(text or _strip_html(html))
    message.add_alternative(html, subtype="html")

    try:
        if cfg["use_ssl"]:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=context, timeout=30) as smtp:
                if cfg["username"]:
                    smtp.login(cfg["username"], cfg["password"])
                smtp.send_message(message)
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as smtp:
                smtp.ehlo()
                if cfg["use_tls"]:
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                if cfg["username"]:
                    smtp.login(cfg["username"], cfg["password"])
                smtp.send_message(message)
    except Exception as exc:
        return False, f"Odoslanie zlyhalo: {exc}"
    return True, f"Odoslané ({len(recipients)} príjemca/ov)."


def _strip_html(html: str) -> str:
    import re
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"</(p|div|li|h[1-6])>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


# =============================================================================
#  Šablóny
# =============================================================================

_STYLE = (
    "font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"
    "color:#1F2430;line-height:1.55;max-width:640px;"
)


def render_task_email(task: dict, steps: list[dict], risks: list[dict],
                      sender_name: str, note: str = "",
                      project: dict | None = None) -> tuple[str, str]:
    """Vráti (predmet, html)."""
    quad = QUADRANTS[quadrant(task.get("importance", 3), task.get("urgency", 3))]
    due_text, due_state = fmt_due(task.get("due_at"))
    due_color = {"overdue": "#DC2626", "today": "#D97706"}.get(due_state, "#4B5563")

    step_rows = "".join(
        f'<li style="margin:4px 0;{"opacity:.55;text-decoration:line-through;" if s.get("is_done") else ""}">'
        f'{_esc(s["title"])} '
        f'<span style="color:#6B7280;font-size:13px;">· {fmt_minutes(s.get("estimated_minutes"))}</span></li>'
        for s in steps
    ) or '<li style="color:#6B7280;">(zatiaľ bez krokov)</li>'

    risk_rows = "".join(
        f'<li style="margin:4px 0;"><b>{_esc(r.get("title",""))}</b> '
        f'<span style="color:#6B7280;font-size:13px;">· závažnosť {r.get("severity")}/5, '
        f'pravdepodobnosť {r.get("likelihood")}/5</span><br>'
        f'<span style="color:#4B5563;font-size:14px;">{_esc(r.get("description") or "")}</span>'
        + (f'<br><span style="color:#047857;font-size:14px;">Zmiernenie: '
           f'{_esc(r.get("mitigation"))}</span>' if r.get("mitigation") else "")
        + "</li>"
        for r in risks
    )
    risk_block = (f'<h3 style="margin:22px 0 6px;font-size:15px;">Riziká a výzvy</h3>'
                  f'<ul style="padding-left:18px;margin:0;">{risk_rows}</ul>') if risk_rows else ""

    note_block = (f'<div style="background:#F1EFEA;border-radius:10px;padding:12px 14px;'
                  f'margin:16px 0;"><b>Odkaz od {_esc(sender_name)}:</b><br>'
                  f'{_esc(note)}</div>') if note.strip() else ""

    project_line = (f'<div style="color:#6B7280;font-size:14px;">'
                    f'{_esc(project.get("emoji",""))} {_esc(project.get("name",""))}</div>'
                    if project else "")

    next_step = next((s for s in steps if not s.get("is_done")), None)
    next_block = (f'<div style="background:#EEF2FF;border-left:4px solid #4F46E5;'
                  f'padding:12px 14px;border-radius:8px;margin:16px 0;">'
                  f'<div style="font-size:12px;letter-spacing:.06em;color:#4F46E5;'
                  f'text-transform:uppercase;">Najbližší krok</div>'
                  f'<div style="font-size:16px;font-weight:600;margin-top:4px;">'
                  f'{_esc(next_step["title"])}</div>'
                  f'<div style="color:#6B7280;font-size:13px;">'
                  f'{fmt_minutes(next_step.get("estimated_minutes"))}</div></div>'
                  ) if next_step else ""

    subject = f"[{quad['emoji']} {quad['label']}] {task.get('title','Úloha')}"
    html = f"""<div style="{_STYLE}">
  <div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#6B7280;">
    FinPlay ToDo · zdieľaná úloha
  </div>
  <h2 style="margin:6px 0 2px;font-size:22px;">{_esc(task.get('title',''))}</h2>
  {project_line}
  <div style="margin:12px 0;">
    <span style="background:{quad['color']}1A;color:{quad['color']};border-radius:999px;
                 padding:4px 10px;font-size:13px;font-weight:600;">
      {quad['emoji']} {quad['label']}
    </span>
    <span style="color:#4B5563;font-size:13px;margin-left:8px;">
      dôležitosť {task.get('importance',3)}/5 · urgentnosť {task.get('urgency',3)}/5
    </span>
  </div>
  <div style="color:{due_color};font-size:14px;">Termín: {due_text}</div>
  <div style="color:#4B5563;font-size:14px;">Odhad: {fmt_minutes(task.get('estimated_minutes'))}</div>
  {note_block}
  {(f'<p style="margin:16px 0;">{_esc(task.get("description"))}</p>'
    if task.get("description") else "")}
  {next_block}
  <h3 style="margin:22px 0 6px;font-size:15px;">Rozklad na kroky</h3>
  <ol style="padding-left:18px;margin:0;">{step_rows}</ol>
  {risk_block}
  <hr style="border:none;border-top:1px solid #E5E7EB;margin:24px 0 10px;">
  <div style="color:#9CA3AF;font-size:12px;">
    Odoslané z FinPlay ToDo používateľom {_esc(sender_name)}.
  </div>
</div>"""
    return subject, html


def render_reminder_email(task: dict, reminder: dict) -> tuple[str, str]:
    due_text, _ = fmt_due(task.get("due_at"))
    subject = f"⏰ Pripomienka: {task.get('title','Úloha')}"
    html = f"""<div style="{_STYLE}">
  <h2 style="margin:0 0 8px;font-size:20px;">⏰ {_esc(task.get('title',''))}</h2>
  <div style="color:#4B5563;">Termín: {due_text}</div>
  {(f'<p>{_esc(reminder.get("message"))}</p>' if reminder.get("message") else "")}
  <p style="color:#6B7280;font-size:13px;">FinPlay ToDo</p>
</div>"""
    return subject, html


def _esc(value) -> str:
    text = "" if value is None else str(value)
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))
