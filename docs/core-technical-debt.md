# Core — Cross-Cutting Technical Debt

Platform-wide Core debt that is not owned by any single product RFC. RFC-scoped
debt stays in its own register (`rfc-0NN-technical-debt.md`).

## Accepted Technical Debt

**DEBT-CORE-REPLAY-01 — Raw EventLog grammar / replay boundary.**

**Status:** OPEN — **NON-BLOCKING**.
**Owner:** Core Architecture, with Test and Security participation when this is
eventually burned.
**Recorded:** 2026-08-12, by Governor ruling on RFC-016 Freeze Amendment 1
([`reviews/RFC-016-dormancy-remediation-architecture-freeze-record.md`](reviews/RFC-016-dormancy-remediation-architecture-freeze-record.md) §16).

**Observed property.**

- `EventLog.append` performs **no event-kind payload schema validation**. It
  writes whatever payload it is given.
- **Supported writers establish structural payload guarantees before append.**
  The shared grammar constructs required keys unconditionally — `grammar.close`,
  for example, always emits `entity_id` — so the guarantee is real for every
  event any authorised writer produces.
- **Direct low-level append can create hash-chain-valid events that violate
  those writer guarantees.** Such an event passes `EventLog.verify()`, so the
  integrity check is not a mitigation for this class. (Hand-editing the stored
  JSONL is a different case and *is* detected by `verify()`.)
- **Multiple existing Core and Finance projections assume structurally required
  payload keys exist**, indexing `payload["entity_id"]` directly across roughly
  sixteen sites in `core/entities.py`, `core/decisions.py` and
  `finance/entities.py`.
- **Replay may therefore fail loudly** on a grammar-invalid but hash-valid raw
  event. Because the composition root rebuilds projections per request, such a
  log would surface as a failure on authenticated pages rather than as a silent
  misreading.
- The behaviour **predates** the RFC-016 dormancy remediation and is
  **platform-wide rather than Mission-specific** — it reproduces for party,
  employer and mission events alike, on both `declared` and `closed` verbs.

**Why no fix is prescribed.** Adding `.get()` is **not** endorsed as the
remedy. Silently skipping an event the log actually contains would make the read
model diverge from canonical history, which is a worse failure than refusing to
interpret it. Fail-loud replay on a log that violates its own grammar may well
be the correct contract.

**Future architecture decision.** A governed burn must determine which policy
Foundry adopts:

- preserve fail-loud replay;
- validate at append;
- strengthen event-grammar enforcement;
- tolerate selected malformed history;
- quarantine invalid events;
- or another governed mechanism.

**Blocking relationship.** This debt **must not block `DEBT-016-P3-01`** unless
future evidence demonstrates that the malformed history is reachable through a
supported production path. The RFC-016 investigation found no such path:
`grammar.close` is the only production writer of `core.mission.closed`,
Operations technical capture refuses that kind, and the CLI exposes no raw-event
append command.
