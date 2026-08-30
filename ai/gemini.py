"""Google Gemini - druhý nezávislý názor na úlohu."""

from __future__ import annotations

import time

from ai.base import ANALYSIS_SCHEMA, SYSTEM_PROMPT, AIProvider, AIResult, parse_payload

DEFAULT_MODEL = "gemini-2.5-pro"


def _to_gemini_schema(schema: dict) -> dict:
    """Gemini neakceptuje 'additionalProperties' - odstránime ho rekurzívne."""
    if isinstance(schema, dict):
        return {k: _to_gemini_schema(v) for k, v in schema.items()
                if k != "additionalProperties"}
    if isinstance(schema, list):
        return [_to_gemini_schema(v) for v in schema]
    return schema


class GeminiProvider(AIProvider):
    name = "gemini"
    label = "Gemini"
    icon = "diamond"

    def analyze(self, prompt: str) -> AIResult:
        model = self.model or DEFAULT_MODEL
        if not self.api_key:
            return AIResult(provider=self.name, model=model, ok=False,
                            error="Chýba GEMINI API kľúč.")
        try:
            from google import genai
        except ImportError:
            return AIResult(provider=self.name, model=model, ok=False,
                            error="Balík 'google-genai' nie je nainštalovaný "
                                  "(pip install google-genai).")

        started = time.perf_counter()
        try:
            client = genai.Client(api_key=self.api_key)
            config = {
                "system_instruction": SYSTEM_PROMPT,
                "response_mime_type": "application/json",
                "response_schema": _to_gemini_schema(ANALYSIS_SCHEMA),
                "temperature": 0.4,
            }
            try:
                response = client.models.generate_content(
                    model=model, contents=prompt, config=config)
            except Exception:
                # staršie/prísnejšie verzie API nemusia schému prijať
                config.pop("response_schema", None)
                response = client.models.generate_content(
                    model=model, contents=prompt, config=config)
        except Exception as exc:
            return AIResult(provider=self.name, model=model, ok=False,
                            latency_ms=int((time.perf_counter() - started) * 1000),
                            error=f"Volanie Gemini zlyhalo: {exc}")

        latency = int((time.perf_counter() - started) * 1000)
        text = getattr(response, "text", None) or ""
        payload = parse_payload(text)
        return AIResult(
            provider=self.name, model=model, ok=payload is not None,
            payload=payload, raw_text=text, latency_ms=latency,
            error=None if payload else "Odpoveď sa nepodarilo prečítať ako JSON.",
        )
