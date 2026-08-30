"""Aktualizácia kalendára mien z oficiálneho zdroja.

Stiahne Oficiálne kalendárium Ministerstva kultúry SR (PDF), naparsuje ho
a prepíše ``data/meniny_sk.json``. Pred zápisom ukáže, čo sa oproti
existujúcemu súboru zmenilo — nikdy neprepisuje ticho.

Spustenie:
    python tools/update_calendar.py            # skontroluje a ukáže rozdiely
    python tools/update_calendar.py --zapisat  # aj zapíše zmeny

Sviatky sa neaktualizujú — tie sa počítajú zo zákona (``core/calendars.py``).
Menia sa len novelou, ktorú treba doplniť ručne; appka na to upozorní,
keď rok presiahne ``VERIFIED_UNTIL``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from collections import OrderedDict
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "data", "meniny_sk.json")

PAGE = "https://www.culture.gov.sk/sk/oficialne-kalendarium"
PDF_PATTERN = "https://www.culture.gov.sk/storage/2020/03/Oficialne-kalendarium_{year}.pdf"

MONTH_LEN = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
LINE = re.compile(r"^(\d{1,2})\.\s*(\d{1,2})\.\s*(.*)$")
MONTHS = {"JANUÁR", "FEBRUÁR", "MAREC", "APRÍL", "MÁJ", "JÚN", "JÚL",
          "AUGUST", "SEPTEMBER", "OKTÓBER", "NOVEMBER", "DECEMBER"}
NOISE = {"Mená v stanovenom poradí", "Deň", "OFICIÁLNE KALENDÁRIUM"}


def find_pdf() -> tuple[str, int] | None:
    """Skúsi najnovší ročník, potom postupne staršie."""
    current = date.today().year
    for year in range(current + 1, current - 4, -1):
        url = PDF_PATTERN.format(year=year)
        try:
            request = urllib.request.Request(url, method="HEAD",
                                             headers={"User-Agent": "FinPlay-ToDo"})
            with urllib.request.urlopen(request, timeout=20) as response:
                if response.status == 200:
                    return url, year
        except Exception:
            continue
    return None


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "FinPlay-ToDo"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def parse(pdf_bytes: bytes) -> dict:
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit("Chýba balík pypdf. Nainštaluj: pip install pypdf")

    import io as _io
    reader = PdfReader(_io.BytesIO(pdf_bytes))
    found: OrderedDict[tuple[int, int], str] = OrderedDict()

    for page in reader.pages:
        for raw in (page.extract_text() or "").split("\n"):
            line = raw.strip()
            if not line or line in NOISE or line in MONTHS:
                continue
            match = LINE.match(line)
            if not match:
                continue
            day, month = int(match.group(1)), int(match.group(2))
            names = match.group(3).strip()
            if not (1 <= month <= 12 and 1 <= day <= MONTH_LEN[month - 1]):
                continue
            for word in MONTHS:
                if names.endswith(word):
                    names = names[: -len(word)].strip()
            found[(month, day)] = "" if names in ("-", "–", "—") else names

    missing = [(m, d) for m in range(1, 13)
               for d in range(1, MONTH_LEN[m - 1] + 1) if (m, d) not in found]
    if missing:
        sys.exit(f"PDF sa nepodarilo naparsovať — chýba {len(missing)} dní: "
                 f"{missing[:8]}")
    return found


def build_table(found: dict, source_url: str, year: int) -> dict:
    table = {"_zdroj": (f"Oficiálne kalendárium {year} — kalendárová komisia pri "
                        f"Ministerstve kultúry SR. Automaticky naparsované z {source_url} "
                        f"nástrojom tools/update_calendar.py. Kľúč je mesiac "
                        f"('01'-'12'), hodnota pole mien pre 1. až posledný deň mesiaca; "
                        f"prázdny reťazec = v ten deň meniny nie sú.")}
    for month in range(1, 13):
        table[f"{month:02d}"] = [
            ", ".join(found.get((month, day), "").split())
            for day in range(1, MONTH_LEN[month - 1] + 1)
        ]
    return table


def diff(old: dict, new: dict) -> list[str]:
    changes = []
    for month in range(1, 13):
        key = f"{month:02d}"
        before, after = old.get(key) or [], new.get(key) or []
        for index in range(max(len(before), len(after))):
            was = before[index] if index < len(before) else "(chýbalo)"
            now = after[index] if index < len(after) else "(zmizlo)"
            if was != now:
                changes.append(f"{index + 1}.{month}.  {was!r} -> {now!r}")
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zapisat", action="store_true",
                        help="zapísať zmeny do data/meniny_sk.json")
    args = parser.parse_args()

    print(f"Hľadám oficiálne kalendárium na {PAGE} …")
    found_pdf = find_pdf()
    if not found_pdf:
        print("Nenašiel som PDF. Skontroluj stránku ministerstva ručne:")
        print(f"  {PAGE}")
        return 1
    url, year = found_pdf
    print(f"Sťahujem ročník {year}: {url}")

    table = build_table(parse(download(url)), url, year)

    old = {}
    if os.path.exists(TARGET):
        with open(TARGET, encoding="utf-8") as handle:
            old = json.load(handle)

    changes = diff(old, table)
    if not changes:
        print("Bez zmien — lokálny súbor zodpovedá oficiálnemu zdroju.")
        return 0

    print(f"\nRozdielov: {len(changes)}")
    for line in changes[:40]:
        print("  " + line)
    if len(changes) > 40:
        print(f"  … a ďalších {len(changes) - 40}")

    if not args.zapisat:
        print("\nNič som nezapísal. Ak zmeny sedia, spusti znova s --zapisat")
        return 0

    with open(TARGET, "w", encoding="utf-8") as handle:
        json.dump(table, handle, ensure_ascii=False, indent=1)
    print(f"\nZapísané do {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
