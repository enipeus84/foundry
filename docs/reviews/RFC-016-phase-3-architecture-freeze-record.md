# RFC-016 Phase 3 — Mission Target Management: Architecture Freeze Record and Implementation Boundary

**Decision: APPROVED — ARCHITECTURE FREEZE GRANTED.**
**Freeze date:** 2026-08-11
**Baseline head:** `b35328e3b8e5df5106cfa7abb68e89a0177f4726` (main, tree CLEAN)
**Baseline validation:** 802 passed; 1 pre-existing FastAPI/TestClient deprecation warning; `git diff --check` clean.
**Branch:** `rfc-016-phase-3-architecture-freeze`
**Authority:** Governor architecture freeze signature, rulings **GD-A** through **GD-J** and Governor findings 1–10.

**IMPLEMENTATION AUTHORITY: NOT GRANTED.** BOOSTER receives implementation
authority only by a subsequent, explicit Governor act (RFC-100 §9.1). Merge of
this record is a distinct Governor act (RFC-100 §9.3).

**Attribution.** §1 and §2 record **Governor acts** and are transcribed by EECOM
at the Governor's direction (RFC-100 §1.2, §9.4); nothing in them is EECOM's
judgement. §3 onward is the EECOM implementation boundary derived from those
acts and from the preceding architecture burn, accepted by the Governor exactly
as proposed and amended by the findings in §2.

**Preceding artefact.** The architecture burn was commissioned under the working
term *RFC-018 — Mission Target Capture*. Ruling **GD-A** settles that this work
is **RFC-016 Phase 3** and creates no RFC-018; ruling **GD-C** and §1.1 retire
the word *Capture*. The burn's findings are carried into this record; the burn
itself is superseded in name and status by this document.

---

## 1. Ruling transcription

| # | Subject | Disposition |
|---|---|---|
| **GD-A** | Programme boundary / numbering | **Settled.** This work proceeds as **RFC-016 Phase 3 — Mission Target Management**. It does **not** create RFC-018. RFC-017 ruling GD-10 is respected: the architecture burn found no genuinely new architectural boundary requiring a new RFC. |
| **GD-B** | Horizon kind | **Settled.** `horizon_kind` **must not** be arbitrary operator input; it is derived from already-authorised RFC-016 Finance target semantics. A minimal Finance-owned mapping may be introduced to make that derivation explicit and deterministic. This authorises **no** expansion or redesign of the RFC-016 descriptor framework. |
| **GD-C** | Product surface | **Settled.** `/missions` is the authorised surface. `/operations/capture` **must not** be extended for this purpose. RFC-013 Capture Contracts and RFC-015 Capture Target Registry **must not** be distorted to represent Missions as telemetry streams, assets or Finance manual-capture subjects. |
| **GD-D** | Mission status | **Accepted with explicit debt.** The Phase 3 surface must refuse Mission Target management where the Mission is not in an appropriate active state. Phase 3 **must not** expand into repair or redesign of `MissionTargetProjection` to implement dormant-state semantics. The projection-level status gap **must** be recorded as explicit RFC-016 technical debt with owner and future disposition. |
| **GD-E** | Mission instantiation | **Settled.** Phase 3 authorises **no** automatic or synthetic Mission instantiation. With no Missions in canonical state, the surface may correctly contain nothing manageable. Mission state **must not** be fabricated to populate the UI. Existing programme sequencing is unchanged. |
| **GD-F** | `basis` | **Include in v1.** The optional RFC-016 `basis` field remains part of the operator capability. The surface must communicate that an approved declaration is canonical append-only history and that `basis` text becomes part of that permanent record. **No** editing or redaction semantics in Phase 3. |
| **GD-G** | Review / approval authority | **Architectural invariant.** In-request review is accepted provided **review is informational, not authoritative**. Approval **must** reconstruct and revalidate the intended canonical change against **current** canonical state immediately before append. The client **must not** be authoritative for derived fields across the review boundary — specifically household authority, subject authority, metric metadata, unit, dimension, direction, horizon semantics, effective lifecycle relationships and `supersedes`. **`supersedes` must be derived again from current canonical state at approval time.** **No stale reviewed state may silently overwrite or supersede newer canonical state.** |
| **GD-H** | Lifecycle capability | **Settled — declare + supersede + withdraw.** Phase 3 must provide an ordinary operator path for the complete reachable RFC-016 management lifecycle. `core.mission_target.updated` or any equivalent mutable shortcut is prohibited. A declaration-only surface is **not sufficient**. |
| **GD-I** | Events | **Settled — no new canonical events.** Phase 3 consumes `core.mission_target.declared` and `core.mission_target.closed`. Any discovery that a new canonical event is required is a **STOP condition** requiring renewed Governor authority before implementation. |
| **GD-J** | Scope boundary | **FREEZE.** Phase 3 authorises none of: Mission Assessment, progress calculation, target/current-value comparison, provenance consumption, provenance UI, Flight Deck changes, AI target recommendations, automatic target changes, Mission instantiation, new provenance events, provenance persistence, Finance acquisition changes, broad Mission Framework redesign. |

