"""Farebné schémy.

Každá schéma je definovaná len zopár základnými farbami; zvyšok premenných
(pozadia odznakov, okraje, gradient hero karty) sa **dopočíta miešaním** —
tak sú všetky schémy konzistentné a nedá sa v nich vyrobiť nečitateľný kontrast.

Palety pochádzajú od uznávaných autorov a tímov:

* **Nord** — Arctic Ice Studio (Sven Greb)
* **Solarized** — Ethan Schoonover, navrhnutá na presné pomery kontrastu
* **Dracula** — Zeno Rocha
* **Tokyo Night** — enkia
* **Gruvbox** — Pavel Pertsev
* **Catppuccin Mocha** — komunita Catppuccin
* **GitHub / Primer** — designový systém GitHubu
* **One Light / One Dark** — Atom (GitHub)
* **Rosé Pine** — tím Rosé Pine
"""

from __future__ import annotations


# =============================================================================
#  Práca s farbami
# =============================================================================

def _rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02X}" for c in rgb)


def mix(color_a: str, color_b: str, ratio: float) -> str:
    """``ratio`` diel farby A, zvyšok farby B."""
    a, b = _rgb(color_a), _rgb(color_b)
    return _hex(tuple(a[i] * ratio + b[i] * (1 - ratio) for i in range(3)))


def _luma(hex_color: str) -> float:
    r, g, b = _rgb(hex_color)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


def readable(color: str, background: str, dark: bool) -> str:
    """Posunie farbu tak, aby bola na danom pozadí čitateľná."""
    target = "#FFFFFF" if dark else "#000000"
    result = color
    for _ in range(8):
        if abs(_luma(result) - _luma(background)) >= 0.42:
            break
        result = mix(target, result, 0.14)
    return result


# =============================================================================
#  Definície schém
# =============================================================================
#  bg    pozadie appky        card  karty a vstupy       card2 sekundárny povrch
#  line  okraje               text  hlavný text          text2 vedľajší text
#  muted potlačený text       accent hlavná farba
#  p1-p4 priority Q1-Q4       ok    potvrdenie / časovač

LIGHT_SCHEMES: dict[str, dict] = {
    "Papier": {
        "bg": "#FBFAF8", "card": "#FFFFFF", "card2": "#F3F1EC", "line": "#E4E0D8",
        "text": "#17181D", "text2": "#4E5563", "muted": "#7C838F", "accent": "#4F46E5",
        "p1": "#E11D48", "p2": "#2563EB", "p3": "#C2700A", "p4": "#98A0AD",
        "ok": "#059669",
        "note": "Teplá neutrálna, nízky jas — pokojná na dlhé sedenie",
    },
    "GitHub": {
        "bg": "#F6F8FA", "card": "#FFFFFF", "card2": "#EEF1F4", "line": "#D0D7DE",
        "text": "#1F2328", "text2": "#57606A", "muted": "#6E7781", "accent": "#0969DA",
        "p1": "#CF222E", "p2": "#0969DA", "p3": "#BC4C00", "p4": "#8C959F",
        "ok": "#1A7F37",
        "note": "Primer — designový systém GitHubu",
    },
    "Solarized": {
        "bg": "#EEE8D5", "card": "#FDF6E3", "card2": "#E7E0CC", "line": "#D9D2BC",
        "text": "#073642", "text2": "#586E75", "muted": "#8A9A9A", "accent": "#268BD2",
        "p1": "#DC322F", "p2": "#268BD2", "p3": "#B58900", "p4": "#93A1A1",
        "ok": "#859900",
        "note": "Ethan Schoonover — počítané pomery kontrastu",
    },
    "Nord Snow": {
        "bg": "#ECEFF4", "card": "#FFFFFF", "card2": "#E5E9F0", "line": "#D8DEE9",
        "text": "#2E3440", "text2": "#434C5E", "muted": "#7B88A1", "accent": "#5E81AC",
        "p1": "#BF616A", "p2": "#5E81AC", "p3": "#D08770", "p4": "#8FA1B3",
        "ok": "#A3BE8C",
        "note": "Arctic Ice Studio — chladná, tlmená",
    },
    "Rosé Pine Dawn": {
        "bg": "#FAF4ED", "card": "#FFFAF3", "card2": "#F2E9E1", "line": "#E5DBD0",
        "text": "#575279", "text2": "#6E6A86", "muted": "#9893A5", "accent": "#907AA9",
        "p1": "#B4637A", "p2": "#286983", "p3": "#EA9D34", "p4": "#9893A5",
        "ok": "#56949F",
        "note": "Rosé Pine — teplá, nízkokontrastná",
    },
    "One Light": {
        "bg": "#FAFAFA", "card": "#FFFFFF", "card2": "#F0F0F1", "line": "#E1E1E2",
        "text": "#383A42", "text2": "#4F525D", "muted": "#9598A1", "accent": "#4078F2",
        "p1": "#E45649", "p2": "#4078F2", "p3": "#C18401", "p4": "#A0A1A7",
        "ok": "#50A14F",
        "note": "Atom One — neutrálna, vysoký kontrast textu",
    },
}

