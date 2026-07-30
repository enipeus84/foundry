# RFC-009 — Pension Independence Technical Debt

No deferred item is represented as implemented.

## Evidence, identity and ingestion

- The pension evidence writer is a deprecated in-process bridge. Subject id,
  source, lineage, confidence and actor are assertions rather than
  authenticated provider attestations. It has no HTTP route, parser,
  connector, credentials or network access. Any successor ingestion design
  must preserve immutable replay, effective dates, correction history and
  household scope before this bridge can be removed.
- Free-text `source` and `lineage` values have no explicit length limit. Add
  reviewed bounds before exposing an unattended or remote writer. Policy
  numbers, National Insurance numbers and provider identifiers remain
  prohibited in those fields.
- Invalid attributable envelopes lower Mission Confidence; unattributable
  invalid envelopes remain visible only through projection diagnostics. A
  scoped operator quarantine surface is required before multi-household use.
- The synthetic proof household records member ages in the existing generic
  household Party attribute map because Core has no governed date-of-birth or
  age-at-date contract. A future identity/temporal-evidence RFC must define
  that contract, preserve privacy classification and expose precise lineage.
- Missing-member State Pension limitations use counts rather than raw entity
  ids because Core has no display-name contract and Mission Detail must not
  expose internal identifiers.

## Pension policy and calculation boundaries

- V1 stops at the accumulation planning point. Pension access, bridging
  income, decumulation, sequencing risk, longevity modelling, annuitisation,
  lump sums and survivor benefits require separately governed work.
- State Pension and DB amounts are treated as real-constant from the planning
  point. Forecast revaluation, early/late retirement factors and policy change
  are not modelled.
- Tax-year contribution telemetry is factual payment aggregation only. Annual
  allowance, carry-forward, tax relief, tapering, lifetime limits and
  jurisdictional tax calculations are not implemented.
- Deterministic Conservative/Expected/Optimistic paths are sensitivities, not
  calibrated probabilities. Stochastic modelling requires a separate RFC.
- The numeric-only Finance Assumption Set represents the approved milestone
  and State Pension reliance tuples as individually named scalar keys. A
  future structured-policy type may remove that encoding only through a
  versioned migration.
- Core requires every bounded milestone to have non-zero width. When W* is
  exactly zero, Pension Independence retains all five approved labels using
  sub-penny negative internal boundaries while completion remains exactly
  `P1 >= W*`. A future Core zero-destination representation should remove this
  internal compatibility encoding without changing rendered values.

## History, presentation and performance

- Observed pension trajectory history remains unavailable because undated
  revision reconstruction is not honest for sparse pension statements. The
  D13 renderer correction shows the provider's current trajectory judgement
  independently; it does not resolve historical reconstruction.
- Pension metric and assessment providers reuse private basis helpers on
  `FinanceMetricProvider`. Promote a stable shared Finance valuation,
  ownership and currency-conversion seam before those helpers are refactored.
- Provider-local metric caching is safe only for one replayed projection.
  Reuse across Event Log appends requires an explicit log identity and
  invalidation contract.
- Adding current tax-residency evidence increases the broad provenance
  cardinality displayed by Mortgage Freedom for the same household even
  though its values and formulas are unchanged. Existing Finance metrics
  should eventually publish narrower dependency references.
- Web requests still rebuild all projections from the Event Log. The
  four-assessor benchmark is recorded in the implementation report; no
  persistent cache or snapshot was introduced.

## Security and authorisation

- The current deployment remains single-account. Membership, sharing and
  object-level household authorisation are not implemented.
- Pension values, ages, contribution payments and derived retirement
  projections are personal-confidential or derived-sensitive. No new log
  sink, export, snapshot, telemetry service or external destination was added.
- Recommendations are read-only deterministic re-projections of declared
  Scenarios. They are not advice, acceptance, scheduling, execution, product
  ranking, transfer analysis or consolidation guidance.
