"""Spoločné rozhranie pre AI modely.

Každý poskytovateľ vracia rovnakú štruktúru (`ANALYSIS_SCHEMA`), takže sa
odpovede od Claude, Gemini a GPT dajú postaviť vedľa seba a porovnať.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from core.models import RISK_KINDS, fmt_minutes  # noqa: F401  (RISK_KINDS pre UI)

# --- Štruktúra odpovede --------------------------------------------------------

ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "2-3 vety: o čo v úlohe naozaj ide a čo je jej skutočný cieľ.",
        },
        "first_action": {
            "type": "string",
            "description": "Jedna konkrétna fyzická akcia na najbližších 5 minút.",
        },
        "missing_steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "estimated_minutes": {"type": "integer"},
                    "why": {"type": "string"},
                },
                "required": ["title", "estimated_minutes", "why"],
                "additionalProperties": False,
            },
        },
        "risks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "severity": {"type": "integer"},
                    "likelihood": {"type": "integer"},
                    "mitigation": {"type": "string"},
                },
                "required": ["title", "description", "severity", "likelihood", "mitigation"],
                "additionalProperties": False,
            },
        },
        "challenges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "mitigation": {"type": "string"},
                },
                "required": ["title", "description", "mitigation"],
                "additionalProperties": False,
            },
        },
        "adhd_tips": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Konkrétne tipy na rozbehnutie a udržanie pozornosti.",
        },
        "estimated_minutes_total": {"type": "integer"},
        "confidence": {"type": "integer"},
        "feedback": {
            "type": "string",
            "description": "Priama kritická spätná väzba na zadanie úlohy.",
        },
    },
    "required": ["summary", "first_action", "missing_steps", "risks", "challenges",
                 "adhd_tips", "estimated_minutes_total", "confidence", "feedback"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "Si skúsený projektový manažér a kouč pre ľudí s ADHD. "
    "Odpovedáš po slovensky, vecne, bez omáčky a bez motivačných fráz. "
    "Tvojou úlohou je rozobrať zadanú úlohu: nájsť chýbajúce kroky, pomenovať riziká "
    "a výzvy, a dať priamu spätnú väzbu na to, či je úloha dobre zadaná. "
    "Kroky navrhuj tak malé, aby sa každý dal začať do 2 minút bez ďalšieho rozhodovania. "
    "Buď kritický - ak je úloha vágna, príliš veľká alebo nemá jasné 'hotovo', napíš to. "
    "Vráť výhradne JSON podľa zadanej schémy, bez komentárov a bez markdown blokov."
)


@dataclass
class AIResult:
    provider: str
    model: str | None = None
    ok: bool = False
    payload: dict | None = None
    raw_text: str | None = None
    error: str | None = None
    latency_ms: int | None = None
    extra: dict = field(default_factory=dict)

    @property
    def summary(self) -> str | None:
        if self.payload:
            return self.payload.get("summary")
        return None


class AIProvider:
    """Základ pre konkrétneho poskytovateľa."""

    name = "base"
    label = "Base"
    icon = "auto_awesome"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key
        self.model = model

    def available(self) -> bool:
        return bool(self.api_key)

    def analyze(self, prompt: str) -> AIResult:  # pragma: no cover - prepisuje potomok
        raise NotImplementedError


# --- Zostavenie promptu --------------------------------------------------------

def build_prompt(task: dict, steps: list[dict], risks: list[dict],
                 project: dict | None = None, assignees: list[str] | None = None,
                 extra_question: str = "") -> str:
    lines = ["# Úloha na analýzu", ""]
    lines.append(f"**Názov:** {task.get('title', '')}")
    if project:
        lines.append(f"**Projekt:** {project.get('emoji', '')} {project.get('name', '')}")
    if task.get("description"):
        lines.append(f"**Popis:** {task['description']}")
    lines.append(f"**Dôležitosť:** {task.get('importance', 3)}/5   "
                 f"**Urgentnosť:** {task.get('urgency', 3)}/5")
    lines.append(f"**Odhad času:** {task.get('estimated_minutes', 0)} min")
    if task.get("due_at"):
        lines.append(f"**Termín:** {task['due_at']}")
    if task.get("energy_level"):
        lines.append(f"**Potrebná energia:** {task['energy_level']}")
    if task.get("context_tag"):
        lines.append(f"**Kontext:** {task['context_tag']}")
    if task.get("recurrence_rule"):
        lines.append(f"**Opakovanie:** {task['recurrence_rule']}")
    if assignees:
        lines.append(f"**Priradené osoby:** {', '.join(assignees)}")

    lines += ["", "## Existujúce kroky"]
    if steps:
        for index, step in enumerate(steps, 1):
            mark = "x" if step.get("is_done") else " "
            lines.append(f"{index}. [{mark}] {step['title']} "
                         f"({step.get('estimated_minutes', 0)} min)")
    else:
        lines.append("(žiadne)")

    lines += ["", "## Už zaznamenané riziká a výzvy"]
    if risks:
        for risk in risks:
            lines.append(f"- [{risk.get('kind')}] {risk.get('title')} — "
                         f"závažnosť {risk.get('severity')}, "
                         f"pravdepodobnosť {risk.get('likelihood')}")
    else:
        lines.append("(žiadne)")

    if extra_question.strip():
        lines += ["", "## Doplňujúca otázka od používateľa", extra_question.strip()]

    lines += [
        "",
        "## Čo od teba chcem",
        "1. Zhodnoť, či je úloha dobre zadaná a či má jasné 'hotovo'.",
        "2. Doplň chýbajúce kroky (len tie, ktoré v zozname naozaj chýbajú).",
        "3. Pomenuj riziká (čo sa môže pokaziť) a výzvy (čo bude ťažké) vrátane zmiernenia.",
        "4. Navrhni jednu konkrétnu prvú akciu na 5 minút.",
        "5. Daj 2-4 praktické ADHD tipy presne pre túto úlohu.",
    ]
    return "\n".join(lines)


# --- Parsovanie odpovede -------------------------------------------------------

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def parse_payload(text: str) -> dict | None:
    """Tolerantné načítanie JSON-u z odpovede modelu."""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK.search(cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def normalize(payload: dict | None) -> dict:
    """Doplní chýbajúce kľúče, aby UI nikdy nepadlo na KeyError."""
    payload = payload or {}
    return {
        "summary": payload.get("summary") or "",
        "first_action": payload.get("first_action") or "",
        "missing_steps": payload.get("missing_steps") or [],
        "risks": payload.get("risks") or [],
        "challenges": payload.get("challenges") or [],
        "adhd_tips": payload.get("adhd_tips") or [],
        "estimated_minutes_total": payload.get("estimated_minutes_total") or 0,
        "confidence": payload.get("confidence") or 0,
        "feedback": payload.get("feedback") or "",
    }