DARK_SCHEMES: dict[str, dict] = {
    "Uhlík": {
        "bg": "#101116", "card": "#1A1C24", "card2": "#22252F", "line": "#2E323F",
        "text": "#ECEEF3", "text2": "#AEB5C4", "muted": "#7E8697", "accent": "#8B87FF",
        "p1": "#FF5E7D", "p2": "#6C9BFF", "p3": "#E9A33C", "p4": "#6B7383",
        "ok": "#35C99B",
        "note": "Neutrálna tmavá, fialový akcent",
    },
    "Nord": {
        "bg": "#2E3440", "card": "#3B4252", "card2": "#434C5E", "line": "#4C566A",
        "text": "#ECEFF4", "text2": "#D8DEE9", "muted": "#8593A8", "accent": "#88C0D0",
        "p1": "#BF616A", "p2": "#81A1C1", "p3": "#EBCB8B", "p4": "#6C7A93",
        "ok": "#A3BE8C",
        "note": "Arctic Ice Studio — jemná, málo unavuje",
    },
    "Dracula": {
        "bg": "#282A36", "card": "#343746", "card2": "#44475A", "line": "#4A4D63",
        "text": "#F8F8F2", "text2": "#D5D6E0", "muted": "#8E92A8", "accent": "#BD93F9",
        "p1": "#FF5555", "p2": "#8BE9FD", "p3": "#FFB86C", "p4": "#6272A4",
        "ok": "#50FA7B",
        "note": "Zeno Rocha — sýte akcenty",
    },
    "Tokyo Night": {
        "bg": "#1A1B26", "card": "#24283B", "card2": "#2F344A", "line": "#3B4261",
        "text": "#C0CAF5", "text2": "#A9B1D6", "muted": "#787C99", "accent": "#7AA2F7",
        "p1": "#F7768E", "p2": "#7AA2F7", "p3": "#E0AF68", "p4": "#565F89",
        "ok": "#9ECE6A",
        "note": "enkia — modrá noc, nízky jas",
    },
    "Gruvbox": {
        "bg": "#282828", "card": "#32302F", "card2": "#3C3836", "line": "#504945",
        "text": "#EBDBB2", "text2": "#D5C4A1", "muted": "#A89984", "accent": "#83A598",
        "p1": "#FB4934", "p2": "#83A598", "p3": "#FABD2F", "p4": "#928374",
        "ok": "#B8BB26",
        "note": "Pavel Pertsev — teplá retro paleta",
    },
    "Catppuccin Mocha": {
        "bg": "#1E1E2E", "card": "#252639", "card2": "#313244", "line": "#3E4058",
        "text": "#CDD6F4", "text2": "#BAC2DE", "muted": "#7F849C", "accent": "#CBA6F7",
        "p1": "#F38BA8", "p2": "#89B4FA", "p3": "#FAB387", "p4": "#6C7086",
        "ok": "#A6E3A1",
        "note": "Catppuccin — pastelová, mäkký kontrast",
    },
}

DEFAULT_LIGHT = "Papier"
DEFAULT_DARK = "Uhlík"


