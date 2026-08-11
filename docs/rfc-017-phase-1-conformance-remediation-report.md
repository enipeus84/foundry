# RFC-017 — Phase 1 OBS-017-A Conformance Remediation Report

**CALLSIGN:** BOOSTER
**SPACECRAFT:** Codex — GPT-5.6
**MISSION:** RFC-017 Phase 1 — OBS-017-A Conformance Remediation

**Status:** Closed for independent SAFE review at final remediation
`00d45f4207c05c8e36f792c8fe1af0668fd40671`; SAFE returned **GO WITH
ADVISORY**. This remains bounded Phase 1 conformance and hardening work, not
Phase 2 and not merge authority.

## Authority and scope

The remediation starts from merged Phase 1 `72f89a3` and applies Governor
amendment `b360892c5f231acafa0e84fdd2ebb884814793a9`, including GD-A1 through
GD-A7. GD-A7 remains deferred: no Finance explainer, consumer, route, UI,
canonical event, persistence, calculation change, `MetricResult` change, or
RFC-006 change is present.

## OBS-017-A conformance

`Subject` remains the identity of each `ValueReference`; it is no longer used
as the authority predicate. `ProvenanceResolver` receives an injected,
read-only `SubjectAuthority` and establishes one root household for each
`explain()` call. It verifies every contributor and exclusion independently
against that fixed household before return or recursive dispatch. `as_of` and
`known_at` remain exact equality checks.

`CanonicalSubjectAuthority.from_canonical_state()` is the composition seam. It
accepts read views of canonical `AssetRegistry.registrations` and
`EntityProjection.parties`, derives household parties, unambiguous person
membership, and registered-resource authority, then exposes only
`household_for(Subject)`. Neither the resolver nor the seam imports a registry,
event writer, or Finance module. The structural P1-B probe proves that absence;
the seam has no write operation.

The amended tests replace only the literal-`Subject` assertions that Governor
superseded. Temporal substitution assertions are retained; SAFE-017-02 now
distinguishes permitted different identity plus same household from refused
foreign authority.

## SAFE-017-04 closure

Memoisation is a local `dict[ValueReference, ProvenanceNode]` created inside
one top-level `explain()` call. The key therefore includes the complete subject
identity, normalised value id, `as_of`, and `known_at`; it uses neither labels
nor provider state. Only verified provider output is memoised. Every traversal
still performs root/child authority checks, emitted-reference checks, depth
checks, and path-cycle checks, so no cached result bypasses an authority
envelope or turns a cycle into success.

Executable evidence: the diamond resolves its shared node once per top-level
call and twice across two calls; an eight-branch fan-out resolves ten distinct
references exactly once each (`root + 8 branches + shared`) rather than the
seventeen provider calls caused by path repetition. The stateful-provider and
cycle probes remain fail-closed.

This closes SAFE-017-04's repeated-identical-reference amplification class for
the next consumer gate. It does not claim a performance envelope: a genuinely
wide graph of distinct `ValueReference`s still costs one provider resolution per
distinct reference.

## Independent self-probes

Foreign-household contributor and exclusion: refused. Unknown subject and
ambiguous party membership: refused. Same-household account, asset, obligation,
and exclusion: accepted. Future `known_at` and different `as_of`: refused.
Separate top-level calls do not share a cache. A stateful provider cannot emit a
second answer for a repeated semantic reference within one tree. A cycle behind
a cached base node remains unavailable.

## Initial OBS-017-A validation

| Surface | Result |
|---|---|
| OBS-017-A plus RFC-017 focused | **66 passed** |
| Relevant Core | **104 passed** |
| Docs governance | **4 passed** |
| Full regression | **773 passed** |
| Warnings | **1 pre-existing FastAPI deprecation** |
| `git diff --check` | **clean** |

This evidence applies to the initial OBS-017-A remediation tree published as
`6f6838d8ac13f7f7e0e039e06ce8b03fd685e0b9`, before TELMU's malformed-Subject
authority-alias finding. It is retained as chronology, not presented as final
candidate evidence.

## Final candidate chronology and validation

1. OBS-017-A conformance remediation was first published as `6f6838d`.
2. Independent TELMU validation found malformed `Subject` identities could
   alias a registered resource authority through the shared id.
3. BOOSTER remediated the alias in the canonical authority adapter and added
   durable root, contributor, exclusion, depth-bound, nested, and cache-path
   regressions.
4. TELMU re-validation returned **GO TO SAFE** for that exact remediation tree.
5. The exact TELMU-validated tree was published unchanged as
   `00d45f4207c05c8e36f792c8fe1af0668fd40671`.
6. Independent SAFE reviewed `00d45f4` and returned **GO WITH ADVISORY**.

TELMU's final-candidate evidence, recorded against `00d45f4`, was:

| Surface | Result |
|---|---|
| RFC-017 focused | **79 passed** |
| Relevant Core | **104 passed** |
| Docs governance | **4 passed** |
| Full regression | **786 passed** |
| Warnings | **1 pre-existing FastAPI deprecation** |
| `git diff --check` | **clean** |

SAFE's independent evidence remains distinct: **79** focused tests, **110**
Core tests, **4** docs-governance tests, and **784 passed with two environmental
`test_demo_data.py` failures** under its root-permission environment. SAFE
determined those failures were unrelated to `00d45f4`; its run retained the one
pre-existing warning and a clean `git diff --check`.

SAFE's final verdict was **GO WITH ADVISORY**: **0 Critical**, **0 High**,
**1 Medium advisory**, **2 Low**, and **1 Observation**. The stale-report
LOW-2 is closed by this dated addendum. SAFE-017-01, SAFE-017-02, SAFE-017-03,
R1, R2, R3, R4, and Loop 2 remain closed; OBS-017-A is architecturally closed.

Phase 2 authority remains **NONE**.
