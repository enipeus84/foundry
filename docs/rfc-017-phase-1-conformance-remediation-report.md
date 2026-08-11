# RFC-017 — Phase 1 OBS-017-A Conformance Remediation Report

**CALLSIGN:** BOOSTER
**SPACECRAFT:** Codex — GPT-5.6
**MISSION:** RFC-017 Phase 1 — OBS-017-A Conformance Remediation

**Status:** Ready for independent TELMU validation. This is a bounded Phase 1
conformance and hardening remediation, not Phase 2 and not merge authority.

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

## Validation

| Surface | Result |
|---|---|
| OBS-017-A plus RFC-017 focused | **66 passed** |
| Relevant Core | **104 passed** |
| Docs governance | pending final documentation validation |
| Full regression | **773 passed** |
| Warnings | **1 pre-existing FastAPI deprecation** |
| `git diff --check` | pending final documentation validation |

Phase 2 authority remains **NONE**.
