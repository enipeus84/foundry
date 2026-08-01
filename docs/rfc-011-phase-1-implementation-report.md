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
owns accounts, positions, ownership, canonical event vocabulary and the
manual draft contract. Core has no `finance.*` event catalogue or prefix
check: it accepts only a supplied domain contract at composition time.

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

## SAFE remediation evidence — 2026-08-01

### B3 — Information Honesty — remediated

`ValuationLenses` now represents a missing material unit or price observation
as `None`, never `0.0`. That unknown propagates through market,
accessibility, mission and reconciliation lenses; the affected result is
`Insufficient`. A genuine observed zero remains a number. The regression
`test_missing_material_market_evidence_remains_unknown_not_zero` asserts both
the unknown propagation and stable replay of the result.

### B4 — Identity Resolution — remediated

`ResolutionService.semantic_duplicate()` now raises when its inbox dependency
is unavailable. `ManualInterpreter.interpret()` refuses before creating a
proposal when duplicate protection is absent. No optional dependency can now
silently turn semantic duplicate detection off. The regression
`test_identity_and_duplicate_protection_refuse_operation_when_inbox_is_unavailable`
asserts both paths.

### S2 — CSRF credentials in URLs — remediated

The authenticated inbox renders a hidden CSRF form field and receives it only
from an `application/x-www-form-urlencoded` POST body. Query parameters are
not read. `test_inbox_requires_session_csrf_escapes_content_and_confirms`
asserts that rendered form actions contain no token, a query-token request is
rejected, and a body-token request succeeds.

### B1 — Core neutrality — SAFE position supported and remediated

Before remediation, `core.acquisition` named a Finance event catalogue and
required the `finance.` prefix in the Confirmation Gate. That is a direct
violation of RFC-011 AC-8, not merely the Finance reference implementation.
The catalogue and payload validation now live in
`foundry.finance.acquisition.FinanceManualDraftContract`; Core owns only the
generic proposal lifecycle and a `DomainDraftContract` protocol. The
regression `test_core_acquisition_contract_contains_no_finance_event_vocabulary`
asserts the Core source contains no `finance.` event vocabulary. Finance
continues to be today's registered domain implementation, but it is no longer
hard-wired into the platform seam.

### B2 — Phase sequencing — SAFE position supported

The frozen RFC explicitly declares Phases 1–4 separate Burn candidates.
Commit `775812c` includes Core grammar and identity (Phase 1), Evidence Vault
and confirmation (Phase 2), valuation/accessibility (Phase 3), and the child
reference implementation (Phase 4). The branch title and earlier report call
this a Phase 1 slice, but the evidence is a combined Phase 1–4 implementation.
No code change can make that historical sequencing claim true. The Governor
should reclassify this branch as the combined Phase 1–4 reference burn and
decide whether its existing review evidence satisfies the separate-gate
intent. No Phase 5 work has begun.

### Significant SAFE identifiers without published finding text

The CAPCOM brief names S1 and S3–S7 but provides no assertion, file, or
acceptance criterion. The authoritative draft PR has no review, inline, or
issue comments (`gh api` returned `[]` for all three resources on 2026-08-01),
and no local SAFE review artefact exists. Each identifier is therefore
classified **SAFE interpretation not supported**: an identifier alone is not
an actionable technical claim and cannot authorize speculative changes to a
frozen architecture. This is evidence of absence of a finding text, not a
claim that the system is defect-free. A supplied review artefact can reopen
the named item without redesign.

## Validation evidence

At remediation commit `7723774`, focused acquisition: 11 passed; focused web
security: 13 passed; Core deterministic replay: 10 passed; focused Finance:
70 passed; full suite: 618 passed (one pre-existing Starlette/httpx
deprecation warning). Security documentation reports COMPLETE and
`git diff --check` is clean. GitHub Actions `tests` run `30692011922` passed
on Python 3.10, 3.11, 3.12 and 3.13. `validate.sh` completed its security,
test and mock deterministic-replay checks, then correctly reported that no
real-model API keys are configured; that is not represented as V1.0 model
validation.

## Scope boundary

Excluded from this burn: PayPal RSUs; APIs; email; PDFs; CSV; OCR; Open
Banking; cash/bank accounts; bills; precious metals; private/director equity;
and every other acquisition channel. No live child data is included in the
repository or preview.
