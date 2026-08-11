# RFC-017 — OBS-017-A: Subject / Scope Architecture Clarification

**Mission:** resolve the subject/scope contradiction identified as OBS-017-A
before any Phase 2 implementation authority is granted.
**Flight Controller:** EECOM. **Spacecraft:** claude-opus-5.
**Burn:** bounded architecture investigation and ruling recommendation.
**Status:** **PROPOSAL — no Governor authority is issued by this document.**
No production implementation. No Phase 2 burn. No Finance explainer. No merge.

| | |
|---|---|
| Architecture authority | `b8cc0ed9c63b10d2fbc03ec9440c154826c7efd6` |
| Architecture merge | `e3e5e25c8e77319aa50f635ed954aa82d57f7806` |
| Phase 1 candidate | `82f7310a67aea4ac57936e76727a677f7fb0bc48` |
| Implementation merge | `80ea9dbb8a241bc904148dd788a92ceddf5a0a34` |
| Investigated at | `72f89a3e59008aaf3576010a3e4e9deeec9b7db9` (`main`) |
| Independent SAFE verdict | GO WITH ADVISORY; OBS-017-A confirmed REAL |
| Phase 2 authority | **NONE** |

---

## A. Root cause

**The frozen RFC never states a contributor-Subject rule at all.** Every
occurrence of `Subject` in the frozen document is one of four things:

| Frozen text | What it is |
|---|---|
| §4.1 `ValueReference.subject: Subject` | a field declaration — no constraint |
| §4.4 `Exclusion.subject: Subject` — *"the contributor that could not be used"* | a field declaration; positively implies a *different* subject |
| §9 *"the requesting `Subject`, `as_of` and `known_at` are carried down every expansion unchanged; **the resolver never broadens them**"* | a constraint on **the resolver's dispatch behaviour** |
| P1-F *"the requesting `Subject`, `as_of` and `known_at` are carried unchanged through every expansion"* | the same constraint, restated as an acceptance criterion |

There is **no clause anywhere requiring `child.subject == parent.subject`**, and
§7.1/§7.2 positively depict contributors whose subject differs from the
explained value's. The equality rule at
`src/foundry/core/value_provenance.py:234-239` is an implementation invention.

### The modelling mistake, stated precisely

**RFC-017 put `subject` inside `ValueReference` — where it denotes *identity*,
which value this is about — and then §9/P1-F wrote about "the requesting
`Subject`" as though that same field denoted *authority*, the envelope a query
may reach within.** One field, two roles, distinguished nowhere.

`as_of` and `known_at` genuinely are query-envelope coordinates: they belong to
the question, not to the value, and equality across an expansion is exactly
right for them. `subject` is not like them. It is part of the value's identity —
"the pension total *of this household*", "the balance *of this account*" — and
requiring identity to be constant across a decomposition forbids decomposition
itself.

The implementation read the three coordinates as one rule because the RFC
presented them as one rule. That is the defect: **insufficient contract
language that conflated Subject identity with authority scope.** The worked
examples were correct; the implementation's reading was a reasonable
interpretation of prose that had merged two concerns.

### The second, compounding error — §9's justification is factually wrong

§9 assigns scope containment to the domain with this basis:

> *Core cannot check it: `resolve_scope` explicitly accepts caller-resolved
> resource ids and takes no view on domain ownership (`core/scope.py:29-53`).*

That statement is true **of `resolve_scope`** and **false of Core**. Core owns a
second, canonical, replayable authority that the RFC did not consider:

**`AssetRegistry`** — `src/foundry/core/acquisition.py:266-334`:

```text
core.asset_registry.declared   { subject_id, domain, household_id, ... }
core.asset_registry.linked     { entity_id, relation: "contains", target }
```

- `AssetRegistration` (`:257-263`) binds **subject_id → household_id**
  canonically. `domain` is an opaque string; Core learns no domain semantics.