### 1.1 Naming — binding

The working term **"Mission Target Capture" is retired.** "Capture" denotes
participation in the RFC-011/013/015 acquisition architecture, which **GD-C**
expressly excludes. This phase is **Mission Target Management** in every
document, route name, module name, test name, CSRF purpose string and UI string.

RFC-016 §0.5's existing naming discipline continues to bind: the concept is
*Mission Target* in prose and `MissionTarget` in code, never the bare word
"target" where **capture target** (RFC-015) or `MissionMilestone.target_value`
(RFC-006) could be read.

### 1.2 Objective — binding statement of sufficiency

> Make the existing RFC-016 Mission Target lifecycle safely and ordinarily
> operable by an authorised human.

Anything not required by that sentence is outside Phase 3.

---

## 2. Governor findings at signature

Recorded as ruled. Where a finding amends the candidate boundary, the amendment
is applied in the section named.

| # | Finding | Disposition | Applied at |
|---|---|---|---|
| **1** | Surface | **APPROVED.** Mission Target Management belongs under `/missions`. The Operations acquisition architecture must remain untouched. The separation through `mission_targets_web.py` is accepted, and that module **must not** depend on `operations_web.py` or `acquisition_web.py`. | §3, I-12 |
| **2** | Review / approval | **APPROVED.** The frozen stale-state mechanism is the authorised implementation of GD-G, with the staleness assertion's prohibited uses enumerated. | §7 |
| **3** | Derived state | **APPROVED.** Household, metric identity, unit, dimension, direction, horizon semantics, `effective_from` and `supersedes` remain server-derived and must not be accepted as operator form fields. Any implementation that lets these become client authority **violates the freeze**. | §5.2, I-4 |
| **4** | Lifecycle | **APPROVED.** First declaration, supersession/replacement and withdrawal. No mutable target-update event or shortcut is authorised. | §6 |
| **5** | Canonical events | **APPROVED.** No new canonical event. Discovery of a requirement for another is a STOP condition. | §10 |
| **6** | Mission status / dormancy | **APPROVED WITH DEBT.** `DEBT-016-P3-01` accepted; the surface guard is mitigation only. **Governor clarification applied:** the resolution condition is semantic, not numerical. | §9.2, §16.1 |
| **7** | Mission instantiation | **APPROVED.** No Mission may be created, bootstrapped or synthesised merely because the surface is rendered. An empty canonical Mission set must remain an honest empty state. | §4, I-13 |
| **8** | Input deferrals | **APPROVED.** `tolerance` and backdated `effective_from` are deferred; their omission alters no RFC-016 canonical contract. **Neither may be added during implementation without renewed architecture authority.** | §5.4 |
| **9** | `basis` | **APPROVED.** Optional `basis` remains available; the surface must make clear that approval creates append-only canonical history. No editing or redaction feature is authorised. | §5.1, §12 |
| **10** | Blast-radius enforcement | **APPROVED.** The untouched-file list is an implementation invariant; `core/mission_targets.py` must remain **byte-identical**. Any prohibited-file modification is a **NO-GO** unless EECOM returns to the Governor with repository evidence that the frozen boundary is insufficient. | §12, I-14 |

### 2.1 Governor clarification — DEBT-016-P3-01 resolution condition

The candidate stated the obligation as "before Phase 4". The Governor replaced
that with a **semantic** condition that travels with the consumer rather than
with a programme label:

> **`DEBT-016-P3-01` MUST be resolved before any later phase or RFC gives
> `in_force` Mission Target state its first production assessment, decisioning,
> recommendation or Flight Deck consumer.**
>
> If that consumer is RFC-016 Phase 4, resolution is required before Phase 4.
> If programme numbering changes, the obligation travels with the first
> consumer.

**No dependency on this debt may be expressed solely by the label "Phase 4".**

---

## 3. Authorised surfaces and routes

Phase 3 authorises **exactly six route handlers** in **one new module**. No other
route may be added, and no existing route outside this table may change
behaviour.

| # | Method | Path | Purpose | CSRF purpose string |
|---|---|---|---|---|
| R1 | `GET` | `/missions` | Mission Target Management surface; replaces the placeholder at `mission_control.py:2419-2423` | — |
| R2 | `GET` | `/missions/targets/new` | Declaration form for one Mission (`?mission=<mission_id>`) | — |
| R3 | `POST` | `/missions/targets/review` | Normalise, validate, render the proposed canonical change. Writes nothing | `rfc016-target-review` |
| R4 | `POST` | `/missions/targets/declare` | Re-derive, revalidate, append `core.mission_target.declared` | `rfc016-target-declare` |
| R5 | `GET` | `/missions/targets/{target_id}/withdraw` | Withdrawal confirmation, with reason | — |
| R6 | `POST` | `/missions/targets/withdraw` | Re-derive, revalidate, append `core.mission_target.closed` | `rfc016-target-withdraw` |

