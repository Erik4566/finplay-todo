# 🎯 FinPlay ToDo

Projektový manažér v **Streamlite**, navrhnutý pre ADHD. Neuloží ti úlohu, kým nevieš,
čím začneš — a vždy ti povie práve jednu vec, ktorú máš urobiť teraz.

---

## Rýchly štart

```bash
pip install -r requirements.txt
streamlit run app.py
```

> Tento priečinok je v OneDrive. Ak si vytváraš virtuálne prostredie, daj ho **mimo
> OneDrive** (napr. `python -m venv C:\venvs\finplay`) — inak sa bude synchronizovať
> vyše 500 MB balíčkov.

Appka nabehne aj **bez akejkoľvek konfigurácie**: použije lokálnu SQLite databázu
(`finplay_local.db`), lokálne účty a demo AI analýzu. Konfigurácia sa dopĺňa postupne
a nič v kóde sa pritom nemení.

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

---

## Čo appka robí

### Zápis úlohy vyžaduje rozklad
Sprievodca (`➕ Nová úloha`) má päť krokov a tlačidlo *Uložiť* zostáva zablokované, kým:

1. úloha nemá názov,
2. nemá aspoň **3 kroky** (nastaviteľné cez `app.min_steps`),
3. nie je priradená aspoň jednej osobe.

Pri každom kroku sa pýta odhad času; ich súčet sa predvyplní ako celkový odhad úlohy.
Dôležitosť aj urgentnosť sa zadávajú samostatne na škále 1–5 a rovno sa zobrazí
výsledný **Eisenhowerov kvadrant**.

Ak na sprievodcu práve nemáš hlavu, `⚡ Rýchle zachytenie` uloží nápad do Inboxu
s jediným krokom „Rozložiť na kroky“ — pravidlo rozkladu tým nepadá, len sa odloží.

### Najbližší krok
Domovská obrazovka `🎯 Dnes` ukazuje **jednu úlohu a jeden krok**. Vyberá ho skóre
z priority, termínu, rozrobenosti a dĺžky. Cez „Nastaviť, na čo mám teraz kapacitu“
sa dá výber zúžiť podľa energie, voľného času a kontextu (`@počítač`, `@telefón`…).
Tlačidlo *Iná úloha* preskočí návrh bez pocitu viny.

### Riziká, výzvy a viac AI modelov
Každá úloha má priestor na riziká (čo sa môže pokaziť; závažnosť × pravdepodobnosť)
a výzvy (čo bude ťažké). Záložka `🤖 AI analýza` pustí **Claude, Gemini aj GPT naraz**
(paralelne) a postaví ich odpovede vedľa seba: zhrnutie, chýbajúce kroky, riziká,
ADHD tipy, kritická spätná väzba na zadanie a odhad času. Návrhy sa dajú jedným
tlačidlom prevziať do úlohy. Všetky výstupy sa ukladajú do histórie.

Bez API kľúčov beží **demo analýza** (heuristiky), aby bolo vidieť, ako to vyzerá.

### Ďalšie
| Funkcia | Kde |
|---|---|
| Sledovanie času | Štart/stop na karte, v hero paneli aj v postrannom paneli; porovnanie odhad vs. realita |
| Opakujúce sa úlohy | Pri dokončení sa automaticky vytvorí ďalší výskyt vrátane krokov a priradení |
| Upozornenia | Pripomienky v aplikácii alebo e-mailom; banner s úlohami po termíne |
| Zdieľanie e-mailom | HTML e-mail s krokmi, prioritou a rizikami; fallback = kopírovateľný text |
| Globálne vyhľadávanie | Naprieč úlohami, krokmi, projektmi, rizikami aj AI výstupmi |
| Archív | Dokončené a archivované úlohy/projekty vrátane nameraného času |
| Export | `.ics` pre jednu úlohu aj celý filtrovaný zoznam |
| Kontext dňa | Meniny, štátny sviatok, odpočet do najbližšieho sviatku |
| Spätná väzba | Zápis trenia priamo v appke, s obrázkami; export .md / .zip |
| Dnešný kalendár | Zoznam udalostí z Google Calendara s časmi (po pripojení účtu) |

