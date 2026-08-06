# RFC-015 — Capture Target Registry: Architecture Freeze Record

**Decision: GO — architecture FROZEN.**
**Freeze date:** 2026-08-05
**Branch:** `rfc-015-capture-target-registry`
**HEAD at gate:** `0ad18b3` (Phase 0 implementation)
**Authority:** Governor freeze gate; review performed by EECOM

Freeze rule applied: *freeze only if the architecture gives BOOSTER an
unambiguous Phase 1 implementation boundary.* It does. No settled decision was
reopened; no repository evidence of a material contradiction was found.

---

## 1. Required checks

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Governor rulings represented consistently across RFC, self-review and index | **PASS** | Rulings appear in RFC §0, §6.1, §13, §14, §14.1, §18; self-review header, C5, Part 4; index "Proposed architecture" note |
| 2 | Title consistently *RFC-015 — Capture Target Registry* | **PASS** | RFC ×6, index ×2, self-review ×2. The only occurrences of the old title are the three deliberate records of the amendment itself |
| 3 | RFC-014 remains reserved for Governed Corrections | **PASS** | RFC §0 ruling block; index note. No document claims RFC-014 |
| 4 | RFC-013 numbering displacement recorded as governance debt | **PASS** | RFC §0 (¶1, ruling block), §18 G2, index ¶ "The RFC-013 number is contested and remains an open Governor decision" |
| 5 | RFC-015's authorised canonical event set is closed | **PASS** | `core.telemetry_stream.retired` was approved at freeze; the Governor-approved [Phase 2A Diagnostic Event Amendment](RFC-015-phase-2a-diagnostic-event-amendment.md) adds `core.capture_target_bootstrap.diagnostic`. No further kind is authorised without Governor approval. |
| 6 | `entity_exists` production stub remains a binding Phase 1 blocker | **PASS** | RFC §14.1 **P1-A** (worded as blocker, "no registration path may be exposed while the stub remains"), §10, §18; self-review S1. Stub still present at `src/foundry/operations_web.py:60` — correctly untouched by Phase 0 |
| 7 | Retirement precedes bootstrap | **PASS** | RFC §14 sequence 0→1→2→3→4 with retirement in Phase 1; ruling block and §18 G6 both state it |
| 8 | Runtime bootstrap fails closed; no display-name inference | **PASS** | RFC §13 G7 ruling: resolve canonical type at runtime, declare nothing and report why if inadmissible, "never promoted because its name contains 'Cash' or 'ISA'"; §7.1 selects by `account_type`/`asset_category` only; §15 invariant 1 |
| 9 | `statement_total` removal outside this branch, pending separate governed amendment | **PASS** | `src/foundry/capture_contracts.py:255` **unchanged**; the file is absent from `git diff --name-only main...HEAD`. RFC §6.1 and §18 G4 both require an explicit governed amendment |
| 10 | Phase 0 changed only truthful empty-state rendering; no registry behaviour | **PASS with recorded carry-forward** | See §2 |
| 11 | No unresolved decision that would materially alter Phase 1 | **PASS** | See §3 |
| 12 | Docs governance and full suite pass | **PASS** | `tests/test_docs_governance.py` 4 passed; full suite **665 passed** |

---

## 2. Phase 0 boundary confirmation *(check 10)*

Phase 0 (`0ad18b3`) touched exactly two files —
`src/foundry/operations_web.py` (+13/−3) and
`tests/test_rfc_013_capture_contracts.py` (+28). It rebound the empty-state
condition from `if guided:` to the three §11 cases and added one test per case,
including the decisive assertion that contracts-without-targets does **not**
emit "Capture is not configured".

**No registry behaviour was implemented.** No projection, no retirement event,
no asset-registration join, no lifecycle filter, no registration route, no
canonical event, and no change to `capture_contracts.py`, `core/acquisition.py`
or any Finance module.

Two items are **carried forward to Phase 1** and recorded in RFC §14.0 so that
Phase 0 is not mistaken for a partial registry:

