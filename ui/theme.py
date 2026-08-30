"""Vizuálny štýl - mobile first, svetlý aj tmavý režim.

Inšpirácia: Todoist (riadky úloh, farebné priority, spodná navigácia),
Things 3 (pokojná typografia, veľkorysé medzery, kruhové zaškrtávadlá),
TickTick (viditeľný čas a časovač).

Zásady:
* základ je telefón - rozmery, medzery a dotykové plochy sú pre palec,
  desktop je nadstavba cez ``@media (min-width: 768px)``,
* navigácia je vždy v spodnej lište, v dosahu palca,
* farba nesie význam (priorita, termín), nie dekoráciu,
* minimálna dotyková plocha 48 px.

Veľkosť rozhrania sa škáluje cez ``html { font-size }`` - všetky rozmery sú
v rem, takže jedna hodnota zväčší celé rozhranie vrátane komponentov Streamlitu.
Tmavý režim je len výmena premenných plus prebitie vlastného chrómu Streamlitu.
"""

from __future__ import annotations

import streamlit as st

from ui import icons, schemes

SCALES = {
    "Kompaktné": 16,
    "Normálne": 18,
    "Veľké": 20,
    "Extra veľké": 22,
}
DEFAULT_SCALE = "Veľké"


def is_dark() -> bool:
    return bool(st.session_state.get("ui_dark", False))


def scale_name() -> str:
    return st.session_state.get("ui_scale", DEFAULT_SCALE)


def _root_px() -> int:
    return SCALES.get(scale_name(), SCALES[DEFAULT_SCALE])


def light_scheme() -> str:
    return st.session_state.get("ui_light_scheme", schemes.DEFAULT_LIGHT)


def dark_scheme() -> str:
    return st.session_state.get("ui_dark_scheme", schemes.DEFAULT_DARK)


def current_scheme() -> str:
    return dark_scheme() if is_dark() else light_scheme()


# =============================================================================
#  Hlavný štýl
# =============================================================================

