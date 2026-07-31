# RFC-008 — Financial Resilience Technical Debt

No deferred item is represented as implemented.

## Evidence and protection

- The manual resilience writer is a deprecated in-process bridge. Source,
  lineage, confidence, actor and household id are assertions rather than
  authenticated attestations. It has no HTTP route, file parser, connector,
  credentials or network access. Before any live provider or multi-household
  writer, bind the evidence subject to an active replayed household and retain
  equivalent provenance, immutable replay and correction semantics.
- Manual envelope strings have no explicit length limits. Add reviewed limits
  and bounded per-commitment presentation before exposing any unattended or
  remote writer.
- Invalid envelopes with an attributable household lower that household's
  confidence. Unattributable invalid envelopes remain visible only through the
  projection diagnostics; an operator quarantine surface is required before
  multi-household operation.
- Income-source plurality supersedes on the explicit but self-asserted
  `source` field. An authenticated income-verification/source-identity contract
  is required before treating declarations as externally verified.
- Protection and insurance have no approved entity, vocabulary, evidence
  policy or score. They remain explicitly not assessed and cap V1 confidence
  at Supported.

The manual writer may be removed only after an approved ingestion design
preserves historical event replay, scope, source, effective date, confidence,
lineage and correction semantics, and after supported callers have migrated
through a documented compatibility release.

## Commitment and stress model

- Dated commitments exist only in the resilience evidence envelope.
  `RecurringSeries` still lacks cadence/next-due semantics and `Obligation`
  lacks due dates. No cadence or due date may be inferred.
- Stress telemetry is deterministic arithmetic under declared magnitudes, not
  a probability model. It does not model redundancy, tax, benefits, severance,
  insurance or behavioural response.
- `movement_lookback_days` is validated and versioned but historical resilience
  reconstruction is unavailable in V1, so `Divergent` cannot be evidenced from
  a like-for-like trajectory. Add effective-dated history before enabling that
  state.

## Presentation and action lifecycle

- Scenario recommendations are read-only calculations. They are not accepted,
  persisted, scheduled or executed. Multiple qualifying scenarios are
  deterministically truncated to one, following the current FI/Mortgage
  precedent; a ranked multi-action contract remains undesigned.
- A generic non-schedule recommendation-impact abstraction is absent.
  Financial Resilience therefore states reserve-position effect in its action
  text and does not fabricate Delta-v.
- Synthesised telemetry ids and the four assumption-bound resilience metrics
  do not have authored public drill-down pages. Direct raw metric routes remain
  an internal contract-inspection surface and can expose raw identifiers.
- Per-instrument applicability reason strings and a `DeltaV.direction`
  extension remain deferred.

## Performance, history and compatibility

- **Resolved by RFC-009 D13:** the Mission Detail trajectory tile no longer
  suppresses a provider's computed `trajectory_state` merely because observed
  trajectory history is unavailable. The history SVG and its explanatory
  sub-line remain governed independently by instrument applicability. This
  resolves the presentation defect only; the historical-reconstruction debt
  below remains open.
- Web requests rebuild projections from the Event Log. Provider-local
  memoisation removes repeated M1/M2/holdings work inside one request, but
  there is no cross-request cache, invalidation policy or persisted assessment
  snapshot. The provider cache is safe only within the lifetime of its replayed
  projections and must gain an explicit log identity/invalidation contract
  before any composition root reuses it across appends.
- Historical resilience trajectory cannot be reconstructed honestly from the
  current averaging-window denominator and undated entity revisions.
- `Divergent` is consequently unreachable in V1 and
  `movement_lookback_days` is reserved and validated but not consumed. Remove
  neither vocabulary nor versioned assumption until a separately approved
  historical reconstruction supplies honest like-for-like movement.
- Resilience evidence is GBP-only in V1. A reporting-currency contract is
  required before supporting non-GBP households.
- The single-basis lock currently reuses private helpers on
  `FinanceMetricProvider`. Promote a shared Finance basis seam before either
  provider's internals are independently refactored.
- Frozen target/horizon/floor constants are validated against the Assumption
  Set as well as pinned in code. A future versioned policy must define whether
  those values become variable inputs or remain identity constraints; it must
  not silently reinterpret historical assumption events.
- Holdings freshness relies on dated contributing transactions or valuations.
  A richer undated-evidence disposition should be defined before a new holding
  type can contribute value without one of those dated records.
- RFC-005 phase aliases and the RFC-006 legacy scalar adapter were subsequently
  retired by RFC-010 Phase 2 after all supported Finance missions migrated to
  the Mission Console Model. Remaining compatibility fields retain their
  separately governed lifecycle.
- Two pre-existing FI early-unavailable construction paths (missing accessible
  assets and reporting-currency mismatch) still inherit all-applicable
  metadata, so registry validation replaces their specific reason and
  provenance with the generic fail-safe envelope. This is fail-closed and does
  not expose or fabricate data, but it should be corrected with registry-level
  degraded-input tests before the next Mission Assessment contract change.
- Multi-user membership, object-level authorisation and household sharing
  remain outside RFC-008.