### Kontext dňa — meniny a sviatky

Pod hlavičkou obrazovky `Dnes` sú dva odznaky: **kto má meniny** a **najbližší
sviatok** (alebo že dnes sviatok je). Krajina sa prepína v `Nastavenia → Kalendár`,
kde je aj celá tabuľka sviatkov na tri roky dopredu a stav overenia dát.

#### Sviatky — počítané zo zákona

| | Zdroj | Overené |
|---|---|---|
| 🇸🇰 | [zákon č. 241/1993 Z. z.](https://static.slov-lex.sk/static/SK/ZZ/1993/241/20210101.print.html) | do 2027 |
| 🇨🇿 | [zákon č. 245/2000 Sb.](https://ppropo.mpsv.cz/zakon_245_2000) | do 2027 |

Slovenský zákon rozlišuje dve veci, ktoré sa bežne zamieňajú, preto sú v modeli
dva nezávislé príznaky `state` a `rest`:

- **28. 10.** je štátny sviatok (§ 1), ale podľa § 2 ods. 3 **nie je** dňom
  pracovného pokoja — pracuje sa.
- **8. 5.** a **15. 9.** sú naopak dni pracovného pokoja, nie štátne sviatky.
- **Rok 2026:** konsolidačná novela ([zákon č. 261/2025 Z. z.](https://www.podnikajte.sk/zamestnanci-a-hr/sviatky-pracovne-dni-s-priplatkom-8-maj-15-september-2026))
  vyňala 8. máj a 15. september spomedzi dní pracovného pokoja — zostávajú
  sviatkami, ale pracuje sa. Appka to označí ako „sviatok · pracovný deň".

V Česku je to jednoduchšie: podľa § 3 sú všetky štátne aj ostatné sviatky dňami
pracovného pokoja. Novela č. 59/2026 Sb. pridáva len *významný deň* (Deň českej
vlajky, 30. 3.), ktorý je bežným pracovným dňom.

Pohyblivé sviatky (Veľký piatok, Veľkonočný pondelok) sa **počítajú** z Veľkej
noci podľa Meeusovho/Butcherovho algoritmu — platí pre gregoriánsky kalendár bez
obmedzenia roku. Tabuľka teda funguje aj o desať rokov bez zásahu.

> **Ako to zostáva aktuálne:** zákon sa nedá dopočítať, mení sa novelou. Preto má
> modul konštantu `VERIFIED_UNTIL` — keď appka beží v roku, ktorý presahuje
> overené obdobie, upozorní na to v `Nastavenia → Kalendár` a odkáže na úplné
> znenie. Doplnenie novely je vtedy úprava jedného riadku.

#### Meniny — z oficiálneho zdroja

🇸🇰 **Slovensko** má oficiálny zdroj: [Oficiálne kalendárium](https://www.culture.gov.sk/sk/oficialne-kalendarium)
kalendárovej komisie pri Ministerstve kultúry SR. Súbor
[`data/meniny_sk.json`](data/meniny_sk.json) je automaticky naparsovaný priamo
z ministerského PDF — 366 dní vrátane 29. februára, žiadny nechýba.

Aktualizácia (nájde najnovší ročník, ukáže rozdiely, nič neprepíše ticho):

```bash
python tools/update_calendar.py            # len skontroluje a vypíše zmeny
python tools/update_calendar.py --zapisat  # zapíše
```

🇨🇿 **Česko oficiálny kalendár mien nemá.** Nepôsobí tam kalendárová komisia ani
iná inštitúcia, ktorá by mená k dňom prideľovala — každé vydavateľstvo si ich
určuje samo (zdroj: Ústav pro jazyk český AV ČR). Preto je
[`data/meniny_cz.json`](data/meniny_cz.json) zámerne prázdny; appka pri českom
nastavení meniny jednoducho nezobrazí, kým si tam vlastný zoznam nedoplníš.
Formát je rovnaký ako v slovenskom súbore.

### Spätná väzba k aplikácii

`Viac → Spätná väzba`. Štyri typy (nefunguje / zdržuje / nápad / otázka), popis,
až štyri obrázky a príznak „blokuje ma to". Obrazovka, verzia appky, téma, schéma
a krajina sa doplnia samy — netreba ich písať.

**Obrázky sa ukladajú do databázy** (zmenšené na 1600 px a prekódované, typicky
150–400 kB), nie na disk. Dôvod: appka má bežať aj nasadená v cloude, kde je
súborový systém dočasný a prílohy zapísané na disk by zmizli pri každom reštarte.
Pri lokálnom behu sa navyše uloží kópia do `data/feedback/`.

Celý zoznam sa dá stiahnuť ako `.md` (prehľad) alebo `.zip` (prehľad + prílohy) —
tým sa dá odovzdať naraz aj s kontextom.

### Dnešný kalendár

Po pripojení Google účtu (`Nastavenia → Integrácie`) sa na obrazovke `Dnes`
zobrazí rozbaľovací zoznam dnešných udalostí — čas, názov a miesto, celodenné
udalosti navrchu. Bez pripojeného účtu sa ukáže len tichá výzva na pripojenie.

---

## Napojenie na Supabase

1. Vytvor projekt na [supabase.com](https://supabase.com).
2. **SQL Editor → New query** → vlož celý obsah [`sql/schema.sql`](sql/schema.sql) → *Run*.
   Skript je idempotentný, dá sa spustiť opakovane.
3. **Project Settings → API** → skopíruj `Project URL` a `anon public` kľúč do
   `.streamlit/secrets.toml`:

```toml
[supabase]
url = "https://xxxx.supabase.co"
anon_key = "eyJhbGciOi..."
```

Schéma obsahuje 13 tabuliek a kompletné **Row Level Security** politiky: úlohu vidí
vlastník, člen projektu alebo priradená osoba. Rekurzii v politikách sa predchádza
`SECURITY DEFINER` funkciami `is_project_member()` a `can_access_task()`.

Profil sa vytvára triggerom po registrácii; appka má aj poistku, keby trigger chýbal.

> Prechodom na Supabase sa dáta z lokálneho režimu **neprenášajú** — lokálny režim je
> na vyskúšanie, nie na migráciu.

---

## AI modely

```toml
[ai.anthropic]
api_key = "sk-ant-..."
model = "claude-opus-5"

[ai.gemini]
api_key = "AIza..."
model = "gemini-2.5-pro"

[ai.openai]
api_key = "sk-..."
model = "gpt-4o"
```

Alternatívne premenné prostredia: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`.
Model sa dá kedykoľvek prepísať v konfigurácii — kód žiadne ID nezamyká.

Volanie Claude ide cez oficiálne Anthropic SDK so **štruktúrovaným výstupom**
(`output_config.format`), adaptívnym myslením a serverovým fallbackom pri odmietnutí;
ak SDK niektorý parameter nepozná, adaptér sa sám degraduje na jednoduchšie volanie.
Každý model beží vo vlastnom vlákne, takže tri modely trvajú približne ako jeden.

`⚙️ Nastavenia → AI modely` má tlačidlo *Otestovať*, ktoré overí kľúč aj latenciu.

---

## Integrácie kalendárov

Obe integrácie sú napísané naplno vrátane OAuth2 a obnovy tokenov. Bez prihlasovacích
údajov bežia v **mock režime**: úloha sa neodošle, ale zapíše sa do `sync_log`
a export `.ics` funguje vždy. Po doplnení údajov sa zapnú bez zmeny kódu.

### Google Calendar
1. Google Cloud Console → *APIs & Services* → povoľ **Google Calendar API**.
2. *Credentials* → **OAuth client ID** → typ *Web application*.
3. *Authorized redirect URIs*: `http://localhost:8501`.
4. `client_id` a `client_secret` do sekcie `[google]`.
5. V appke: `⚙️ Nastavenia → Integrácie` → *Získať odkaz* → prihlásiť sa → vložiť
   `?code=` z návratovej adresy (alebo celú URL).

Úloha sa odošle ako udalosť s popisom, zoznamom krokov, pripomienkou 30 minút vopred
a `RRULE` pri opakovaní. Opakovaný odoslaním sa udalosť aktualizuje, nevytvára duplicitu.

### Microsoft To Do
1. Azure Portal → *App registrations* → **New registration**.
2. Redirect URI typu *Web*: `http://localhost:8501`.
3. *API permissions* → delegované: `Tasks.ReadWrite`, `User.Read`, `offline_access`.
4. *Certificates & secrets* → nový client secret.
5. Údaje do sekcie `[microsoft]`, potom rovnaký postup v Nastaveniach.

Kroky úlohy sa prenesú ako **checklist položky**, dôležitosť sa mapuje z kombinácie
dôležitosť + urgentnosť. Zoznam sa vytvorí automaticky podľa `todo_list_name`.

---

## E-mail (SMTP)

```toml
[smtp]
host = "smtp.gmail.com"
port = 587
username = "ty@firma.sk"
password = "app-password"
from_email = "ty@firma.sk"
use_tls = true
```

Gmail vyžaduje **App Password** (so zapnutým dvojfaktorom), nie bežné heslo.
`⚙️ Nastavenia → E-mail` pošle testovaciu správu.

Bez SMTP zdieľanie nespadne — appka to jasne oznámi a ponúkne kopírovateľný text úlohy.

---

## Štruktúra

```
app.py                    vstupný bod, prihlásenie, navigácia
core/
  config.py               secrets.toml + premenné prostredia
  db.py                   dátová vrstva: Supabase (PostgREST) | lokálna SQLite
  models.py               číselníky, Eisenhower, skóre priority, formátovanie
  auth.py                 Supabase Auth + lokálne účty (PBKDF2)
  repo.py                 všetky operácie nad dátami
  recurrence.py           podmnožina RRULE + popis v slovenčine
  calendars.py            sviatky SK/CZ (počítané zo zákona) + meniny
  feedback.py             spätná väzba k appke vrátane príloh
  notifications.py        pripomienky, zdieľanie, textový export
ai/
  base.py                 spoločná schéma odpovede, prompt, parsovanie
  claude.py               Anthropic SDK
  gemini.py               google-genai
  openai_provider.py      OpenAI
  orchestrator.py         paralelný beh, demo režim, prevzatie návrhov
integrations/
  google_calendar.py      OAuth2 + Calendar API
  microsoft_todo.py       MSAL + Microsoft Graph
  email_smtp.py           SMTP + HTML šablóny
  ics.py                  export do iCalendar
ui/
  theme.py                CSS ladené pre ADHD
  components.py           karty úloh, odznaky, časovač
  page_*.py               jednotlivé obrazovky
data/meniny_sk.json       kalendár mien z MK SR (automaticky parsovaný)
data/meniny_cz.json       šablóna pre české meniny (bez oficiálneho zdroja)
tools/update_calendar.py  aktualizácia menín z ministerského PDF
sql/schema.sql            Supabase schéma + RLS
```

Dátová vrstva má jedno rozhranie a dve implementácie, takže rovnaký kód repozitára
beží nad Supabase aj nad lokálnou SQLite.

---

## Dizajn: mobile first

Základ je telefón, desktop je nadstavba. Všetky rozmery, medzery a dotykové plochy
sú navrhnuté pre palec; `@media (min-width: 768px)` až potom rozšíri obsah do
centrovaného stĺpca max. 800 px.

**Odkiaľ je čo prevzaté**

| Vzor | Odkiaľ | Kde v appke |
|---|---|---|
| Spodná navigačná lišta s piatimi cieľmi a zvýrazneným „+“ | Todoist, TickTick | `ui/nav.py` |
| Riadok úlohy: kruhové zaškrtávadlo, názov, meta riadok, farebný prúžok priority | Todoist | `components.task_card` |
| Pokojná typografia, veľkorysé medzery, kruhové zaškrtávadlá | Things 3 | `ui/theme.py` |
| Vždy viditeľný odhad aj nameraný čas | TickTick | odznaky a záložka Čas |
| Jedna vec naraz na úvodnej obrazovke | Sunsama, Amie | hero „Najbližší krok“ |

**Piktogramy.** Celé rozhranie používa jednu obrysovú sadu — **Material Symbols
Rounded**, ktorý Streamlit načítava lokálne pre svoje ikony. Žiadne emoji, žiadny
externý request. Vo widgetoch cez `icon=icons.st(...)`, vo vlastnom HTML cez
`icons.html(...)`. Emoji zostali len tam, kde sú **obsahom**: ikona projektu a avatar
používateľa.

> Ikony sa vkladajú ako textové ligatúry, preto každý `<span>` nesie `translate="no"`
> a triedu `notranslate`. Bez toho ich prekladač prehliadača preloží
> (`local_fire_department` → „miestny hasičský zbor“), ligatúra prestane sedieť na
> glyf a namiesto ikony sa vypíše text. Streamlit robí pri svojich ikonách to isté.

**Farebné schémy.** Šesť svetlých a šesť tmavých, od uznávaných autorov: Nord
(Arctic Ice Studio), Solarized (Ethan Schoonover), Dracula (Zeno Rocha), Tokyo Night
(enkia), Gruvbox (Pavel Pertsev), Catppuccin Mocha, Primer/GitHub, Atom One, Rosé Pine
a vlastné Papier + Uhlík. Každá je definovaná len ~14 základnými farbami; odtiene
odznakov, okrajov a gradientov sa **dopočítajú miešaním** (`ui/schemes.py`), takže sú
schémy konzistentné a nedá sa v nich vyrobiť nečitateľný kontrast. Vyberajú sa vo
**Viac → Vzhľad** zvlášť pre svetlý a tmavý režim; prepínač v hlavičke potom prepína
medzi tou dvojicou.

**Tmavý režim a veľkosť rozhrania.** Prepínač 🌙 / ☀️ je v pravom hornom rohu každej
obrazovky, kompletné ovládanie vo **Viac → Vzhľad**. Všetky farby idú cez CSS premenné,
takže tmavý režim je len ich výmena plus prebitie vlastného chrómu Streamlitu
(vstupy, rozbaľovačky, záložky, upozornenia). Veľkosť rozhrania má štyri stupne
(16–22 px) a mení sa cez `html { font-size }` — keďže je všetko v `rem`, škáluje sa
celé rozhranie vrátane komponentov Streamlitu, nielen text. Predvolené je **Veľké**.

**Technické riešenie.** Streamlit stĺpce na úzkom displeji nestohuje, iba ich stláča.
Rieši to `@media (max-width: 640px)`, ktoré `stHorizontalBlock` prepne na
`flex-wrap: wrap`. Riadky, ktoré musia zostať vedľa seba (navigácia, riadok úlohy,
dvojice akčných tlačidiel, metriky), sú z toho vyňaté cez `st.container(key=...)` —
Streamlit z kľúča vyrobí CSS triedu `st-key-<kľúč>`, na ktorú sa dá presne cieliť.

Ikony v navigácii sú Material (`:material/bolt:`), nie emoji — sú monochromatické,
takže aktívna položka sa dá odlíšiť farbou.

---

## Poznámky k dizajnu pre ADHD

- **Jedna vec naraz.** Hero panel „Najbližší krok“ dominuje obrazovke; zvyšok je nižšie.
- **Farba nesie význam**, nie dekoráciu — kvadrant priority a stav termínu.
- **Čas je vždy viditeľný** — odhad na každom kroku, nameraný čas vedľa neho.
- **Žiadne slepé uličky.** Prázdne stavy sú formulované vecne, nie vyčítavo
  („Nemáš žiadnu aktívnu úlohu“, nie „Nič si dnes neurobil“).
- **Preskočiť je legitímne.** *Iná úloha* je rovnocenné tlačidlo, nie únik.
- **Nič sa nestráca.** Archív aj globálne vyhľadávanie siahajú aj na hotové veci.
