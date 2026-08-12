# RFC-016 — Technical Debt and Accepted Observations

## Accepted Technical Debt

**DEBT-016-P3-01 — projection-level Mission status gap.**
`MissionTargetProjection` does not implement RFC-016's derived `dormant`
state: an existing target remains `in_force` after its Mission becomes achieved
or abandoned. Phase 3 mitigates this at the operator surface by refusing both
declaration and withdrawal unless the Mission is active. The protected Core
projection remains byte-identical. **Owner:** Core Architecture. **Required
disposition:** resolve the dormant-state semantics before any later phase or
RFC gives `in_force` Mission Target state its first production assessment,
decisioning, recommendation or Flight Deck consumer. The dependency travels
with that first consumer; it is not tied solely to a phase number.

**Status: OPEN — remediation architecture FROZEN 2026-08-12.** Governor rulings
**GD-1** through **GD-6** and the frozen implementation boundary are recorded in
[`reviews/RFC-016-dormancy-remediation-architecture-freeze-record.md`](reviews/RFC-016-dormancy-remediation-architecture-freeze-record.md).
The frozen contract derives each Mission's **earliest valid applicable**
`core.mission.closed` timestamp inside `MissionTargetProjection` and excludes a
target from `in_force` at or after it, while preserving every answer for an
`as_of` strictly before closure. **No new canonical event and no migration are
authorised**, and the intended production blast radius is
`src/foundry/core/mission_targets.py` alone. That freeze grants no
implementation, test-implementation or BOOSTER authority. This debt is **closed
only** on the evidence in §10 of the freeze record, which requires a dated
Resolved entry here naming the resolving commit.

**Implementation candidate — 2026-08-12.** The frozen replay contract is
implemented on branch `rfc-016-dormancy-remediation-candidate`; see
[`rfc-016-dormancy-remediation-implementation-report.md`](rfc-016-dormancy-remediation-implementation-report.md).
The candidate awaits independent TELMU and SAFE review. **Status remains OPEN**
until the review and governed completion conditions are met.

**DEBT-016-P3-02 — horizon derivation is surface-side, not canonical.**
Finance now owns the deterministic mapping between the four locked Mission
metrics and `none` / `by_date` / `derived`. It constrains the Phase 3 writer;
`MetricDescriptor` and the Core projection remain unchanged and other future
writers are not thereby constrained. **Owner:** Finance domain. **Future
disposition:** if a second writer is authorised, decide through a governed
RFC-016 amendment whether horizon admissibility belongs in the descriptor
contract.

**SAFE-016-03 — FR-011 neutrality guard depth.** The guard is now independent
of the repository root, but it remains a source-level assertion rather than a
transitive import-boundary proof. **Owner:** Core Architecture. **Future
disposition:** assess a repository-wide dependency-boundary check in a future
Core governance burn; no RFC-016 implementation change is authorised.

**SAFE-016-05 — hostile-history test breadth.** T1-E now covers cross-household,
cross-mission, double-supersession and cyclic lineage regressions. It is not a
generated exhaustive event-history suite. **Owner:** SAFE. **Future
disposition:** consider property-based hostile-log generation in a dedicated
test-infrastructure burn.

## Accepted Observation

**OBS-016-B — release evidence completeness.** Engineering readiness and
governance readiness are separate merge conditions. **Owner:** Governor / RFC-100
Engineering Governance. **Future disposition:** consider codifying the release
evidence gate and GUIDO's certification responsibilities in a future RFC-100
governance amendment.
