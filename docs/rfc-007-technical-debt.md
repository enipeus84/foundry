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

## Action lifecycle

Scenario recommendations are read-only calculations. They are not accepted,
scheduled, persisted or executed. Any Decision/Execution integration requires
a separately approved RFC and must preserve Financial Resilience precedence.

## Existing RFC-006 compatibility

RFC-005 alias/result fields and `_legacy_scalar_mission_status` remain governed
by [`rfc-006-technical-debt.md`](rfc-006-technical-debt.md). RFC-007 adds no
consumer and does not change their removal conditions.
