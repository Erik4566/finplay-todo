"""Dátová vrstva.

Jedno rozhranie, dve implementácie:

* ``SupabaseBackend`` - produkčná, PostgREST + RLS (token prihláseného používateľa)
* ``LocalBackend``    - záložná, SQLite súbor ``finplay_local.db``

Vďaka tomu appka beží aj bez akejkoľvek konfigurácie a po doplnení
``[supabase]`` do secrets.toml sa prepne na Supabase bez zmeny kódu.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from typing import Any, Iterable

from core import config

LOCAL_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "finplay_local.db")

_local_lock = threading.RLock()  # re-entrantný: _load sa volá aj zvnútra zamknutých sekcií


def new_id() -> str:
    return str(uuid.uuid4())


# =============================================================================
#  Query builder - spoločné API pre oba backendy
# =============================================================================

class Query:
    def __init__(self, backend: "Backend", table: str):
        self._backend = backend
        self._table = table
        self._filters: list[tuple] = []
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None

    # -- filtre ---------------------------------------------------------------
    def eq(self, col: str, value) -> "Query":
        self._filters.append(("eq", col, value)); return self

    def neq(self, col: str, value) -> "Query":
        self._filters.append(("neq", col, value)); return self

    def in_(self, col: str, values: Iterable) -> "Query":
        self._filters.append(("in", col, list(values))); return self

    def is_null(self, col: str) -> "Query":
        self._filters.append(("is_null", col, None)); return self

    def not_null(self, col: str) -> "Query":
        self._filters.append(("not_null", col, None)); return self

    def gte(self, col: str, value) -> "Query":
        self._filters.append(("gte", col, value)); return self

    def lte(self, col: str, value) -> "Query":
        self._filters.append(("lte", col, value)); return self

    def ilike(self, col: str, pattern: str) -> "Query":
        self._filters.append(("ilike", col, pattern)); return self

    def search(self, columns: list[str], text: str) -> "Query":
        """Hľadanie naprieč viacerými stĺpcami (OR)."""
        self._filters.append(("or_ilike", columns, text)); return self

    # -- ostatné --------------------------------------------------------------
    def order(self, col: str, desc: bool = False) -> "Query":
        self._order = (col, desc); return self

    def limit(self, n: int) -> "Query":
        self._limit = n; return self

    # -- vykonanie ------------------------------------------------------------
    def all(self) -> list[dict]:
        return self._backend.select(self._table, self._filters, self._order, self._limit)

    def first(self) -> dict | None:
        rows = self.limit(1).all()
        return rows[0] if rows else None

    def count(self) -> int:
        return len(self.all())

    def update(self, values: dict) -> list[dict]:
        return self._backend.update(self._table, self._filters, values)

    def delete(self) -> None:
        self._backend.delete(self._table, self._filters)


class Backend:
    kind = "abstract"

    def table(self, name: str) -> Query:
        return Query(self, name)

    # rozhranie, ktoré implementujú potomkovia
    def select(self, table, filters, order, limit) -> list[dict]: raise NotImplementedError
    def insert(self, table, row: dict) -> dict: raise NotImplementedError
    def insert_many(self, table, rows: list[dict]) -> list[dict]: raise NotImplementedError
    def update(self, table, filters, values: dict) -> list[dict]: raise NotImplementedError
    def delete(self, table, filters) -> None: raise NotImplementedError


# =============================================================================
#  Supabase
# =============================================================================

class SupabaseBackend(Backend):
    kind = "supabase"

    def __init__(self, client):
        self.client = client

    def _apply(self, q, filters):
        for op, col, val in filters:
            if op == "eq":
                q = q.eq(col, val)
            elif op == "neq":
                q = q.neq(col, val)
            elif op == "in":
                q = q.in_(col, val or ["__none__"])
            elif op == "is_null":
                q = q.is_(col, "null")
            elif op == "not_null":
                q = q.not_.is_(col, "null")
            elif op == "gte":
                q = q.gte(col, val)
            elif op == "lte":
                q = q.lte(col, val)
            elif op == "ilike":
                q = q.ilike(col, val)
            elif op == "or_ilike":
                needle = str(val).replace(",", " ").replace("(", " ").replace(")", " ").strip()
                clause = ",".join(f"{c}.ilike.*{needle}*" for c in col)
                q = q.or_(clause)
        return q

    def select(self, table, filters, order, limit):
        q = self._apply(self.client.table(table).select("*"), filters)
        if order:
            q = q.order(order[0], desc=order[1])
        if limit:
            q = q.limit(limit)
        return q.execute().data or []

    def insert(self, table, row):
        row = dict(row)
        row.setdefault("id", new_id())
        data = self.client.table(table).insert(row).execute().data
        return (data or [row])[0]

    def insert_many(self, table, rows):
        rows = [dict(r) for r in rows]
        for r in rows:
            r.setdefault("id", new_id())
        if not rows:
            return []
        return self.client.table(table).insert(rows).execute().data or rows

    def update(self, table, filters, values):
        q = self._apply(self.client.table(table).update(values), filters)
        return q.execute().data or []

    def delete(self, table, filters):
        q = self._apply(self.client.table(table).delete(), filters)
        q.execute()


# =============================================================================
#  Lokálna SQLite náhrada (dokumentové úložisko)
# =============================================================================

class LocalBackend(Backend):
    kind = "local"

    def __init__(self, path: str = LOCAL_DB_PATH):
        self.path = path
        self._init()

    def _conn(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with _local_lock:
            conn = self._conn()
            try:
                with conn:
                    conn.execute(
                        """create table if not exists records (
                               tbl text not null,
                               id  text not null,
                               doc text not null,
                               primary key (tbl, id))"""
                    )
            finally:
                conn.close()

    # -- pomocné --------------------------------------------------------------
    @staticmethod
    def _match(row: dict, filters) -> bool:
        for op, col, val in filters:
            if op == "or_ilike":
                needle = str(val).lower()
                if not any(needle in str(row.get(c) or "").lower() for c in col):
                    return False
                continue
            cur = row.get(col)
            if op == "eq" and cur != val:
                return False
            if op == "neq" and cur == val:
                return False
            if op == "in" and cur not in (val or []):
                return False
            if op == "is_null" and cur not in (None, ""):
                return False
            if op == "not_null" and cur in (None, ""):
                return False
            if op == "gte" and (cur is None or str(cur) < str(val)):
                return False
            if op == "lte" and (cur is None or str(cur) > str(val)):
                return False
            if op == "ilike":
                pattern = str(val).strip("%").lower()
                if pattern not in str(cur or "").lower():
                    return False
        return True

    def _load(self, table) -> list[dict]:
        with _local_lock:
            conn = self._conn()
            try:
                rows = conn.execute("select doc from records where tbl = ?",
                                    (table,)).fetchall()
            finally:
                conn.close()
        return [json.loads(r["doc"]) for r in rows]

    def _save(self, table, row: dict):
        with _local_lock:
            conn = self._conn()
            try:
                with conn:
                    conn.execute(
                        "insert or replace into records (tbl, id, doc) values (?, ?, ?)",
                        (table, row["id"], json.dumps(row, ensure_ascii=False)),
                    )
            finally:
                conn.close()

    # -- rozhranie ------------------------------------------------------------
    def select(self, table, filters, order, limit):
        rows = [r for r in self._load(table) if self._match(r, filters)]
        if order:
            col, desc = order
            rows.sort(key=lambda r: (r.get(col) is None, str(r.get(col) or "")), reverse=desc)
        if limit:
            rows = rows[:limit]
        return rows

    def insert(self, table, row):
        row = dict(row)
        row.setdefault("id", new_id())
        self._save(table, row)
        return row

    def insert_many(self, table, rows):
        out = []
        for r in rows:
            out.append(self.insert(table, r))
        return out

    def update(self, table, filters, values):
        changed = []
        for row in self._load(table):
            if self._match(row, filters):
                row.update(values)
                self._save(table, row)
                changed.append(row)
        return changed

    def delete(self, table, filters):
        doomed = [r["id"] for r in self._load(table) if self._match(r, filters)]
        if not doomed:
            return
        with _local_lock:
            conn = self._conn()
            try:
                with conn:
                    conn.executemany("delete from records where tbl = ? and id = ?",
                                     [(table, row_id) for row_id in doomed])
            finally:
                conn.close()


# =============================================================================
#  Továreň
# =============================================================================

_backend_cache: dict[str, Backend] = {}


def get_supabase_client(access_token: str | None = None):
    """Supabase klient; s access_token sa dotazy vykonávajú pod RLS používateľa."""
    cfg = config.supabase_config()
    if not cfg:
        return None
    from supabase import create_client

    client = create_client(cfg["url"], cfg["anon_key"])
    if access_token:
        try:
            client.postgrest.auth(access_token)
        except Exception:
            pass
    return client


def get_backend(access_token: str | None = None) -> Backend:
    """Backend pre aktuálnu reláciu. Cache-uje sa podľa tokenu."""
    key = access_token or "__anon__"
    if config.has_supabase():
        cached = _backend_cache.get(key)
        if cached is not None:
            return cached
        client = get_supabase_client(access_token)
        if client is not None:
            backend = SupabaseBackend(client)
            _backend_cache[key] = backend
            return backend
    cached = _backend_cache.get("__local__")
    if cached is None:
        cached = LocalBackend()
        _backend_cache["__local__"] = cached
    return cached


def reset_backend_cache() -> None:
    _backend_cache.clear()
