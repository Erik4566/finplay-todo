"""Prihlásenie.

Primárne Supabase Auth (e-mail + heslo). Bez konfigurácie Supabase sa použije
lokálny účet uložený v SQLite - aby sa appka dala vyskúšať okamžite.
"""

from __future__ import annotations

import hashlib
import os

import streamlit as st

from core import config, db
from core.models import now_utc, iso

_PBKDF_ROUNDS = 200_000


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF_ROUNDS)
    return f"{salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
    except ValueError:
        return False
    expected = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex),
                                   _PBKDF_ROUNDS)
    return expected.hex() == digest_hex


# =============================================================================
#  Stav relácie
# =============================================================================

def current_user() -> dict | None:
    return st.session_state.get("auth_user")


def access_token() -> str | None:
    return st.session_state.get("auth_token")


def backend() -> db.Backend:
    return db.get_backend(access_token())


def is_local_mode() -> bool:
    return not config.has_supabase()


def sign_out() -> None:
    token = access_token()
    if token and config.has_supabase():
        try:
            client = db.get_supabase_client(token)
            if client:
                client.auth.sign_out()
        except Exception:
            pass
    for key in ("auth_user", "auth_token", "running_timer", "nav_task_id"):
        st.session_state.pop(key, None)
    db.reset_backend_cache()


# =============================================================================
#  Registrácia / prihlásenie
# =============================================================================

def sign_up(email: str, password: str, full_name: str) -> tuple[bool, str]:
    email = email.strip().lower()
    if len(password) < 8:
        return False, "Heslo musí mať aspoň 8 znakov."

    if config.has_supabase():
        client = db.get_supabase_client()
        try:
            res = client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {"data": {"full_name": full_name}},
            })
        except Exception as exc:
            return False, f"Registrácia zlyhala: {exc}"
        if res.session is None:
            return True, ("Účet vytvorený. Skontroluj e-mail a potvrď registráciu, "
                          "potom sa prihlás.")
        _store_supabase_session(res)
        return True, "Účet vytvorený a prihlásený."

    # --- lokálny režim ---
    be = db.get_backend()
    if be.table("local_users").eq("email", email).first():
        return False, "Účet s týmto e-mailom už existuje."
    user_id = db.new_id()
    be.insert("local_users", {
        "id": user_id, "email": email, "full_name": full_name or email,
        "password_hash": _hash_password(password), "created_at": iso(now_utc()),
    })
    be.insert("profiles", {
        "id": user_id, "email": email, "full_name": full_name or email,
        "timezone": config.app_config()["default_timezone"],
        "avatar_emoji": "🙂", "created_at": iso(now_utc()),
    })
    st.session_state["auth_user"] = {"id": user_id, "email": email,
                                     "full_name": full_name or email}
    return True, "Lokálny účet vytvorený."


def sign_in(email: str, password: str) -> tuple[bool, str]:
    email = email.strip().lower()

    if config.has_supabase():
        client = db.get_supabase_client()
        try:
            res = client.auth.sign_in_with_password({"email": email, "password": password})
        except Exception as exc:
            return False, f"Prihlásenie zlyhalo: {exc}"
        if res.session is None:
            return False, "Nesprávny e-mail alebo heslo."
        _store_supabase_session(res)
        return True, "Prihlásený."

    be = db.get_backend()
    user = be.table("local_users").eq("email", email).first()
    if not user or not _verify_password(password, user.get("password_hash", "")):
        return False, "Nesprávny e-mail alebo heslo."
    st.session_state["auth_user"] = {
        "id": user["id"], "email": user["email"], "full_name": user.get("full_name") or email,
    }
    return True, "Prihlásený."


def _store_supabase_session(res) -> None:
    session, user = res.session, res.user
    meta = getattr(user, "user_metadata", None) or {}
    st.session_state["auth_token"] = session.access_token
    st.session_state["auth_user"] = {
        "id": user.id,
        "email": user.email,
        "full_name": meta.get("full_name") or user.email,
    }
    db.reset_backend_cache()
    ensure_profile()


def ensure_profile() -> None:
    """Poistka, keby trigger v databáze nebol nasadený."""
    user = current_user()
    if not user:
        return
    be = backend()
    try:
        if be.table("profiles").eq("id", user["id"]).first():
            return
        be.insert("profiles", {
            "id": user["id"], "email": user["email"],
            "full_name": user.get("full_name") or user["email"],
            "timezone": config.app_config()["default_timezone"],
            "avatar_emoji": "🙂", "created_at": iso(now_utc()),
        })
    except Exception:
        pass


def list_people() -> list[dict]:
    """Všetky profily - kandidáti na priradenie úlohy."""
    try:
        return backend().table("profiles").order("full_name").all()
    except Exception:
        return []
