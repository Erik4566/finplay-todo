"""OpenAI GPT - tretí názor do porovnania."""

from __future__ import annotations

import time

from ai.base import SYSTEM_PROMPT, AIProvider, AIResult, parse_payload

DEFAULT_MODEL = "gpt-4o"


class OpenAIProvider(AIProvider):
    name = "openai"
    label = "GPT"
    icon = "blur_on"

    def analyze(self, prompt: str) -> AIResult:
        model = self.model or DEFAULT_MODEL
        if not self.api_key:
            return AIResult(provider=self.name, model=model, ok=False,
                            error="Chýba OPENAI API kľúč.")
        try:
            from openai import OpenAI
        except ImportError:
            return AIResult(provider=self.name, model=model, ok=False,
                            error="Balík 'openai' nie je nainštalovaný (pip install openai).")

        started = time.perf_counter()
        try:
            client = OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            return AIResult(provider=self.name, model=model, ok=False,
                            latency_ms=int((time.perf_counter() - started) * 1000),
                            error=f"Volanie OpenAI zlyhalo: {exc}")

        latency = int((time.perf_counter() - started) * 1000)
        text = (response.choices[0].message.content or "") if response.choices else ""
        payload = parse_payload(text)
        return AIResult(
            provider=self.name, model=model, ok=payload is not None,
            payload=payload, raw_text=text, latency_ms=latency,
            error=None if payload else "Odpoveď sa nepodarilo prečítať ako JSON.",
        )
