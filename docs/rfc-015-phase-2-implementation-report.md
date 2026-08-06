# RFC-015 Phase 2 — Runtime Bootstrap Implementation Report

## Outcome

Phase 2 installs a Finance-owned bootstrap at `foundry.web` process composition,
immediately after the existing demo-startup hook and before routers are
registered. It replays the configured canonical event log once, appends only
missing `core.asset_registry.declared` and `core.telemetry_stream.declared`
events, and leaves request-time console reconstruction read-only.

## Discovery and declarations

`FinanceCaptureTargetBootstrap` derives active household membership from the
Core projection and then uses Finance projections only. Active, household-owned
`pension` accounts receive `pension_balance`; every active household-owned
`checking` or `savings` account receives `cash_balance`. Brokerage accounts,
including ISA-wrapped brokerages, are excluded. The primary residence must be
the unique active property secured by an active household mortgage whose
Finance mortgage-evidence projection records `property_role=primary_residence`.
Zero candidates emits no property declaration; multiple candidates fail closed.

The emitted streams are manual, annual, `review_each`, numeric and use the
canonical entity currency. Their IDs are UUIDv5 values derived from the
household id, entity id and observable property. Display names never enter
selection or identity; they remain presentation data resolved by the existing
target projection.

## Integrity behaviour

The bootstrap reports entities examined, declarations created or retained,
ineligible skips, ambiguous rejections and conflicts without financial values.
Equivalent pre-existing declarations are retained, including their historical
stream id and declarer provenance. A competing declaration with different
capability-bearing fields, duplicate semantic target, cross-household asset
registration, invalid household, or ambiguous primary residence fails closed.
All writes use existing registry APIs and the append-only event log. No Finance
event is written and RFC-011 draft, review and confirmation semantics are
unchanged.

## Validation

Focused Phase 2 coverage lives in `tests/test_rfc_015_runtime_bootstrap.py`:
pension discovery without names; multiple cash accounts; ineligible brokerage
exclusion; canonical primary-residence resolution; absent and ambiguous primary
residence handling; idempotence; deterministic identity; declaration conflict;
household rejection; and startup composition before Operations consumes targets.
Existing RFC-015 coverage continues to prove retirement, household projection,
Finance resolution, duplicate conflict handling and Operations/Acquisition
entity validation.

`git diff --check` passed. The prescribed focused regressions passed:
RFC-015 7, Phase 2 8, RFC-013 14, RFC-012 5, RFC-011 web 6. The full suite
passed: **683 passed, 1 upstream FastAPI/Starlette deprecation warning**.

## Deployment gate

This implementation environment has no `FOUNDRY_DATA_PATH`, Supabase OAuth
configuration, allowed email, session secret or application base URL. Therefore
the mandated authenticated normal-OAuth preview could not be executed without
bypassing SAFE-012-01. The RFC register remains unchanged until that preview is
performed against the deployed Parker-Brads event log and confirms no canonical
declaration conflict. Phase 3 and Phase 4 remain deferred.
