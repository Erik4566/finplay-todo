"""Google Calendar.

Bez sekcie ``[google]`` v secrets.toml beží vrstva v **mock režime**: úlohy sa
neodosielajú do Googlu, ale zaznamenajú sa do ``sync_log`` a dajú sa stiahnuť
ako .ics. Po doplnení client_id/client_secret sa zapne skutočná OAuth2
synchronizácia bez zmeny kódu.
"""

from __future__ import annotations

from datetime import timedelta

from core import config, repo
from core.models import iso, now_utc, parse_dt

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
TOKEN_URI = "https://oauth2.googleapis.com/token"
PROVIDER = "google"


def is_configured() -> bool:
    return bool(config.google_config())


def is_connected() -> bool:
    account = repo.get_integration_account(PROVIDER)
    return bool(account and account.get("refresh_token"))


def status() -> dict:
    account = repo.get_integration_account(PROVIDER)
    return {
        "configured": is_configured(),
        "connected": bool(account and account.get("refresh_token")),
        "email": (account or {}).get("account_email"),
        "expires_at": (account or {}).get("expires_at"),
        "mode": "live" if is_configured() else "mock",
    }


# =============================================================================
#  OAuth
# =============================================================================

def _flow():
    cfg = config.google_config()
    from google_auth_oauthlib.flow import Flow

    client_config = {
        "web": {
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": TOKEN_URI,
            "redirect_uris": [cfg["redirect_uri"]],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = cfg["redirect_uri"]
    return flow


def auth_url() -> tuple[str | None, str]:
    if not is_configured():
        return None, "Google nie je nakonfigurovaný (sekcia [google] v secrets.toml)."
    try:
        flow = _flow()
        url, _state = flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent")
        return url, "Otvor odkaz, povoľ prístup a skopíruj sem parameter ?code= z adresy."
    except ImportError:
        return None, "Chýba balík google-auth-oauthlib (pip install google-auth-oauthlib)."
    except Exception as exc:
        return None, f"Nepodarilo sa vytvoriť prihlasovací odkaz: {exc}"


def exchange_code(code: str) -> tuple[bool, str]:
    if not is_configured():
        return False, "Google nie je nakonfigurovaný."
    code = (code or "").strip()
    if not code:
        return False, "Chýba kód."
    # používateľ môže vložiť celú návratovú URL
    if "code=" in code:
        from urllib.parse import parse_qs, urlparse
        query = parse_qs(urlparse(code).query)
        code = (query.get("code") or [""])[0]
    try:
        flow = _flow()
        flow.fetch_token(code=code)
        creds = flow.credentials
    except Exception as exc:
        return False, f"Výmena kódu zlyhala: {exc}"

    email = None
    try:
        from googleapiclient.discovery import build
        service = build("oauth2", "v2", credentials=creds, cache_discovery=False)
        email = service.userinfo().get().execute().get("email")
    except Exception:
        pass

    repo.save_integration_account(PROVIDER, {
        "account_email": email,
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expires_at": iso(creds.expiry) if creds.expiry else None,
        "scope": " ".join(SCOPES),
        "extra": None,
    })
    return True, f"Google Calendar pripojený{f' ({email})' if email else ''}."


def disconnect() -> None:
    repo.delete_integration_account(PROVIDER)


def _credentials():
    cfg = config.google_config()
    account = repo.get_integration_account(PROVIDER)
    if not cfg or not account or not account.get("refresh_token"):
        return None
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    creds = Credentials(
        token=account.get("access_token"),
        refresh_token=account.get("refresh_token"),
        token_uri=TOKEN_URI,
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        scopes=SCOPES,
    )
    expires = parse_dt(account.get("expires_at"))
    if not creds.token or (expires and expires <= now_utc() + timedelta(minutes=2)):
        creds.refresh(Request())
        repo.save_integration_account(PROVIDER, {
            "access_token": creds.token,
            "expires_at": iso(creds.expiry) if creds.expiry else None,
        })
    return creds


# =============================================================================
#  Synchronizácia úlohy
# =============================================================================

def _event_body(task: dict, steps: list[dict]) -> dict:
    start = parse_dt(task.get("due_at")) or now_utc() + timedelta(hours=1)
    minutes = max(15, int(task.get("estimated_minutes") or 30))
    end = start + timedelta(minutes=minutes)

    lines = []
    if task.get("description"):
        lines.append(task["description"])
    if steps:
        lines.append("")
        lines.append("Kroky:")
        for index, step in enumerate(steps, 1):
            mark = "✓" if step.get("is_done") else "·"
            lines.append(f"{mark} {index}. {step['title']} ({step.get('estimated_minutes', 0)} min)")
    lines.append("")
    lines.append(f"Dôležitosť {task.get('importance', 3)}/5 · "
                 f"urgentnosť {task.get('urgency', 3)}/5")
    lines.append("— FinPlay ToDo")

    body = {
        "summary": task.get("title", "Úloha"),
        "description": "\n".join(lines),
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
        "reminders": {"useDefault": False,
                      "overrides": [{"method": "popup", "minutes": 30}]},
    }
    if task.get("recurrence_rule"):
        body["recurrence"] = [f"RRULE:{task['recurrence_rule']}"]
    return body


def push_task(task: dict, steps: list[dict] | None = None) -> tuple[bool, str]:
    """Vytvorí alebo aktualizuje udalosť v Google Calendari."""
    steps = steps or []

    if not is_configured():
        repo.log_sync(task["id"], PROVIDER, "mock",
                      "Mock režim — chýba sekcia [google] v secrets.toml.")
        return False, ("Google Calendar beží v mock režime. Úloha nebola odoslaná, "
                       "ale môžeš si ju stiahnuť ako .ics.")
    if not is_connected():
        repo.log_sync(task["id"], PROVIDER, "error", "Účet nie je pripojený.")
        return False, "Google účet nie je pripojený (Nastavenia → Integrácie)."

    try:
        from googleapiclient.discovery import build
        creds = _credentials()
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        calendar_id = config.google_config()["calendar_id"]
        body = _event_body(task, steps)

        if task.get("google_event_id"):
            event = service.events().update(
                calendarId=calendar_id, eventId=task["google_event_id"], body=body).execute()
        else:
            event = service.events().insert(calendarId=calendar_id, body=body).execute()
            repo.update_task(task["id"], {"google_event_id": event["id"]})
    except Exception as exc:
        repo.log_sync(task["id"], PROVIDER, "error", str(exc))
        return False, f"Synchronizácia zlyhala: {exc}"

    repo.log_sync(task["id"], PROVIDER, "ok", "Udalosť zosynchronizovaná",
                  external_id=event.get("id"))
    return True, f"Úloha je v Google Calendari ({event.get('htmlLink', 'ok')})."


def delete_event(task: dict) -> tuple[bool, str]:
    if not task.get("google_event_id") or not is_connected():
        return False, "Nie je čo mazať."
    try:
        from googleapiclient.discovery import build
        service = build("calendar", "v3", credentials=_credentials(), cache_discovery=False)
        service.events().delete(calendarId=config.google_config()["calendar_id"],
                                eventId=task["google_event_id"]).execute()
        repo.update_task(task["id"], {"google_event_id": None})
    except Exception as exc:
        return False, f"Zmazanie zlyhalo: {exc}"
    return True, "Udalosť zmazaná."


def todays_events(day=None) -> list[dict]:
    """Udalosti z Google Calendara pre daný deň, zoradené podľa času.

    Vracia zjednodušené záznamy: ``{title, start, end, all_day, link, location}``.
    Bez pripojeného účtu vráti prázdny zoznam - volajúci si stav zistí cez
    ``status()`` a zobrazí návod.
    """
    from datetime import datetime, time as dtime

    if not is_connected():
        return []

    day = day or now_utc().astimezone().date()
    start = datetime.combine(day, dtime.min).astimezone()
    end = datetime.combine(day, dtime.max).astimezone()

    try:
        from googleapiclient.discovery import build
        service = build("calendar", "v3", credentials=_credentials(),
                        cache_discovery=False)
        result = service.events().list(
            calendarId=config.google_config()["calendar_id"],
            timeMin=start.isoformat(), timeMax=end.isoformat(),
            singleEvents=True, orderBy="startTime", maxResults=50).execute()
    except Exception as exc:
        repo.log_sync(None, PROVIDER, "error", f"Načítanie dňa zlyhalo: {exc}",
                      direction="pull")
        return []

    events = []
    for item in result.get("items", []):
        if item.get("status") == "cancelled":
            continue
        start_raw = item.get("start", {})
        end_raw = item.get("end", {})
        all_day = "date" in start_raw
        events.append({
            "title": item.get("summary") or "(bez názvu)",
            "start": parse_dt(start_raw.get("dateTime") or start_raw.get("date")),
            "end": parse_dt(end_raw.get("dateTime") or end_raw.get("date")),
            "all_day": all_day,
            "link": item.get("htmlLink"),
            "location": item.get("location"),
        })
    events.sort(key=lambda e: (not e["all_day"], e["start"] or now_utc()))
    return events


def upcoming_events(limit: int = 10) -> list[dict]:
    if not is_connected():
        return []
    try:
        from googleapiclient.discovery import build
        service = build("calendar", "v3", credentials=_credentials(), cache_discovery=False)
        result = service.events().list(
            calendarId=config.google_config()["calendar_id"],
            timeMin=now_utc().isoformat(), maxResults=limit,
            singleEvents=True, orderBy="startTime").execute()
        return result.get("items", [])
    except Exception:
        return []
