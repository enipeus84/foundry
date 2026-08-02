# RFC-012 Phase 1A — Operations Console Model Foundation — Implementation Report

```text
Mission Declaration (RFC-100 §6.0 / Amendment 1) — as run
Spacecraft:    Claude Code
Fuel:          Claude Opus
Effort Level:  STANDARD
Mission Type:  Implementation Burn
Authority:     Governor (see Governance deviations)
```

*Model statement (RFC-100 §12.0.2): executed under `claude-opus-5`.*

Date: 2026-08-02. Base: `main` at `595cba1` (Release Closeout merged via
PR #32; RFC-012 architecture post-flight merged via PR #31). The branch was
updated from post-closeout `main`, which supersedes any earlier review SHA.

## Decision

**READY FOR SAFE REVIEW.** Classified **Phase 1A — Operations Console Model Foundation** by Governor direction (FR-015: reclassification is a Governor decision, not a self-adjustment). This burn implements the first bounded slice of
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
2. **Release Closeout was open when this burn began; it is now complete.**
   G6 requires closeout to complete **before the RFC-012 implementation
   merge**. [PR #32](https://github.com/enipeus84/foundry/pull/32) merged at
   `595cba1` on 2026-08-02, and this branch has been updated onto it. G6 is
   satisfied.

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

---

# Remediation Burn — SAFE-33 findings

```text
Mission Declaration (RFC-100 §6.0 / Amendment 1) — as run
Spacecraft:    Claude Code
Fuel:          Claude Opus
Effort Level:  MEDIUM
Mission Type:  Remediation Burn
Authority:     Governor
```

Bounded by the published SAFE report at
[PR #33 comment](https://github.com/enipeus84/foundry/pull/33#issuecomment-5160047506).
Reviewed failing head `a1c0b9e57c245d20e526f6a044c34d9da1ef38a1`. No
opportunistic improvement is carried (RFC-100 §3.1 rule 4).

## Finding resolution

| Finding | Severity | Root cause | Code change | Regression test | Residual |
|---|---|---|---|---|---|
| SAFE-33-01 | HIGH | One universal dedup key `(kind, subject_id, stream_id)` omitted proposal identity, so two proposals on one stream collapsed and the survivor depended on dict insertion order | New `attention_identity()` selects identity **per item source**: proposal-backed kinds key on `(kind, proposal_id)`, stream-backed on `(kind, subject_id, stream_id)`, subject-backed on `(kind, subject_id)`. `_deduplicate` keys on `item.identity` | `..._two_pending_proposals_on_one_stream_produce_two_items`, `..._two_ambiguous_proposals...`, `..._insertion_order_does_not_change_the_queue`, `..._repeated_folding_is_byte_identical`, `..._aggregation_scope_still_does_not_multiply_items` | None |
| SAFE-33-02 | MEDIUM-HIGH | Exact IEEE-754 inequality on `Reconciliation.difference` made 3.0×0.1 vs 0.3 a permanent, unclearable divergence | **`reconciliation_divergence` is no longer emitted in Phase 1A.** See the escalation below — no compliant in-scope fix exists | `..._unimplementable_kinds_are_never_emitted` (asserts the 3×0.1 case yields no item and the queue reaches nominal) | **Yes — architecture escalation** |
| SAFE-33-03 | MEDIUM | `within_class=as_of` is constant across a view, so §4.5's "longest-standing divergence" rule contributed nothing; `Reconciliation` carries no `valid_at` | Governor's Phase 1A ruling applied: stable identifier ascending, `within_class` left at its `0.0` default, with the limitation documented at `_ORDER_CLASS` | `..._reconciliation_class_orders_by_stable_identifier` (also asserts no timestamp is invented) | **Yes — return-to-architecture** |
| SAFE-33-04 | MEDIUM | `stream.property in {"valuation","estimate"}` split two attention kinds on an unconstrained free-text field | **`valuation_expiring` is no longer emitted.** Every cadence breach is `telemetry_stale`; no parser, naming convention or heuristic remains | `..._free_text_property_cannot_trigger_valuation_expiry` (four adversarial property names) | **Yes — return-to-architecture** |
| SAFE-33-05 | MEDIUM | `assert ... or True` was a tautology presented as the AC-7 proof; two kinds untested | Tautology and its near-vacuous companion deleted; a genuine total-order test added over hand-built items with deliberate ties; both unimplementable kinds now tested for **deliberate absence** | `..._ordering_is_a_genuine_total_order_under_adversarial_ties`, plus mutation checks below | None |
| SAFE-33-06 (report 07) | LOW | `"|".join(...)` over unescaped components let `("a\|b","c")` and `("a","b\|c")` collide | `stable_id` is now `_digest(list(identity))` — the platform's own canonical sorted-key JSON + SHA-256 over the structural tuple. No process-randomised `hash()` | `..._stable_identifier_resists_delimiter_collision`, `..._identity_is_per_source_not_universal` | None |
| Report 06 | LOW | The `work_pending` sentence counted only actionable items, hiding unknowns | `summary_line()` appends the unknown count whenever one exists | `..._summary_line_never_hides_a_material_unknown` | None |
| Report 08 | LOW | A stream id was rendered in the `subject_id` field when a stream declaration was absent | Such proposals are skipped: without a declared stream there is no authoritative subject | `..._proposal_without_a_declared_stream_is_not_rendered` | None |
| Report 09 | INFORMATIONAL | "1 item need attention" | Verb agreement corrected via `_count()` | Covered by the summary-line test | None |

## SAFE-33-02 — escalation to the Governor

The brief's preferred remediation order was: an existing Decimal value type or
quantisation contract; existing currency precision rules; an existing
reconciliation helper. **None of the three exists.** Searches across
`src/foundry/` find no `Decimal`, no `quantize`, no minor-unit or precision
contract, and no `isclose`/tolerance helper; `core/vocab.py` carries
`currency` only as a display-unit token.

The brief forbids an ad hoc epsilon in the console, and scope discipline
permits changes only to the console model, its tests and its report — so the
lens that produces the noisy float (`core/acquisition.py`) may not be touched,
and its frozen semantics may not change. There is therefore **no compliant fix
available inside this burn.**

Rather than ship a defect the operator can never clear, Phase 1A applies the
same disposition the Governor ordered for SAFE-33-04: the kind is
architecturally defined but **not emitted** until the platform can support it
honestly. This is a deliberate trade recorded for ruling, not a silent
decision: false permanent items are unclearable under the no-dismiss design,
whereas a temporarily absent kind is visible, bounded and reversible.

**It also departs from the presumption behind the SAFE-33-03 ruling**, which
assumed reconciliation items continue to be emitted. The ordering rule is
implemented and tested regardless, so enabling the kind later requires no
ordering work.

**Governor decision requested — one of:**

1. confirm the Phase 1A suppression and schedule a monetary-comparison
   contract (integer minor units, or a declared tolerance on a frozen
   contract) as a return-to-architecture item; or
2. authorise a bounded RFC-011 change so the lens returns an authoritative
   divergence determination and a finding `valid_at`, which would resolve
   SAFE-33-02 and SAFE-33-03 together at the correct layer.

## Mutation sanity checks

Each mutation was applied temporarily, the suite run, and the implementation
restored. **No mutation is committed** (`git diff` confirms the module matches
the remediated version).

| Mutation | Result |
|---|---|
| Restore the universal dedup key | 3 failed — both SAFE-33-01 collapse tests and the insertion-order test |
| Invert the ordering tuple | 3 failed — both AC-7 ordering tests and the new total-order test |
| Restore the unescaped `\|` join for `stable_id` | 1 failed — the collision test |
| Restored implementation | 26 passed |

## Files changed

- `src/foundry/operations_console.py`
- `tests/test_rfc_012_operations_console.py`
- `docs/rfc-012-phase-1a-implementation-report.md`

No routes, templates, CSS, JavaScript, authentication, CSRF, providers, event
kinds, persistence, RFC-010/RFC-011 contracts or RFC-012 architecture were
touched. No Phase 1B work began.

## Validation

- Focused Phase 1A tests: **26 passed** (13 before remediation)
- Full local suite: **647 passed**, 1 pre-existing deprecation warning
- `git diff --check`: clean; module byte-compiles
- No linter or formatter is configured in `pyproject.toml` or the CI workflow;
  CI runs the suite across Python 3.10–3.13

## Residual architecture gaps

| # | Gap | Owner |
|---|---|---|
| G-A | No authoritative monetary comparison, so `reconciliation_divergence` cannot be classified honestly | Governor decision requested above |
| G-B | `Reconciliation` carries no `valid_at`, so §4.5's longest-standing ordering is unimplementable | Return-to-architecture; RFC-011 projection enhancement |
| G-C | No authoritative estimate-basis signal on a stream, so `valuation_expiring` cannot be separated from `telemetry_stale` | Return-to-architecture; supersedes the earlier L1 |
| G-D | A container and its holding both report `unknown_material` for one underlying gap | Unchanged; flagged for the G5 visual gate |

SAFE-012-01 remains **mandatory and undischarged** for the later web surface;
SAFE-012-02 is unchanged and not widened.

## Governor Product Decision — Dormant Capabilities

Phase 1A intentionally implements only attention kinds that can be derived
solely from authoritative platform facts. `reconciliation_divergence` and
`valuation_expiring` remain architecturally defined but intentionally dormant.

They remain inactive because the platform does not yet expose authoritative
monetary comparison, reconciliation temporal identity, or estimate-basis
telemetry. These are platform responsibilities, not console responsibilities.

### Terminal state clarification

The Governor rules that an empty Phase 1A queue means **no active Phase 1A
attention items**. It does not imply all telemetry is nominal, reconciliation
is healthy, or valuations are fresh. Future implementation phases may broaden
these operational semantics once authoritative platform contracts exist.

### Architecture gap register

| Gap | Accepted programme item |
|---|---|
| G-A | Monetary comparison contract |
| G-B | Reconciliation `valid_at` |
| G-C | Estimate-basis telemetry signal |
| G-D | Container/Holding duplicate unknowns |

These are accepted architectural limitations. They are not implementation
defects.

### SAFE carry forward

**SAFE-012-01** remains **undischarged** and applies beginning Phase 1B.
Every future state-changing Operations Console route must require
authenticated access, household scoping, signed purpose-bound body-only CSRF,
and regression coverage.
