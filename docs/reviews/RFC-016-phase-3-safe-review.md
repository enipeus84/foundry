# RFC-016 Phase 3 — Mission Target Management SAFE Review

**Review type:** Independent SAFE adversarial review

**Frozen architecture:** `b7957d63524e49bedcf60273ff5634ebaf8861e3`

**Reviewed implementation candidate:** `b81517e74adcd3e116a52ef0b7f6c3fc235f8350`

**Candidate integrity:** The reviewed candidate tree was not modified during
SAFE review. This report attaches to the exact SHA above; it does not approve
any later documentation or governance-evidence commit.

## Scope and evidence

SAFE independently ran 44 adversarial probes against the frozen six-route
boundary and the exact candidate. The probes covered stale review/approval,
forged and duplicate form fields, lifecycle ordering, cross-household and
cross-Mission access, hostile canonical histories, replay and empty-world
rendering. The full suite passed: **872 passed**, with **one pre-existing
FastAPI/TestClient deprecation warning**.

TELMU's isolated `test_demo_data.py` failure was reproduced as an environment
write restriction: the test attempted to create its lock under the externally
mounted repository. The same exact candidate passed the full suite in a
writable detached checkout. Candidate code was uninvolved.

## Findings against the frozen targets

| Target | SAFE result |
|---|---|
| S11 — staleness assertion | `reviewed_in_force` is match-only: it is absent from event payloads and cannot select `supersedes`, metric metadata or horizon semantics. |
| Authentication | All six routes require the existing signed session and configured-email equality. |
| Household and Mission authority | Household, Mission activity, metric semantics and binding are re-derived from canonical state; cross-household and unavailable state refuse without append. |
| CSRF separation | Review, declaration and withdrawal use distinct non-transferable CSRF purposes. |
| Hidden fields and parameter pollution | Exact form fields, URL-encoded bodies and single-valued keys are enforced; forged derived fields and duplicates refuse without append. |
| Canonical events | The surface writes only the existing `core.mission_target.declared` and `core.mission_target.closed` paths through the protected projection. |
| Basis | Optional basis is bounded to 500 Unicode characters, escaped at render, never interpreted, and disclosed as permanent append-only history. |
| Horizon | Finance supplies deterministic horizon mapping; the browser cannot choose horizon semantics; unsupported metrics refuse. |
| Empty world | No household, Mission or target is fabricated. Rendering performs zero canonical writes. |
| Acquisition boundary | No acquisition, Capture Contract or Capture Target Registry integration is introduced. |
| Protected Core | `src/foundry/core/mission_targets.py` remains byte-identical: SHA-256 `90cc500b3859bc47ef5ffb4813d4f513274eeb038aad8ccba481ca55101325a0`. |
| Regression | Full regression passed as stated above; no Mission Assessment, provenance consumer, Flight Deck change or new canonical event was introduced. |

## Observations

| Identifier | Severity | Observation | Disposition |
|---|---|---|---|
| OBS-P3-01 | Low | CSRF verification follows some canonical-state resolution on `/review` and `/declare`, allowing the authenticated configured operator to distinguish limited 403/404 outcomes. No state mutation occurs before CSRF verification. | Governor: **accepted for this release**. No candidate change authorised. |
| OBS-P3-02 | Info | Conflicted state may return differing 404/409 behaviour between workflow stages. | **Accepted.** |
| OBS-P3-03 | Info | An uncomposed `Console` yields a 500 while failing closed, appending nothing and disclosing no internal message. | **Accepted.** |

The unsigned `reviewed_in_force` assertion is intentional: it holds no
canonical authority and can only match server-derived state or cause refusal.

## Debt and residuals

`DEBT-016-P3-01`, `DEBT-016-P3-02`, and RFC-016 W7 remain recorded without
remediation. In particular, the inactive-Mission/dormancy gap must be resolved
before the first production assessment, decisioning, recommendation or Flight
Deck consumer relies on `in_force` Mission Target state, regardless of future
phase or RFC numbering.

## SAFE verdict

**PASS WITH NON-BLOCKING OBSERVATIONS — READY FOR GOVERNOR MERGE REVIEW**
