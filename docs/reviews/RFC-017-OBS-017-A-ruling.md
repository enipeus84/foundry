# RFC-017 — OBS-017-A: Governor Ruling

**Decision: OBS-017-A architecture contradiction ACCEPTED as real. Governor
rulings GD-A1 through GD-A7 recorded. RFC-017 amended.**
**Ruling date:** 2026-08-10
**Authority:** Governor, via CAPCOM
**PR:** [#46](https://github.com/enipeus84/foundry/pull/46)

**Attribution.** This document records a **Governor act**. It is transcribed
by CAPCOM at the Governor's direction and is held separately from EECOM's
investigating artefact so the decision is never mistaken for
self-certification (RFC-100 §1.2, §9.4). EECOM's proposal — preserved
unmodified as evidence, not authority — is
[`RFC-017-OBS-017-A-clarification.md`](RFC-017-OBS-017-A-clarification.md).

---

## Mission state verified at ruling time

| | |
|---|---|
| Architecture authority | `b8cc0ed9c63b10d2fbc03ec9440c154826c7efd6` |
| Architecture merge | `e3e5e25c8e77319aa50f635ed954aa82d57f7806` |
| Phase 1 implementation | `82f7310a67aea4ac57936e76727a677f7fb0bc48` |
| Implementation merge | `80ea9dbb8a241bc904148dd788a92ceddf5a0a34` |
| `main` at ruling time | `72f89a3e59008aaf3576010a3e4e9deeec9b7db9` |
| Independent SAFE verdict on Phase 1 | GO WITH ADVISORY |
| EECOM investigation | PR #46, head `babb077807bab11b70e888988a665aea4ef89e52` — verified unchanged and containing no production code before this ruling was recorded |

## Governor determination

**OBS-017-A: REAL ARCHITECTURE CONTRADICTION, accepted.**

> Subject identity was conflated with authority scope. The frozen RFC requires
> the resolver to preserve the requesting authority boundary, but does not
> normatively require every recursively referenced value to have an identical
> `Subject`. The merged Phase 1 implementation introduced literal `Subject`
> equality as a stricter fail-closed interpretation. That interpretation is
> safe but prevents legitimate RFC-017 cross-resource decomposition.

Verified against repository text, not accepted on report alone: every
occurrence of `Subject` in the frozen RFC (`b8cc0ed`) is either a field
declaration (§4.1, §4.4) or a constraint on the resolver's dispatch behaviour
(§9, P1-F, invariant 10); §7.1 and §7.2 positively depict contributors whose
`Subject` differs from the explained value's. The correction is therefore a
**bounded contract clarification/amendment**, not a new provenance
architecture.

## Governor rulings

### GD-A1 — Subject traversal: **ACCEPTED**

Literal recursive `Subject` equality is not the RFC-017 authority invariant. A
contributor or exclusion **MAY** refer to a different `Subject` from its
parent where that `Subject` is independently proven by Core to belong to the
same authorising household. Subject identity and authority scope are distinct
concepts.

### GD-A2 — `as_of`: **ACCEPTED**

For recursive provenance resolution, `child.as_of` **MUST** equal
`parent.as_of`. Core **MUST NOT** alter, widen, default it, or accept provider
substitution of it. Preserves the temporal component of R1 and SAFE-017-02.

### GD-A3 — `known_at`: **ACCEPTED**

For recursive provenance resolution, `child.known_at` **MUST** equal
`parent.known_at`. Core **MUST NOT** alter, widen, default it, or accept
provider substitution of it. The bitemporal knowledge boundary is unchanged.

### GD-A4 — Root authority: **ACCEPTED**

One authorising household **MUST** be established from canonical Core state
for the root resolution. That authorising household **MUST NOT** change during
one provenance resolution. Ambiguous or unresolvable root authority **MUST**
fail closed.

### GD-A5 — Child authority: **ACCEPTED**

Every emitted contributor or exclusion `Subject` **MUST** independently
resolve through canonical Core authority state to the root authorising
household. A child `Subject` that is unknown, unregistered, ambiguous, or
associated with another household **MUST** be refused. No "unknown means
probably same household" behaviour is permitted.

### GD-A6 — Authority source: **ACCEPTED**

The explainer **MUST NOT** declare, assert, override, or supply the household
authority used to authorise traversal. Authority **MUST** derive from
canonical Core state established independently of the explainer. The current
architectural evidence identifies `AssetRegistry` / canonical household
membership as the existing authority source. **This ruling does not authorise
a direct `AssetRegistry` dependency from the provenance resolver.**

### GD-A7 — Phase 2: **DEFERRED**

Phase 2 implementation authority remains **NONE**. No Finance explainer or
production provenance consumer is authorised by these rulings.

---

## New normative scope contract

Recorded in RFC-017 §9.1 (new subsection) as VP-SCOPE-1 through VP-SCOPE-6.
Summarised here for the ruling record; RFC-017 §9.1 is authoritative for exact
wording:

```text
VP-SCOPE-1  as_of and known_at MUST remain identical to the parent reference,
            in every recursive resolution. Core MUST NOT alter, widen,
            default, or accept provider substitution of either.

VP-SCOPE-2  One authorising household MUST be derived from canonical Core
            state for the root resolution and MUST remain fixed for the
            entire resolution.

VP-SCOPE-3  Every contributor and exclusion Subject MUST independently
            resolve through canonical Core authority state to the root
            authorising household. Unknown, ambiguous, or foreign authority
            MUST refuse.

VP-SCOPE-4  A contributor or exclusion Subject MAY differ from its parent
            Subject. Literal Subject equality MUST NOT be required as the
            authority test.

VP-SCOPE-5  The authorising household MUST NOT be accepted from an
            explainer assertion. Core MUST derive authority from canonical
            state established independently of the explainer.

VP-SCOPE-6  RFC-017 guarantees household isolation at this boundary. It does
            not imply finer-grained per-member or per-resource
            authorisation guarantees that Core does not possess.
```

## Preserved security properties

The amendment does **not** mean "provider chooses another Subject and Core
trusts it." The provider may **identify** a contributor; Core **independently
decides**, from canonical state, whether that contributor belongs to the fixed
authorising household. The following continue to refuse, and were re-verified
against the amended contract rather than assumed:

| Attack | Result |
|---|---|
| `household-A` → resource belonging to `household-B` | refuses |
| `household` → unknown/unregistered `Subject` | refuses |
| parent → child with substituted `as_of` | refuses |
| parent → child with substituted `known_at` | refuses |
| explainer asserts its own household binding | ignored / refuses |
| cycle | refuses (parent `unavailable`) |
| depth bound | unchanged — bounded, lazy expansion |

R1 and SAFE-017-02 are explicitly preserved: R1 was "a provider can cause Core
to resolve coordinates of the provider's choosing." Under VP-SCOPE-3/5 the
provider may still only *name* a subject — Core resolves the binding itself
from canonical state and refuses anything outside the authorising household.
The provider gains the ability to name a contributor, not the authority to
widen the query.

## RFC amendment discipline applied

Per RFC-100 §9.2 — original text retained, dated amendment recorded beside it,
responsible ruling identified, normative change distinguished from
clarification. Applied to RFC-017 (`docs/rfcs/RFC-017-value-provenance-framework.md`):

| Location | Classification | Verified against repository text |
|---|---|---|
| §9 row 2 (*"Scope containment … Core cannot check it"*) | **NORMATIVE AMENDMENT** | confirmed — the claim is factually incomplete; `AssetRegistry` (`core/acquisition.py:266-334`) is a Core, canonical, domain-neutral, production-written authority the original text did not survey |
| W8 (*"Core cannot verify domain scope containment"*) | **NORMATIVE AMENDMENT** | confirmed — narrowed rather than withdrawn: Core verifies the household dimension; finer containment remains a domain obligation |
| §9 row 1 (*"No scope substitution … the resolver never broadens them"*) | **CLARIFICATION** | confirmed — always constrained resolver dispatch, never required contributor `Subject` equality |
| P1-F | **CLARIFICATION** | confirmed — acceptance criterion as delivered was satisfied; its `Subject` clause is restated forward as VP-SCOPE-2–5 |
| Invariant 10 | **CLARIFICATION** | confirmed — "scope" always meant the authority envelope, not literal equality |
| §5.1 | **CLARIFICATION** | confirmed — expansion verification language contains no Subject-equality claim |
| §7.1 / §7.2 | **AFFIRMED — examples remain valid** | confirmed — both worked examples predate and motivate this ruling; neither is corrected |

**No other frozen RFC requires normative amendment.** RFC-011 (`AssetRegistry`
contract) and RFC-015 (`runtime_bootstrap.py` production registration) are
read as evidence of an existing authority source; neither is changed. Had
either required amendment, this burn would have stopped and returned to
Governor — it did not.

## Phase 1 disposition

```text
PHASE 1 IMPLEMENTATION: REMEDIATION REQUIRED
```

**Reason — contract conformance, not repair of a disclosure vulnerability.**
The merged implementation (`82f7310`) remains safe and fail-closed; it
satisfied every stated Phase 1 acceptance criterion, including P1-F as
originally worded. Literal `Subject` equality is **stricter** than the amended
RFC-017 contract requires and prevents legitimate cross-resource provenance.
The already-merged implementation was not unsafe when merged and is not
retroactively judged unsafe by this ruling.

## SubjectAuthority seam — authorised

BOOSTER is authorised to introduce the smallest neutral Core abstraction
necessary to answer the authority question required by VP-SCOPE-2 through
VP-SCOPE-5 (conceptually `SubjectAuthority`; the exact name is not frozen).
Requirements, binding on the remediation:

- read-only; Core-neutral; no event writes; no Finance dependency;
  deterministic; supplied/injected at composition;
- canonical authority remains **external to the explainer**;
- **no** direct `AssetRegistry`, `EventLog`, or Finance dependency from the
  resolver — this preserves P1-A and P1-B, which are asserted structurally;
- **no** general permissions/capability framework. YAGNI applies.

## SAFE-017-04 — Governor disposition

```text
SAFE-017-04 MUST CLOSE BEFORE NEXT CONSUMER
```

**Reason.** The prior debt was acceptable while no materially branching
production provenance graph existed. Same-authority traversal makes
legitimate household-level branching reachable — precisely the shape the
measurement in `docs/rfc-017-technical-debt.md` warned about. The bounded
Phase 1 remediation burn authorised by this ruling is **also authorised** to
close SAFE-017-04.

**Expected minimum-power remediation:** per-resolution memoisation keyed by
`ValueReference`, scoped to the lifetime of one top-level `explain()` call.
BOOSTER must verify the correct deterministic key from the frozen/amended
contract rather than assume this description. **Not authorised:** persistent
caches, cross-request caches, mutable global caches, TTL semantics, cache
events.

## Remediation scope authorised

BOOSTER may change only what is necessary for:

- **A.** Same-authority traversal — replace literal `Subject` equality with
  canonical same-household authority verification.
- **B.** Temporal preservation — exact `as_of`/`known_at` equality, unchanged.
- **C.** Fail-closed authority — refuse foreign household, unknown `Subject`,
  ambiguous authority, provider-asserted authority.
- **D.** Read-only authority seam — preserve P1-A/P1-B structural guarantees.
- **E.** SAFE-017-04 — bounded per-resolution memoisation.
- **F.** Tests — adversarial coverage for every amended invariant and
  amplification behaviour.

### Explicitly out of scope

Finance explainers (pension, property, mortgage or otherwise); production
provenance consumers; UI; Flight Deck work; Mission Assessment changes;
Mission Target changes; new canonical events; new persistence; new capture
workflows; generic authorisation/capability systems; Phase 2 in any form.

### Required validation contract for the remediation burn

Preserve all existing RFC-017 Phase 1 tests. Add coverage for at least: same
Subject/same household; different Subject/same household; different
Subject/foreign household; unknown Subject; ambiguous authority if
representable; exclusion with same authority; foreign exclusion; `as_of`
substitution; `known_at` substitution; provider-asserted authority attempt;
cycle; depth bound; memoised repeated reference; branching graph. Re-run the
existing attack classes — SAFE-017-01, SAFE-017-02, SAFE-017-03, R1, R2, R3,
R4, Loop 2 — none may be weakened to accommodate the amendment.

---

## Stop conditions — assessed at ruling time, none met

| Condition | Assessment |
|---|---|
| Another frozen RFC needs normative amendment | **No** |
| Safe authority verification requires a new global permissions subsystem | **No** — `AssetRegistry` plus `members_of` already establish it |
| `AssetRegistry`/existing Core state cannot provide the binding | **No** — verified directly against `core/acquisition.py:266-334` and `finance/runtime_bootstrap.py:121` |
| Temporal equality must be relaxed | **No** — VP-SCOPE-1 preserves it |
| Remediation requires a canonical event | **No** |
| Remediation requires persistence changes | **No** |
| Remediation requires Finance coupling | **No** — the seam is Core-neutral by construction |
| Amendment materially expands beyond OBS-017-A | **No** |
| PR #46 contains unexpected production code | **No** — verified: one documentation file, zero `src/`/`scripts/` changes |

## Documentation of record

- RFC-017 amended: `docs/rfcs/RFC-017-value-provenance-framework.md` (§9,
  §9.1 new, P1-F note, invariant 10, §7.1/§7.2 affirmation, §14.1 new, W4/W8).
- Technical debt updated: `docs/rfc-017-technical-debt.md` (OBS-017-A
  resolved, SAFE-017-04 disposition changed) — dated blocks beside retained
  originals.
- This ruling record: `docs/reviews/RFC-017-OBS-017-A-ruling.md`.
- EECOM's investigation preserved unmodified as evidence:
  `docs/reviews/RFC-017-OBS-017-A-clarification.md`.
- `docs/rfcs/index.md` updated to reflect this ruling.

## Disposition

```text
BOOSTER remediation authority: READY
Phase 2 authority:              NONE
```

No implementation is performed by this ruling. No production code is changed.
No merge is authorised by this document.
