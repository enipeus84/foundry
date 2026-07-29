# RFC-006 Technical-Debt Register

| Debt | Current limitation | Removal or follow-up condition |
|---|---|---|
| Legacy scalar Mission adapter | Missions without an assessment policy still use one deprecated homepage-only scalar adapter. | Remove only after every supported active/replayed mission has a registered definition/provider, a consumer audit is empty, migration guidance has shipped, and a breaking change is approved. No new consumer is permitted. |
| RFC-005 contract aliases | `MissionPhaseAssessment`, `phase`, `phases`, `flight_status_*` and `confidence_basis` remain for source compatibility. | Remove under the same consumer-audit and compatibility-release conditions; new code must use milestone, trajectory and structured confidence fields. |
| Generic trajectory value formatting | Shared milestone/current-value trajectory labels still use the existing currency-oriented formatter. This is sufficient for FI and the later Mortgage Freedom proof case, but not every possible domain unit. | Add explicit non-currency trajectory format metadata only when a concrete mission requires it; never add mission-name branching to the renderer. |
| Provider lifecycle | Definitions/providers are registered in-process at composition time; there is no signed package, version negotiation or hot reload. | Design only if providers become external or independently deployed. |
| Household/member authorisation | `Subject` preserves household/member scope and provider envelopes reject scope substitution, but the application still grants one configured email access to all data. | Define ownership, membership, roles and object-level policy before multi-user release. |
| Historical evidence reconstruction | FI trajectory cannot fully reconstruct undated historical entity revisions. | Add effective-dated history and migration semantics in a Finance history RFC. |
| Persisted assessment reproduction | Assessments are deterministic read models, not retained snapshots. | Define snapshot trigger, calculation-version retention, invalidation and access policy before persistence. |
| Non-FI assessments | Financial Resilience, Pension Independence, Mortgage Freedom and Children have no providers here. | Each requires a separate approved domain-policy implementation; Mortgage Freedom is the first architecture proof case. |

No deferred item is represented as implemented.
