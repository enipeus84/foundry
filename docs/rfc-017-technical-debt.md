# RFC-017 — Value Provenance Technical Debt

## SAFE-017-04 — Recursive expansion work amplification

**Owner:** Value Provenance successor / first production consumer authority.
**RFC link:** RFC-017 watch item W4.
**Disposition:** Accepted technical debt; no optimisation is implemented in
Phase 1 because this burn has no production provenance route.

SAFE measured legal directed-acyclic expansion at fan-out 3/depth 12 as
797,161 explainer resolutions; width 6/depth 8 as 2,015,539 calls; and width
8/depth 7 as 2,396,745 calls, approximately 48.7 seconds and 471 MiB peak
RSS.  The recursion depth limit prevents unbounded depth, but does not by
itself meaningfully bound legal branching work.

The practical blast radius begins with a production consumer that permits a
materially branching provenance graph.  Phase 1 exposes no route, UI or real
explainer, so caching would add policy and invalidation machinery before a
consumer establishes its required scope.

The proposed successor remedy is per-resolution memoisation keyed by
`ValueReference`, with explicit treatment of depth and conflict propagation.
It is mandatory reconsideration work before a production provenance consumer
permits materially branching recursive expansion.  This record does not claim
that depth limits alone fully mitigate the cost.