- `contain()` (`:312`) **already refuses cross-household containment**:
  `if container.household_id != holding.household_id: raise "cross-household
  containment is forbidden"` (`:317-318`), and already refuses containment
  cycles (`:321-326`).
- Its own docstring (`:267`): *"Core routing metadata, never a financial ledger
  or ownership store."* — precisely a neutral authority index.

**And it has a production writer.** RFC-015's runtime bootstrap
(`src/foundry/finance/runtime_bootstrap.py:121`, applied at `:183`) constructs
`AssetRegistration(subject_id, "finance", self.household_id)` only after
`_owned(entity, members)` (`:87-89`) has established that the entity's canonical
Finance ownership links are a **subset of Core household membership**
(`members_of`, `core/entities.py:208-210`).

So the household binding is established by a **separate, earlier, canonical
act** that consulted domain ownership and Core party membership — not by the
explainer at resolution time. That distinction is the one §8-D of the brief
calls critical, and Foundry already satisfies it.

**Root cause, one line:** the RFC conflated identity with authority, then
justified delegating authority to the domain from an incomplete survey of Core —
and the implementation hardened the resulting ambiguity into the strictest rule
available.

---

## B. Options

Evaluated on the brief's seven axes. **Compat-P1** = compatibility with the
merged Phase 1 implementation; **Compat-RFC** = compatibility with §7.1/§7.2.

### A — Literal Subject equality (retain Phase 1 unchanged)

| Axis | Assessment |
|---|---|
| Security | Strongest available; refuses everything |
| Determinism | Total |
| Domain neutrality | Total |
| Complexity | None |
| Compat-P1 | Perfect |
| Compat-RFC | **Fails** |
| Future coupling | None |

**The RFC's intended cross-resource provenance can never be expressed under
this option.** Stating that plainly, as the brief requires: property equity
cannot decompose into an asset and an obligation; pension wealth cannot
decompose into accounts; §7.1 and §7.2 are permanently dead letters; and the
framework can only ever explain a value in terms of other values about the
identical subject — which excludes every worked example that motivated the RFC.
Retaining it means RFC-017 delivers a contract nothing can use.

### B — Provider-declared cross-subject traversal

Provider emits any Subject; Core accepts it.

| Axis | Assessment |
|---|---|
| Security | **Unacceptable** |
| Determinism | Preserved |
| Domain neutrality | Total |
| Complexity | Lowest |
| Compat-P1 | Removes a control |
| Compat-RFC | Full |
| Future coupling | None |

**This recreates R1 and SAFE-017-02 exactly.** R1 was the finding that a
provider could emit a child `ValueReference` with substituted coordinates and
have Core resolve coordinates of the provider's choosing. Option B is that
finding, adopted as the design. A provider could emit
`Subject("party", "household-B")` and Core would resolve and return another
household's values. **Rejected.**

### C — Core-verifiable containment

Core permits traversal only where it can itself prove the child subject sits
within the parent's authorised scope.

| Axis | Assessment |
|---|---|
| Security | Strong — Core holds the decision |
| Determinism | Total; canonical projection, replayable |
| Domain neutrality | **Preserved** — `AssetRegistry` is Core and domain-opaque |
| Complexity | One narrow lookup |
| Compat-P1 | Requires changing one rule |
| Compat-RFC | Full |
| Future coupling | Binds provenance to `AssetRegistry` |

RFC-017 §9 asserts Core lacks the knowledge. **Verified, and the assertion is
wrong** — see §A. `AssetRegistry` supplies exactly `subject_id → household_id`,
canonically and neutrally, with a production writer.

### D — Domain-authorised traversal

The domain explainer asserts containment; Core enforces structure and time.

| Axis | Assessment |
|---|---|
| Security | Depends entirely on the source of the assertion |
| Determinism | Preserved |
| Domain neutrality | Total |
| Complexity | Lowest of the workable options |
| Compat-P1 | Requires changing one rule |
| Compat-RFC | Full |
| Future coupling | None |