**Route constraints.**

- All six require the authenticated operator; unauthenticated requests redirect
  to `/login` with 303, matching the existing convention.
- The three CSRF purpose strings are **new and distinct**, and must not collide
  with `rfc012-capture`, `rfc013-capture` or `rfc011-confirmation`.
- R3's token must not be accepted by R4, and neither by R6.
- All POST bodies are `application/x-www-form-urlencoded` only, parsed with
  `strict_parsing=True`, single-valued keys only, and validated against an
  **exact expected field set** — an unexpected field is a refusal, never a
  silent drop. This is the discipline already proven at
  `operations_web.py:427-432` and `acquisition_web.py:253-268`.
- The module renders in the existing Mission Control shell via `_render` /
  `_footer` / `_as_of`, with `/missions` as the active nav path. The nav entry
  already exists (`mission_control.py:982-983`).

**Module placement.** A new `src/foundry/mission_targets_web.py`, registered in
`web.py` beside the existing routers. Per Governor finding 1 it **must not**
import from `operations_web.py` or `acquisition_web.py`; importing the shared
shell helpers from `mission_control` follows the precedent at
`operations_web.py:35`.

---

## 4. Operator workflow

```
R1  /missions
    per active Mission:  label · metric · in-force target or "No target declared"
                         · conflict state where the projection reports one
    actions:             Declare  (no target)
                         Change   (target in force)   → same form, supersession derived
                         Withdraw (target in force)

R2  /missions/targets/new?mission=<id>
    operator supplies:   destination value
                         horizon date        (only when the derived kind is by_date)
                         basis               (optional, permanence stated — GD-F)

R3  POST /missions/targets/review
    server derives everything else (§5), dry-run validates (§7.2),
    renders the exact canonical change and what it supersedes.
    NOTHING IS WRITTEN.

R4  POST /missions/targets/declare
    server re-derives from CURRENT canonical state (GD-G),
    revalidates, appends exactly one core.mission_target.declared,
    redirects 303 to /missions

R5  GET  /missions/targets/{id}/withdraw   → confirmation + reason field
R6  POST /missions/targets/withdraw        → one core.mission_target.closed
                                             redirect 303 to /missions
```

**Empty and degraded states must be honest (GD-E, Governor finding 7).** No
household; no active Mission; a Mission whose metric has no descriptor; a
Mission in target conflict. Each renders an explanatory state. **No Mission,
household, target, telemetry stream or asset registration may be created,
bootstrapped, synthesised or fabricated for any reason, including to populate a
surface.**

---

## 5. Canonical input versus derived state

### 5.1 The complete operator input set

| Field | Form control | Constraint |
|---|---|---|
| Mission | `select` over a closed, canonical set | active Missions of the session household that hold a described metric |
| Destination value | `number` | finite; typed by `TargetQuantity` |
| Horizon date | `date` | **present only when** the derived `horizon_kind` is `by_date`; absent otherwise |
| Basis | `textarea`, optional | ≤ 500 Unicode characters (Governor clarification C-016-01); escaped at render; never parsed |
| Withdrawal reason | `text` (R5/R6 only) | non-empty |

**No other operator input is authorised.** Per Governor finding 9, the surface
must state at the point of approval — not merely at the point of entry — that an
approved declaration becomes canonical append-only history and that `basis` text
becomes part of that permanent record.

### 5.2 Derived by Foundry — never accepted from the client (Governor finding 3)

| Field | Derivation |
|---|---|
| `household_id` | session-derived active household |
| `metric_id` | `Mission.target_metric` |
| `destination_dimension` | `MetricDescriptor.describe(metric_id).dimension` |
| `destination_unit` | `MetricDescriptor.describe(metric_id).unit_or_currency` |
| `destination_direction` | `MetricDescriptor` + `MissionDefinition.destination_direction`, both re-checked by the gate |
| `horizon_kind` | Finance-owned mapping (§5.3) |
| `effective_from` | approval time (`time.time()`), computed at R4, never carried from R3 |
| `supersedes` | id of the currently in-force target for the Mission, or absent — **re-derived at R4** |
| `entity_id` | `grammar.new_id()` |
| `actor` | session email |

**These names must not appear in any accepted form field set.** A field that
cannot be submitted cannot be trusted; the exact-field-set check is the
enforcement, and it is invariant I-4. **Any implementation that allows these
fields to become client authority violates this freeze** (Governor finding 3).

### 5.3 Horizon derivation (GD-B)