- **`compatible_targets` is a rendering predicate, not the registry.** It
  filters household manual streams by contract-accepted property and performs
  none of the §6 fail-closed resolution. Phase 1 **replaces** it rather than
  extending it (criterion **P1-F**).
- **The per-contract message at `operations_web.py:296` is still stream
  language.** §11 specifies target language there; it was correctly deferred,
  because the registration route it should offer does not exist until Phase 1.
  Carried as UI state 2 of §12 under **P1-F**.

Neither affects the architecture. Both are implementation deliverables now
named explicitly rather than left implicit.

---

## 3. Residual ambiguity *(check 11)*

**None that alters Phase 1.** Three items remain open, and all three are
scoped outside Phase 1 by ruling:

| Item | Scope | Why it does not block Phase 1 |
|---|---|---|
| G2 — the RFC-013 number and displaced boundary | Governance | A numbering decision; touches no code, no event, no projection |
| G4 — `statement_total` removal | Separate governed amendment | Phase 1 builds the projection; the property set is contract metadata. Bootstrapping on `cash_balance` only is correct both before and after |
| G7 — deployed Cash ISA type | **Phase 2** runtime resolution | Phase 1 declares no real targets; the fail-closed rule is already specified |

---

## 4. Phase 1 is implementable without architectural invention

Every decision Phase 1 must make is already made in the frozen document:

| Phase 1 question | Answered by |
|---|---|
| What is a target? | §2 — projection over `AssetRegistration` ⋈ `TelemetryStream` ⋈ domain entity |
| Which events? | §3.1 (existing two) + §4.1 (`core.telemetry_stream.retired`) + approved [Phase 2A amendment](RFC-015-phase-2a-diagnostic-event-amendment.md) (`core.capture_target_bootstrap.diagnostic`) |
| When is a target offered? | §6 — the six-clause rule, declarative |
| When is it active? | §9 — the three-clause predicate |
| Which entity types per property? | §5.2 — the descriptor table |
| Where does the domain seam sit? | §5.3 — neutral projection, domain-owned descriptor provider |
| What must not happen? | §15 — nine invariants |
| What must be tested? | §16 |
| When is Phase 1 done? | §14.1 — P1-A…P1-F |

No open question requires BOOSTER to invent structure.

---

## 5. Frozen invariants

1. No display name is ever an identity.
2. A target exists only where stream, registration and domain entity agree on household.
3. Capability is derived from canonical state; no mutable side-table.
4. Operations names no domain type, no contract identifier and no entity.
5. The authorised canonical event set is `core.telemetry_stream.retired` and
   `core.capture_target_bootstrap.diagnostic`; no further kind is authorised
   without Governor approval.
6. Registration writes `core.*` declarations only; never `finance.*`.
7. Retirement removes a target from current selection and operational action
   generation while preserving history, evidence, provenance and deterministic
   replay.
8. `(household_id, subject_id, property)` is unique among active targets.
9. Every gate fails closed; ambiguity is refused, never resolved by guess.
10. Entity closure and stream retirement remain separate canonical facts.

Changing any of these requires a Governor amendment, not an implementation
decision.

---

## 6. Phase 1 entry conditions

- **P1-A is a blocker, not a task.** No registration path may be exposed while
  `entity_exists=lambda _entity: True` stands at `src/foundry/operations_web.py:60`
  and in the capture POST path.
- Phase 1 declares **no real household targets** — that is Phase 2, after G7 is
  resolved against the deployed log.
- Phase 1 introduces exactly one canonical event. Any second event is a freeze
  breach and returns to the Governor.
- Phase 1 replaces `compatible_targets`; it does not extend it.
- RFC-011 acquisition, RFC-012 Operations, RFC-013 contracts, confirmation
  semantics, append-only storage, household scoping, authentication, body-only
  signed CSRF and SAFE-012-01 are all out of scope for modification.

---

## 7. Repository state at freeze

| | |
|---|---|
| Branch | `rfc-015-capture-target-registry` |
| Implementation files changed by this gate | **none** |
| Tests | 665 passed; docs governance 4 passed |
| Pushed | no |
| PR | not created |

**RFC-015 architecture is frozen as of 2026-08-05. Phase 1 is GO for
implementation.**
