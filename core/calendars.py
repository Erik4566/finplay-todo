"""Kalendár sviatkov a menín — Slovensko a Česko.

ZDROJE
======

**Slovenské sviatky** — zákon NR SR č. 241/1993 Z. z. o štátnych sviatkoch,
dňoch pracovného pokoja a pamätných dňoch. Overené proti úplnému zneniu na
Slov-Lexe. Zákon rozlišuje dve veci, ktoré sa bežne zamieňajú, preto sú
v modeli dva nezávislé príznaky ``state`` a ``rest``:

* **28. október** je štátny sviatok (§ 1), ale podľa § 2 ods. 3 **nie je** dňom
  pracovného pokoja — pracuje sa.
* **8. máj** a **15. september** sú naopak dni pracovného pokoja, nie štátne
  sviatky.

Dočasná zmena: zákon č. 261/2025 Z. z. (konsolidačná novela) vyňal 8. máj
a 15. september **2026** spomedzi dní pracovného pokoja — zostávajú sviatkami
(nárok na príplatok), ale pracuje sa. Rieši to ``rest_exceptions``.

**České sviatky** — zákon č. 245/2000 Sb., o státních svátcích, o ostatních
svátcích, o významných dnech a o dnech pracovního klidu. Podľa § 3 sú všetky
štátne aj ostatné sviatky dňami pracovného pokoja. Novela č. 59/2026 Sb.
pridáva len *významný deň* (Deň českej vlajky, 30. marca), ktorý je bežným
pracovným dňom — zoznamu sviatkov sa nedotýka.

**Slovenské meniny** — Oficiálne kalendárium, ktoré zostavuje kalendárová
komisia pri Ministerstve kultúry SR. Dáta v ``data/meniny_sk.json`` sú
automaticky naparsované z ministerského PDF (``tools/update_calendar.py``).

**České meniny** — *neexistuje oficiálny zdroj.* V Česku nepôsobí kalendárová
komisia ani iná inštitúcia, ktorá by mená k dňom prideľovala; každé
vydavateľstvo kalendárov si ich určuje samo. Preto je ``data/meniny_cz.json``
zámerne prázdny — appka pri českom nastavení meniny jednoducho nezobrazí,
kým si tam vlastný zoznam nedoplníš.

AKTUÁLNOSŤ
==========
Sviatky sa počítajú zo zákona, takže platia pre ľubovoľný rok dopredu vrátane
pohyblivých (Veľká noc podľa Meeusovho/Butcherovho algoritmu). Čo sa
**nedopočíta**, sú novely — preto je tu ``VERIFIED_UNTIL``: keď appka beží
v roku, ktorý presahuje overené obdobie, upozorní na to v Nastaveniach.
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from functools import lru_cache

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# Do vrátane ktorého roku bolo znenie zákona ručne overené pri zdroji.
VERIFIED_UNTIL = 2027

COUNTRIES = {
    "SK": {
        "label": "Slovensko",
        "nameday_file": "meniny_sk.json",
        "nameday_source": ("Oficiálne kalendárium — kalendárová komisia "
                           "pri Ministerstve kultúry SR"),
        "nameday_url": "https://www.culture.gov.sk/sk/oficialne-kalendarium",
        "law": "zákon č. 241/1993 Z. z.",
        "law_url": "https://static.slov-lex.sk/static/SK/ZZ/1993/241/20210101.print.html",
        # (mesiac, deň, názov, štátny_sviatok, deň_pracovného_pokoja)
        "fixed": [
            (1, 1, "Deň vzniku Slovenskej republiky", True, True),
            (1, 6, "Zjavenie Pána (Traja králi)", False, True),
            (5, 1, "Sviatok práce", False, True),
            (5, 8, "Deň víťazstva nad fašizmom", False, True),
            (7, 5, "Sviatok svätého Cyrila a svätého Metoda", True, True),
            (8, 29, "Výročie Slovenského národného povstania", True, True),
            (9, 1, "Deň Ústavy Slovenskej republiky", True, True),
            (9, 15, "Sedembolestná Panna Mária", False, True),
            (10, 28, "Deň vzniku samostatného česko-slovenského štátu", True, False),
            (11, 1, "Sviatok všetkých svätých", False, True),
            (11, 17, "Deň boja za slobodu a demokraciu", True, True),
            (12, 24, "Štedrý deň", False, True),
            (12, 25, "Prvý sviatok vianočný", False, True),
            (12, 26, "Druhý sviatok vianočný", False, True),
        ],
        "easter": [(-2, "Veľký piatok", False, True),
                   (1, "Veľkonočný pondelok", False, True)],
        # {rok: {(mesiac, deň), ...}} — sviatok zostáva, voľno nie
        "rest_exceptions": {2026: {(5, 8), (9, 15)}},
        "labels": {
            (True, True): "štátny sviatok",
            (True, False): "štátny sviatok · pracovný deň",
            (False, True): "deň pracovného pokoja",
            (False, False): "sviatok · pracovný deň",
        },
    },
    "CZ": {
        "label": "Česko",
        "nameday_file": "meniny_cz.json",
        "nameday_source": "bez oficiálneho zdroja — v Česku kalendárová komisia nie je",
        "nameday_url": None,
        "law": "zákon č. 245/2000 Sb.",
        "law_url": "https://ppropo.mpsv.cz/zakon_245_2000",
        "fixed": [
            (1, 1, "Den obnovy samostatného českého státu / Nový rok", True, True),
            (5, 1, "Svátek práce", False, True),
            (5, 8, "Den vítězství", True, True),
            (7, 5, "Den slovanských věrozvěstů Cyrila a Metoděje", True, True),
            (7, 6, "Den upálení mistra Jana Husa", True, True),
            (9, 28, "Den české státnosti", True, True),
            (10, 28, "Den vzniku samostatného československého státu", True, True),
            (11, 17, "Den boje za svobodu a demokracii a Mezinárodní den studentstva",
             True, True),
            (12, 24, "Štědrý den", False, True),
            (12, 25, "1. svátek vánoční", False, True),
            (12, 26, "2. svátek vánoční", False, True),
        ],
        "easter": [(-2, "Velký pátek", False, True),
                   (1, "Velikonoční pondělí", False, True)],
        "rest_exceptions": {},
        "labels": {
            (True, True): "státní svátek",
            (True, False): "státní svátek · pracovní den",
            (False, True): "ostatní svátek (den pracovního klidu)",
            (False, False): "svátek · pracovní den",
        },
    },
}

DEFAULT_COUNTRY = "SK"


def country_config(country: str) -> dict:
    return COUNTRIES.get(country, COUNTRIES[DEFAULT_COUNTRY])


# =============================================================================
#  Veľká noc
# =============================================================================

def easter_sunday(year: int) -> date:
    """Veľkonočná nedeľa (Meeus/Jones/Butcher, gregoriánsky kalendár)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    lunar = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * lunar) // 451
    month, day = divmod(h + lunar - 7 * m + 114, 31)
    return date(year, month, day + 1)


