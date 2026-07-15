"""
Foundry V1.0 Validation Harness
================================

Proves the V1.0 North Star with REAL models over REAL documents:

  1. knowledge is derived from immutable source events
  2. provenance is preserved throughout
  3. memory belongs to the substrate, not the model
  4. models are replaceable compute over user-owned state
  5. the system continues functioning when the model changes

Usage
-----
    export ANTHROPIC_API_KEY=...        # and/or
    export OPENAI_API_KEY=...
    python3 run_v1.py [file1.md file2.txt export.json ...]

With both keys set, the harness swaps between Anthropic and OpenAI
mid-session — the strongest form of the demonstration. With one key it
swaps between two model sizes from the same vendor. With no keys it
refuses to claim validation and falls back to mocks with a loud warning.

If no files are given, it ingests its own repository documents
(README.md, ASSESSMENT.md) — real documents by any definition.

Output: a validation transcript written to v1_transcript.md, suitable
for archiving as evidence.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from foundry.eventlog import EventLog
from foundry.kernel import Kernel
from foundry.ingestors import (ingest_chatgpt_export,
                               ingest_claude_export, ingest_file)
from foundry.models import MockModelAlpha, MockModelBeta

DATA = Path("v1_data/events.jsonl")
TRANSCRIPT = Path("v1_transcript.md")

QUESTIONS = [
    "What is the central architectural claim of Foundry?",
    "What must every claim contain?",
    "What does the hash chain detect?",
]


def pick_models():
    """Two distinct models = a visible swap. Prefer cross-vendor."""
    ant, oai = os.environ.get("ANTHROPIC_API_KEY"), os.environ.get("OPENAI_API_KEY")
    if ant and oai:
        from foundry.models import AnthropicAdapter, OpenAIAdapter
        return AnthropicAdapter(ant), OpenAIAdapter(oai), True
    if ant:
        from foundry.models import AnthropicAdapter
        return (AnthropicAdapter(ant, "claude-sonnet-4-6"),
                AnthropicAdapter(ant, "claude-haiku-4-5-20251001"), True)
    if oai:
        from foundry.models import OpenAIAdapter
        return (OpenAIAdapter(oai, "gpt-4o"),
                OpenAIAdapter(oai, "gpt-4o-mini"), True)
    return MockModelAlpha(), MockModelBeta(), False


def ingest_inputs(k: Kernel, paths: list[str]) -> list[dict]:
    if not paths:
        paths = ["README.md", "docs/architecture.md"]
    events = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            print(f"  skipping missing file: {p}")
            continue
        if path.suffix == ".json":
            text = path.read_text(encoding="utf-8")
            fn = ingest_chatgpt_export if '"mapping"' in text else ingest_claude_export
            events += fn(k, path)
        else:
            events += ingest_file(k, path)
    return events


def main(argv: list[str]) -> int:
    model_a, model_b, real = pick_models()
    out = [f"# Foundry V1.0 Validation Transcript",
           f"run: {time.strftime('%Y-%m-%d %H:%M:%S')}",
           f"models: {model_a.name} -> {model_b.name}",
           f"real models: {real}", ""]
    if not real:
        print("!" * 70)
        print("! NO API KEYS FOUND — running with mock models.")
        print("! This exercises the architecture but does NOT constitute")
        print("! V1.0 validation. Set ANTHROPIC_API_KEY / OPENAI_API_KEY.")
        print("!" * 70)

    k = Kernel(EventLog(DATA), model_a)

    # -- North Star 1: knowledge derived from immutable source events
    events = ingest_inputs(k, argv)
    out.append(f"## Ingested {len(events)} events (originals preserved verbatim)")
    assert k.log.verify(), "hash chain broken"
    out.append("hash chain: OK\n")

    out.append(f"## Derivation by {model_a.name}")
    for e in k.underived(by_model=model_a.name):
        claims = k.derive(e["id"])
        out.append(f"- event {e['id'][:8]} ({e['payload']['source']}): "
                   f"{len(claims)} claims")
    n_a = len(k.canon.active())
    out.append(f"total active claims: {n_a}\n")

    # -- North Star 2: provenance preserved throughout
    active = k.canon.active()
    if not active:
        print("ERROR: zero claims extracted — cannot validate provenance.")
        print("With mocks, ingest documents containing declarative sentences.")
        return 2
    sample = active[0]
    why = k.why(sample.id)
    out.append("## Provenance check ('why do you believe this?')")
    out.append(f"claim: {sample.statement}")
    out.append(f"derived_by: {why['derived_by']}")
    out.append(f"source event: {why['source_events'][0]['id'][:8]} "
               f"({why['source_events'][0]['payload']['source']})")
    out.append(f"evidence: {why['evidence'][:1]}\n")

    # -- North Star 3: memory belongs to substrate — destroy and rebuild
    from foundry.canon import Canon
    before = {c.id: c.to_dict() for c in k.canon.claims.values()}
    k.canon.rebuild()
    rebuilt = {c.id: c.to_dict() for c in k.canon.claims.values()}
    independent = {c.id: c.to_dict() for c in Canon(k.log).claims.values()}
    assert before == rebuilt == independent, "replay is not deterministic"
    out.append("## Deterministic replay")
    out.append("three independently-computed Canons (incremental, rebuilt,")
    out.append("fresh-from-log) are byte-identical: OK\n")

    # -- North Star 4 & 5: swap the model, keep working
    out.append(f"## MODEL SWAP: {model_a.name} -> {model_b.name} (one line, no migration)")
    k.swap_model(model_b)
    for q in QUESTIONS:
        r = k.ask(q)
        out.append(f"\nQ: {q}")
        out.append(f"A ({r['model']}): {r['answer'][:400]}")
        for c in r["citations"][:2]:
            out.append(f"  cite: '{c['claim'][:90]}' "
                       f"[derived by {c['derived_by']}, "
                       f"event {c['source_events'][0][:8]}]")
    out.append("")

    # New model derives into the SAME substrate
    e2 = k.ingest(
        "Foundry V1.0 validation was executed on "
        + time.strftime("%d %B %Y") + ". The harness swapped models mid-session.",
        source="v1-harness",
    )
    k.derive(e2["id"])
    actors = {c.derived_by for c in k.canon.claims.values()}
    out.append(f"## Coexistence: claims in canon derived by: {sorted(actors)}")
    assert len(actors) >= 2, "swap not visible in provenance"
    assert k.log.verify()
    out.append("final hash chain: OK\n")

    verdict = ("VALIDATED with real models." if real else
               "ARCHITECTURE EXERCISED — mocks only. Not V1.0 validation.")
    out.append(f"## Verdict: {verdict}")
    TRANSCRIPT.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))
    print(f"\ntranscript written to {TRANSCRIPT}")
    return 0 if real else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