def _css(dark: bool, root_px: int) -> str:
    palette = schemes.css_variables(current_scheme(), dark)
    return f"""
<style>
{icons.CSS}
:root {{
{palette}
  --fp-radius:    16px;
  --fp-radius-lg: 22px;
  --fp-tap:       48px;
  --fp-navh:      74px;
}}

html {{ font-size: {root_px}px; }}

/* ---------- odstránenie zbytočného chrómu Streamlitu ---------- */
header[data-testid="stHeader"], #MainMenu, footer,
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="stToolbar"] {{ display: none !important; }}

.stApp, body {{ background: var(--fp-bg) !important; color: var(--fp-text); }}
html, body, [class*="css"] {{ -webkit-font-smoothing: antialiased; text-size-adjust: 100%; }}

.block-container {{
  padding: 1rem .8rem calc(var(--fp-navh) + 2.4rem) !important;
  max-width: 100% !important;
}}
@media (min-width: 768px) {{
  .block-container {{
    max-width: 46rem !important;
    padding: 1.6rem 1.4rem calc(var(--fp-navh) + 2.4rem) !important;
  }}
}}

h1, h2, h3, h4 {{ letter-spacing: -.02em; color: var(--fp-text); padding: 0 !important; }}
h2 {{ font-size: 1.55rem !important; }}
h3 {{ font-size: 1.2rem !important; }}
h4 {{ font-size: 1.05rem !important; }}
p, li, label, span, .stMarkdown, [data-testid="stMarkdownContainer"] {{ color: var(--fp-text); }}
p, li {{ font-size: 1rem; line-height: 1.6; }}
small {{ color: var(--fp-muted) !important; }}

/* ---------- mobilné skladanie stĺpcov ---------- */
@media (max-width: 640px) {{
  [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; gap: .5rem !important; }}
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
    flex: 1 1 100% !important; min-width: 100% !important; width: 100% !important;
  }}
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {{
    flex-wrap: nowrap !important; gap: .3rem !important;
  }}
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"] {{
    flex: 1 1 0 !important; min-width: 0 !important; width: auto !important;
  }}
  .st-key-bottomnav [data-testid="stHorizontalBlock"],
  div[class*="st-key-row-"] [data-testid="stHorizontalBlock"],
  div[class*="st-key-act-"] [data-testid="stHorizontalBlock"] {{
    flex-wrap: nowrap !important; gap: .4rem !important;
  }}
  .st-key-bottomnav [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
  div[class*="st-key-act-"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
    flex: 1 1 auto !important; min-width: 0 !important; width: auto !important;
  }}
}}

/* ---------- ovládacie prvky ---------- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button,
[data-testid="stPopover"] > div > button {{
  min-height: var(--fp-tap);
  border-radius: var(--fp-radius);
  font-weight: 600;
  font-size: 1rem;
  background: var(--fp-card);
  color: var(--fp-text);
  border: 1px solid var(--fp-line);
  transition: transform .06s ease, background .15s ease, border-color .15s ease;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
  border-color: var(--fp-accent); color: var(--fp-accent);
}}
.stButton > button:active {{ transform: scale(.985); }}
.stButton > button:focus:not([kind="primary"]),
.stButton > button:focus-visible:not([kind="primary"]),
.stDownloadButton > button:focus {{
  background: var(--fp-card) !important;
  color: var(--fp-accent) !important;
  border-color: var(--fp-accent) !important;
  box-shadow: none !important;
  outline: none !important;
}}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
  background: var(--fp-accent) !important;
  border-color: var(--fp-accent) !important;
  color: #fff !important;
  box-shadow: var(--fp-shadow-lg);
}}
.stButton > button[kind="primary"] p {{ color: #fff !important; }}

/* Vstupy majú vlastný obal (stTextInputRootElement a spol.), ktorý si farbu
   berie zo Streamlit témy - v tmavom režime by zostal svetlý. */
input, textarea,
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"],
[data-testid$="RootElement"], [data-baseweb$="RootElement"],
[data-testid="stNumberInputContainer"], [data-testid="stDateInputField"] {{
  background: var(--fp-card) !important;
  color: var(--fp-text) !important;
  border-color: var(--fp-line) !important;
}}
[data-testid$="RootElement"]:focus-within,
[data-baseweb="input"]:focus-within {{
  border-color: var(--fp-accent) !important; box-shadow: none !important;
}}
input::placeholder, textarea::placeholder {{ color: var(--fp-muted) !important; }}
/* tlačidlo na odkrytie hesla a krokovanie čísel */
.stTextInput button, .stNumberInput button {{
  background: transparent !important; border: none !important;
  color: var(--fp-muted) !important; min-height: 0 !important;
}}
.stTextInput button:hover, .stNumberInput button:hover {{
  color: var(--fp-accent) !important; background: transparent !important;
}}
.stTextInput input, .stNumberInput input, .stDateInput input, .stTimeInput input {{
  min-height: var(--fp-tap); border-radius: var(--fp-radius) !important;
  font-size: 1rem !important;
}}
.stTextArea textarea {{ min-height: 5.5rem; border-radius: var(--fp-radius) !important;
                        font-size: 1rem !important; }}
[data-baseweb="select"] > div {{
  min-height: var(--fp-tap); border-radius: var(--fp-radius) !important;
  background: var(--fp-card) !important; border-color: var(--fp-line) !important;
  color: var(--fp-text) !important; font-size: 1rem;
}}
[data-baseweb="popover"] [role="listbox"], [data-baseweb="menu"], [role="option"] {{
  background: var(--fp-card) !important; color: var(--fp-text) !important;
}}
[role="option"]:hover {{ background: var(--fp-card-2) !important; }}
[data-baseweb="tag"] {{ background: var(--fp-accent) !important; color: #fff !important; }}
[data-testid="stWidgetLabel"] p {{ font-size: .95rem; color: var(--fp-text-2); }}

[data-testid="stExpander"] {{
  border-radius: var(--fp-radius); border-color: var(--fp-line) !important;
  background: var(--fp-card);
}}
[data-testid="stExpander"] summary {{ font-size: 1rem; min-height: var(--fp-tap); }}
[data-testid="stExpander"] summary p {{ font-size: 1rem !important; }}

[data-testid="stAlert"] {{
  background: var(--fp-card-2) !important; color: var(--fp-text) !important;
  border-radius: var(--fp-radius); font-size: .98rem;
}}
[data-testid="stAlert"] p {{ color: var(--fp-text) !important; }}
[data-testid="stPopoverBody"] {{ background: var(--fp-card) !important; }}
[data-testid="stMetricValue"] {{ font-size: 1.7rem !important; color: var(--fp-text) !important; }}
[data-testid="stMetricLabel"] p {{ font-size: .92rem !important; color: var(--fp-muted) !important; }}
[data-testid="stTabs"] [data-baseweb="tab-list"] {{
  gap: .25rem; overflow-x: auto; scrollbar-width: none; padding-bottom: 2px;
  border-bottom-color: var(--fp-line) !important;
}}
[data-testid="stTabs"] [data-baseweb="tab-list"]::-webkit-scrollbar {{ display: none; }}
[data-testid="stTabs"] [data-baseweb="tab"] {{
  font-size: .95rem; padding: .4rem .8rem; white-space: nowrap; min-height: 2.6rem;
  color: var(--fp-text-2) !important;
}}
[data-testid="stTabs"] [aria-selected="true"] {{ color: var(--fp-accent) !important; }}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{ background: var(--fp-accent) !important; }}
/* Streamlit má prechod pri šípkach rolovania natvrdo na svetlé pozadie */
[data-testid="stTabsScrollRight"] {{
  background-image: linear-gradient(to right, rgba(0,0,0,0), var(--fp-bg) 45%) !important;
  color: var(--fp-text) !important;
}}
[data-testid="stTabsScrollLeft"] {{
  background-image: linear-gradient(to left, rgba(0,0,0,0), var(--fp-bg) 45%) !important;
  color: var(--fp-text) !important;
}}
.stCheckbox p, .stRadio p {{ font-size: 1rem; }}
hr {{ border-color: var(--fp-line) !important; }}
code {{ background: var(--fp-card-2) !important; color: var(--fp-text) !important; }}

/* ---------- horná lišta ---------- */
.fp-topbar-title {{ font-size: 2rem; font-weight: 760; letter-spacing: -.03em; line-height: 1.1; }}
.fp-topbar-sub {{ font-size: .95rem; color: var(--fp-muted); margin-top: .1rem; }}
div[class*="st-key-act-topbar"] {{ margin-bottom: .6rem; }}
div[class*="st-key-themebtn"] button {{
  min-height: 2.8rem !important; height: 2.8rem !important;
  width: 2.8rem !important; min-width: 2.8rem !important;
  padding: 0 !important; border-radius: 50% !important;
  margin-left: auto; display: flex !important;
  align-items: center !important; justify-content: center !important;
  /* všetky stavy explicitne - Streamlit inak pri fokuse pretlačí vlastné farby
     a v tmavom režime z tlačidla spraví bielý kruh s bielou ikonou */
  background: var(--fp-card-2) !important;
  border: 1px solid var(--fp-line) !important;
  color: var(--fp-text) !important;
  box-shadow: none !important;
}}
div[class*="st-key-themebtn"] button:hover,
div[class*="st-key-themebtn"] button:focus,
div[class*="st-key-themebtn"] button:focus-visible,
div[class*="st-key-themebtn"] button:active {{
  background: var(--fp-accent-sf) !important;
  border-color: var(--fp-accent) !important;
  color: var(--fp-accent) !important;
  outline: none !important;
}}
/* Ikona musí sedieť presne v strede kruhu. Streamlit dáva do tlačidla
   niekoľko zanorených obalov s rôznym line-height (32 px / 46 px / 29 px),
   čo ju vertikálne posunie. Zrovnáme celý reťazec obalov. */
div[class*="st-key-themebtn"] button > div,
div[class*="st-key-themebtn"] button > div > span,
div[class*="st-key-themebtn"] button span,
div[class*="st-key-themebtn"] button [data-testid="stIconMaterial"] {{
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  line-height: 1 !important;
  margin: 0 !important;
  padding: 0 !important;
  color: inherit !important;
}}
div[class*="st-key-themebtn"] button [data-testid="stIconMaterial"] {{
  font-size: 1.45rem !important;
  width: 1.45rem !important;
  height: 1.45rem !important;
}}
/* prázdny popisok tlačidla inak zaberá miesto a ikonu vytlačí nahor */
div[class*="st-key-themebtn"] button [data-testid="stMarkdownContainer"],
div[class*="st-key-themebtn"] button p {{
  display: none !important;
}}

/* ---------- zoznamové tlačidlá (rozcestník Viac) ---------- */
div[class*="st-key-act-more-"] button {{
  padding: .7rem .9rem !important; text-align: left !important;
}}
div[class*="st-key-act-more-"] button > div,
div[class*="st-key-act-more-"] button > div > span {{
  justify-content: flex-start !important; align-items: center !important;
  text-align: left !important; width: 100% !important; gap: .7rem !important;
}}
div[class*="st-key-act-more-"] button p {{ text-align: left !important; margin: 0 !important; }}

/* ---------- pás s kontextom dňa (meniny, sviatok) ---------- */
.fp-daystrip {{
  display: flex; flex-wrap: wrap; gap: .35rem;
  margin: -.2rem 0 .85rem;
}}
.fp-event {{
  display: flex; gap: .7rem; align-items: baseline;
  padding: .45rem 0; border-bottom: 1px solid var(--fp-line-soft);
}}
.fp-event:last-child {{ border-bottom: none; }}
.fp-event-time {{
  flex: 0 0 4.6rem; font-variant-numeric: tabular-nums;
  font-weight: 650; color: var(--fp-accent); font-size: .95rem;
}}
.fp-event-title {{ flex: 1 1 auto; color: var(--fp-text); font-size: 1rem; }}
.fp-event-place {{ color: var(--fp-muted); font-size: .85rem; }}

/* ---------- hero: Najbližší krok ---------- */
.fp-hero {{
  background: linear-gradient(160deg, var(--fp-hero-a) 0%, var(--fp-hero-b) 72%);
  border: 1px solid var(--fp-accent-bd);
  border-radius: var(--fp-radius-lg);
  padding: 1.15rem 1.15rem 1.25rem;
  margin-bottom: .75rem;
  box-shadow: var(--fp-shadow-lg);
}}
.fp-hero-kicker {{
  font-size: .74rem; letter-spacing: .13em; text-transform: uppercase;
  color: var(--fp-accent); font-weight: 800;
}}
.fp-hero-step {{
  font-size: 1.65rem; font-weight: 730; line-height: 1.25;
  margin: .5rem 0 .55rem; color: var(--fp-text);
}}
.fp-hero-task {{ font-size: 1rem; color: var(--fp-text-2); }}
.fp-hero-meta {{ font-size: .95rem; color: var(--fp-muted); margin-top: .6rem; }}
@media (min-width: 768px) {{
  .fp-hero {{ padding: 1.6rem 1.7rem; }}
  .fp-hero-step {{ font-size: 2rem; }}
}}

/* ---------- riadok úlohy ---------- */
div[class*="st-key-row-"] {{
  background: var(--fp-card);
  border: 1px solid var(--fp-line);
  border-left: 4px solid var(--fp-p4);
  border-radius: var(--fp-radius);
  padding: .6rem .75rem .7rem;
  margin-bottom: .55rem;
  box-shadow: var(--fp-shadow);
  gap: 0 !important;
}}
div[class*="st-key-row-"] [data-testid="stVerticalBlock"],
div[class*="st-key-row-"] [data-testid="stLayoutWrapper"] {{ gap: 0 !important; }}
div[class*="st-key-row-"] [data-testid="stHorizontalBlock"] {{
  margin: 0 !important; flex-wrap: nowrap !important; gap: .5rem !important;
  align-items: flex-start;
}}
div[class*="st-key-row-"] [data-testid="stElementContainer"] {{ margin: 0 !important; }}
div[class*="st-key-row-"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {{
  flex: 0 0 2.1rem !important; min-width: 2.1rem !important; width: 2.1rem !important;
}}
div[class*="st-key-row-"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) {{
  flex: 1 1 auto !important; min-width: 0 !important; width: auto !important;
}}
div[class*="st-key-row-"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {{
  flex: 0 0 2.3rem !important; min-width: 2.3rem !important; width: 2.3rem !important;
}}
div[class*="st-key-row-"]:has(.fp-pri-q1) {{ border-left-color: var(--fp-p1); }}
div[class*="st-key-row-"]:has(.fp-pri-q2) {{ border-left-color: var(--fp-p2); }}
div[class*="st-key-row-"]:has(.fp-pri-q3) {{ border-left-color: var(--fp-p3); }}
div[class*="st-key-row-"]:has(.fp-pri-q4) {{ border-left-color: var(--fp-p4); }}
div[class*="st-key-row-"]:has(.fp-done) {{ opacity: .55; }}

div[class*="st-key-check-"] [data-testid="stButton"] {{ width: 1.85rem !important; }}
div[class*="st-key-check-"] button {{
  display: inline-flex !important; align-items: center !important; justify-content: center !important;
  width: 1.85rem !important; min-width: 1.85rem !important; max-width: 1.85rem !important;
  height: 1.85rem !important; min-height: 1.85rem !important;
  padding: 0 !important; border-radius: 50% !important;
  border: 2px solid var(--fp-muted) !important;
  background: transparent !important; color: transparent !important;
  margin-top: .3rem; overflow: hidden;
}}
div[class*="st-key-check-"] button:hover {{
  border-color: var(--fp-ok) !important; background: rgba(5,150,105,.16) !important;
}}
div[class*="st-key-check-"] button p, div[class*="st-key-check-"] button div {{
  font-size: 0 !important; color: transparent !important;
}}

div[class*="st-key-title-"] button {{
  background: transparent !important; border: none !important;
  padding: .1rem 0 !important; min-height: 1.6rem !important;
  color: var(--fp-text) !important; line-height: 1.35 !important;
  width: 100% !important; box-shadow: none !important;
}}
div[class*="st-key-title-"] button:hover {{ color: var(--fp-accent) !important; }}
div[class*="st-key-title-"] button > div,
div[class*="st-key-title-"] button span,
div[class*="st-key-title-"] button p {{
  text-align: left !important; justify-content: flex-start !important;
  align-items: flex-start !important; width: 100% !important;
  white-space: normal !important; margin: 0 !important;
  font-size: 1.08rem !important; font-weight: 620 !important;
}}

div[class*="st-key-more-"] button {{
  background: transparent !important; border: none !important;
  color: var(--fp-muted) !important; min-height: 2rem !important;
  padding: 0 !important; justify-content: center !important; box-shadow: none !important;
}}
div[class*="st-key-more-"] button svg {{ display: none !important; }}

.fp-meta {{
  font-size: .9rem; color: var(--fp-muted);
  display: flex; flex-wrap: wrap; align-items: center; gap: .3rem .55rem;
  margin: .25rem 0 0 2.6rem; line-height: 1.5;
}}
.fp-meta-next {{ color: var(--fp-text-2); font-weight: 600; }}
.fp-meta span {{ color: inherit; }}

/* ---------- odznaky ---------- */
.fp-badge {{
  display: inline-flex; align-items: center; gap: .2rem;
  border-radius: 999px; padding: .16rem .55rem;
  font-size: .82rem; font-weight: 640; white-space: nowrap;
  background: var(--fp-b4-bg); color: var(--fp-b4-fg) !important;
}}
.fp-q1, .fp-due-overdue {{ background: var(--fp-b1-bg) !important; color: var(--fp-b1-fg) !important; }}
.fp-q2, .fp-due-soon    {{ background: var(--fp-b2-bg) !important; color: var(--fp-b2-fg) !important; }}
.fp-q3, .fp-due-today   {{ background: var(--fp-b3-bg) !important; color: var(--fp-b3-fg) !important; }}
.fp-q4, .fp-ai, .fp-due-later, .fp-due-none {{
  background: var(--fp-b4-bg) !important; color: var(--fp-b4-fg) !important;
}}
.fp-time {{ background: var(--fp-bt-bg) !important; color: var(--fp-bt-fg) !important; }}
.fp-ctx  {{ background: var(--fp-bc-bg) !important; color: var(--fp-bc-fg) !important; }}

/* ---------- postup, upozornenia, časovač ---------- */
.fp-progress {{ height: .4rem; background: var(--fp-line-soft); border-radius: 99px;
                overflow: hidden; margin-top: .5rem; }}
.fp-progress > div {{ height: 100%; background: var(--fp-accent); border-radius: 99px;
                      transition: width .3s ease; }}
.fp-alert {{
  background: var(--fp-alert); border-left: 4px solid var(--fp-p1);
  border-radius: 14px; padding: .7rem .9rem; margin-bottom: .5rem; font-size: 1rem;
}}
.fp-timer {{
  background: var(--fp-timer-bg); border: 1px solid var(--fp-timer-bd);
  border-radius: var(--fp-radius); padding: .7rem .9rem;
  font-weight: 640; color: var(--fp-timer-fg) !important; font-size: 1rem;
}}
.fp-muted {{ color: var(--fp-muted) !important; font-size: .95rem; line-height: 1.55; }}
.fp-quote {{ border-left: 3px solid var(--fp-line); padding-left: .85rem;
             color: var(--fp-text-2) !important; font-size: 1rem; }}
.fp-divider {{ height: 1px; background: var(--fp-line); margin: 1.3rem 0; border: none; }}
.fp-section {{ font-size: .78rem; letter-spacing: .1em; text-transform: uppercase;
               color: var(--fp-muted) !important; font-weight: 800; margin: 1.2rem 0 .55rem; }}

/* ---------- spodná navigácia ---------- */
.st-key-bottomnav {{
  position: fixed !important; left: 0; right: 0; bottom: 0; z-index: 9990;
  background: var(--fp-navbg);
  backdrop-filter: saturate(180%) blur(14px);
  border-top: 1px solid var(--fp-line);
  padding: .3rem .3rem calc(.3rem + env(safe-area-inset-bottom, 0px)) !important;
  box-shadow: 0 -2px 22px rgba(0,0,0,.10);
}}
.st-key-bottomnav [data-testid="stVerticalBlock"] {{ gap: 0 !important; }}
.st-key-bottomnav [data-testid="stHorizontalBlock"] {{ gap: .1rem !important; }}
.st-key-bottomnav .stButton > button {{
  display: flex !important; flex-direction: column !important;
  align-items: center !important; justify-content: center !important;
  gap: .1rem !important; width: 100% !important;
  min-height: 3.4rem !important; padding: .2rem 0 !important;
  border: none !important; background: transparent !important; box-shadow: none !important;
  font-size: .78rem !important; font-weight: 620 !important;
  color: var(--fp-muted) !important; line-height: 1.15 !important;
}}
/* Streamlit dáva ikonu aj text do jedného riadkového spanu - stohujeme ten */
.st-key-bottomnav .stButton > button > div,
.st-key-bottomnav .stButton > button > div > span {{
  display: flex !important;
  flex-direction: column !important;
  align-items: center !important;
  justify-content: center !important;
  gap: .1rem !important;
  width: 100% !important;
}}
.st-key-bottomnav .stButton > button:hover {{ color: var(--fp-accent) !important; }}
.st-key-bottomnav .stButton > button span[data-testid="stIconMaterial"] {{
  font-size: 1.5rem !important;
}}
.st-key-bottomnav .stButton > button p {{ font-size: .78rem !important; margin: 0 !important;
                                          color: inherit !important; }}
.st-key-bottomnav .stButton > button[kind="primary"] {{
  background: transparent !important; color: var(--fp-accent) !important;
}}
.st-key-navadd .stButton > button {{
  background: var(--fp-accent) !important; color: #fff !important;
  border-radius: 1.2rem !important; min-height: 3rem !important; margin-top: .2rem;
  box-shadow: var(--fp-shadow-lg) !important;
}}
.st-key-navadd .stButton > button p {{ font-size: .72rem !important; color: #fff !important; }}
@media (min-width: 768px) {{
  .st-key-bottomnav {{
    left: 50%; transform: translateX(-50%); max-width: 46rem; right: auto; width: 100%;
    border-radius: var(--fp-radius-lg) var(--fp-radius-lg) 0 0;
    border: 1px solid var(--fp-line); border-bottom: none;
  }}
}}

/* ---------- prihlásenie ---------- */
/* voľba účet/prihlásenie ako dve veľké tlačidlá, nie drobné rádio */
.stRadio [role="radiogroup"] {{ gap: .5rem !important; }}
.stRadio [role="radiogroup"] label {{
  border: 1px solid var(--fp-line); border-radius: var(--fp-radius);
  padding: .7rem .9rem; background: var(--fp-card); width: 100%;
  min-height: var(--fp-tap); align-items: center;
}}
.stRadio [role="radiogroup"] label:hover {{ border-color: var(--fp-accent); }}
.fp-login-logo {{ font-size: 3rem; line-height: 1; margin-bottom: .3rem; }}
.fp-login-title {{ font-size: 2.1rem; font-weight: 780; letter-spacing: -.03em; }}
</style>
"""