# =============================================================================
#  Sviatky
# =============================================================================

@lru_cache(maxsize=16)
def holidays(year: int, country: str = DEFAULT_COUNTRY) -> dict:
    """{date: {"name", "state", "rest"}} pre daný rok a krajinu."""
    cfg = country_config(country)
    skip = cfg["rest_exceptions"].get(year, set())
    result: dict[date, dict] = {}

    for month, day, name, state, rest in cfg["fixed"]:
        result[date(year, month, day)] = {
            "name": name, "state": state,
            "rest": rest and (month, day) not in skip,
        }

    easter = easter_sunday(year)
    for offset, name, state, rest in cfg["easter"]:
        result[easter + timedelta(days=offset)] = {
            "name": name, "state": state, "rest": rest}
    return result


def holiday_on(day: date, country: str = DEFAULT_COUNTRY) -> dict | None:
    return holidays(day.year, country).get(day)


def next_holiday(after: date, country: str = DEFAULT_COUNTRY,
                 only_days_off: bool = False) -> tuple[date, dict] | None:
    """Najbližší sviatok po zadanom dni; pozerá aj do budúceho roka."""
    candidates = [
        (day, info)
        for year in (after.year, after.year + 1)
        for day, info in holidays(year, country).items()
        if day > after and (info["rest"] or not only_days_off)
    ]
    return min(candidates, key=lambda item: item[0]) if candidates else None


def label_for(info: dict, country: str = DEFAULT_COUNTRY) -> str:
    return country_config(country)["labels"][(info["state"], info["rest"])]


def is_verified(year: int) -> bool:
    return year <= VERIFIED_UNTIL


# =============================================================================
#  Meniny
# =============================================================================

@lru_cache(maxsize=4)
def _nameday_table(country: str) -> dict:
    path = os.path.join(DATA_DIR, country_config(country)["nameday_file"])
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def name_day(day: date, country: str = DEFAULT_COUNTRY) -> str | None:
    month = _nameday_table(country).get(f"{day.month:02d}")
    if not isinstance(month, list) or day.day > len(month):
        return None
    return month[day.day - 1] or None


def has_namedays(country: str) -> bool:
    return bool(_nameday_table(country).get("01"))


# =============================================================================
#  Zhrnutie pre dnešok
# =============================================================================

def today_context(today: date | None = None,
                  country: str = DEFAULT_COUNTRY) -> dict:
    today = today or date.today()
    current = holiday_on(today, country)
    upcoming = next_holiday(today, country)

    result = {
        "country": country,
        "date": today,
        "name_day": name_day(today, country),
        "holiday": current["name"] if current else None,
        "holiday_label": label_for(current, country) if current else None,
        "is_day_off": bool(current and current["rest"]),
        "next_holiday": None,
        "next_holiday_date": None,
        "next_holiday_in_days": None,
        "next_holiday_label": None,
        "verified": is_verified(today.year),
    }
    if upcoming:
        day, info = upcoming
        result.update({
            "next_holiday": info["name"],
            "next_holiday_date": day,
            "next_holiday_in_days": (day - today).days,
            "next_holiday_label": label_for(info, country),
        })
    return result


def humanize_days(days: int) -> str:
    if days == 0:
        return "dnes"
    if days == 1:
        return "zajtra"
    if days == 2:
        return "pozajtra"
    if days < 5:
        return f"o {days} dni"
    return f"o {days} dní"
