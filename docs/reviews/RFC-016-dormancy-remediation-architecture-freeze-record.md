# RFC-016 — `DEBT-016-P3-01` Mission Target Dormancy Remediation: Architecture Freeze Record

**Decision: ARCHITECTURE FROZEN — GO.**
**Freeze date:** 2026-08-12
**Canonical baseline / parent:** `9b30601608d06b911d3811ab8b436ed1d1beff31` (`main` = `origin/main`)
**Baseline validation at publication:** 872 passed; 1 pre-existing FastAPI/TestClient
deprecation warning; `git diff --check` CLEAN; working tree CLEAN.
**Branch:** `rfc-016-dormancy-architecture-freeze`
**Authority:** Governor architecture rulings **GD-1** through **GD-6**.

**PRODUCTION IMPLEMENTATION: NOT AUTHORISED.** **TEST IMPLEMENTATION: NOT
AUTHORISED.** BOOSTER is not yet authorised. Mission Assessment is not
authorised. This commit is **documentation and governance only** — no `src/`
change, no `tests/` change.

**`DEBT-016-P3-01` REMAINS OPEN.** It is not closed by this freeze and may be
closed only on the evidence in §10.

**Attribution.** §2 records **Governor acts**, transcribed by EECOM at the
Governor's direction (RFC-100 §1.2, §9.4). §1 and §3 onward are the accepted
EECOM architecture burn and the frozen implementation boundary derived from it.

---

## 1. Payoff

**Frozen: `MissionTargetProjection` derives each Mission's earliest valid
applicable canonical closure from `core.mission.closed` during its existing
deterministic rebuild, and `in_force(as_of)` excludes a target at or after that
timestamp — restoring RFC-016 §7.1 dormancy without a new event, without
migration, and without touching the Phase 3 operator surface.**

## 2. Governor rulings — binding freeze authority

| # | Subject | Ruling |
|---|---|---|
| **GD-1** | Dormancy ownership | **ACCEPTED.** Derive Mission closure timestamps inside `MissionTargetProjection` from canonical Mission lifecycle history. **Do not** add `closed_at` to the broadly consumed `Mission` dataclass for this remediation. |
| **GD-2** | Temporal semantics | **ACCEPTED.** `in_force(as_of)` must preserve historical truth. For a Mission closure at `T`, a target may be returned for a valid `as_of < T` and must not be returned for `as_of >= T`. Closure must not retroactively erase pre-closure history. |
| **GD-3** | Terminality | **ACCEPTED.** A valid canonical Mission closure is terminal for Mission Target actionability. Later malformed, duplicated or re-declared Mission state must not resurrect an associated target. The decision derives from canonical closure history, **not** from the latest projected `Mission.status`. |
| **GD-4** | Duplicate closure history | **ACCEPTED.** Where replay contains multiple valid terminal closures, the **earliest valid applicable** closure governs. Later log noise must not move terminality forward or resurrect actionability. This record must define precisely what constitutes a valid applicable closure **under existing canonical Mission authority**, inventing no new lifecycle rule (§4.2). |
| **GD-5** | Declaration policy | **DEFERRED.** Do not broaden `MissionTargetProjection.declare()` to reject declaration against an already-closed Mission. The reachable Phase 3 surface already refuses inactive Missions; the debt being repaired is erroneous `in_force` actionability. A declaration-policy change requires separate authority. |
| **GD-6** | W6 / explanation semantics | **DEFERRED.** `in_force()` returns `None` for several reasons; this remediation need not distinguish them. RFC-016 **W6** remains the future consideration when Mission Assessment must explain absence. Do not build explanation semantics now. |

## 3. Accepted architecture findings

Established by the EECOM architecture burn and accepted by the Governor. Not
re-litigated here.

