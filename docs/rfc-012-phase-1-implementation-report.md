# RFC-012 Phase 1 — Operations Console Model — Implementation Report

```text
Mission Declaration (RFC-100 §6.0 / Amendment 1) — as run
Spacecraft:    Claude Code
Fuel:          Claude Opus
Effort Level:  STANDARD
Mission Type:  Implementation Burn
Authority:     Governor (see Governance deviations)
```

*Model statement (RFC-100 §12.0.2): executed under `claude-opus-5`.*

Date: 2026-08-02. Base: `main` at `cea35f0` (RFC-012 architecture post-flight
merged via PR #31).

## Decision

**READY FOR SAFE REVIEW.** This burn implements the first bounded slice of
the frozen RFC-012 architecture: the **Operations Console Model** — the
deterministic fold of RFC-011 projections into a classified, ordered
attention queue. It ships **no web surface**, no route, no template and no
CSS.

## Governance deviations — declared, not buried

Two, both material enough that SAFE and the Governor should rule on them
rather than discover them:

1. **No CAPCOM implementation brief exists.** RFC-100 §12.4 expects
   `Governor → CAPCOM → BOOSTER`. This burn was directed straight by the
   Flight Director. The frozen architecture supplied the scope (§2.6's
   proving slice), but the brief that normally bounds an Implementation Burn
   was not written.
2. **Release Closeout is open, not complete.** G6 requires closeout to
   complete **before the RFC-012 implementation merge**. It is
   [PR #32](https://github.com/enipeus84/foundry/pull/32), open at the time
   of writing. Beginning implementation is compliant — G6 gates the merge —
   but **this PR must not merge before #32 does.**

Neither deviation is repaired by code, and neither is claimed to be
authorised by this report.

## What was built

`src/foundry/operations_console.py` (one module, no package changes):

- **`OperationsConsoleModel.view(household, as_of, known_at)`** — a pure fold
  over the Asset Registry, Telemetry Stream Registry, Proposal Inbox,
  envelope projection and valuation lenses. It takes projections, not a log,
  so it structurally cannot append.
- **Closed V1 attention taxonomy** (`ATTENTION_KIND`): `identity_ambiguous`,
  `proposal_pending`, `unknown_material`, `reconciliation_divergence`,
  `telemetry_stale`, `valuation_expiring`. Owned by this versioned model,
  deliberately absent from `core.vocab` (A4/AC-6).
- **The §4.5 ordering policy** — five ranked classes over authoritative
  platform facts only, with breach duration descending and a stable
  identifier as the final tie-break, giving a total, reproducible order.
- **The §4.4 terminal states** — `all_nominal` only when zero items of any
  kind exist; `actionable_complete` when only material unknowns remain;
  `work_pending` otherwise.

**Nothing else.** No event kind, no vocabulary, no entity, no channel, no
write path, no persistence.

## Acceptance criteria evidence

| AC | Evidence |
|---|---|
| AC-1 | Full suite 634 passed (621 baseline + 13 new); no existing test changed |
| AC-2 | `test_ac2_...deterministic_fold...` — same clock twice, plus a fully independent replay from the log file, both byte-identical |
| AC-3, AC-4 | `test_ac3_and_ac4_...` — three views append zero events; the model holds no store |
| AC-5 | `test_ac5_no_disposition...` — source contains no defer/dismiss/acknowledge/snooze/suppress and no `core.attention` |
| AC-6 | `test_ac6_attention_kinds_are_model_owned...` — no attention term appears in `core/vocab.py` |
| AC-7 | Two tests: class ordering (identity blockage ahead of pending review, freshness below both) and breach-duration ordering; plus a source assertion that no ordering input mentions account type, asset category, mission or engagement |
| AC-8 | Unknown propagates as `None` from the lenses and renders as `unknown_material`; never zero or blank |
| AC-9 | Two tests: a material unknown forbids "all nominal" and yields the honest "N material values remain unavailable"; "all telemetry nominal" only with an empty queue |
| AC-11 | `test_ac11_...` — one item per (kind, subject, stream); distinct streams stay distinct |
| AC-13 | Every fixture uses the deterministic clock; `as_of`/`known_at` are always explicit, no wall clock anywhere |

AC-10 and AC-12 are not in scope for this slice: no surface exists yet to
reach parity with, and the architecture is frozen and merged.

## Defect found and fixed during the burn

The first implementation deduplicated attention items on
`(kind, subject_id)`, reading AC-11 too literally. A test proved this
collapsed three *different streams* on one subject — a stale unit count, a
stale price and a stale registration — into a single item, hiding telemetry
rather than deduplicating it. Aggregation neutrality forbids **scope** from
multiplying work; it does not license merging distinct streams. The key is
now `(kind, subject_id, stream_id)`, and the test asserts both halves.

## Known limitations

| # | Limitation | Disposition |
|---|---|---|
| L1 | `valuation_expiring` cannot fire for `on_event` valuation streams, which never go stale by frozen contract. An undated director's estimate ages invisibly | Already recorded as RFC-012 R10; needs a declared valuation horizon on the domain entity — a domain amendment, never a renderer heuristic |
| L2 | A container and its holding both report `unknown_material` for one underlying gap, so one missing price can produce two items | Honest (each subject's fold genuinely is unknown) but arguably noisy. Flagged for the visual gate (G5) rather than fixed by inventing a suppression rule the frozen contract does not authorise |
| L3 | A stream that has never reported reads as `unavailable`, not `stale`, so it raises no freshness item; the value consequence still surfaces as `unknown_material` | Correct against the merged lens; recorded so the surface burn does not mistake it for a gap |

## Carried SAFE findings

- **SAFE-012-01** — no state-changing route exists in this slice, so the
  criterion is not yet exercisable. It **binds the surface burn**: every
  state-changing console route must require authenticated, household-scoped
  access and signed, purpose-bound, body-only CSRF protection, with
  regression coverage.
- **SAFE-012-02** — unchanged and not widened. The model filters strictly by
  `household_id` and adds no authority model; a cross-household test asserts
  the filter.

## Scope boundary

Excluded: every acquisition channel beyond the existing manual provider; any
web route, template or CSS; correction authoring; dispositions of any kind;
Asset Registry, Asset Detail and Timeline surfaces; Mission Console change;
any RFC-011 contract change; RFC-013 and RFC-014.

## Validation

- Full suite: **634 passed**, 1 pre-existing Starlette/httpx deprecation
  warning
- New tests: 13, each named for the acceptance criterion it defends
- `git diff --check` clean; two new files, no modified files
