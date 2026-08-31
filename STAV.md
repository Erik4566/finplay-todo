# Stav projektu

Pracovný denník, nie dokumentácia — tá je v [README.md](README.md). Toto je
odpoveď na otázku „kde sme skončili a prečo je to spravené takto".

**Posledná aktualizácia:** 31. 8. 2026

> **Pravidlo:** tento súbor sa aktualizuje **po každej uzavretej veci** —
> dokončená funkcia, opravená chyba, prijaté rozhodnutie, míľnik, alebo
> zistenie, že sa niečo nedá. Nie po každom kroku. Vždy aj s **dôvodom**:
> po zhrnutí kontextu prežije „čo", vytratí sa „prečo" — a to je pri návrate
> najdrahšie.

---

## Kde to beží

| | |
|---|---|
| Appka | https://finplay-ulohy.streamlit.app |
| Kód | https://github.com/Erik4566/finplay-todo (verejný) |
| Databáza | Supabase, projekt `ctoizpyewbsbfpkvvwwe` |
| Lokálne | `Spustit FinPlay.bat`, prostredie v `C:\venvs\finplay` |

Nasadenie sa aktualizuje samo pri každom `git push` do vetvy `main`.

---

## Čo je overené a čo nie

Toto je najdôležitejšia tabuľka v celom dokumente.

| Časť | Stav |
|---|---|
| Rozhranie, všetky obrazovky | **overené** — AppTest + screenshoty v prehliadači |
| Supabase (registrácia, RLS, zápis/čítanie) | **overené naostro** |
| Nasadenie na Streamlit Cloud | **beží** |
| Sviatky SK/CZ | **overené pri zdroji** (zákon 241/1993, 245/2000) |
| Meniny SK | **overené** — parsované z PDF Ministerstva kultúry SR |
| Google Calendar | kód napísaný, **nikdy nebežal proti živej službe** |
| Microsoft To Do | kód napísaný, **nikdy nebežal proti živej službe** |
| SMTP / e-mail | kód napísaný, **nikdy nebežal proti živej službe** |
| AI modely (Claude, Gemini, GPT) | kód napísaný, **bez kľúčov beží demo režim** |

Pri prvom reálnom spustení integrácií treba počítať s chybami. Presne tak sa
prejavili tri, ktoré sme už opravili — viď nižšie.

---

## Rozhodnutia a ich dôvody

**Dáta cez jedno rozhranie, dve implementácie.** `core/db.py` má `SupabaseBackend`
a `LocalBackend` (SQLite). Appka teda beží aj bez konfigurácie. Vďaka tomu sa
dala vyvíjať a testovať skôr, než existoval Supabase projekt.

**Prílohy spätnej väzby idú do databázy, nie na disk.** Streamlit Cloud má
dočasný súborový systém — súbory zapísané na disk zmiznú pri reštarte. Obrázky
sa preto zmenšia na 1600 px a uložia ako base64 v tabuľke.

**Sviatky sa počítajú, nie tabuľkujú.** Pohyblivé sviatky z Veľkej noci
(Meeusov algoritmus), takže tabuľka platí pre ľubovoľný rok. `VERIFIED_UNTIL`
v `core/calendars.py` hovorí, do ktorého roku bolo znenie zákona ručne overené;
appka na prekročenie upozorní v Nastaveniach.

**České meniny sú zámerne prázdne.** V Česku neexistuje oficiálny kalendár mien
(nepôsobí tam kalendárová komisia). Radšej žiadne dáta než neoveriteľné.

**Ikony sú Material Symbols, nie emoji.** A každá nesie `translate="no"` —
bez toho ich prekladač prehliadača preloží (`local_fire_department` →
„miestny hasičský zbor") a namiesto ikony sa vypíše text. Streamlit robí pri
svojich ikonách to isté.

**Dva GitHub účty.** Repozitár leží pod `Erik4566` (tým je prihlásený git
v termináli), `FinPlay-www` je pridaný ako spolupracovník s právom **admin**
(admin je nutný, inak Streamlit nevie nasadiť). **Uložené prihlásenie pre
github.com sa nesmie prepisovať** — git ho má jedno na hostiteľa a prepnutie
by rozbilo iný rozrobený projekt.

---

## Opravené chyby, ktoré by sa inak vrátili

1. **Konfigurácia zo `secrets.toml` sa vôbec nenačítala.** Streamlit vracia
   vnorené sekcie ako `AttrDict`, ktorý nie je potomkom `dict`. Kontrola
   `isinstance(data, dict)` ticho zlyhala a appka sa tvárila, že Supabase, SMTP
   ani AI kľúče nie sú nastavené. Prejavilo sa až pri prvom reálnom súbore.

2. **`st.tabs` sa po odoslaní formulára prepne späť na prvú záložku.** Na
   prihlasovacej obrazovke to znamenalo, že po neúspešnom pokuse používateľ
   nevidel, kde je, a zdalo sa, že prepnutie na registráciu nefunguje.
   Nahradené voľbou v `session_state`.

3. **Deadlock v lokálnom backende** — `delete()` volal `_load()` zvnútra
   zamknutej sekcie s neresentrantným zámkom. Appka zamrzla.

4. **Tlačidlá s nápovedou majú v DOM skrytý duplikát.** Automatické testy
   klikali a merali ten neviditeľný. Pri hľadaní elementov filtrovať cez
   `offsetParent !== null` alebo `:visible`.

---

## Čo je ďalej

**Najbližšie:** Gemini kľúč (free, ~10 min) → zapne skutočnú AI analýzu rizík
namiesto demo režimu. Je zároveň predpokladom pre hlasové zadávanie úloh.

**Rozpracovaný nápad:** hlasové zachytenie úlohy. `st.audio_input` je
k dispozícii, Gemini zvláda zvuk priamo. Zámer: používateľ nadiktuje jednu
súvislú vetu, appka z nej vyskladá názov, termín, odhad aj rozklad na kroky.
Nedoriešené: či robiť len prepis do políčok, alebo celý rozbor.

**Neriešené obmedzenie:** upozornenia sa vyhodnocujú pri načítaní stránky —
keď je appka zavretá, nič nepríde. Riešiteľné naplánovanou úlohou, ktorá raz
za hodinu spustí rozposielanie. Má zmysel až po nastavení SMTP.

**Nepoužité:** appka zatiaľ neobsahuje ani jednu reálnu úlohu. Než sa pridá
čokoľvek ďalšie, má sa pár dní používať.

---

## Ako čítať spätnú väzbu od používateľa

Je v tabuľke `feedback` v Supabase a chráni ju RLS — z vonku sa nedá prečítať.
Používateľ ju vyexportuje v appke: **Viac → Spätná väzba → Podklad pre vývoj →
„Aj s prílohami (.zip)"**. Balík obsahuje prehľad v Markdowne aj obrázky.
