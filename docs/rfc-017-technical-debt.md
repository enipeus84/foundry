# RFC-017 — Technical Debt and Accepted Observations

Recorded against the [frozen RFC-017 architecture](https://github.com/enipeus84/foundry/blob/b8cc0ed9c63b10d2fbc03ec9440c154826c7efd6/docs/rfcs/RFC-017-value-provenance-framework.md)
(architecture authority `b8cc0ed`) and the Phase 1 implementation reviewed at
`dfbaeab`.

## Accepted Technical Debt

**SAFE-017-04 — recursive width amplification. Recorded against watch item W4.**

W4 records that "recursive expansion multiplies an already-uncached
per-request replay cost" and dispositions it as "bounded by mandatory depth
limits". **SAFE measurement shows depth limits alone do not bound the work.**

The resolver memoises nothing, so an explanation costs O(width^depth)
explainer resolutions. The cycle guard is *path*-based, which is correct — a
contributor repeated across sibling branches is a legal DAG, not a cycle
(RFC §5.2) — but it therefore does not damp repeated-subtree expansion.

Measured on the reviewed candidate (SAFE probes P7b and P11):

| Shape | Distinct values | Explainer resolutions | Wall time | Peak RSS |
|---|---|---|---|---|
| width 4, depth 6 | 5,461 | 5,461 | 0.11 s | — |
| width 5, depth 7 | 97,656 | 97,656 | 1.96 s | — |
| width 6, depth 8 | 2,015,539 | 2,015,539 | 42.50 s | — |
| width 8, depth 7 | 2,396,745 | 2,396,745 | 48.67 s | 471 MiB |
| **fan-out 3, depth 12, one repeated contributor per level** | **13** | **797,161** | **16.91 s** | — |

The last row is the material one: **thirteen distinct values cost 797,161
resolutions**, because the same contributor is re-resolved independently on
every branch it appears on.

**Disposition — accepted as debt, not remediated in this burn.**

- **Not reachable today.** Phase 1 has no consumer, no route and no production
  explainer; `max_depth` is chosen by the caller, and the only callers are
  tests. There is no path by which an external party selects a shape.
- **Not a false-provenance or authority defect.** Every result remains correct;
  the cost is the defect.
- **Code-only remediation exists** and needs no architecture change: memoise
  resolved nodes by `ValueReference` for the lifetime of one `explain()` call.
  A provenance is a pure function of its reference under fixed coordinates, so
  memoisation is sound, and it additionally hardens determinism against a
  stateful explainer.

**Owner:** Core Architecture. **Future disposition:** close before the first
consumer burn. A surface that chooses `max_depth` against a real household
graph is the point at which this becomes reachable, and RFC §11 Phase 4 is
where that decision is made. W4's stated mitigation ("bounded by mandatory
depth limits") should be corrected at the same time, because it is not
sufficient on its own.

## Accepted Observations

**OBS-017-A — coordinate rule contradicts the RFC's worked examples.**
Core requires a contributor's `Subject` to *equal* its parent's
(`value_provenance.py`, `_verify_child_coordinates`). RFC §7.1 and §7.2 both
show contributors whose subject differs from the explained value's — a
`party:household` equity or pension figure decomposed into
`resource:obligation` and `resource:account` contributors. **The frozen
architecture's own worked examples are therefore inexpressible**, verified
directly against `dfbaeab`:

```text
RFC-017 §7.1 shape REFUSED: ValueProvenanceError -
  recursive contributor must preserve subject, as_of, and known_at
```

This predates the SAFE remediation; SAFE-017-02 extended the existing rule's
*coverage* without changing the rule. **Owner:** Governor. **Future
disposition:** a Governor decision is required before Phase 2, because a
property-equity explainer cannot be written under the current rule. RFC §9
states that Core *cannot* verify domain scope containment and assigns it to the
domain, which suggests the Core rule should be temporal equality plus a
non-broadening subject rule rather than subject equality — but that is an
architectural decision and is not taken here.

**OBS-017-B — refusal shapes are not uniform.** An expanded additive child that
is *available* but carries no quantity raises `ValueProvenanceError`, whereas
one whose magnitude *disagrees* resolves the parent `unavailable` (the Loop 2
shape). Both fail closed. **Owner:** Core Architecture. **Future disposition:**
consider one refusal shape for semantic conflicts in a later phase.

**OBS-017-C — `decreases` sign convention is unstated.** A liability node
reporting its own magnitude as negative, against a contribution declared
`decreases` with a positive magnitude, resolves the parent `unavailable`.
Fail-closed, but the first real explainer will meet it. **Owner:** Core
Architecture. **Future disposition:** state the convention in the Phase 2
explainer guidance.

**OBS-017-D — coordinate verification relies on `__eq__`.** A `Subject`
subclass overriding `__eq__` passes verification. An in-process adversary can
already replace the resolver, so this is defence-in-depth only. **Owner:** Core
Architecture. **Future disposition:** compare validated field values and
require exact types if a later burn hardens the provider boundary.

**OBS-017-E — `ProvenanceNode.with_derived_completeness` is public.** The
resolver always overrides both fields, so no explanation returned by
`ProvenanceResolver.explain()` can carry provider-set completeness. A consumer
calling an explainer directly would bypass that. **Owner:** Core Architecture.
**Future disposition:** consider making the helper private when the first
consumer lands.

**OBS-017-F — the implementation branch carries no copy of its authority.**
The candidate is based on `a9799bf` and does not contain the RFC-017
architecture, self-review, report or freeze record, so it cannot be checked
against its own frozen authority from within its own tree. **Owner:** TELMU /
Release. **Future disposition:** merge order should bring the architecture and
its implementation into one history before Phase 2 begins.