A minimal Finance-owned mapping, placed beside the existing descriptors in
`src/foundry/finance/mission_targets.py`, transcribing RFC-016 §6's table — which
that RFC asserts is complete for the four locked missions:

| `metric_id` | `horizon_kind` | RFC-016 §6 row |
|---|---|---|
| `finance.liquidity_runway` | `none` | Financial Resilience |
| `finance.accessible_assets` | `by_date` | Financial Independence |
| `finance.pension_wealth` | `derived` | Pension Independence |
| `finance.mortgage_balance` | `by_date` | Mortgage Freedom |

**A metric absent from this mapping refuses declaration.** Unknown is never
assumed (RFC-016 FR-008). The mapping is **capture-side only**: it adds no field
to `MetricDescriptor`, changes no frozen contract, and is not a canonical
invariant — the projection continues to accept any admissible `horizon_kind`
from any writer, and today this surface is the only writer. See `DEBT-016-P3-02`.

`horizon_at` is supplied **only** for `by_date` and must be **absent** from the
payload for `none` and `derived`, which the projection enforces at
`core/mission_targets.py:173-176`.

### 5.4 Explicit field deferrals (Governor finding 8)

- **`tolerance`** — optional in RFC-016, consumed by nothing today. Deferred.
  A target may gain a tolerance later by ordinary supersession with no loss of
  lineage, so deferral forecloses nothing.
- **Backdated `effective_from`** — deferred. RFC-016 §7.3 permits backdating
  only with an explicit retrospective-declaration disclosure, which lives in the
  assessment path and is unimplemented. Offering backdating without it would let
  the log assert foresight it did not have.

**Neither may be added during implementation without renewed architecture
authority.** Their omission alters no RFC-016 canonical contract.

---

## 6. Lifecycle transitions (GD-H, Governor finding 4)

| Operator situation | Canonical mechanism | Event |
|---|---|---|
| First target for a Mission | `declare()` with `supersedes` absent | `core.mission_target.declared` |
| Replace / change an active target | `declare()` with `supersedes` **derived** from the in-force target | `core.mission_target.declared` |
| Withdraw an active target | `withdraw()` with an operator reason | `core.mission_target.closed` |
| Resume after withdrawal | fresh declaration, `supersedes` absent | `core.mission_target.declared` |
| Target met | **nothing** — attainment is an assessment outcome, never an event (RFC-016 §7.5) | none |
| Mission closed | nothing written; the target is dormant by interpretation | none |

**Refused at the surface, appending nothing:**

- a second active target without supersession (projection, `:321-323`);
- supersession of a withdrawn, already-superseded, cross-mission or
  cross-household target (`:325-329`);
- any declaration or withdrawal against a Mission that is not active (GD-D, §9.2);
- any declaration or withdrawal against a Mission the projection reports in
  conflict — neither target is offered and no new target may be layered onto an
  ambiguous lineage (RFC-016 §3.4);
- any declaration whose metric has no descriptor or no horizon mapping.

**Prohibited outright:** `core.mission_target.updated`, any equivalent mutable
shortcut, and any write to `Mission.target_value`, `target_date`,
`target_range`, `tolerance` or `core.mission.updated`.

---

## 7. Review and approval mechanics (GD-G, Governor finding 2)

### 7.1 The invariant

> **Review is informational, not authoritative.**

R3 exists so a human can read the canonical consequence before it becomes
permanent. It confers no authority on anything it rendered. R4 behaves as though
R3 never happened, except for one staleness assertion (§8).

### 7.2 R3 — review

1. Verify session, allowed email, CSRF purpose `rfc016-target-review`, exact
   field set.
2. Resolve the Mission from canonical state; refuse if unknown, not active, not
   the session household's, in conflict, or without a described metric and a
   mapped horizon.
3. Derive every field of §5.2 from current canonical state.
4. Run the **existing** declaration validation as a dry run —
   `MissionTargetProjection._validate_declaration` — with no append.
5. Render: Mission, metric, destination with unit, direction, horizon, the
   predecessor it would supersede (or "this is the first target"), the `basis`
   text, and the GD-F permanence statement.
6. Emit the R4 form carrying **only**: the operator inputs of §5.1, the
   `mission_id`, the staleness assertion of §8, and a fresh
   `rfc016-target-declare` CSRF token.

**R3 writes nothing to the log, the vault or any store.**

### 7.3 R4 — approval

1. Verify session, allowed email, CSRF purpose `rfc016-target-declare`, exact
   field set.
2. **Re-derive every field of §5.2 from current canonical state**, including
   `supersedes` and `effective_from`. Nothing derived is read from the request.
3. Apply the staleness check of §8.
4. Call `MissionTargetProjection.declare(...)`, which validates before appending
   and appends exactly once.
5. Redirect 303 to `/missions`.

**The single append is the last step.** Any refusal at any point leaves no
partial state — the property RFC-016 §9 requires.

### 7.4 R6 — withdrawal approval

