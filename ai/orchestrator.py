"""Spustenie viacerých AI modelov naraz a uloženie ich spätnej väzby."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from ai.base import AIProvider, AIResult, build_prompt, normalize
from ai.claude import ClaudeProvider
from ai.gemini import GeminiProvider
from ai.openai_provider import OpenAIProvider
from core import config, repo


# =============================================================================
#  Mock - aby appka dávala zmysel aj bez API kľúčov
# =============================================================================

class MockProvider(AIProvider):
    name = "mock"
    label = "Demo analýza"
    icon = "science"

    def available(self) -> bool:
        return True

    def analyze(self, prompt: str) -> AIResult:
        started = time.perf_counter()
        title_line = next((line for line in prompt.splitlines()
                           if line.startswith("**Názov:**")), "")
        title = title_line.replace("**Názov:**", "").strip() or "úloha"
        has_steps = "(žiadne)" not in prompt.split("## Existujúce kroky")[-1][:40]

        payload = {
            "summary": (f"Demo analýza úlohy „{title}“. Bežia len heuristiky, nie skutočný "
                        "model — doplň API kľúč v Nastaveniach a spusť analýzu znova."),
            "first_action": "Otvor dokument/nástroj, v ktorom sa úloha reálne robí, "
                            "a napíš prvú vetu alebo prvý riadok.",
            "missing_steps": ([] if has_steps else [
                {"title": f"Ujasniť, čo presne znamená „hotovo“ pri: {title}",
                 "estimated_minutes": 10,
                 "why": "Bez definície hotovo sa úloha nedá zavrieť."},
                {"title": "Pripraviť podklady a otvoriť potrebné nástroje",
                 "estimated_minutes": 10, "why": "Odstraňuje trenie pri štarte."},
                {"title": "Urobiť prvý viditeľný výstup (aj nedokonalý)",
                 "estimated_minutes": 25, "why": "Prvý výstup rozbehne pozornosť."},
            ]),
            "risks": [
                {"title": "Úloha je príliš veľká na jedno sedenie",
                 "description": "Ak sa nedá dokončiť do 90 minút, hrozí odklad.",
                 "severity": 4, "likelihood": 3,
                 "mitigation": "Rozdeliť na kroky po max. 25 minútach."},
                {"title": "Závislosť na inej osobe",
                 "description": "Čakanie na odpoveď blokuje postup.",
                 "severity": 3, "likelihood": 3,
                 "mitigation": "Poslať otázku hneď na začiatku, nie na konci."},
            ],
            "challenges": [
                {"title": "Rozbeh (activation energy)",
                 "description": "Najťažšia je prvá minúta, nie samotná práca.",
                 "mitigation": "Nastav timer na 5 minút a rob len prvý krok."},
            ],
            "adhd_tips": [
                "Zapni časovač hneď pri prvom kroku — meranie času drží pozornosť.",
                "Zavri všetko okrem jedného okna potrebného na prvý krok.",
                "Ak sa zasekneš na viac ako 10 minút, prepni úlohu do stavu „Zaseknuté“.",
            ],
            "estimated_minutes_total": 60,
            "confidence": 2,
            "feedback": ("Toto je ukážkový výstup. Reálna kritika zadania príde po napojení "
                         "Claude / Gemini / GPT v Nastaveniach."),
        }
        return AIResult(provider=self.name, model="demo", ok=True, payload=payload,
                        raw_text=None,
                        latency_ms=int((time.perf_counter() - started) * 1000))


# =============================================================================
#  Register poskytovateľov
# =============================================================================

PROVIDER_CLASSES = {
    "anthropic": ClaudeProvider,
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
}

# `icon` sú názvy z Material Symbols (viď ui/icons.py), nie emoji.
PROVIDER_META = {
    "anthropic": {"label": "Claude", "icon": "auto_awesome"},
    "gemini": {"label": "Gemini", "icon": "diamond"},
    "openai": {"label": "GPT", "icon": "blur_on"},
    "mock": {"label": "Demo analýza", "icon": "science"},
}


def build_provider(name: str) -> AIProvider:
    if name == "mock":
        return MockProvider()
    cfg = config.ai_config(name)
    return PROVIDER_CLASSES[name](api_key=cfg["api_key"], model=cfg["model"])


def provider_status() -> list[dict]:
    """Prehľad poskytovateľov pre Nastavenia."""
    out = []
    for name in PROVIDER_CLASSES:
        cfg = config.ai_config(name)
        out.append({
            "name": name,
            "label": PROVIDER_META[name]["label"],
            "icon": PROVIDER_META[name]["icon"],
            "model": cfg["model"],
            "configured": bool(cfg["api_key"]),
        })
    return out


def available_providers() -> list[str]:
    names = [p["name"] for p in provider_status() if p["configured"]]
    return names or ["mock"]


# =============================================================================
#  Spustenie analýzy
# =============================================================================

def analyze_task(task_id: str, providers: list[str], extra_question: str = "",
                 persist: bool = True) -> list[AIResult]:
    task = repo.get_task(task_id)
    if not task:
        return []

    steps = repo.list_steps(task_id)
    risks = repo.list_risks(task_id)
    project = repo.get_project(task.get("project_id")) if task.get("project_id") else None
    emails = repo.assignee_emails(task_id)
    prompt = build_prompt(task, steps, risks, project, emails, extra_question)

    def run(name: str) -> AIResult:
        try:
            return build_provider(name).analyze(prompt)
        except Exception as exc:  # poistka, aby jeden model nezhodil ostatné
            return AIResult(provider=name, ok=False, error=f"Neočakávaná chyba: {exc}")

    if len(providers) == 1:
        results = [run(providers[0])]
    else:
        with ThreadPoolExecutor(max_workers=max(1, len(providers))) as pool:
            results = list(pool.map(run, providers))

    if persist:
        for result in results:
            try:
                repo.add_ai_feedback(
                    task_id,
                    provider=result.provider,
                    model=result.model,
                    kind="analysis",
                    summary=(result.payload or {}).get("summary") if result.payload else None,
                    payload=result.payload,
                    raw_text=result.raw_text,
                    latency_ms=result.latency_ms,
                    error=result.error,
                )
            except Exception:
                pass
    return results


def suggest_steps(title: str, description: str = "", provider: str | None = None,
                  minutes: int = 30) -> AIResult:
    """Rýchly rozklad na kroky ešte pred uložením úlohy."""
    name = provider or available_providers()[0]
    fake_task = {"title": title, "description": description, "importance": 3,
                 "urgency": 3, "estimated_minutes": minutes}
    prompt = build_prompt(fake_task, [], [], None, None,
                          "Zameraj sa hlavne na rozklad na najmenšie možné kroky.")
    try:
        return build_provider(name).analyze(prompt)
    except Exception as exc:
        return AIResult(provider=name, ok=False, error=f"Neočakávaná chyba: {exc}")


# =============================================================================
#  Prevzatie návrhov do úlohy
# =============================================================================

def apply_steps(task_id: str, suggestions: list[dict]) -> int:
    count = 0
    for item in suggestions:
        title = (item or {}).get("title", "").strip()
        if not title:
            continue
        repo.add_step(task_id, title, int(item.get("estimated_minutes") or 10))
        count += 1
    return count


def apply_risks(task_id: str, result: AIResult) -> int:
    payload = normalize(result.payload)
    model_label = f"{PROVIDER_META.get(result.provider, {}).get('label', result.provider)}" \
                  f" ({result.model})" if result.model else result.provider
    count = 0
    for risk in payload["risks"]:
        repo.add_risk(task_id, kind="risk", title=risk.get("title", "Riziko"),
                      description=risk.get("description", ""),
                      severity=int(risk.get("severity") or 3),
                      likelihood=int(risk.get("likelihood") or 3),
                      mitigation=risk.get("mitigation", ""),
                      source="ai", source_model=model_label)
        count += 1
    for challenge in payload["challenges"]:
        repo.add_risk(task_id, kind="challenge", title=challenge.get("title", "Výzva"),
                      description=challenge.get("description", ""),
                      severity=3, likelihood=3,
                      mitigation=challenge.get("mitigation", ""),
                      source="ai", source_model=model_label)
        count += 1
    return count
