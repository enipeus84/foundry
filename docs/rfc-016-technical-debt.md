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
