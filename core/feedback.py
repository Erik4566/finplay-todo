"""Spätná väzba k aplikácii — zachytenie trenia v momente, keď vznikne.

Nie je to spätná väzba k úlohám (tú rieši ``ai_feedback`` a ``task_risks``),
ale k samotnej appke: chyby, nápady, veci, ktoré zdržujú.

ULOŽENIE OBRÁZKOV
-----------------
Obrázok sa **zmenší a uloží priamo do databázy** (base64). Dôvod: appka je
navrhnutá tak, aby bežala aj nasadená v cloude, kde je súborový systém dočasný
— prílohy zapísané na disk by zmizli pri každom reštarte. V databáze prežijú
a sú dostupné z telefónu aj z počítača.

Aby to databázu nenafúklo, obrázok sa pred uložením zmenší na dlhšiu stranu
``MAX_SIDE`` px a prekóduje. Zo screenshotu z telefónu tak zostane typicky
150-400 kB namiesto niekoľkých megabajtov.

Ak je súborový systém zapisovateľný (lokálny beh), uloží sa aj kópia do
``data/feedback/`` — vtedy sa dá k prílohe dostať priamo, bez appky.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from io import BytesIO

from core import auth, config, db
from core.models import iso, now_utc, parse_dt

IMAGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "feedback")

MAX_UPLOAD_BYTES = 12 * 1024 * 1024    # čo prijmeme na vstupe
MAX_STORED_BYTES = 1_200_000           # čo uložíme do databázy po zmenšení
MAX_SIDE = 1600                        # dlhšia strana obrázka v px
MAX_IMAGES = 4
ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

KINDS = {
    "bug": "Nefunguje to",
    "friction": "Zdržuje ma to",
    "idea": "Nápad na zlepšenie",
    "question": "Otázka",
}

KIND_ICONS = {
    "bug": "bug_report",
    "friction": "sentiment_dissatisfied",
    "idea": "lightbulb",
    "question": "help",
}

STATUSES = {"new": "Nové", "in_progress": "Rieši sa", "done": "Vybavené"}


def _be() -> db.Backend:
    return auth.backend()


def _uid() -> str:
    user = auth.current_user()
    if not user:
        raise RuntimeError("Nie je prihlásený používateľ.")
    return user["id"]


# =============================================================================
#  Obrázky
# =============================================================================

def _shrink(data: bytes, suffix: str) -> tuple[bytes, str, str]:
    """Zmenší obrázok. Vracia (dáta, prípona, mime). Bez Pillow vráti originál."""
    try:
        from PIL import Image
    except ImportError:
        return data, suffix, "image/png"

    try:
        image = Image.open(BytesIO(data))
        image.thumbnail((MAX_SIDE, MAX_SIDE))
        buffer = BytesIO()
        if suffix in (".jpg", ".jpeg"):
            image.convert("RGB").save(buffer, "JPEG", quality=82, optimize=True)
            return buffer.getvalue(), ".jpg", "image/jpeg"
        image.convert("RGBA").save(buffer, "PNG", optimize=True)
        return buffer.getvalue(), ".png", "image/png"
    except Exception:
        return data, suffix, "image/png"


def prepare_image(uploaded) -> dict | None:
    """Z nahraného súboru spraví záznam pripravený na uloženie."""
    if uploaded is None:
        return None
    suffix = os.path.splitext(uploaded.name)[1].lower()
    if suffix not in ALLOWED_SUFFIXES:
        return None
    raw = uploaded.getvalue()
    if not raw or len(raw) > MAX_UPLOAD_BYTES:
        return None

    data, suffix, mime = _shrink(raw, suffix)
    if len(data) > MAX_STORED_BYTES:                      # ešte raz, agresívnejšie
        data, suffix, mime = _shrink(data, ".jpg")
    if len(data) > MAX_STORED_BYTES:
        return None

    name = f"{now_utc().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}{suffix}"

    # kópia na disk je len bonus pre lokálny beh - v cloude sa ticho preskočí
    try:
        os.makedirs(IMAGE_DIR, exist_ok=True)
        with open(os.path.join(IMAGE_DIR, name), "wb") as handle:
            handle.write(data)
    except OSError:
        pass

    return {"name": name, "mime": mime,
            "data": base64.b64encode(data).decode("ascii"),
            "bytes": len(data)}


def image_bytes(image: dict) -> bytes | None:
    try:
        return base64.b64decode(image["data"])
    except Exception:
        return None


def images_of(item: dict) -> list[dict]:
    raw = item.get("images")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return []
    return [i for i in (raw or []) if isinstance(i, dict)]


# =============================================================================
#  Záznamy
# =============================================================================

def create(message: str, kind: str = "friction", page: str | None = None,
           blocking: bool = False, images: list[dict] | None = None,
           extra_context: dict | None = None) -> dict:
    context = {
        "verzia": config.APP_VERSION,
        "backend": _be().kind,
        "obrazovka": page,
    }
    context.update(extra_context or {})

    return _be().insert("feedback", {
        "id": db.new_id(),
        "user_id": _uid(),
        "kind": kind if kind in KINDS else "friction",
        "message": message.strip(),
        "page": page,
        "blocking": bool(blocking),
        "images": images or [],
        "context": context,
        "status": "new",
        "created_at": iso(now_utc()),
        "resolved_at": None,
    })


def list_all(status: str | None = None) -> list[dict]:
    rows = _be().table("feedback").eq("user_id", _uid()).all()
    if status:
        rows = [r for r in rows if r.get("status") == status]
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows


def counts() -> dict:
    rows = list_all()
    return {key: sum(1 for r in rows if r.get("status") == key) for key in STATUSES}


def set_status(feedback_id: str, status: str) -> None:
    _be().table("feedback").eq("id", feedback_id).update({
        "status": status,
        "resolved_at": iso(now_utc()) if status == "done" else None,
    })


def delete(feedback_id: str) -> None:
    item = _be().table("feedback").eq("id", feedback_id).first()
    for image in images_of(item or {}):
        path = os.path.join(IMAGE_DIR, image.get("name", ""))
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    _be().table("feedback").eq("id", feedback_id).delete()


# =============================================================================
#  Export
# =============================================================================

def as_markdown(only_open: bool = True) -> str:
    rows = [r for r in list_all() if not only_open or r.get("status") != "done"]
    if not rows:
        return "Žiadna otvorená spätná väzba."

    lines = [f"# Spätná väzba k FinPlay ToDo ({len(rows)})", ""]
    for item in rows:
        stamp = parse_dt(item.get("created_at"))
        when = stamp.astimezone().strftime("%d.%m.%Y %H:%M") if stamp else "?"
        head = f"## [{KINDS.get(item.get('kind'), item.get('kind'))}] {when}"
        if item.get("blocking"):
            head += "  — BLOKUJE"
        lines.append(head)
        if item.get("page"):
            lines.append(f"*Obrazovka:* `{item['page']}`")
        lines += ["", item.get("message") or ""]

        images = images_of(item)
        if images:
            lines += ["", "Prílohy:"]
            lines += [f"- `{i.get('name')}` ({round((i.get('bytes') or 0)/1024)} kB)"
                      for i in images]

        context = item.get("context")
        if isinstance(context, str):
            try:
                context = json.loads(context)
            except Exception:
                context = None
        if isinstance(context, dict):
            pairs = ", ".join(f"{k}={v}" for k, v in context.items() if v)
            if pairs:
                lines += ["", f"<sub>{pairs}</sub>"]
        lines += ["", "---", ""]
    return "\n".join(lines)


def as_zip(only_open: bool = True) -> bytes:
    """Celý balík pre vývojára: prehľad v Markdowne + všetky prílohy."""
    import zipfile

    rows = [r for r in list_all() if not only_open or r.get("status") != "done"]
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("spatna-vazba.md", as_markdown(only_open))
        for item in rows:
            for image in images_of(item):
                data = image_bytes(image)
                if data:
                    archive.writestr(f"prilohy/{image.get('name')}", data)
    return buffer.getvalue()