Same shape: session, allowed email, CSRF purpose `rfc016-target-withdraw`, exact
field set, Mission re-resolved and re-checked for active status, target
re-resolved from current canonical state, then
`MissionTargetProjection.withdraw(household_id=<derived>, target_id=..., reason=..., actor=<session email>)`.
The projection already enforces household ownership and refuses an
already-withdrawn target (`core/mission_targets.py:277-285`).

---

## 8. Stale-state behaviour (GD-G, Governor finding 2)

### 8.1 Required behaviour — refuse, do not reconstruct

GD-G permitted either safe reconstruction or refusal. **This freeze requires
refusal.** Reconstructing a command whose predecessor changed would mean
superseding a target the operator never saw, which the ruling forbids in
substance even where it would be technically valid.

### 8.2 Mechanism

The R4 and R6 forms carry a **staleness assertion**: the id of the in-force
target the review was rendered against, or the literal `none`.

At approval the server derives the current in-force target independently and
compares.

| Outcome | Effect |
|---|---|
| **MATCH** | approval may continue |
| **MISMATCH** | approval is refused; a fresh review is required |

### 8.3 The staleness assertion is not canonical input — binding

Per Governor finding 2, the assertion **MUST NOT**:

- become event data;
- determine `supersedes`;
- override canonical state;
- grant authority;
- influence metric or horizon semantics.

Its only valid outcomes are MATCH and MISMATCH. It is compared, never written.
A forged assertion can therefore cause only a refusal, or agree with a truth the
server derived independently — which is what keeps it compatible with GD-G's
prohibition on client-supplied lifecycle relationships.

### 8.4 Cases that must refuse and require a fresh review

| Case | Reviewed | At approval |
|---|---|---|
| Double submit / back-button replay | `none` | a target now exists |
| Concurrent declaration in another tab | `t1` | `t2` |
| Target withdrawn between review and approval | `t1` | `none` |
| Target superseded between review and approval | `t1` | `t2` |
| Mission closed between review and approval | active | not active |
| Mission fell into conflict between review and approval | clean | conflict |

### 8.5 Concurrency note

`EventLog` documents single-writer access (`eventlog.py:49-52`); Phase 3 adds no
locking and must not claim to. The staleness check is what makes the *observable*
outcome safe: a racing second approval either refuses or is refused by the
projection's uniqueness rule. It is never silently deduplicated.

---

## 9. Authority enforcement

### 9.1 Reused unchanged

| Control | Mechanism |
|---|---|
| Authenticated operator | signed session cookie + `FOUNDRY_ALLOWED_EMAIL` equality, the fail-closed check at `mission_control.py:157-163` |
| Household authority | re-derived server-side as the most recently declared active household; **never** submitted |
| CSRF | `webauth.csrf_token` / `verify_csrf`, POST-body only, purpose-scoped, 10-minute TTL |
| Target household equality | `MissionTargetProjection` — `_validate_declaration:304-307`, `withdraw:279` |
| First-target-binds; one active target per `(household, mission)` | `_validate_declaration:318-323` |
| Supersession legality | `_validate_declaration:325-329` |
| Canonical write authority | validate-then-append inside `declare()` / `withdraw()` |

### 9.2 New guard — Mission active (GD-D)

Declaration **and** withdrawal are refused unless the Mission's status is
`active`. Enforced at render (the Mission is not offered) **and** at both POST
handlers (a crafted request is refused). This is a **surface control, not a
canonical invariant** — see `DEBT-016-P3-01` at §16.1.

### 9.3 Not applicable, and must not be introduced

`CanonicalSubjectAuthority` (`core/subject_authority.py`) resolves value
subjects (`party` / `resource`) for RFC-017. A Mission Target binds a Mission and
a household, not a value subject. Phase 3 must not route through it, extend it,
or construct a parallel authority model.

### 9.4 Inherited residuals — stated, not narrowed, not widened

- **W7** — Mission Control resolves the household as the last-declared active
  household. Pre-existing and platform-wide. Phase 3 now uses it to gate a
  **write** as well as a read; it must not be described as narrowing or widening
  it. See SAFE target S6.
- **T6** — Foundry has no multi-member authorisation model. Unchanged.

---

## 10. Canonical event boundary (GD-I, Governor finding 5)

**Authorised, and exhaustive:**

```
core.mission_target.declared
core.mission_target.closed
```

Both are already authorised by RFC-016 GD-2 and already written by the existing
gate. Phase 3 adds **no** event kind, **no** payload field, **no** vocabulary
value and **no** persistence mechanism.

> **STOP CONDITION.** If implementation discovers that a new canonical event, a
> new payload field or a new vocabulary value is required, work halts and
> returns to the Governor for renewed authority. It is not resolved by
> implementation choice (RFC-100 §9.2).

---

## 11. Implementation invariants

