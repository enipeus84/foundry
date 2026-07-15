# Foundry Architecture

## The thesis

Foundry demonstrates that durable organisational intelligence can exist
independently of any individual AI model. Knowledge is derived from
immutable source events. Provenance is preserved throughout the system.
Memory belongs to the substrate, not the model. Models are replaceable
compute operating over user-owned state.

## The layers

```
                 ┌─────────────────────────┐
                 │      Model Adapters      │  replaceable witnesses
                 │ mocks │ anthropic │ openai
                 └───────────┬─────────────┘
                             │ extract_claims / answer / name
                 ┌───────────▼─────────────┐
                 │        KERNEL            │  7 operations, no state
                 │ ingest derive retrieve   │
                 │ ask update link resolve  │
                 └─────┬──────────────┬─────┘
                       │ append only  │ replay / apply
             ┌─────────▼────────┐ ┌───▼──────────────┐
             │    EVENT LOG      │ │      CANON        │
             │ immutable JSONL   │→│ derived claims =  │
             │ hash-chained      │ │ pure projection   │
             │ THE ONLY TRUTH    │ │ deletable         │
             └───────────────────┘ └──────────────────┘
```

## Constitutional invariants

These properties are load-bearing. Changing them is a new architecture,
not a new version.

1. **The event log is append-only.** Events are never edited or
   deleted. The log is the only source of truth in the system.
2. **Claim mutations are events.** Derivation, revision, supersession
   and linking all enter the log as events. The Canon has no write path
   of its own — it is a fold over the log and is always rebuildable.
3. **Replay is deterministic.** Projecting the log into the Canon
   involves no model. Two independent replays of the same log produce
   identical state, byte for byte.
4. **Model identity is provenance.** Every derived claim records which
   model asserted it. Models are replaceable, never anonymous — a model
   is a witness with an identity, not an interchangeable executor.
5. **A model failure never corrupts the substrate.** Unparseable model
   output yields zero claims; each event append is atomic.

## Why claims are events

The original design said "claims may evolve, events never do" alongside
"every answer must be traceable." Mutable claims break traceability:
you can answer *why do you believe this* but not *why did you stop
believing that*. Event-sourcing claim mutations resolves the
contradiction and collapses the system to one storage primitive.

## Known, deliberate limitations

- The hash chain detects edits and insertions but not truncation of
  trailing events. External anchoring is a roadmap item.
- Retrieval is word-overlap scoring. Retrieval quality was never the
  thesis under test; an embedding index is a projection and can be
  added without touching the substrate.
- LLM-reported confidences are stored and displayed but are not
  calibrated probabilities. Cross-model corroboration (roadmap) is the
  intended calibration mechanism.
- Single-writer assumption on the log file. Concurrency is roadmap.
