# RFC-005 Technical-Debt Register

This register records adversarial-review findings deliberately outside the
RFC-005 remediation boundary. None is required to make the current
Financial Independence vertical slice truthful, secure, deterministic, and
reviewable. Each requires an explicit follow-up design rather than a local
presentation patch.

| Debt | Current limitation | Required follow-up |
|---|---|---|
| Historical portfolio reconstruction | V1 trajectory applies `as_of` filtering to available events, but undated entity revisions cannot be reconstructed as a complete historical portfolio. | Add effective-dated valuation/entity history with migration and audit semantics. |
| Monthly projection granularity | ETA is resolved on a monthly grid. User-facing output now matches that precision, but sub-month forecasts are not supported. | Decide whether finer deterministic steps are valuable and document interpolation policy before implementation. |
| Per-request replay and assessment cost | A request rebuilds projections/assessment from the append-only log. This is acceptable for one mission but has no broad performance envelope. | Benchmark realistic logs and design invalidation-aware caching only when warranted. |
| Assumption and Scenario scoping | V1 uses the Mission’s declared Assumption Set and household-scoped metric request; it does not redesign multi-household ownership/lifecycle. | Specify tenant ownership, authorization, sharing, and amendment rules. |
| Mission amendment lifecycle | Optional policy and Assumption Set references are declared, but a complete amendment/supersession workflow is absent. | Define event verbs, authorization, effective dating, and replay semantics. |
| Persisted assessment reproducibility | Assessments are deterministic read models, not persisted snapshots. A viewed historical assessment is not independently retained. | Define snapshot triggers, retention, invalidation, and calculation-version pinning. |
| Unsupported Scenario adjustment keys | The FI assessor intentionally understands only `monthly_contribution_delta`; other keys are not modelled or promoted. | Add a versioned adjustment catalogue and validation/ranking policy in Finance. |
| Structural accessible-assets classification | V1 uses declared liquidity/account structure to include or exclude assets. Complex encumbrance, settlement, access-age, and tax constraints are not represented. | Extend the Finance policy and source data model through a dedicated RFC. |

The following broader product work also remains deferred: additional Finance
missions; Work, Health, or Household assessment providers; broad caching or
event-log redesign; and automated remediation by the adversarial-review
agent.
