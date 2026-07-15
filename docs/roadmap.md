# Foundry Roadmap

Everything here was deliberately excluded from V1.0 under the Decision
Rule: it does not strengthen the core demonstration. Each item includes
the rationale for wanting it and the reason it can wait. Nothing here
requires changing the substrate — that is the point of the substrate.

## Near-term candidates (V2 discussion)

**Conflict detection.** Resolution exists (`resolve_conflict`);
*noticing* that two claims contradict does not. A model pass comparing
claim pairs, emitting `claim.conflict` events for human or policy
resolution. Waits because: detection quality depends on real usage
patterns we don't have yet.

**Cross-model corroboration.** The same event derived by two models;
agreement raises confidence via `claim.updated` events. Turns model
divergence — V1.0's documented weakness — into the calibration
mechanism. This is the most commercially interesting item on the list.
Waits because: it doubles derivation cost and needs conflict detection
first.

**Semantic search.** Embedding index as a second projection over the
log — rebuildable, disposable, substrate untouched. Waits because:
word-overlap retrieval is adequate below a few thousand events and
retrieval quality was never the thesis.

**Integrity anchoring.** The hash chain detects edits, not truncation.
Periodically anchor the head hash externally (a file elsewhere, a
timestamping service, a git commit). Small, genuinely useful, first in
the queue.

## Medium-term

**Knowledge evolution & temporal reasoning.** Claims already carry full
history; what's missing is *querying* it — "what did we believe on
1 March?" is a replay-up-to-timestamp, which the architecture gets
almost for free. Waits for a real use case to shape the query surface.

**Trust scoring.** Per-source and per-model reliability derived from
corroboration and supersession history. Depends on corroboration.

**Snapshot/compaction.** When replay gets slow, checkpoint the Canon
and replay only the tail — the standard event-sourcing playbook.
Waits because: replay of tens of thousands of events is still
sub-second.

**Semantic compression.** Summarisation claims derived from clusters of
events, themselves fully provenanced. Interesting; unproven need.

## Long-term / speculative

**Multi-user graphs.** Multiple actors writing to shared substrate;
requires identity, permissions, and merge semantics. Large. Not before
single-user value is proven.

**Distributed stores.** The JSONL log has an obvious mapping onto
replicated append-only stores. No motivation at current scale.

**Plugin architecture.** Ingestors and adapters are already the
extension points; a formal plugin system adds machinery without adding
capability until third parties exist.

## Never (violates the philosophy)

- Mutable events, in any form, for any reason.
- A Canon write path that bypasses the event log.
- Model-specific logic outside `models.py`.
- Frameworks or mandatory dependencies in the core.
- Auth, billing, telemetry in the substrate — product concerns live
  above the substrate, never in it.
- Background daemons the user can't see or stop. The substrate is a
  file the user owns; it stays that way.
