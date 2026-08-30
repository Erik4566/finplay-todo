"""Microsoft To Do (cez Microsoft Graph).

Rovnaký princíp ako pri Google Calendari: bez sekcie ``[microsoft]`` beží vrstva
v mock režime a len loguje. Po doplnení client_id/client_secret sa zapne reálna
synchronizácia vrátane checklistu (kroky úlohy → podúlohy v To Do).
"""

from __future__ import annotations

from datetime import timedelta

import requests

from core import config, repo
from core.models import iso, now_utc, parse_dt

PROVIDER = "microsoft"
GRAPH = "https://graph.microsoft.com/v1.0"
SCOPES = ["Tasks.ReadWrite", "User.Read"]


def is_configured() -> bool:
    return bool(config.microsoft_config())


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
#  OAuth (MSAL)
# =============================================================================

def _msal_app():
    cfg = config.microsoft_config()
    import msal
    authority = f"https://login.microsoftonline.com/{cfg['tenant']}"
    if cfg.get("client_secret"):
        return msal.ConfidentialClientApplication(
            cfg["client_id"], authority=authority, client_credential=cfg["client_secret"])
    return msal.PublicClientApplication(cfg["client_id"], authority=authority)


def auth_url() -> tuple[str | None, str]:
    if not is_configured():
        return None, "Microsoft nie je nakonfigurovaný (sekcia [microsoft] v secrets.toml)."
    try:
        cfg = config.microsoft_config()
        url = _msal_app().get_authorization_request_url(
            SCOPES, redirect_uri=cfg["redirect_uri"], prompt="select_account")
        return url, "Otvor odkaz, prihlás sa a skopíruj sem parameter ?code= z adresy."
    except ImportError:
        return None, "Chýba balík msal (pip install msal)."
    except Exception as exc:
        return None, f"Nepodarilo sa vytvoriť prihlasovací odkaz: {exc}"


def exchange_code(code: str) -> tuple[bool, str]:
    if not is_configured():
        return False, "Microsoft nie je nakonfigurovaný."
    code = (code or "").strip()
    if "code=" in code:
        from urllib.parse import parse_qs, urlparse
        code = (parse_qs(urlparse(code).query).get("code") or [""])[0]
    if not code:
        return False, "Chýba kód."

    cfg = config.microsoft_config()
    try:
        result = _msal_app().acquire_token_by_authorization_code(
            code, scopes=SCOPES, redirect_uri=cfg["redirect_uri"])
    except Exception as exc:
        return False, f"Výmena kódu zlyhala: {exc}"

    if "access_token" not in result:
        return False, f"Prihlásenie zlyhalo: {result.get('error_description', result)}"

    email = (result.get("id_token_claims") or {}).get("preferred_username")
    repo.save_integration_account(PROVIDER, {
        "account_email": email,
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token"),
        "expires_at": iso(now_utc() + timedelta(seconds=int(result.get("expires_in", 3600)))),
        "scope": " ".join(SCOPES),
        "extra": None,
    })
    return True, f"Microsoft To Do pripojené{f' ({email})' if email else ''}."


def disconnect() -> None:
    repo.delete_integration_account(PROVIDER)


def _access_token() -> str | None:
    account = repo.get_integration_account(PROVIDER)
    if not account:
        return None
    expires = parse_dt(account.get("expires_at"))
    if account.get("access_token") and expires and expires > now_utc() + timedelta(minutes=2):
        return account["access_token"]
    if not account.get("refresh_token"):
        return account.get("access_token")
    try:
        result = _msal_app().acquire_token_by_refresh_token(account["refresh_token"], SCOPES)
    except Exception:
        return account.get("access_token")
    if "access_token" not in result:
        return account.get("access_token")
    repo.save_integration_account(PROVIDER, {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token") or account["refresh_token"],
        "expires_at": iso(now_utc() + timedelta(seconds=int(result.get("expires_in", 3600)))),
    })
    return result["access_token"]


def _headers() -> dict:
    return {"Authorization": f"Bearer {_access_token()}", "Content-Type": "application/json"}


# =============================================================================
#  Zoznamy a úlohy
# =============================================================================