| # | Finding |
|---|---|
| **F1** | The debt is real. Against canonical lifecycle history, `in_force` currently returns a target after its Mission has been achieved or abandoned. |
| **F2** | Current-status filtering is incorrect. §7.3 makes `in_force` an as-of query; a present-tense `mission.status != "active"` check would retroactively change historical answers. |
| **F3** | Dormancy is temporal. Actionability is evaluated relative to the effective Mission closure timestamp. |
| **F4** | `Mission.status` is insufficient authority. `MISSION_STATUS` is an `ExtensibleVocabulary` that does not even contain `"active"`, and a later malformed `core.mission.declared` makes projected Mission state appear active again. |
| **F5** | Canonical closure history is the authority. Mission inactivity is represented by `core.mission.closed`; no authorised Mission reopen lifecycle exists; a valid closure is terminal for target actionability. |
| **F6** | `MissionTargetProjection` is the correct seam — it owns `in_force`, holds the log and `EntityProjection`, performs replay, already derives other temporal terminal conditions, and already derives a Mission event timestamp elsewhere. Consumer-side filtering is explicitly rejected. |
| **F7** | No product-surface expansion is required. The Phase 3 `/missions` surface already guards inactive Missions before calling `in_force`. |

## 4. Frozen semantics

### 4.1 Derivation contract

```text
canonical event history
      ↓  exact-kind match on core.mission.closed
valid applicable closures for a mission            (§4.2)
      ↓  earliest by log order
effective terminal closure timestamp T
      ↓  held by MissionTargetProjection, derived during rebuild
in_force(mission_id, as_of)
      ↓
as_of <  T   →  existing target rules apply unchanged
as_of >= T   →  None   (dormant)
```

Derivation occurs during the projection's existing deterministic
rebuild/replay. This is architectural semantics, not prescribed code structure;
BOOSTER may choose the smallest implementation consistent with this contract.

### 4.2 What constitutes a **valid applicable closure** *(required by GD-4)*

This definition is **read off existing canonical Mission authority**
(`EntityProjection._apply_mission`, `src/foundry/core/entities.py:256-285`) and
invents no lifecycle rule. Verified against the current implementation:

A `core.mission.closed` event is a **valid applicable closure** for a mission
when **all** of the following hold:

1. its event kind is **exactly** `core.mission.closed` — never a prefix match
   (§6, I-6);
2. its `payload.entity_id` is a non-empty string; and
3. that mission id was **already declared earlier in log order**.

Observed behaviour of the existing Mission projection, which condition 3
mirrors rather than extends:

| History | Existing `Mission.status` | Applicable closure? |
|---|---|---|
| closure for a never-declared id | mission absent from projection | **No** |
| closure *before* that id's declaration | `active` — closure ignored | **No** |
| closure *after* declaration, `status="achieved"` | `achieved` | **Yes** |
| closure *after* declaration, `status` absent | `closed` (fallback) | **Yes** |
| malformed `entity_id` (`None`, numeric, empty) | projection unaffected | **No** |

**The `status` value carries no weight.** Applicability is decided by the
event's existence, well-formedness and ordering — not by its label. This is what
makes the contract robust against `MISSION_STATUS` extensibility (F4), and it
is why a closure carrying an assessment-shaped word such as `on_track` is still
terminal.

Among all valid applicable closures for a mission, the **earliest** governs
(GD-4). Qualifying "earliest" by applicability is load-bearing: in a forged
history `closed(T0) → declared → closed(T1)`, `T0` is inapplicable and `T1`
governs.

### 4.3 Composition with existing target terminality

Mission dormancy is an **additional temporal exclusion**. It does not change the
meaning of any existing condition. `in_force` continues to apply, unchanged:
mission conflict; `effective_from <= as_of`; withdrawal
(`closed_at is None or closed_at > as_of`); and supersession as at `as_of`.
Dormancy composes as one further as-at exclusion alongside them.

### 4.4 What must not change

The target archive is untouched. `projection.targets`, every `MissionTarget`
field, `provenance`, `history` and `conflicts` are unaffected by Mission
closure. `_validate_loaded_target` must continue to load a target whose Mission
later closed: refusing at load would poison a legitimate stream and destroy
history, the opposite of §7.1, which keeps the record intact and changes only
interpretation.

## 5. Frozen implementation boundary

**Intended production blast radius — one file:**

```
src/foundry/core/mission_targets.py
```

**Plus, in the implementation burn:** focused tests, architecture/governance
evidence and debt/status documentation.

**Expansion into any other production module is a STOP condition** unless
repository evidence proves it unavoidable.

