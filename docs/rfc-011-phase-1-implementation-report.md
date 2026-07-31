# RFC-011 Phase 1 Reference Slice — Implementation Report

## Decision

**READY FOR GOVERNOR PHASE 1 REVIEW.** This burn implements the bounded,
manual child-account reference slice only. It does not merge RFC-011, and it
does not introduce a provider beyond manual JSON evidence capture.

## Delivered seam

The implementation proves the approved path end to end:

```text
Manual provider → telemetry envelope → protected verbatim evidence
→ deterministic versioned interpreter → Identity Resolution
→ inert proposal → authenticated confirmation → finance event
→ valuation/accessibility/mission lenses
```

`core.acquisition` owns the channel-neutral grammar. `AssetRegistry` folds
metadata-only registrations, external references, containment and lifecycle
metadata; it holds neither money nor ownership. `TelemetryStreamRegistry`
owns per-stream acquisition strategy, refresh policy, validation contract,
source identity, unit/currency and confirmation policy. The Finance domain
continues to own accounts, positions, ownership and canonical value events.

The manual provider accepts bounded structured facts and writes a
content-addressed envelope only. Its evidence is stored outside JSONL in a
private `0700` vault with `0600` blobs; access is authorized, hashes are
verified on every read, redaction appends an event after removing the blob,
and no raw manual payload is written to the log. The storage control is
deliberately not an improvised cipher: production deployment must place the
vault on encrypted storage or replace it with a reviewed encryption adapter.

The deterministic `manual-json@1` interpreter reads only captured evidence,
records its identity/version, emits proposals and cannot append `finance.*`.
The confirmation gate is the sole path that can append a draft canonical
event. It rejects tampering, spoofed `recorded_at`, unsupported drafts,
ambiguous identities, semantic duplicates and cross-household registrations.
Confirmed events carry evidence, proposal and confirming-actor provenance.

## Child-account proof

The reference tests use generic child/custodian relationships rather than
hard-coding Hamish or Harriet into Core. Finance vocabulary now admits `jisa`,
`junior_sipp` and `tracker_fund`; these are Finance data values, not Core
branches. The proof covers custodian and beneficial-owner relationships,
container → holding containment, separate unit/price/statement-total streams,
derived market value, reconciliation, and age-gate accessibility. The same
holding is shown with positive market value, zero adult-policy contribution,
and positive value for a later-horizon child policy.

## Temporal and valuation contract

Every confirmed observation includes `valid_at` and `observed_at`; each
envelope includes explicit `received_at`; `recorded_at` is always the
substrate's event timestamp and is refused if proposed by input. The
bitemporal fold applies `valid_at ≤ T` and `recorded_at ≤ D` deterministically.
Late-arrival tests prove that knowledge time and world-valid time remain
distinct.

Market, accessibility and mission value are lenses. They are never appended.
Container totals supplied by a statement are reconciliation evidence, not a
second stored total. Evidence grades propagate by categorical dominance only;
there is no confidence arithmetic.

## Surface and security

`/acquisition/inbox` is an authenticated, separate review surface. It shows
the evidence hash, source, target, proposed value, all four timestamps,
identity state, evidence grade, interpreter/version, warnings and the events
confirmation would create. Its forms carry a signed, short-lived CSRF token;
they submit only a proposal identifier, never editable draft data. Displayed
values are escaped. Mission Console semantics and assessment contracts are
unchanged.

## Validation evidence

Focused RFC-011 acquisition and UI suites pass. Existing Core grammar,
Finance vocabulary, event-log, Finance entity, Finance metric, web,
authentication and Mission Control suites pass. The final Governor package
will include the full-suite, security-document, deterministic-fixture,
`git diff --check`, and clean-worktree results from this branch.

## Scope boundary

Excluded from this burn: PayPal RSUs; APIs; email; PDFs; CSV; OCR; Open
Banking; cash/bank accounts; bills; precious metals; private/director equity;
and every other acquisition channel. No live child data is included in the
repository or preview.
