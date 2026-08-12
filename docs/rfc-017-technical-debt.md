# RFC-017 — Technical Debt and Accepted Observations

Recorded against the [frozen RFC-017 architecture](https://github.com/enipeus84/foundry/blob/b8cc0ed9c63b10d2fbc03ec9440c154826c7efd6/docs/rfcs/RFC-017-value-provenance-framework.md)
(architecture authority `b8cc0ed`) and the Phase 1 implementation reviewed at
`dfbaeab`. **Amended 2026-08-10** by Governor rulings GD-A1–GD-A7 resolving
OBS-017-A — see the dated blocks below and
[`reviews/RFC-017-OBS-017-A-ruling.md`](reviews/RFC-017-OBS-017-A-ruling.md).

## Accepted Technical Debt

**DEBT-017-CI-01 — strict floating-point assertion instability.**

The RFC-017 Pension Phase 2 provenance test
`test_production_pension_descriptor_reconciles_representation_noise_and_retains_residual`
intermittently compares `0.6000000000000001` with `0.6` using strict equality
under Python 3.11. The identical failure was independently reproduced on the
canonical baseline `b35328e3b8e5df5106cfa7abb68e89a0177f4726` and on the
initial CI run for RFC-016 Phase 3 candidate
`b81517e74adcd3e116a52ef0b7f6c3fc235f8350`; a fresh retry of that immutable
candidate passed, as did Python 3.10, 3.12 and 3.13.

**Owner:** RFC-017 / Core Architecture and Test Engineering. **Future
disposition:** investigate and remediate in a separately authorised RFC-017
testing or provenance burn; do not alter RFC-016 Phase 3, its candidate, or
`DEBT-016-P3-01`, `DEBT-016-P3-02` or RFC-016 W7.

> **Governor disposition — GD-P3-M1, 2026-08-12.** Accepted as inherited CI
> instability for RFC-016 Phase 3 only. It is non-blocking for PR #47 provided
> the exact PR head has fresh green required checks. This is neither an
> indefinite acceptance nor authority to change production or tests in RFC-016.
> Formal ruling record:
> [`reviews/RFC-016-phase-3-governor-pre-merge-ruling.md`](reviews/RFC-016-phase-3-governor-pre-merge-ruling.md).

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

> **Governor disposition — ruling GD-A5, 2026-08-10 (OBS-017-A).**
> **SAFE-017-04 MUST CLOSE BEFORE THE NEXT CONSUMER.** The prior "future
> disposition" above is superseded from a recommendation into a requirement,
> for a specific reason: OBS-017-A's remediation (RFC-017 §9.1) replaces
> `Subject` equality with same-authority verification, which is precisely what
> makes a real household graph traversable. Under equality, a decomposition
> could only ever reference values about one subject; under same-authority, a
> household value may expand into every registered resource in the household
> and each of *those* into its own contributors — the branching this debt
> measured and warned about. The bounded Phase 1 conformance remediation
> authorised by GD-A1–GD-A6 is **also authorised to close this debt**, via
> per-resolution memoisation keyed by `ValueReference`, scoped to the lifetime
> of one top-level `explain()` call. No persistent cache, cross-request cache,
> mutable global cache, TTL semantics or cache event is authorised. Formal
> ruling record: [`reviews/RFC-017-OBS-017-A-ruling.md`](reviews/RFC-017-OBS-017-A-ruling.md).

> **Remediated — Phase 1 OBS-017-A conformance remediation, 2026-08-11.**
> SAFE-017-04's repeated-identical-reference amplification class is closed by
> per-top-level-resolution memoisation of verified provider output, keyed by
> the full `ValueReference`. The cache is not persistent, global, or shared
> across requests. Authority, coordinate, depth, and path-cycle verification
> still run on every traversal. The executable eight-branch probe now performs
> **10** provider resolutions (`root + 8 branches + shared`) rather than **17**
> path-based resolutions; the diamond resolves its shared node once per call.
> See [`rfc-017-phase-1-conformance-remediation-report.md`](rfc-017-phase-1-conformance-remediation-report.md).
>
> **Remaining risk.** This is not a general performance claim. A graph with
> genuinely distinct `ValueReference`s still performs one provider resolution
> per distinct reference; any broader performance envelope remains future Core
> work and must be reassessed before a materially branching consumer.

> **SAFE advisory closeout — 2026-08-11, reviewed implementation `00d45f4`.**
> **SAFE-017-04 is CLOSED for repeated provider/explainer-resolution
> amplification.** Per-resolution memoisation reduces repeated semantic
> references to one `explainer.explain()` call per `ValueReference`; it does
> **not** bound total resolver traversal. SAFE measured a legal repeated graph
> with fan-out **3**, depth **12**, and **13** distinct values: it made **13**
> `explainer.explain()` calls but **797,161** `ProvenanceResolver._resolve()`
> calls, because cached subtrees are still recursively revisited along each
> path. Authority verification is also performed on those revisits and adds
> measurable overhead.
>
> **SAFE-017-04B — cached-subtree traversal amplification. ACCEPTED PHASE 1
> DEBT.** Repeated semantic references avoid repeated provider computation,
> but total traversal can remain path-amplified. No production consumer exists,
> no security boundary is bypassed, and no current performance envelope is
> promised. The remedy is code-only and must be reconsidered before a consumer
> may select materially deep provenance traversal. Wide graphs of genuinely
> distinct `ValueReference`s remain linear in distinct work; that observation
> does not close this repeated cached-subtree traversal debt.

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

> **RESOLVED — Governor ruling GD-A1–GD-A6, 2026-08-10.**
> **REAL ARCHITECTURE CONTRADICTION, confirmed.** Root cause: the frozen RFC
> conflated `Subject` **identity** with authority **scope**, and separately
> under-surveyed Core's own canonical authority — `AssetRegistry`
> (`core/acquisition.py:266-334`) already binds `subject_id → household_id`
> neutrally, already refuses cross-household containment, and has a production
> writer, so §9's "Core cannot check it" was factually incomplete for the
> household dimension. §7.1/§7.2 are **affirmed**; they were always correct.
>
> **Resolution:** RFC-017 §9.1 (new) replaces `Subject` equality with
> same-authority verification (VP-SCOPE-1 through VP-SCOPE-6): temporal
> coordinates stay exactly equal; a contributor's `Subject` may differ from its
> parent's but must independently resolve, through canonical Core state, to
> the one authorising household fixed at the root; the explainer may never
> assert that authority itself.
>
> **Phase 1 disposition: REMEDIATION REQUIRED — contract conformance, not an
> active vulnerability.** The merged implementation is fail-closed and
> satisfied every stated acceptance criterion; it was simply stricter than the
> frozen contract required. R1, R2, R3, R4, Loop 2, SAFE-017-01, SAFE-017-02
> and SAFE-017-03 are unaffected — VP-SCOPE-1 preserves R1's temporal half
> verbatim, and VP-SCOPE-3–5 replace only SAFE-017-02's `Subject` predicate.
>
> **Implementation constraint carried into the remediation:** the resolver
> must not gain a direct dependency on `AssetRegistry`/`EventLog`/Finance — the
> authority binding arrives through a narrow, read-only, Core-neutral protocol
> injected at composition (conceptually `SubjectAuthority`), preserving P1-A
> and P1-B.
>
> Phase 2 authority remains **NONE**. Formal ruling record:
> [`reviews/RFC-017-OBS-017-A-ruling.md`](reviews/RFC-017-OBS-017-A-ruling.md);
> EECOM's investigation (evidence, not itself a ruling):
> [`reviews/RFC-017-OBS-017-A-clarification.md`](reviews/RFC-017-OBS-017-A-clarification.md).

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