**Note for SAFE.** `src/foundry/core/mission_targets.py` was on the Phase 3
protected-file list and was required to remain byte-identical **for Phase 3**.
That protection was phase-scoped. This remediation is its authorised change; its
hash will differ from
`90cc500b3859bc47ef5ffb4813d4f513274eeb038aad8ccba481ca55101325a0`, and that is
expected rather than a boundary breach.

### 5.1 STOP conditions

Implementation halts and returns to the Governor if correctness requires:

1. a new canonical event, payload field or vocabulary value (§7);
2. any migration or rewriting of existing events (§8);
3. changing any production module other than the one named above;
4. changing `Mission`, `EntityProjection` or any Mission writer;
5. Mission reopen semantics;
6. broadening `declare()` (GD-5) or building explanation semantics (GD-6);
7. any Phase 3 UX change.

## 6. Invariants

| # | Invariant |
|---|---|
| **I-1** | No new canonical event, payload field or vocabulary value. |
| **I-2** | Dormancy is derived, never stored, never written. |
| **I-3** | Dormancy is evaluated **as at `as_of`** against the effective closure timestamp — never against present `Mission.status`. Queries whose `as_of` precedes closure return exactly what they returned before. |
| **I-4** | The target archive, `provenance`, `history` and `conflicts` are unchanged by Mission closure. |
| **I-5** | Replay never refuses a target because of a later Mission event; `_validate_loaded_target` is unchanged. |
| **I-6** | Mission events are matched by **exact kind equality**, never by prefix. (`"core.mission_target.declared".startswith("core.mission.")` is `False` today; a prefix match would break silently if either name changed.) |
| **I-7** | A later malformed, duplicated or re-declared Mission state never resurrects actionability (GD-3). |
| **I-8** | Only the **earliest valid applicable** closure governs (GD-4, §4.2). |
| **I-9** | Mission isolation: a closure for Mission A never affects Mission B. |
| **I-10** | Rebuild remains deterministic and wall-clock-free; results are identical across repeated rebuilds and processes. |
| **I-11** | Core gains no domain vocabulary; the FR-011 neutrality guard still passes. |
| **I-12** | `in_force` remains the sole actionability contract; the remediation adds no alternative accessor. |
| **I-13** | Phase 3 operator behaviour, household/subject authority and Finance descriptor semantics are unchanged. |
| **I-14** | The change is **restrictive only** — it can remove a target from `in_force`, never add one. |

## 7. Canonical events

### NEW CANONICAL EVENT REQUIRED: **NO**

`core.mission.closed` already provides the terminal lifecycle evidence and is
written today by `achieve_mission` and `abandon_mission`. §7.1 states dormancy
is "derived, never written". No payload field and no vocabulary value is added;
`MISSION_STATUS` and both target vocabularies are untouched. A requirement for a
new event is a **STOP** condition.

## 8. Migration

### MIGRATION REQUIRED: **NO**

Existing append-only history becomes semantically correct through deterministic
replay alone. No event is rewritten, added or removed; no payload changes shape;
every existing target record loads exactly as before. No migration is
authorised. A finding that migration is required is a **STOP** condition.

## 9. Frozen replay contract

`T` = the earliest valid applicable Mission closure timestamp (§4.2).

| Case | History | Frozen expected behaviour |
|---|---|---|
| **A** | Mission declared; target declared; no closure | Target may be `in_force` per existing target rules. Unchanged from today. |
| **B** | Mission declared; target declared; Mission closed at `T` | `as_of < T` → target may be in force; `as_of = T` → **None**; `as_of > T` → **None**. |
| **C** | Target withdrawn at `W`; Mission closed at `T` | Existing withdrawal semantics remain authoritative from `W`. Closure does not rewrite earlier history. |
| **D** | Target A; target B supersedes A; Mission closed at `T` | Existing supersession semantics remain correct before `T` — B resolves. At and after `T`, no target is actionable. |
| **E** | Mission A + target; Mission B + target; A closes | Only A's target becomes dormant. B is entirely unaffected. |
| **F** | Mission declared; target declared; closed at `T`; later malformed/re-declared Mission state appears active | Target remains dormant for `as_of >= T`. **No resurrection**, notwithstanding projected `Mission.status`. |
| **G** | Valid closure `T1`; later valid or noisy closure `T2` | Earliest valid applicable closure governs. No actionability at or after `T1`; `T2` neither moves terminality nor restores it. |
| **H** | Full log contains a later closure; query an `as_of` predating it | The historical target answer is preserved exactly. |

