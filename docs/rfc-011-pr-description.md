# RFC-011 — Asset & Telemetry Acquisition Framework (architecture only, Revision 2)

**Approved — architecture frozen. Ready for merge review.** Architecture-only
burn: this branch contains documentation exclusively — no production source,
tests, templates, connectors or runtime configuration are changed.

The Governor approved Revision 2 on **2026-07-31**: the five Revision 2
rulings are ratified, **OQ1–OQ7 are all resolved on their recorded
recommendations** (Evidence Vault adopted; per-artefact Governor-gated
redaction; Spec 001 Amendment 5 approved; vocabulary additions approved;
children's accounts as reference implementation with PayPal RSUs second;
rejected proposals stay in the log; prices are ordinary telemetry streams),
and the contracts in this RFC are frozen: **implementation must not change a
frozen contract without a new Governor ruling.**

## What this is

RFC-010 answered *how does Foundry present information?* RFC-011 answers
*how does Foundry know what is true?* It defines the Telemetry Acquisition
platform layer above Evidence: how balances, holdings, valuations,
statements, vesting notices and bills are captured, identified, validated,
attributed, valued and committed to the canonical event streams the frozen
pipeline consumes.

The approved core invariant, untouched by Revision 2:
**channels multiply; the seam does not.** Every channel — manual, API, CSV,
email, PDF, future Open Banking/OCR — flows through one pipeline:

```text
Provider → Telemetry Envelope (verbatim Evidence) → Interpreter
        → [Identity Resolution] → Observation Proposal
        → Confirmation Gate → Canonical Domain Events
```

Adding a channel is a plugin, never a new architecture.

## Revision 2 — architecture change summary

The Governor's first review assessed Revision 1 as architecturally strong
and directed five strengthenings. All five are adopted; each carries full
analysis (problem, alternatives, rejected options, compatibility, security,
extensibility) in the RFC:

| # | Amendment | What changed |
|---|---|---|
| GA1 | **Identity Resolution** | Permanent platform layer: typed `ExternalRef`s from interpreters, an event-sourced Identity Index (`core.identity_alias.*`), and a read-only Resolution Service with three fail-closed outcomes (`resolved` / `ambiguous` / `unresolved`). Aliases enter only through confirmed proposals; fuzzy or model-suggested matches never auto-commit. **Justified deviation from the brief:** the layer sits at proposal formation, not between Evidence and Interpreter, because identity consumes interpreted symbols that do not exist earlier |
| GA2 | **Container → Holding** | Containment becomes a Core axis of the Asset Registry via a new `contains` structural relation. Normative composition rules: derive upward, never store upward; container totals become *reconciliation evidence* when holdings exist (no double-count, AC-16); ownership/accessibility inherit downward with per-holding override |
| GA3 | **Refresh behaviour → streams** | `refresh_policy` and `update_strategy` are per-Telemetry-Stream only; the Revision 1 duplication on `AssetRegistration` is removed. Asset-level freshness is derived per valuation lens as the worst *material* stream's freshness — gold's weight, price and cost each keep their own honest cadence |
| GA4 | **Temporal contracts** | Four first-class timestamps, each with one owner: `valid_at` (state true in the world), `observed_at` (source's claim), `received_at` (Foundry first possessed it), `recorded_at` (substrate-set, non-spoofable). Plus the bitemporal read rule — fold `recorded_at ≤ D`, select `valid_at ≤ T` — making "as believed then" vs "as known now" architectural |
| GA5 | **Accessibility lifecycle → Core** | Accessibility is a platform capability: Core owns the profile contract, the condition vocabulary (now including `action_required` and `third_party_gate` — options, trusts, escrow, inheritance) and the `pending → satisfied / lapsed / revoked` lifecycle; domains own profiles and the events that assert transitions. Vesting stays Finance-owned and becomes the lifecycle's first instantiation. Terminal states never rewind: a clawback is a new condition instance |

Structural bookkeeping: platform contracts 5 → 7 (Identity Resolution,
Temporal Contract added); ADR gains D13–D17; risks gain R11–R13 (identity
poisoning, temporal misuse, containment double-count); acceptance criteria
gain AC-16–AC-20; the five Revision 2 Governor questions are answered with
rationale in the RFC's rulings section.

Self-review ([`reviews/RFC-011-architecture-self-review.md`](reviews/RFC-011-architecture-self-review.md))
produced three further amendments: external-ref namespace *values* are
domain-contributed, not Core (A1); semantic duplicates are
recommend-reject, never silently discarded (A2); clawback after
satisfaction is a new condition instance, never a backwards transition
(A3). Two watch items recorded (consumer-side `valid_at` discipline; seam
contract count).

## What Revision 2 does not change

The frozen constraints, verified item by item in the self-review:
append-only evidence, immutable provenance, the confirmation gate (now
stricter — the identity floor), no AI writing to canon (now extended: no AI
writes to the Identity Index either), Mission Engine and Mission Console
untouched, provider plugin architecture, domain neutrality, fail-closed
behaviour. No existing RFC or specification is modified; Spec 001
Amendment 5 (Grant, Vesting Event) remains a *proposal* awaiting ruling
OQ3.

## Files

- `docs/rfcs/RFC-011-asset-telemetry-acquisition-framework.md` — the
  architecture (Revision 2)
- `docs/reviews/RFC-011-architecture-self-review.md` — adversarial
  self-review, three amendments, two watch items
- `docs/rfc-011-pr-description.md` — this document
- `docs/rfcs/index.md` — index row

## Status and next step

All Governor decisions are made: the five Revision 2 rulings are ratified
and OQ1–OQ7 are closed (Phase 0 of the implementation sequence is
complete). This PR is the architecture record awaiting **Governor merge
review** — merging it unblocks the implementation Burns, which proceed to
BOOSTER per the ten-phase sequence: Phase 1 is mock-only Core grammar
including the Identity Index and temporal fields; the reference
implementation is the children's accounts, with PayPal RSUs as second
validator. No production code is changed by this PR.
