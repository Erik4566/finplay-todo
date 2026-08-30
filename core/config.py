"""Načítanie konfigurácie zo st.secrets s fallbackom na premenné prostredia.

Aplikácia je navrhnutá tak, aby bežala aj úplne bez konfigurácie:
chýbajúca sekcia znamená, že daná funkcia beží v lokálnom / mock režime.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

try:  # streamlit nemusí byť dostupný pri importe z testov
    import streamlit as st
except Exception:  # pragma: no cover
    st = None  # type: ignore


def _secrets() -> dict:
    """Bezpečné načítanie st.secrets - bez secrets.toml Streamlit vyhadzuje výnimku."""
    if st is None:
        return {}
    try:
        return dict(st.secrets)
    except Exception:
        return {}


def section(name: str) -> dict:
    """Vráti sekciu zo secrets (podporuje aj bodkovú notáciu: 'ai.gemini').

    Pozor na typy: Streamlit vracia vnorené sekcie ako ``AttrDict``, ktorý
    NIE JE potomkom ``dict`` — je to len ``Mapping``. Kontrola cez
    ``isinstance(data, dict)`` preto ticho zlyhá a appka sa tvári, že
    konfigurácia neexistuje. Testuje sa proti ``Mapping``.
    """
    data: Any = _secrets()
    for part in name.split("."):
        if not isinstance(data, Mapping) or part not in data:
            return {}
        data = data[part]
    return dict(data) if isinstance(data, Mapping) else {}


def get(path: str, env: str | None = None, default: Any = None) -> Any:
    """Hodnota zo secrets ('smtp.host') s fallbackom na premennú prostredia."""
    *parts, key = path.split(".")
    data = section(".".join(parts)) if parts else _secrets()
    value = data.get(key) if isinstance(data, Mapping) else None
    if value in (None, ""):
        value = os.environ.get(env) if env else None
    return default if value in (None, "") else value


# --- Odvodené vlastnosti prostredia --------------------------------------------

def supabase_config() -> dict:
    cfg = section("supabase")
    url = cfg.get("url") or os.environ.get("SUPABASE_URL")
    key = cfg.get("anon_key") or os.environ.get("SUPABASE_ANON_KEY")
    return {"url": url, "anon_key": key} if url and key else {}


def has_supabase() -> bool:
    return bool(supabase_config())


def ai_config(provider: str) -> dict:
    """provider: anthropic | gemini | openai"""
    cfg = section(f"ai.{provider}")
    env_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
    }
    api_key = cfg.get("api_key") or os.environ.get(env_map.get(provider, ""), "")
    defaults = {
        "anthropic": "claude-opus-5",
        "gemini": "gemini-2.5-pro",
        "openai": "gpt-4o",
    }
    return {
        "api_key": api_key or None,
        "model": cfg.get("model") or defaults.get(provider),
    }


def smtp_config() -> dict:
    cfg = section("smtp")
    host = cfg.get("host") or os.environ.get("SMTP_HOST")
    if not host:
        return {}
    return {
        "host": host,
        "port": int(cfg.get("port") or os.environ.get("SMTP_PORT") or 587),
        "username": cfg.get("username") or os.environ.get("SMTP_USER"),
        "password": cfg.get("password") or os.environ.get("SMTP_PASSWORD"),
        "from_email": cfg.get("from_email") or cfg.get("username"),
        "from_name": cfg.get("from_name") or "FinPlay ToDo",
        "use_tls": bool(cfg.get("use_tls", True)),
        "use_ssl": bool(cfg.get("use_ssl", False)),
    }


def google_config() -> dict:
    cfg = section("google")
    if not cfg.get("client_id") or not cfg.get("client_secret"):
        return {}
    return {
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "redirect_uri": cfg.get("redirect_uri", "http://localhost:8501"),
        "calendar_id": cfg.get("calendar_id", "primary"),
    }


def microsoft_config() -> dict:
    cfg = section("microsoft")
    if not cfg.get("client_id"):
        return {}
    return {
        "client_id": cfg["client_id"],
        "client_secret": cfg.get("client_secret"),
        "tenant": cfg.get("tenant", "common"),
        "redirect_uri": cfg.get("redirect_uri", "http://localhost:8501"),
        "todo_list_name": cfg.get("todo_list_name", "FinPlay ToDo"),
    }


def app_config() -> dict:
    cfg = section("app")
    return {
        "min_steps": int(cfg.get("min_steps", 3)),
        "auto_send_reminders": bool(cfg.get("auto_send_reminders", False)),
        "default_timezone": cfg.get("default_timezone", "Europe/Bratislava"),
    }


APP_VERSION = "0.9"
MIN_STEPS = app_config()["min_steps"]
