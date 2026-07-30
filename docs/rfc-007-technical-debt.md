# RFC-007 — Mortgage Freedom Technical Debt

## Manual evidence migration adapter

`record_mortgage_evidence` is a documented deprecated bridge for supplied
manual proof data. It must gain no implicit file parsing, remote access,
credential handling or hidden default policy.

The writer may be removed only when:

1. an approved evidence-ingestion design preserves source, effective date,
   confidence, lineage, scope and immutable event provenance;
2. Mortgage Freedom has migrated to that writer with behavioural-equivalence
   tests;
3. supported external consumers no longer call the manual writer;
4. at least one compatibility release has documented the migration; and
5. the read projection continues to replay historical
   `finance.mortgage_evidence.recorded` events.

## Model limitations

- Monthly amortisation does not implement lender-specific day-count, payment
  timing, rounding or fee conventions.
- Post-fix paths are static sensitivities, not rate forecasts or
  probabilities.
- Fees, early-repayment charges, overpayment caps, offsets, arrears,
  payment holidays and product transfers are unsupported.
- Affordability is unavailable until verified income/expenditure evidence has
  an approved contract.
- One active household mortgage securing one member-owned primary residence is
  supported. Multiple or mixed-scope mortgages fail closed.
- Month-only source dates retain their source precision through lineage; a
  richer temporal-precision contract is deferred.

## Property valuation canon

Mortgage Freedom's property valuation and `finance.net_worth` currently use
different valuation evidence and may therefore report different property
bases. Revision 2 deliberately discloses that isolation and does not change
`finance.net_worth`.

A successor **Property Valuation Canon** must define shared valuation identity,
basis, effective-date precision and consumer-selection rules before the two
domains can be reconciled. Until that work is approved, Mortgage Freedom
accepts only the optional `valuation_basis` values `index_estimate`,
`owner_estimate` and `agent_appraisal`, never infers a basis from text, and
keeps Net Worth isolated.

## Acquisition-evidence correction workflow

Revision 2 records `initial_deposit`, optional `acquisition_costs` and
acquisition facts as immutable evidence. Conflicting applicable observations
remain visible and referenced; the deterministic latest observation may be
displayed with a limitation, but the system performs no automatic correction
and exposes no `supersedes_event_id`.

A governed correction workflow is deferred. It must preserve the full event
history, distinguish correction intent from ordinary conflicting evidence,
define authorisation and audit semantics, and specify deterministic projection
behaviour. It must not recast explanatory equity attribution as validation.

## Action lifecycle

Scenario recommendations are read-only calculations. They are not accepted,
scheduled, persisted or executed. Any Decision/Execution integration requires
a separately approved RFC and must preserve Financial Resilience precedence.

## Existing RFC-006 compatibility

RFC-005 alias/result fields and `_legacy_scalar_mission_status` remain governed
by [`rfc-006-technical-debt.md`](rfc-006-technical-debt.md). RFC-007 adds no
consumer and does not change their removal conditions.