## 10. `DEBT-016-P3-01` closure condition

The debt may be closed **only** when a reviewed implementation demonstrates:

> No production consumer of `MissionTargetProjection.in_force(as_of)` can
> receive a target as actionable at or after the associated Mission's earliest
> valid effective canonical closure, while historical queries strictly before
> closure continue to return the correct historical target state.

Additionally, all of the following must hold:

1. deterministic replay holds;
2. hostile later Mission redeclaration does not resurrect actionability;
3. Mission isolation holds;
4. no new canonical event is introduced;
5. no migration is required;
6. Phase 3 behaviour is regression-clean;
7. `docs/rfc-016-technical-debt.md` records a dated **Resolved** entry naming the
   resolving commit, and the RFC-016 §7.1 implementation-status note is
   corrected.

Until item 7 lands, the debt remains **OPEN** regardless of code state.

## 11. TELMU acceptance targets

Focused tests must cover at minimum:

1. target before Mission closure;
2. the **exact closure boundary** (`as_of == T` is dormant, not active);
3. target after Mission closure;
4. historical `as_of` before closure, asserted **after full replay** of a log
   that already contains the closure;
5. withdrawal before closure;
6. supersession before closure;
7. multiple-Mission isolation;
8. forged Mission redeclaration after closure;
9. duplicate closure history (earliest valid applicable governs);
10. deterministic replay from a fresh projection;
11. existing Phase 3 target-management regression — `tests/test_rfc_016_phase_3_mission_target_management.py` expected to pass **unmodified**;
12. malformed or unrelated Mission history cannot make another Mission's target
    dormant.

> **Target 12 is narrowed by Amendment 1 (2026-08-12) — see §16.** "Malformed"
> means malformed **within the supported canonical event-shape boundary**. This
> remediation is not required to recover from raw events missing structurally
> required writer-grammar keys. Targets 1–11 are unchanged.

TELMU must explicitly prove that **fixing present-state actionability does not
destroy historical replay semantics** — items 4 and 2 together are the
anti-rewriting proof, and a run that satisfies 1–3 but not 4 is a failed
remediation.

Reporting requirements: exact test counts, warnings, `git diff --check`, tree
state, and confirmation that the full suite remains consistent with the 872
baseline plus the new focused cases.

## 12. SAFE targets

| # | Target |
|---|---|
| **S-D1** | Confirm the change is **restrictive only** (I-14): no input previously refused is now accepted, and no target can be added to `in_force`. |
| **S-D2** | Confirm malformed log content cannot resurrect target actionability. |
| **S-D3** | Confirm a closure for Mission A cannot affect Mission B. |
| **S-D4** | Confirm malformed closure references (absent, empty, non-string or unknown `entity_id`; closure preceding declaration) fail safely and never raise. **Amended by Amendment 1 (2026-08-12) — the `absent` case is removed; see §16.** |
| **S-D5** | Confirm no new browser or client authority is introduced, and Phase 3's authority model — household/subject authority, the three CSRF purposes, the staleness assertion, exact-field-set discipline — is untouched. |
| **S-D6** | Confirm the remediation broadens no accepted canonical event kind. |
| **S-D7** | Confirm no new persistence, mutation or write path appears; this remains a read-side projection correction. |
| **S-D8** | Confirm the Phase 3 surface guard becomes defence in depth rather than sole protection, closing Phase 3 SAFE question **S5**. |

**Expected security impact: LOW / CONTAINED.** No new write authority is
expected.

## 13. Hard non-scope

This freeze authorises none of: Mission Assessment; progress calculation;
target/current-value comparison; target attainment; recommendation logic; Flight
Deck consumption; provenance consumption; provenance UI; new canonical events;
Mission reopen semantics; Mission instantiation; Finance metric changes; target
tolerance; backdated target-management UX; explanation or reason objects for
`in_force(None)`; RFC-017 changes; `DEBT-017-CI-01` remediation; or any
unrelated Phase 3 UX change.