**The brief's critical distinction resolves in Foundry's favour, but only
partly.** If the explainer asserts containment *at resolution time*, this is
Option B with extra words — the same provider that wants the traversal is the
one authorising it. If containment was established *at registration time* by a
different act and recorded canonically, it is sound. Foundry has the latter —
but the *record* of it is `AssetRegistry`, which is Core. So D, done safely,
collapses into C. **D is not a separate option; it is C's provenance story.**

### E — Explicit resolution capability/context

A `ResolutionContext` carrying authorised household, permitted resources and
temporal coordinates.

| Axis | Assessment |
|---|---|
| Security | Strong |
| Determinism | Preserved |
| Domain neutrality | Total |
| Complexity | **Highest** — a new authority object and its lifecycle |
| Compat-P1 | Changes the query contract |
| Compat-RFC | Full |
| Future coupling | Creates a general capability model |

An equivalent already exists in substance: the query's root reference plus
`AssetRegistry`. Introducing a capability object would be **building Foundry's
authorisation subsystem inside a provenance RFC** — precisely what minimum-power
rule 6 forbids. Foundry has no sub-household authorisation model, so a
`permitted_resources` list would have nothing to populate it. **Rejected under
YAGNI**, and recorded as the shape to revisit only if intra-household privilege
boundaries ever exist.

### F — Non-recursive contextual references

Cross-subject contributors emitted as references but never expanded by Core.

| Axis | Assessment |
|---|---|
| Security | Strong — nothing is resolved |
| Determinism | Preserved |
| Domain neutrality | Total |
| Complexity | Very low |
| Compat-P1 | Small change |
| Compat-RFC | **Partial** |
| Future coupling | None |

This solves nothing that matters. §7.1's own text requires expansion:
*"Expanding either contextual contributor yields an `observed` node — £300,000
and £180,000 respectively, each anchored in its mortgage-evidence event."* An
unexpandable reference cannot be verified against its child (Loop 2's
protection is lost for exactly the references most worth checking), and the
household still cannot see what supports the number. **It hides the problem.**
Note, however, that SAFE-017-02 already made unexpanded references *coordinate-
verified*, so F's supposed safety advantage over C is nil.

---

## C. Recommendation — Option C, minimum form

> **Recommended: replace Subject *equality* with Subject *same-authority*,
> verified by Core against canonical state, with temporal equality unchanged.**

### The new normative invariant

**VP-SCOPE-1 — temporal coordinates (unchanged, restated).**
A contributor's `as_of` and `known_at` **MUST** equal the parent's exactly.
Core **MUST NOT** alter, widen or default either during expansion. A mismatch
**MUST** be refused. *(This preserves R1's temporal half and SAFE-017-02
entirely. It is not relaxed for any reason, including Subject traversal.)*

**VP-SCOPE-2 — the authorising household.**
Every resolution has exactly one **authorising household**, derived once from
the root reference and **MUST NOT** change during the resolution:

- root `Subject("party", H)` where `H` is an active household party → `H`;
- root `Subject("party", P)` where `P` is an active person belonging to exactly
  one active household → that household;
- any other root subject → the `household_id` of its `AssetRegistration`;
- otherwise, or where the household is ambiguous or unresolvable → the
  resolution **MUST** be refused.

**VP-SCOPE-3 — same-authority traversal.**
A contributor's or exclusion's `Subject` **MUST** resolve to the authorising
household by the same rules. A subject that does not, or that Core cannot
resolve at all, **MUST** be refused. Core **MUST NOT** infer, default or repair
a household binding.

**VP-SCOPE-4 — identity is not authority.**
A contributor's `Subject` **MAY** differ from its parent's. Subject equality
**MUST NOT** be required, and **MUST NOT** be treated as evidence of authority.

**VP-SCOPE-5 — Core's authority source is canonical and neutral.**
Core **MUST** derive the subject→household binding solely from canonical state
already recorded — `AssetRegistry` registrations and Core party membership. Core
**MUST NOT** consult a domain projection, read domain ownership semantics, or
accept a household binding asserted by an explainer at resolution time.

