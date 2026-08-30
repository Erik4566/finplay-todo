"""Jednotná sada obrysových piktogramov.

Používa font **Material Symbols Rounded**, ktorý Streamlit načítava lokálne pre
svoje ikony (``:material/...:``). Vďaka tomu vyzerajú rovnako ikony vo widgetoch
aj vo vlastnom HTML - žiadne emoji, žiadny externý request.

Dva spôsoby použitia:

* ``icons.st("play_arrow")`` -> reťazec pre parameter ``icon=`` Streamlit widgetu
* ``icons.html("play_arrow")`` -> ``<span>`` pre vlastné HTML (odznaky, karty)
"""

from __future__ import annotations

# --- sémantické názvy -> Material Symbols -----------------------------------

NAV_TODAY = "bolt"
NAV_TASKS = "checklist"
NAV_ADD = "add"
NAV_SEARCH = "search"
NAV_MORE = "more_horiz"

LIGHT_MODE = "light_mode"
DARK_MODE = "dark_mode"

PROJECTS = "folder_open"
ARCHIVE = "inventory_2"
SETTINGS = "tune"

# priorita (Eisenhower)
Q1 = "local_fire_department"
Q2 = "event_upcoming"
Q3 = "groups"
Q4 = "keyboard_double_arrow_down"

# termín
DUE_OVERDUE = "running_with_errors"
DUE_TODAY = "alarm"
DUE_SOON = "event"
DUE_LATER = "calendar_month"
DUE_NONE = "event_busy"

# vlastnosti úlohy
TIME = "timer"
CONTEXT = "label"
ENERGY_LOW = "battery_2_bar"
ENERGY_MID = "battery_5_bar"
ENERGY_HIGH = "battery_full"
STEPS = "format_list_numbered"
RECURRING = "autorenew"
NEXT_STEP = "arrow_forward"

# akcie
PLAY = "play_arrow"
STOP = "stop_circle"
CHECK = "check"
DONE_ALL = "done_all"
SKIP = "skip_next"
OPEN = "open_in_new"
BACK = "arrow_back"
EDIT = "edit"
DELETE = "delete"
SEND = "send"
DOWNLOAD = "download"
COPY = "content_copy"
FILTER = "filter_list"
CAPACITY = "tune"
SYNC = "sync"
LINK = "link"
PERSON = "person"
PEOPLE = "group"
MAIL = "mail"
BELL = "notifications"
RISK = "warning"
CHALLENGE = "landscape"
AI = "auto_awesome"
DEMO = "science"
INBOX = "inbox"
FLAG = "flag"
CHART = "insights"
HEALTH = "monitor_heart"
LOGOUT = "logout"
PLUS = "add"
CLOSE = "close"
UP = "keyboard_arrow_up"
DOWN = "keyboard_arrow_down"
CELEBRATE = "celebration"
NAMEDAY = "cake"
HOLIDAY = "flag"
CALENDAR = "calendar_month"
EVENT_TIME = "schedule"
IDEA = "lightbulb"


def st(name: str) -> str:
    """Reťazec pre parameter ``icon=`` Streamlit widgetov."""
    return f":material/{name}:"


def html(name: str, size: str = "1.05em", color: str | None = None,
         nudge: str = "-.12em") -> str:
    """``<span>`` s ikonou do vlastného HTML.

    ``translate="no"`` a trieda ``notranslate`` sú nutné, nie kozmetické:
    názov ikony je v DOM ako anglický text (ligatúra) a prekladač prehliadača
    ho inak preloží — z ``local_fire_department`` sa stane „miestny hasičský
    zbor“, ligatúra prestane sedieť na glyf a namiesto ikony sa vypíše text.
    """
    style = f"font-size:{size};vertical-align:{nudge};"
    if color:
        style += f"color:{color};"
    return (f'<span class="fp-ic notranslate" translate="no" '
            f'style="{style}">{name}</span>')


# CSS pre vlastné HTML ikony. FILL 0 = obrysový variant.
CSS = """
.fp-ic {
  font-family: 'Material Symbols Rounded';
  font-weight: 400;
  font-style: normal;
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
  line-height: 1;
  display: inline-block;
  letter-spacing: normal;
  text-transform: none;
  white-space: nowrap;
  word-wrap: normal;
  direction: ltr;
  -webkit-font-feature-settings: 'liga';
  -webkit-font-smoothing: antialiased;
  user-select: none;
}
"""