| # | Invariant |
|---|---|
| **I-1** | Phase 3 writes exactly `core.mission_target.declared` and `core.mission_target.closed`, and nothing else. |
| **I-2** | Phase 3 never writes `core.mission.updated`, `Mission.target_value`, `target_date`, `target_range` or `tolerance`. |
| **I-3** | A Mission Target is immutable; replacement is supersession, and `supersedes` is derived from current canonical state at approval time — never accepted from the client. |
| **I-4** | Every derived field of §5.2 is absent from every accepted form field set; an unexpected field is a refusal. |
| **I-5** | Review writes nothing. Approval re-derives and revalidates from current canonical state before append. |
| **I-6** | Validation precedes the single append; a refusal appends nothing and leaves no partial state. |
| **I-7** | Mission identity is `Mission.id`; no name, label or slug is ever an identity, a key or a lookup term. |
| **I-8** | `core/mission_targets.py` gains no domain vocabulary; the FR-011 neutrality guard continues to pass. |
| **I-9** | No assessment, renderer, scheduler or model is on the write path. No target is ever marked "met". |
| **I-10** | Rendering and replay append nothing. |
| **I-11** | Declaring or withdrawing a target changes no existing assessment result; the existing suite passes unmodified. |
| **I-12** | `mission_targets_web.py` imports nothing from `operations_web.py` or `acquisition_web.py`. |
| **I-13** | No Mission, household, target, telemetry stream or asset registration is created, bootstrapped, synthesised or fabricated for any reason, including to populate a surface. |
| **I-14** | `core/mission_targets.py` remains **byte-identical**; `MissionTargetProjection` is not modified by Phase 3. |
| **I-15** | The horizon mapping is capture-side only and adds no field to `MetricDescriptor`. |

---

## 12. Prohibited changes and blast-radius enforcement (Governor finding 10)

**Files that must appear in no diff.** The untouched-file list is an
implementation invariant. Any prohibited-file modification is a **NO-GO** unless
EECOM returns to the Governor with repository evidence that the frozen boundary
is insufficient:

```
src/foundry/core/mission_targets.py        RFC-016 Phase 1 contract — byte-identical (I-14)
src/foundry/capture_contracts.py           RFC-013 (GD-C)
src/foundry/core/capture_targets.py        RFC-015 (GD-C)
src/foundry/finance/capture_targets.py     RFC-015 (GD-C)
src/foundry/operations_web.py              RFC-012/013 surface (GD-C)
src/foundry/acquisition_web.py             RFC-011 confirmation surface (GD-C)
src/foundry/core/acquisition.py            RFC-011 (GD-C)
src/foundry/finance/acquisition.py         RFC-011/013 Finance adapter (GD-C)
src/foundry/core/mission_assessment.py     RFC-006 frozen contracts (GD-J)
src/foundry/core/value_provenance.py       RFC-017, CLOSED (GD-J)
src/foundry/finance/pension_provenance.py  RFC-017, CLOSED (GD-J)
src/foundry/core/entities.py               legacy scalar target path (I-2)
every assessor in src/foundry/finance/     RFC-006 adoption is Phase 4 (GD-J)
tests/test_rfc_016_mission_targets.py      Phase 1/2 contract must not move
```

**Behaviours that must not be introduced:** Mission Assessment; progress
calculation; target-versus-current comparison; provenance consumption,
provenance UI, new provenance events or provenance persistence; Flight Deck
changes; AI or automatic target recommendation or modification; Mission
instantiation; Finance acquisition changes; broad Mission Framework redesign;
editing or redaction of `basis`; any new persistence mechanism, cache or store.

---

## 13. Expected file-level blast radius

**Production**

| File | Expected change |
|---|---|
| `src/foundry/mission_targets_web.py` | **new** — the six route handlers of §3 |
| `src/foundry/finance/mission_targets.py` | the minimal horizon mapping of §5.3 |
| `src/foundry/mission_control.py` | replace the `/missions` placeholder (`:2419-2423`); add the target projection to `Console` (`:89-99`) |
| `src/foundry/web.py` | compose `MissionTargetProjection` in `_build_console` (`:240-283`); register the new router (`:287-289`) |

**Governance and release**

| File | Expected change |
|---|---|
| [`../rfcs/RFC-016-mission-target-framework.md`](../rfcs/RFC-016-mission-target-framework.md) | Phase 3 authority block; §11 phase-table status |
| this record | landed at the authorised governance path |
| `docs/rfc-016-phase-3-implementation-report.md` | **new**, BOOSTER |
| [`../rfc-016-technical-debt.md`](../rfc-016-technical-debt.md) | the §16 debt records |
| [`../rfcs/index.md`](../rfcs/index.md) | RFC-016 status row and the GD-A record |
| `docs/security/` assurance register | one new authenticated write surface (RFC-016 §9 obligation) |
| `CHANGELOG.md`, `PROJECT_STATUS.md` | TELMU release closeout |

