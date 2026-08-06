# RFC-016 — Technical Debt and Accepted Observations

## Accepted Technical Debt

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