**VP-SCOPE-6 — the boundary Core still does not claim.**
Core guarantees **household isolation** and nothing finer. Whether a caller may
query a given household at all remains the caller's authorisation problem,
unchanged. Foundry has no intra-household privilege boundary, so Core claims
none — this is stated so no reader infers a per-member or per-resource
guarantee that does not exist (T6 residual, unchanged).

### Why this is the minimum-power answer

| Rule | Satisfied by |
|---|---|
| 1 — RFC examples expressible | VP-SCOPE-4 |
| 2 — fail-closed preserved | VP-SCOPE-2/3 refuse unknown and unresolvable subjects |
| 3 — cross-household traversal prevented | VP-SCOPE-3, backed by `AssetRegistry` which already forbids cross-household containment |
| 4 — `as_of`/`known_at` preserved | VP-SCOPE-1, untouched |
| 5 — Core stays domain-neutral | VP-SCOPE-5; `AssetRegistry.domain` is an opaque string |
| 6 — no general authorisation subsystem | no new entity, event, vocabulary or capability object |
| 7 — deterministically testable | canonical projection; replayable; frozen-clock stable |
| 8 — no Phase 1 finding reopened | see §D |

**Nothing new is created.** No canonical event, no vocabulary value, no shape
change to `ValueReference`, `ProvenanceNode`, `Contribution` or `Exclusion`, no
change to the query signature.

### One implementation constraint that must be stated now

The resolver **MUST NOT** import `AssetRegistry` directly. `AssetRegistry`
imports `EventLog`, and P1-B is asserted structurally — SAFE verified that no
`foundry` module reachable from `value_provenance.py` can append. The binding
must arrive through a **narrow read-only protocol** injected at the composition
root, e.g.

```text
class SubjectAuthority(Protocol):
    def household_for(self, subject: Subject) -> str | None: ...
```

with the concrete implementation living outside the provenance module. This
keeps P1-A (mock-domain proof) and P1-B (no write capability) intact and is the
same descriptor-seam pattern RFC-015 §5.3 and RFC-016 §5.3 established.

---

## D. Attack analysis

| Case | Result under the recommendation | Mechanism |
|---|---|---|
| **Same-subject child** | allowed | resolves to the same authorising household |
| **Legitimate contained resource** (`party:household` → `resource:account`) | allowed | `AssetRegistration.household_id` matches |
| **Property equity** (`party:household` → `resource:asset` → `resource:obligation`) | allowed | both registered to the household |
| **Foreign-household resource** (`household-A` → resource of `household-B`) | **refused** | registration household ≠ authorising household |
| **Unregistered / unknown subject** | **refused** | no binding ⇒ unknown, never assumed (FR-008) |
| **Unrelated party** (`household` → arbitrary `party:X`) | **refused** unless `X` is the household itself or an active member of it |
| **Authority broadening** (`resource` → broader `party:household`) | allowed **only** where that household is the authorising household derived at the root; the envelope is fixed at the root and never widened mid-resolution. Stated honestly: this is intra-household movement, and Foundry has no intra-household privilege boundary to breach (VP-SCOPE-6) |
| **`as_of` substitution** | **refused** | VP-SCOPE-1, unchanged from SAFE-017-02 |
| **`known_at` substitution** | **refused** | VP-SCOPE-1, unchanged |
| **Provider asserts its own household binding** | **refused / ignored** | VP-SCOPE-5 — Core reads canonical state only |
| **Cycle** | **refused** | unchanged; path-based guard, parent resolves `unavailable` |
| **Depth bound** | unchanged | expansion still bounded and lazy; SAFE-017-02 verifies unexpanded references too |
| **Ambiguous household** (person in two households) | **refused** | VP-SCOPE-2 fails closed rather than picking |

**R1 is not reopened.** R1 was "a provider can cause Core to resolve coordinates
of the provider's choosing". Under VP-SCOPE-3 the provider still cannot: it may
*name* a subject, but Core resolves the binding itself from canonical state and
refuses anything outside the authorising household. The provider gains the
ability to name a contributor, not the authority to widen the query.