def get(name: str, dark: bool) -> dict:
    table = DARK_SCHEMES if dark else LIGHT_SCHEMES
    default = DEFAULT_DARK if dark else DEFAULT_LIGHT
    return table.get(name, table[default])


def names(dark: bool) -> list[str]:
    return list((DARK_SCHEMES if dark else LIGHT_SCHEMES).keys())


# =============================================================================
#  Odvodenie CSS premenných
# =============================================================================

def css_variables(name: str, dark: bool) -> str:
    s = get(name, dark)
    bg, card, line = s["bg"], s["card"], s["line"]

    def badge(color: str) -> tuple[str, str]:
        """(pozadie, popredie) odznaku pre danú významovú farbu."""
        background = mix(color, card, 0.20 if dark else 0.13)
        return background, readable(color, background, dark)

    b1, f1 = badge(s["p1"])
    b2, f2 = badge(s["p2"])
    b3, f3 = badge(s["p3"])
    b4, f4 = badge(s["p4"])
    bt, ft = badge(s["ok"])
    bc, fc = badge(s["accent"])

    shadow = ("0 1px 2px rgba(0,0,0,.35), 0 2px 14px rgba(0,0,0,.28)" if dark
              else "0 1px 2px rgba(23,24,29,.05), 0 1px 10px rgba(23,24,29,.05)")
    shadow_lg = ("0 6px 26px rgba(0,0,0,.45)" if dark
                 else f"0 4px 24px {mix(s['accent'], '#FFFFFF', 0.18)}")
    nav_rgb = _rgb(card)

    return f"""
  color-scheme: {'dark' if dark else 'light'};
  --fp-bg:        {bg};
  --fp-card:      {card};
  --fp-card-2:    {s['card2']};
  --fp-line:      {line};
  --fp-line-soft: {mix(line, bg, 0.5)};
  --fp-text:      {s['text']};
  --fp-text-2:    {s['text2']};
  --fp-muted:     {s['muted']};
  --fp-accent:    {s['accent']};
  --fp-accent-sf: {mix(s['accent'], bg, 0.14)};
  --fp-accent-bd: {mix(s['accent'], bg, 0.38)};
  --fp-hero-a:    {mix(s['accent'], bg, 0.17)};
  --fp-hero-b:    {card};

  --fp-p1: {s['p1']};
  --fp-p2: {s['p2']};
  --fp-p3: {s['p3']};
  --fp-p4: {s['p4']};
  --fp-ok: {s['ok']};

  --fp-b1-bg: {b1};  --fp-b1-fg: {f1};
  --fp-b2-bg: {b2};  --fp-b2-fg: {f2};
  --fp-b3-bg: {b3};  --fp-b3-fg: {f3};
  --fp-b4-bg: {b4};  --fp-b4-fg: {f4};
  --fp-bt-bg: {bt};  --fp-bt-fg: {ft};
  --fp-bc-bg: {bc};  --fp-bc-fg: {fc};
  --fp-alert: {mix(s['p1'], bg, 0.13)};
  --fp-timer-bg: {bt}; --fp-timer-bd: {mix(s['ok'], card, 0.42)}; --fp-timer-fg: {ft};
  --fp-shadow:    {shadow};
  --fp-shadow-lg: {shadow_lg};
  --fp-navbg:     rgba({nav_rgb[0]}, {nav_rgb[1]}, {nav_rgb[2]}, .97);
"""


def swatch_html(name: str, dark: bool) -> str:
    """Malý farebný pás na náhľad schémy."""
    s = get(name, dark)
    colors = [s["bg"], s["card"], s["accent"], s["p1"], s["p3"], s["ok"], s["text"]]
    dots = "".join(
        f'<span style="width:1.15rem;height:1.15rem;border-radius:50%;background:{c};'
        f'border:1px solid rgba(128,128,128,.35);display:inline-block;"></span>'
        for c in colors)
    return (f'<div style="display:flex;gap:.3rem;align-items:center;margin:.15rem 0 .1rem;">'
            f'{dots}</div>'
            f'<div class="fp-muted" style="font-size:.85rem;">{s["note"]}</div>')