# =============================================================================
#  Verejné API
# =============================================================================

def inject() -> None:
    st.markdown(_css(is_dark(), _root_px()), unsafe_allow_html=True)


def topbar(title: str, subtitle: str = "") -> None:
    """Hlavička obrazovky + rýchly prepínač svetlý/tmavý režim."""
    with st.container(key="act-topbar"):
        left, right = st.columns([0.8, 0.2])
        with left:
            st.markdown(
                f'<div class="fp-topbar-title">{title}</div>'
                + (f'<div class="fp-topbar-sub">{subtitle}</div>' if subtitle else ""),
                unsafe_allow_html=True)
        with right:
            theme_button("theme_toggle")


def theme_button(key: str = "theme_toggle") -> None:
    """Prepínač svetlý/tmavý režim. Prepína medzi zvolenou svetlou a tmavou schémou."""
    with st.container(key=f"themebtn_{key}"):
        dark = is_dark()
        if st.button("", icon=icons.st(icons.LIGHT_MODE if dark else icons.DARK_MODE),
                     key=key, help="Prepnúť svetlý / tmavý režim"):
            st.session_state["ui_dark"] = not dark
            st.rerun()


def appearance_controls() -> None:
    """Ovládanie vzhľadu - obrazovka Viac."""
    section("Vzhľad")

    dark = is_dark()
    mode = st.radio("Režim", ["Svetlý", "Tmavý"], index=1 if dark else 0,
                    horizontal=True, key="ui_mode_radio", label_visibility="collapsed")
    if (mode == "Tmavý") != dark:
        st.session_state["ui_dark"] = (mode == "Tmavý")
        st.rerun()

    if dark:
        _scheme_picker(True, "Tmavá schéma", "ui_dark_scheme", dark_scheme())
    else:
        _scheme_picker(False, "Svetlá schéma", "ui_light_scheme", light_scheme())

    with st.expander("Nastaviť aj druhý režim"):
        if dark:
            _scheme_picker(False, "Svetlá schéma", "ui_light_scheme", light_scheme(),
                           suffix="_alt")
        else:
            _scheme_picker(True, "Tmavá schéma", "ui_dark_scheme", dark_scheme(),
                           suffix="_alt")

    names = list(SCALES.keys())
    current = scale_name()
    choice = st.select_slider("Veľkosť rozhrania", options=names, value=current,
                              key="ui_scale_slider")
    if choice != current:
        st.session_state["ui_scale"] = choice
        st.rerun()
    st.markdown('<div class="fp-muted">Mení veľkosť celého rozhrania, nielen textu.</div>',
                unsafe_allow_html=True)


def _scheme_picker(dark: bool, label: str, state_key: str, current: str,
                   suffix: str = "") -> None:
    options = schemes.names(dark)
    index = options.index(current) if current in options else 0
    choice = st.selectbox(label, options, index=index, key=f"{state_key}_select{suffix}")
    st.markdown(schemes.swatch_html(choice, dark), unsafe_allow_html=True)
    if choice != current:
        st.session_state[state_key] = choice
        st.rerun()


def section(label: str) -> None:
    st.markdown(f'<div class="fp-section">{label}</div>', unsafe_allow_html=True)


def divider() -> None:
    st.markdown('<hr class="fp-divider">', unsafe_allow_html=True)