**Tests**

| File | Expected change |
|---|---|
| `tests/test_rfc_016_phase_3_mission_target_management.py` | **new** — the §14 matrix |
| `tests/test_mission_control.py` | `/missions` is no longer a placeholder |
| `tests/test_web.py` | router registration and composition |

Four production files. Anything beyond them is a boundary question, not an
implementation detail.

---

## 14. TELMU acceptance requirements

### 14.1 Repository state

| # | Requirement |
|---|---|
| **A-1** | Full suite green. Baseline is **802 passed** with **one** pre-existing FastAPI/TestClient deprecation warning; no new warning is introduced. |
| **A-2** | `git diff --check` clean; no stray artefact; `foundry_data/` and vault paths untouched by the diff. |
| **A-3** | No file from §12's prohibited list appears in the diff. |
| **A-4** | `CHANGELOG.md` and `PROJECT_STATUS.md` are updated and non-contradictory. |
| **A-5** | The first post-merge `main` workflow passes before the burn is declared complete. |

### 14.2 Governor-mandated minimum validation

TELMU must validate, at minimum:

first declaration; supersession; withdrawal; stale predecessor refusal;
stale-`none` refusal; stale-after-withdrawal cases; malformed operator input;
inactive Mission refusal; empty-world rendering with **zero writes**; replay
correctness; canonical event shape; absence of fabricated Missions; absence of
client authority over derived fields.

### 14.3 Full validation matrix — all must be covered by named tests

**Happy path.** First declaration; replacement by derived supersession;
withdrawal; predecessor remains resolvable by id after supersession;
`in_force` returns the successor.

**Derivation.** `metric_id`, unit, dimension and direction come from canonical
state and the descriptor; `horizon_kind` comes from the §5.3 mapping;
`horizon_at` present only for `by_date` and absent for `none` and `derived`;
`effective_from` is computed at approval, not carried from review.

**Field forgery (I-4).** POST carrying any of `household_id`, `metric_id`,
`supersedes`, `effective_from`, `destination_unit`, `destination_dimension`,
`destination_direction`, `horizon_kind` — each refused, nothing appended.

**Stale state (§8.4).** Every one of the six rows, asserted individually, each
refusing and appending nothing.

**Authority.** Unauthenticated; wrong email; absent CSRF; expired CSRF; a
`rfc016-target-review` token replayed at R4; a `rfc013-capture` or
`rfc011-confirmation` token replayed at R4 or R6.

**Mission lifecycle (GD-D).** Declaration and withdrawal refused against an
achieved Mission, an abandoned Mission, an unknown Mission, a Mission of another
household, a Mission whose metric has no descriptor, and a Mission whose metric
has no horizon mapping.

**Target lifecycle.** Second active target without supersession refused;
withdraw an already-withdrawn target; withdraw another household's target;
supersede a withdrawn target; supersede an already-superseded target.

**Hostile log.** A log seeded with two active targets, a forked chain, a cyclic
chain, and a `core.mission_target.updated` event: `/missions` renders the
conflict honestly and every write against that Mission is refused. Quiet must
never be presented where a conflict exists.

**Malformed input.** Non-numeric and non-finite values; `basis` at 500 and at
501 characters; empty withdrawal reason; unparseable and out-of-range dates;
wrong content type; multi-valued form keys; unknown `mission` query parameter.

**Empty world (GD-E).** No household; no Mission; no described metric. Each
renders an honest empty state and fabricates nothing — asserted by comparing the
event log before and after the render.

**Determinism and replay.** Declare, rebuild the projection from disk, assert
identical `in_force` under two distinct frozen clocks; assert a full render of
every Phase 3 route appends no event.

**Neutrality and regression.** The FR-011 guard over `core/mission_targets.py`
passes unchanged; existing assessment results are unchanged; the existing suite
passes unmodified.

---

## 15. SAFE review targets

SAFE must inspect the implementation against the frozen blast radius, including
the explicitly protected files and the dependency boundaries.

> **Passing functional tests does not waive a boundary violation.**