**SAFE-017-02 is not reopened.** Its guarantee — every emitted reference is
verified before Core returns it, expanded or not — is retained verbatim; only
the *predicate* applied to `subject` changes. The exclusion check introduced by
SAFE-017-02 (NEW-3) is corrected by VP-SCOPE-3 from equality to same-authority,
which is what §7.2's excluded `resource:account` requires.

---

## E. Contract impact

Classified per the brief. **No unrelated section is touched.**

| Frozen clause | Change class | Action |
|---|---|---|
| §9 authorisation table, row 2 (*"Scope containment … Core cannot check it: `resolve_scope` … takes no view on domain ownership"*) | **normative contract change** | superseded: Core **can** verify household containment via `AssetRegistry`; the delegation to the domain is withdrawn for the household dimension and retained for everything finer |
| §9 authorisation table, row 1 (*"No scope substitution … the resolver never broadens them"*) | **clarification** | retained and sharpened: it constrains the resolver's dispatch, and never required contributor Subject equality |
| P1-F | **clarification** | retained; "carried unchanged" applies to `as_of`/`known_at`; the Subject clause is restated as VP-SCOPE-2/3/4 |
| Invariant 10 (*"Scope, `as_of` and `known_at` are carried down unchanged and are never broadened by the resolver"*) | **clarification** | retained; "scope" now reads as the authorising household, fixed at the root |
| §5.1 expansion verification | **clarification** | unchanged in substance; the predicate changes, the timing does not |
| §7.1, §7.2 worked examples | **no change — they were correct** | explicitly affirmed; they become expressible |
| W8 (*"Core cannot verify domain scope containment"*) | **normative contract change** | narrowed: Core verifies the **household** dimension; finer containment remains a domain obligation |
| §4.1 / §4.2 / §4.3 / §4.4 shapes, all four vocabularies, §3 projection rules, §4.5 completeness, §5.2/§5.3, §6 | **untouched** | no change |

**No new canonical event. No vocabulary addition. No shape change.**

### Other RFCs

**None require amendment.** RFC-011 supplies `AssetRegistry` unchanged and is
only *read*. RFC-015 supplies the production registrations unchanged. RFC-006
and RFC-016 are untouched. RFC-001's `Subject` is unchanged — this clarification
changes what provenance *requires* of a Subject, not what a Subject *is*.

---

## F. Phase 1 impact

```text
PHASE 1 REQUIRES REMEDIATION
```

**Not for safety — for contract conformance.** Precisely:

- The merged Phase 1 is **fail-closed** and satisfies every Phase 1 acceptance
  criterion as written, including P1-F. It was validly delivered.
- It enforces a rule **stricter than any frozen clause**, and stricter than the
  recommended one. No security property is lost by leaving it in place.
- But it **cannot host a Phase 2 explainer**, because §7.1's own shape is
  refused. The ruling therefore requires changing
  `value_provenance.py:234-239` and adding the `SubjectAuthority` seam before
  Phase 2 can begin.

The remediation is bounded and can be scheduled with the Phase 2 authorisation
rather than as an emergency: one predicate, one injected protocol, and the
regression battery re-pointed. **It is not implemented here.**

---

## G. SAFE-017-04 gate

```text
SAFE-017-04 MUST CLOSE BEFORE NEXT CONSUMER
```

**Reasoning, and an additional recommendation.**

The debt was recorded to protect exactly this gate: *"close before the first
consumer burn … a surface that chooses `max_depth` against a real household
graph is the point at which this becomes reachable."*

This clarification **materially increases possible branching**, and that must
not pass silently. Under Subject equality a decomposition could only ever
reference values about one subject; under VP-SCOPE-3 a household value may
expand into every registered resource in the household, and each of those into
its own contributors. **The clarification is precisely what makes the household
graph traversable — which is what SAFE-017-04 measured and warned about.** The
measured shape (13 distinct values → 797,161 resolutions) becomes reachable
through legitimate structure rather than only through a synthetic probe.

