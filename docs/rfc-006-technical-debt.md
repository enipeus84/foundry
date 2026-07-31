# RFC-006 Technical-Debt Register

| Debt | Current limitation | Removal or follow-up condition |
|---|---|---|
| Legacy scalar Mission adapter | **Retired by RFC-010 Phase 2.** Every supported Finance mission has a registered definition/provider and uses the Mission Console Model. | Closed after provider migration, repository-search proof of disuse and route coverage for all four supported missions. |
| RFC-005 phase aliases | **Retired by RFC-010 Phase 2.** `MissionPhaseAssessment`, `MissionAssessment.phase`, `MissionAssessment.phases` and `MissionAssessment.phase_thresholds` no longer exist. | Closed after provider migration, repository-search proof of disuse and direct contract tests. |
| Remaining RFC-005 compatibility fields | `flight_status_*` and `confidence_basis` remain for source compatibility. | Remove only under a separately approved compatibility decision; new code uses trajectory and structured confidence fields. |
| Generic trajectory value and instrument-shape formatting | The original shared renderer assumed currency-oriented trajectory values and that ETA, Delta-v, trajectory and forecast were always meaningful together. RFC-008 closed the concrete months-format and applicability-shape defects through provider metadata and a domain-neutral applicability contract. Other domain-specific formats and per-instrument reason strings remain unsupported. | Extend explicit presentation metadata only for a concrete approved mission; never add mission-name, slug or policy-id branching, and never infer applicability from missing values. |
| Provider lifecycle | Definitions/providers are registered in-process at composition time; there is no signed package, version negotiation or hot reload. | Design only if providers become external or independently deployed. |
| Household/member authorisation | `Subject` preserves household/member scope and provider envelopes reject scope substitution, but the application still grants one configured email access to all data. | Define ownership, membership, roles and object-level policy before multi-user release. |
| Historical evidence reconstruction | FI trajectory cannot fully reconstruct undated historical entity revisions. | Add effective-dated history and migration semantics in a Finance history RFC. |
| Persisted assessment reproduction | Assessments are deterministic read models, not retained snapshots. | Define snapshot trigger, calculation-version retention, invalidation and access policy before persistence. |
| Remaining mission assessments | Financial Resilience and Mortgage Freedom now have separately governed Finance providers. Pension Independence remains metadata-only and Children remains outside the fixed hierarchy. | Each remaining mission requires a separate approved domain-policy implementation. |

No deferred item is represented as implemented.