| # | Target |
|---|---|
| **S1** | Is in-request, non-persisted review sufficient as the review control for an immutable, permanent canonical declaration correctable only by supersession? |
| **S2** | Is the §8.2 staleness assertion the right anti-replay control, and must it be signed rather than plain given that it is only ever compared, never written? |
| **S3** | Do the three new CSRF purpose strings partition correctly from `rfc012-capture`, `rfc013-capture` and `rfc011-confirmation`, with no token transferable between surfaces? |
| **S4** | `basis` is permanent, unredactable operator free text (RFC-016 W5). Is the GD-F wording sufficient at the point of approval, not merely at the point of entry? |
| **S5** | The Mission-active guard is a surface control, not a canonical invariant (§9.2, §16.1). Is that accepted for Phase 3? |
| **S6** | W7 now gates a write. Does that change its risk rating? |
| **S7** | Does an empty, refusing or conflicted mission list disclose the existence of another household's Missions? (RFC-015 §12 state-5 non-disclosure precedent.) |
| **S8** | Does the assurance register update cover the new authenticated write surface, per RFC-016 §9's explicit obligation on the phase that adds the declaration route? |
| **S9** | Confirm by diff inspection that no file in §12 changed and that `core/mission_targets.py` is byte-identical (I-14). |
| **S10** | Confirm the horizon mapping introduced no field on `MetricDescriptor` and no Core change (I-15, GD-B). |
| **S11** | Confirm the staleness assertion satisfies every prohibition of §8.3 — it must not appear in any event payload, determine `supersedes`, or influence metric or horizon semantics. |

---

## 16. Technical-debt recording requirements

The following **must** be recorded in
[`../rfc-016-technical-debt.md`](../rfc-016-technical-debt.md) as a condition of
Phase 3 completion.

### 16.1 DEBT-016-P3-01 — projection-level Mission status gap (required by GD-D)

**Assertion.** `src/foundry/core/mission_targets.py` contains no reference to
Mission status. `_validate_declaration` and `_validate_loaded_target` verify that
the Mission exists and that `target_metric` matches, but never that
`mission.status == "active"`. `in_force` therefore returns a target for an
achieved or abandoned Mission, and RFC-016 §7.1's derived `dormant` state is
unimplemented.

**Phase 3 disposition.** Mitigated at the operator surface only (§9.2). The
projection is **not** modified (GD-D, I-14).

**Residual, stated plainly.** A target already declared against a Mission that is
later closed remains `in_force` for any future consumer. Phase 3 hides such a
Mission from management, which means that target can no longer be withdrawn
through the ordinary surface.

**Owner.** Core Architecture.

**Required disposition (Governor clarification, §2.1).** Resolve by governed
implementation of RFC-016 §7.1 `dormant` semantics **before any later phase or
RFC gives `in_force` Mission Target state its first production assessment,
decisioning, recommendation or Flight Deck consumer.** If that consumer is
RFC-016 Phase 4, resolution is required before Phase 4; if programme numbering
changes, the obligation travels with the first consumer. **No dependency on this
debt may be expressed solely by the label "Phase 4".**

### 16.2 DEBT-016-P3-02 — horizon derivation is capture-side, not canonical

**Assertion.** `MetricDescriptor` carries dimension, unit and direction but no
permitted horizon kind. The §5.3 mapping constrains this surface only; the
projection continues to accept any admissible `horizon_kind` from any writer.

**Owner.** Finance domain.

**Future disposition.** If a second writer of `core.mission_target.declared` is
ever authorised, decide then whether horizon admissibility belongs in the
descriptor contract — a governed RFC-016 amendment, not an implementation choice.

### 16.3 Deferrals recorded without debt status

`tolerance` (§5.4); backdated `effective_from` and RFC-016 §7.3's retrospective
disclosure (§5.4); RFC-016 W1, W3, W4, W6, W7 inherited unchanged; RFC-017
TELMU-P2-02 and SAFE-P2-03 untouched.

---

## 17. Phase authority and STOP conditions

**RFC-016 Phase 3 — Mission Target Management: ARCHITECTURE FROZEN. GO.**

**Implementation authority: NOT GRANTED.** BOOSTER receives it only by a
subsequent, explicit Governor act (RFC-100 §9.1).

**Phase 4 (per-mission assessment adoption) and Phase 5 (deprecation of the
legacy scalar path) remain unauthorised**, each behind its own governed
amendment and Governor gate (RFC-016 GD-9).

### 17.1 STOP conditions

Implementation halts and returns to the Governor if engineering discovers that
correctness requires:

1. modifying the RFC-016 core target projection, or any file in §12;
2. adding a canonical event, payload field or vocabulary value;
3. persisting review proposals;
4. extending RFC-013 / RFC-015 capture machinery;
5. trusting browser-supplied lifecycle or authority state;
6. automatic Mission instantiation, or fabricating Mission state;
7. Mission Assessment behaviour;
8. adding `tolerance` or backdated `effective_from` (§5.4).

A STOP condition is never resolved by implementation choice (RFC-100 §9.2).

---

## 18. Next sequence

1. **Record the approved architecture freeze in the repository.** — this record,
   with the RFC-016 Phase 3 authority block and the `index.md` update.
2. **Produce the resulting commit SHA and confirm the tree and baseline.**
3. **CAPCOM issues the implementation mission** from that exact frozen authority.
4. **BOOSTER/Codex may begin only after explicit Governor implementation
   authority.**

---

**RFC-016 PHASE 3 — ARCHITECTURE: FROZEN. ENGINEERING: NOT YET AUTHORISED.**