**Recommendation beyond the gate:** close SAFE-017-04 in the *same* remediation
that implements VP-SCOPE-1…6. Both touch the resolver; memoising resolved nodes
by `ValueReference` within one `explain()` call is a few lines, is sound because
a provenance is a pure function of its reference under fixed coordinates, and
additionally hardens determinism against a stateful explainer. Doing them
together avoids a second pass through TELMU and SAFE. **This is a
recommendation, not an authorisation.**

---

## Proposed amendment — RFC-100 §9.2 discipline

**Not applied.** The frozen RFC is not edited by this burn. If the Governor
rules, the amendment should be recorded beside the retained original:

1. **Exact frozen text superseded:** RFC-017 §9, authorisation table row 2 —
   *"**Scope containment** — a contributor is one the requesting scope could
   itself have read | **the domain explainer** | Core cannot check it:
   `resolve_scope` explicitly accepts caller-resolved resource ids and takes no
   view on domain ownership (`core/scope.py:29-53`)"*.
2. **Preserve it verbatim**, with a dated amendment block beneath recording that
   the survey was incomplete: `AssetRegistry` (`core/acquisition.py:266-334`) is
   Core, canonical, domain-neutral, production-written and already
   household-scoped.
3. **Add VP-SCOPE-1…6** as a new normative subsection, cross-referenced from
   §5.1, §9, P1-F, invariant 10 and W8.
4. **Why required:** without it the RFC's own §7.1/§7.2 are inexpressible and
   Phase 2 cannot be implemented.
5. **SAFE properties that must remain invariant:** R1 (coordinate
   substitution), SAFE-017-01 (positive status authority), SAFE-017-02 (every
   emitted reference verified before return), SAFE-017-03 (canonical registry
   ownership), Loop 2 (expanded additive magnitude agreement). None is relaxed;
   VP-SCOPE-1 preserves R1's temporal half unchanged, and VP-SCOPE-3 replaces
   only the `subject` predicate inside SAFE-017-02's existing check.

---

## Stop conditions — assessed, none met

| Condition | Assessment |
|---|---|
| Requires a new global authorisation subsystem | **No** — `AssetRegistry` exists, is canonical and is production-written |
| Existing household/resource relationships cannot establish containment | **No** — `AssetRegistration.household_id` plus `members_of` establish it |
| Phase 1 security requires substantial redesign | **No** — one predicate changes; every SAFE property is preserved |
| Bitemporal coordinates must be relaxed | **No** — VP-SCOPE-1 leaves them untouched |
| Alters canonical event semantics | **No** — no event is added, changed or read differently |
| Cannot be resolved without materially reopening another frozen RFC | **No** — RFC-011 and RFC-015 are read, not amended |

---

## Governor decisions required

| # | Decision | EECOM recommendation |
|---|---|---|
| **GD-A1** | Adopt Option C in the VP-SCOPE-1…6 form, replacing Subject equality with same-authority verification | **Accept** |
| **GD-A2** | Amend RFC-017 §9 row 2 and W8: Core verifies the household dimension; finer containment remains a domain obligation | **Accept**, recorded beside the retained original |
| **GD-A3** | Affirm §7.1/§7.2 as correct and expressible; no worked-example correction | **Accept** |
| **GD-A4** | Authorise a bounded Phase 1 remediation implementing VP-SCOPE-1…6 behind a `SubjectAuthority` protocol, with no direct `AssetRegistry` import | **Accept** — required before Phase 2 |
| **GD-A5** | Close SAFE-017-04 in the same remediation | **Accept** — recommended, not required by the gate |
| **GD-A6** | Correct NEW-3: the exclusion-subject check becomes same-authority rather than equality | **Accept** — folded into GD-A4 |
| **GD-A7** | Whether Phase 2 authority is granted, and for which explainer | **Defer** — outside this burn |

**No implementation authority is granted or assumed by this document.**
