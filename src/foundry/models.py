"""
Model abstraction — the "CPU socket".

The kernel talks to models through exactly one interface:

    ModelAdapter.extract_claims(text) -> list[RawClaim]
    ModelAdapter.answer(question, context) -> str
    ModelAdapter.name -> str

Nothing model-specific exists anywhere else in the system. Swapping
models is one constructor call.

An honest note on the CPU analogy (see ASSESSMENT.md): CPUs share an
instruction set; models do not. Two models given the same text will
extract *different* claims. The architecture survives this only because
model identity is recorded in provenance (the `actor` field on every
derivation event). The model is replaceable, but never anonymous.

Adapters included:
- MockModelAlpha / MockModelBeta: deterministic rule-based extractors,
  used for tests and the acceptance demo (no API key required). They
  deliberately behave differently from each other, which makes the
  swap *visible* rather than hidden.
- AnthropicAdapter / OpenAIAdapter: thin real adapters. Same interface,
  ~30 lines each. Require API keys at runtime.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger("foundry.models")


@dataclass
class RawClaim:
    statement: str
    confidence: float
    evidence: str  # verbatim source text supporting the claim


class ModelAdapter(Protocol):
    name: str

    def extract_claims(self, text: str) -> list[RawClaim]: ...
    def answer(self, question: str, context: str) -> str: ...


# ---------------------------------------------------------------------------
# Deterministic mock models (no network, no keys, fully testable)
# ---------------------------------------------------------------------------

_SENTENCE = re.compile(r"[^.!?\n]+[.!?]")

_FACT_MARKERS = (" is ", " are ", " was ", " were ", " has ", " have ",
                 " will ", " costs ", " prefers ", " uses ", " lives ")


class MockModelAlpha:
    """Extracts declarative sentences containing factual markers."""

    name = "mock-alpha"

    def extract_claims(self, text: str) -> list[RawClaim]:
        claims = []
        for m in _SENTENCE.finditer(text):
            s = m.group().strip()
            low = " " + s.lower()
            if any(k in low for k in _FACT_MARKERS) and "?" not in s:
                claims.append(RawClaim(statement=s, confidence=0.8, evidence=s))
        return claims

    def answer(self, question: str, context: str) -> str:
        return _keyword_answer(self.name, question, context)


class MockModelBeta:
    """
    A different extractor: also catches numbers and named preferences,
    and reports lower confidence. Its divergence from Alpha is the point —
    it demonstrates that model identity must live in provenance.
    """

    name = "mock-beta"

    def extract_claims(self, text: str) -> list[RawClaim]:
        claims = []
        for m in _SENTENCE.finditer(text):
            s = m.group().strip()
            low = " " + s.lower()
            factual = any(k in low for k in _FACT_MARKERS)
            numeric = bool(re.search(r"\d", s))
            if (factual or numeric) and "?" not in s:
                claims.append(RawClaim(statement=s, confidence=0.7, evidence=s))
        return claims

    def answer(self, question: str, context: str) -> str:
        return _keyword_answer(self.name, question, context)


def _keyword_answer(model_name: str, question: str, context: str) -> str:
    """Naive extractive QA: return context lines sharing words with the question."""
    qwords = {w for w in re.findall(r"\w+", question.lower()) if len(w) > 3}
    hits = [ln for ln in context.splitlines()
            if qwords & set(re.findall(r"\w+", ln.lower()))]
    body = " ".join(hits[:3]) if hits else "No relevant knowledge found."
    return f"[{model_name}] {body}"


# ---------------------------------------------------------------------------
# Real adapters — identical interface, swapped in with one line
# ---------------------------------------------------------------------------

_EXTRACT_PROMPT = (
    "Extract atomic factual claims from the text below. Respond ONLY with a "
    'JSON array: [{"statement": str, "confidence": float, "evidence": str}]. '
    "Evidence must be verbatim source text. No prose, no markdown fences.\n\nTEXT:\n"
)


def _parse_claims(raw: str) -> list[RawClaim]:
    """
    Defensive parsing of model output. Models are witnesses, not
    compilers; they occasionally wrap JSON in fences or preamble.
    Strategy: strip fences, then locate the outermost JSON array.
    A model that can't produce parseable claims yields zero claims —
    it never corrupts the substrate.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        text = text.removeprefix("json").strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        items = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    out = []
    for c in items:
        try:
            out.append(RawClaim(
                statement=str(c["statement"]),
                confidence=max(0.0, min(1.0, float(c.get("confidence", 0.5)))),
                evidence=str(c.get("evidence", "")),
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return out


class _RealAdapter:
    """
    Shared logic for real LLM adapters. Vendor subclasses supply only
    `_complete(prompt) -> str` and `name`. This is the entire vendor
    surface area — by design, adding a new provider is ~15 lines.

    Trade-off: no retries or rate-limit handling in V1.0. A failed call
    raises; the substrate is never left half-written because derive()
    appends claim events one at a time and each append is atomic.
    """

    name: str = "real"

    def _complete(self, prompt: str) -> str:  # pragma: no cover - abstract
        raise NotImplementedError

    def extract_claims(self, text: str) -> list[RawClaim]:
        claims = _parse_claims(self._complete(_EXTRACT_PROMPT + text))
        if not claims:
            log.warning("%s returned no parseable claims", self.name)
        return claims

    def answer(self, question: str, context: str) -> str:
        return self._complete(
            f"Answer using ONLY this context.\n\nCONTEXT:\n{context}\n\nQUESTION: {question}"
        )


class AnthropicAdapter(_RealAdapter):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self.name = f"anthropic/{model}"

    def _complete(self, prompt: str) -> str:
        r = self._client.messages.create(
            model=self._model, max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        return r.content[0].text


class OpenAIAdapter(_RealAdapter):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        import openai
        self._client = openai.OpenAI(api_key=api_key)
        self._model = model
        self.name = f"openai/{model}"

    def _complete(self, prompt: str) -> str:
        r = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
        )
        return r.choices[0].message.content
