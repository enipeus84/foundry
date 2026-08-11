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
- The frozen RFC states both the ordinary five-band W* hierarchy (A22) and an
  honest zero-W* case (A23). The implementation treats A23 as the governing
  degenerate case and emits only the already-achieved terminal milestone when
  W*=0. A future RFC editorial erratum may make that exception explicit; no
  Core contract change is needed and no negative boundary remains.

## History, presentation and performance

- Observed pension trajectory history remains unavailable because undated
  revision reconstruction is not honest for sparse pension statements. The
  D13 renderer correction shows the provider's current trajectory judgement
  independently; it does not resolve historical reconstruction.
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

## RFC-017 Phase 2 pre-implementation observation

**OBS-PENSION-01 — person-scoped weighting filters ownership links before
computing shares.** Recorded 2026-08-11, during RFC-017 Pension Phase 2
pre-implementation validation (BOOSTER, ruling
[`reviews/RFC-017-GD-P2-ruling.md`](reviews/RFC-017-GD-P2-ruling.md)).

`FinancePensionMetricProvider._pension_accounts` calls
`FinanceAggregationService.owned_entities(person_ids, ...)`
(`pension_metrics.py:521-530`, `aggregation.py:64-81`), which — for a
`party:person` scope, where `person_ids` is the single requested person —
returns only that person's own `OwnershipLink`s; co-owners' links are
filtered out before `_weight` ever runs. `_weight` then calls
`FinanceAggregationService.shares` (`pension_metrics.py:532-535`,
`aggregation.py:83-96`) over that already-filtered, single-person link list.
If the surviving link carries no explicit `share`, `shares`'s implicit-split
rule (`remaining = 1.0 - sum(explicit); each = remaining / len(implicit)`)
divides the *unclaimed remainder among the links present in the filtered
list* — one link, one implicit owner as far as this calculation can see — and
returns `1.0`, even where the account's full canonical ownership state
records other owners or shares invisible to this particular query.

**Disposition: OUTSIDE RFC-017 PHASE 2.** No Finance metric modification is
authorised by RFC-017 or by this observation. RFC-017 provenance explains
whatever `finance.pension_wealth` actually computes (GD-P2-F) — it does not
correct, infer, or reinterpret pension weighting semantics. This observation
does **not** classify the current metric as incorrect; whether
`owned_entities`/`shares` should see full account ownership state before
filtering to the requested scope is a Finance/RFC-009 calculation-semantics
question requiring its own dedicated architecture investigation, separate
from and after RFC-017 Phase 2, if the Governor chooses to open one.

## Closed during PR #22 SAFE remediation

- Private Pension coupling to `FinanceMetricProvider` was removed.
  `FinanceAggregationService` now owns the supported Finance-internal scope,
  ownership, share and observed-currency operations used by the existing
  Finance metric provider and both Pension providers.
- The negative-epsilon zero-W* compatibility encoding was removed. A zero
  destination now has one honest terminal milestone and renders no negative
  currency boundary.
