"""Anthropic Claude - analýza rizík, výziev a spätná väzba k úlohe."""

from __future__ import annotations

import time

from ai.base import ANALYSIS_SCHEMA, SYSTEM_PROMPT, AIProvider, AIResult, parse_payload

DEFAULT_MODEL = "claude-opus-5"


class ClaudeProvider(AIProvider):
    name = "anthropic"
    label = "Claude"
    icon = "auto_awesome"

    def analyze(self, prompt: str) -> AIResult:
        model = self.model or DEFAULT_MODEL
        if not self.api_key:
            return AIResult(provider=self.name, model=model, ok=False,
                            error="Chýba ANTHROPIC API kľúč.")
        try:
            import anthropic
        except ImportError:
            return AIResult(provider=self.name, model=model, ok=False,
                            error="Balík 'anthropic' nie je nainštalovaný (pip install anthropic).")

        client = anthropic.Anthropic(api_key=self.api_key)
        started = time.perf_counter()

        base_kwargs = {
            "model": model,
            "max_tokens": 16000,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
            "output_config": {
                "format": {"type": "json_schema", "schema": ANALYSIS_SCHEMA},
            },
        }

        # Postupné varianty: najbohatšia najprv, pri chybe sa degraduje.
        # 1) beta endpoint so serverovým fallbackom pri odmietnutí + adaptívne myslenie
        # 2) štandardný endpoint s adaptívnym myslením
        # 3) štandardný endpoint bez myslenia (staršie SDK)
        attempts = [
            ("beta", {**base_kwargs,
                      "thinking": {"type": "adaptive"},
                      "betas": ["server-side-fallback-2026-07-01"],
                      "fallbacks": "default"}),
            ("plain", {**base_kwargs, "thinking": {"type": "adaptive"}}),
            ("plain", base_kwargs),
        ]

        last_error: Exception | None = None
        for endpoint, kwargs in attempts:
            try:
                if endpoint == "beta":
                    response = client.beta.messages.create(**kwargs)
                else:
                    response = client.messages.create(**kwargs)
            except Exception as exc:  # neznámy parameter / nepodporovaná beta / API chyba
                last_error = exc
                continue

            latency = int((time.perf_counter() - started) * 1000)

            if getattr(response, "stop_reason", None) == "refusal":
                details = getattr(response, "stop_details", None)
                category = getattr(details, "category", None) if details else None
                return AIResult(provider=self.name, model=model, ok=False,
                                latency_ms=latency,
                                error=f"Model odmietol odpovedať (kategória: {category}).")

            text = "".join(block.text for block in response.content
                           if getattr(block, "type", None) == "text")
            payload = parse_payload(text)
            return AIResult(
                provider=self.name,
                model=getattr(response, "model", model),
                ok=payload is not None,
                payload=payload,
                raw_text=text,
                latency_ms=latency,
                error=None if payload else "Odpoveď sa nepodarilo prečítať ako JSON.",
                extra={"usage": getattr(response, "usage", None).__dict__
                       if getattr(response, "usage", None) else {}},
            )

        return AIResult(provider=self.name, model=model, ok=False,
                        latency_ms=int((time.perf_counter() - started) * 1000),
                        error=f"Volanie Claude zlyhalo: {last_error}")