def _ensure_list() -> str | None:
    """Nájde alebo vytvorí zoznam podľa názvu z konfigurácie."""
    name = config.microsoft_config()["todo_list_name"]
    account = repo.get_integration_account(PROVIDER) or {}
    cached = (account.get("extra") or {}).get("list_id") if isinstance(account.get("extra"), dict) else None
    if cached:
        return cached

    response = requests.get(f"{GRAPH}/me/todo/lists", headers=_headers(), timeout=30)
    response.raise_for_status()
    for item in response.json().get("value", []):
        if item.get("displayName") == name:
            repo.save_integration_account(PROVIDER, {"extra": {"list_id": item["id"]}})
            return item["id"]

    created = requests.post(f"{GRAPH}/me/todo/lists", headers=_headers(),
                            json={"displayName": name}, timeout=30)
    created.raise_for_status()
    list_id = created.json()["id"]
    repo.save_integration_account(PROVIDER, {"extra": {"list_id": list_id}})
    return list_id


def _importance(task: dict) -> str:
    score = (task.get("importance") or 3) + (task.get("urgency") or 3)
    if score >= 8:
        return "high"
    if score <= 4:
        return "low"
    return "normal"


def _graph_datetime(dt) -> dict | None:
    dt = parse_dt(dt)
    if not dt:
        return None
    return {"dateTime": dt.strftime("%Y-%m-%dT%H:%M:%S.0000000"), "timeZone": "UTC"}


def push_task(task: dict, steps: list[dict] | None = None) -> tuple[bool, str]:
    steps = steps or []

    if not is_configured():
        repo.log_sync(task["id"], PROVIDER, "mock",
                      "Mock režim — chýba sekcia [microsoft] v secrets.toml.")
        return False, "Microsoft To Do beží v mock režime. Úloha nebola odoslaná."
    if not is_connected():
        repo.log_sync(task["id"], PROVIDER, "error", "Účet nie je pripojený.")
        return False, "Microsoft účet nie je pripojený (Nastavenia → Integrácie)."

    body = {
        "title": task.get("title", "Úloha"),
        "importance": _importance(task),
        "status": "completed" if task.get("status") == "done" else "notStarted",
        "body": {"contentType": "text",
                 "content": (task.get("description") or "") + "\n\n— FinPlay ToDo"},
    }
    due = _graph_datetime(task.get("due_at"))
    if due:
        body["dueDateTime"] = due
        body["reminderDateTime"] = due
        body["isReminderOn"] = True

    try:
        list_id = _ensure_list()
        if task.get("ms_todo_task_id"):
            response = requests.patch(
                f"{GRAPH}/me/todo/lists/{list_id}/tasks/{task['ms_todo_task_id']}",
                headers=_headers(), json=body, timeout=30)
        else:
            response = requests.post(f"{GRAPH}/me/todo/lists/{list_id}/tasks",
                                     headers=_headers(), json=body, timeout=30)
        response.raise_for_status()
        remote = response.json()
        remote_id = remote["id"]
        if not task.get("ms_todo_task_id"):
            repo.update_task(task["id"], {"ms_todo_task_id": remote_id})
            # kroky ako checklist položky - len pri prvom vytvorení
            for step in steps:
                requests.post(
                    f"{GRAPH}/me/todo/lists/{list_id}/tasks/{remote_id}/checklistItems",
                    headers=_headers(),
                    json={"displayName": step["title"],
                          "isChecked": bool(step.get("is_done"))}, timeout=30)
    except Exception as exc:
        repo.log_sync(task["id"], PROVIDER, "error", str(exc))
        return False, f"Synchronizácia zlyhala: {exc}"

    repo.log_sync(task["id"], PROVIDER, "ok", "Úloha zosynchronizovaná",
                  external_id=remote_id)
    return True, "Úloha je v Microsoft To Do."


def delete_task(task: dict) -> tuple[bool, str]:
    if not task.get("ms_todo_task_id") or not is_connected():
        return False, "Nie je čo mazať."
    try:
        list_id = _ensure_list()
        requests.delete(f"{GRAPH}/me/todo/lists/{list_id}/tasks/{task['ms_todo_task_id']}",
                        headers=_headers(), timeout=30).raise_for_status()
        repo.update_task(task["id"], {"ms_todo_task_id": None})
    except Exception as exc:
        return False, f"Zmazanie zlyhalo: {exc}"
    return True, "Úloha zmazaná z Microsoft To Do."
