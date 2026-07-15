# Foundry V1.0 — Validation Runbook

## What V1.0 proves
Durable organisational intelligence independent of any individual model:
immutable events -> attributed claims -> provenance everywhere ->
mid-session model swap with zero state migration.

## Run the validation (your machine, ~5 minutes)
    pip install anthropic openai
    export ANTHROPIC_API_KEY=...     # and/or OPENAI_API_KEY
    python3 scripts/validate.py                          # ingests repo docs, or:
    python3 scripts/validate.py notes.md conversations.json

With both keys: Anthropic derives, OpenAI answers over Anthropic's
claims — the cross-vendor swap. One key: swaps between model sizes.
No keys: mocks, exit code 1, transcript marked NOT validated.

Evidence lands in `v1_transcript.md`. Archive it.

## Real inputs supported
- .md / .txt files (verbatim preservation)
- ChatGPT conversations.json export
- Claude conversation export

## What was deliberately NOT built (Decision Rule applied)
- Conflict detection (resolution exists; detection is V2)
- Cross-model corroboration (Discovery 003 — V2)
- Embedding retrieval (a projection; add anytime without breaking anything)
- Deduplication, UI, auth, deployment

## New in V1.0 over Alpha
- foundry/ingestors.py — real document/conversation ingestion
- Defensive claim parsing — a misbehaving model yields zero claims,
  never substrate corruption
- kernel.underived() — derivation state read from the log itself
- run_v1.py — the validation harness and transcript generator
- see CHANGELOG for the full V1.0 delta