## 14. Next-phase gate

Successful implementation **and independent TELMU/SAFE review** of this frozen
remediation satisfies the prerequisite attached to `DEBT-016-P3-01`.

Only after that debt is **formally closed** may the Governor consider
authorising the Mission Assessment architecture burn as the first production
consumer of `in_force` Mission Target state. **Closing this debt does not itself
authorise Mission Assessment.**

## 15. Authority status

| Item | Status |
|---|---|
| Architecture burn | COMPLETE |
| Governor architecture rulings GD-1 – GD-6 | GRANTED |
| Architecture freeze publication | **AUTHORISED — this record** |
| Production implementation | **NOT AUTHORISED** |
| Test implementation | **NOT AUTHORISED** |
| BOOSTER | **NOT YET AUTHORISED** |
| Mission Assessment | **NOT AUTHORISED** |
| RFC-017 remediation / `DEBT-017-CI-01` | **NOT AUTHORISED** |
| `DEBT-016-P3-01` | **OPEN** |

---

## 16. Amendment 1 — acceptance-boundary narrowing *(Governor ruling, 2026-08-12)*

**Ruling: AMEND FREEZE — CANDIDATE REMAINS VALID.** No BOOSTER remediation is
required and no production boundary expansion is authorised.

The original freeze above is **preserved in full**; nothing in §1–§15 is
rewritten or replaced. This amendment narrows one over-broad acceptance probe
and nothing else (RFC-100 §9.2).

### 16.1 What the remediation guarantees

> The RFC-016 dormancy remediation guarantees correct replay and dormancy
> semantics over **supported canonical Mission lifecycle history** — the event
> history produced by authorised Foundry writers and contracts.

### 16.2 What is outside the acceptance boundary

> A raw `core.mission.closed` event whose payload **entirely omits** the
> structurally required `entity_id` key is **outside the acceptance boundary**
> of this remediation.

**This is a narrowing of an over-broad acceptance probe. It is not a weakening
of the core dormancy invariant.**

### 16.3 Basis in repository evidence

| Path | Finding |
|---|---|
| `grammar.close` — the sole production writer of `core.mission.closed` | Constructs a payload containing `entity_id` **unconditionally**; `achieve_mission` and `abandon_mission` delegate to it |
| Any other production writer of that kind | **None exists** |
| Operations technical capture | **Refuses** `core.mission.closed` — outside the approved Finance manual contract |
| CLI | No supported raw-event append command |
| Direct low-level `EventLog.append` | **Can** manufacture such an event while retaining a valid hash chain. This is outside the supported writer grammar, is not introduced by this remediation, and is recorded as `DEBT-CORE-REPLAY-01` |

The same direct payload-indexing assumption exists across multiple Core and
Finance projection paths, so the behaviour is **platform-wide, not
Mission-specific**.

### 16.4 The applicability contract is unchanged

§4.2 stands exactly as frozen. An applicable closure remains one where the event
kind is exactly `core.mission.closed`, `entity_id` is **present and a non-empty
string**, and the Mission was already declared earlier in canonical log order.
The closure `status` payload does not determine applicability, and the earliest
valid applicable closure remains terminal for target actionability.

### 16.5 Amended acceptance targets

**SAFE S-D4** — remove **only** the requirement to tolerate a raw closure event
whose payload key `entity_id` is entirely absent. Continue to require
adversarial handling of: empty identifier; non-string identifier; unknown
Mission; pre-declaration closure; wrong event kind; duplicate closure history;
hostile Mission redeclaration. **No other SAFE target is weakened.**

**TELMU target 12** — narrowed to the supported canonical event-shape boundary
(§11). **Targets 1–11 are unchanged.**

### 16.6 Candidate and review status

Candidate `b6b224d99d2135b3c3846dbbf5b4cda225b682e0` is **unchanged and review
valid**. All prior TELMU evidence gathered against that exact SHA — including
the hostile Mission redeclaration property — **remains valid**. TELMU
continuation is authorised against that SHA; a complete restart of independent
review is not required. `DEBT-016-P3-01` remains **OPEN**.

---

**Frozen SHA returns to CAPCOM / Governor before implementation begins.**
