# RFC-016 — `DEBT-016-P3-01` Dormancy Remediation SAFE Review

**Review type:** Independent SAFE adversarial review
**Reviewed implementation candidate:**
`b6b224d99d2135b3c3846dbbf5b4cda225b682e0`
**Frozen architecture:** `5ca521b3b1155dad71b1f4a775bd6e1e37659307`
**Freeze Amendment 1:** `fdab858502a1bd56559bcd75bf29a34f9cffec63`

SAFE reviewed the exact candidate above. It was not modified during SAFE review.
This report attaches to that production SHA, not to any later documentation or
governance-publication commit.

## Scope reviewed

SAFE independently exercised 26 adversarial probes. They cover the closure
boundary, historical replay, anti-rewriting, hostile redeclaration and
re-closure, Mission and household isolation, withdrawal, supersession,
effective-time ordering, conflict handling, deterministic replay and
restrictive-only behaviour. The candidate's derivation ignores invalid
non-string identifiers rather than granting actionable state.

Regression evidence: **85 passed** focused; **877 passed** full; **1
pre-existing FastAPI/TestClient warning**. `git diff --check` was clean. No
client authority surface was added: no route, form field, CSRF purpose, writer,
or event kind can invoke Mission closure.

## Findings

| Identifier | Assertion | Reference | Acceptance criterion | Severity |
|---|---|---|---|---|
| OBS-D1 | Structurally invalid, unhashable `entity_id` values such as lists and objects can raise `TypeError` in the older `EntityProjection`. | Pre-existing Core replay behaviour; `DEBT-CORE-REPLAY-01`; candidate derivation accepts only string identifiers. | A future governed Core replay boundary decides and implements handling for invalid identifier types without creating actionable target state. | Low |
| OBS-D2 | Some hostile redeclaration histories trigger the pre-existing Phase 1 loaded-target provenance refusal, dropping the target. | Pre-existing `_validate_loaded_target` provenance rule; parent `5ca521b3`. | Preserve restrictive, fail-closed behaviour; any broader provenance change requires a separate governed burn. | Info |

Neither finding is introduced by the reviewed candidate. OBS-D1 fails loudly and
does not make a closed Mission target actionable. OBS-D2 is restrictive-only and
does not defeat dormancy terminality.

## Severity summary and merge policy

There are no Critical, High, or Medium findings. OBS-D1 is Low and is retained
as **`DEBT-CORE-REPLAY-01`**, OPEN and non-blocking. OBS-D2 is informational
and requires no candidate change. Neither observation authorises a broadened
remediation.

## SAFE verdict

**APPROVE WITH CONDITIONS — PASS WITH NON-BLOCKING OBSERVATIONS — READY FOR
GOVERNOR MERGE REVIEW.** `DEBT-016-P3-01` remains **OPEN** until successful
integration and the frozen §10 closure conditions are met.
