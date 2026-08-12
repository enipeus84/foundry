# RFC-016 — Mission Target Framework

**Status:** **Phases 1, 2 and 3 COMPLETE** — Phase 3 Mission Target Management
merged 2026-08-12 (`e64ab2d`), closeout `9b30601`.
**`DEBT-016-P3-01` dormancy remediation: COMPLETE — merged 2026-08-12 via PR
#48, merge `1a93407`; post-merge closeout is recorded in
[`../reviews/RFC-016-dormancy-remediation-post-merge-closeout.md`](../reviews/RFC-016-dormancy-remediation-post-merge-closeout.md).**
Governor rulings **GD-1** through **GD-11** are
recorded (2026-08-06); Phase 3 rulings **GD-A** through **GD-J** are recorded
(2026-08-11) in
[`../reviews/RFC-016-phase-3-architecture-freeze-record.md`](../reviews/RFC-016-phase-3-architecture-freeze-record.md);
dormancy-remediation rulings **GD-1** through **GD-6** are recorded (2026-08-12)
in [`../reviews/RFC-016-dormancy-remediation-architecture-freeze-record.md`](../reviews/RFC-016-dormancy-remediation-architecture-freeze-record.md).
The formal Phase 1/2 freeze record
is [`../reviews/RFC-016-architecture-freeze-record.md`](../reviews/RFC-016-architecture-freeze-record.md).
**Burn:** Architecture Burn (RFC-100 §3), Effort **HIGH**; governance
amendments applied by the Phase 1A burn, Effort **STANDARD**.
**Author:** EECOM (architecture Flight Controller role, Claude Opus 5).
**Date:** 2026-08-06. **Amended:** 2026-08-06 (Phase 1A — Governor rulings
GD-1, GD-11 and watch item W7). **Frozen:** 2026-08-06 (Governor freeze gate).
**Number:** **settled — RFC-016** by Governor ruling GD-1 (2026-08-06). *Asset
Detail & Provenance Investigation* is reassigned to **RFC-017**, amending
RFC-015 ruling G3. See §0. **Amended 2026-08-06** by ruling GD-1 of RFC-017:
RFC-017 is *Value Provenance Framework* and the investigation boundary becomes
**unnumbered**. RFC-016's number and contracts are unaffected.
**Depends on:** RFC-001 (Core domain — Mission entity, grammar, vocabularies),
RFC-005 (Financial Independence assessment), RFC-006 (Mission Assessment
Framework — the boundary this RFC must not move), RFC-007/008/009 (the three
remaining mission policies).
**Does not depend on:** RFC-011/012/013/015. Acquisition supplies *evidence*;
this RFC supplies *intent*. The two meet only inside a domain assessor.
**Self-review:** [`../reviews/RFC-016-architecture-self-review.md`](../reviews/RFC-016-architecture-self-review.md)
**Architecture report:** [`../rfc-016-architecture-report.md`](../rfc-016-architecture-report.md)
**Freeze record:** [`../reviews/RFC-016-architecture-freeze-record.md`](../reviews/RFC-016-architecture-freeze-record.md)
**Phase 3 freeze record:** [`../reviews/RFC-016-phase-3-architecture-freeze-record.md`](../reviews/RFC-016-phase-3-architecture-freeze-record.md)

---

> ### Phase 3 authority — **Mission Target Management**, frozen 2026-08-11
>
> The Governor has **frozen the architecture for Phase 3** and recorded rulings
> **GD-A** through **GD-J** plus ten signature findings in
> [`../reviews/RFC-016-phase-3-architecture-freeze-record.md`](../reviews/RFC-016-phase-3-architecture-freeze-record.md).
> **Implementation authority was granted by the subsequent Governor mission
> issued from frozen authority `b7957d6`.** BOOSTER has produced a bounded
> candidate for TELMU and SAFE review. Merge remains unauthorised.
>
> **Nothing in RFC-016's frozen Phase 1/2 contracts changes.** No canonical
> event, vocabulary, invariant, acceptance criterion or earlier ruling is
> affected — Phase 3 is a consumer/operator surface over the contract this
> document already froze (**GD-I**: no new canonical event; **I-14**:
> `core/mission_targets.py` remains byte-identical).
>
> Four points bear on the text below and are recorded here rather than by
> editing it:
>
> - **GD-A** — the work commissioned under the working term *RFC-018 — Mission
>   Target Capture* **is this RFC's Phase 3**. No RFC-018 is created; RFC-017
>   ruling GD-10 is respected. The word *Capture* is **retired** for this
>   subject, because it denotes participation in the RFC-011/013/015
>   acquisition architecture, which **GD-C** expressly excludes.
> - **GD-C** — the authorised surface is `/missions`. `/operations/capture` is
>   not extended, and RFC-013 / RFC-015 contracts are not distorted to represent
>   Missions as telemetry streams, assets or Finance manual-capture subjects.
> - **GD-D** — §7.1's derived `dormant` state is **specified here but
>   unimplemented**. Phase 3 mitigates it at the operator surface only and
>   records `DEBT-016-P3-01`. A target declared against a Mission later closed
>   remains `in_force` for any future consumer; that debt **must be resolved
>   before any later phase or RFC gives `in_force` Mission Target state its
>   first production assessment, decisioning, recommendation or Flight Deck
>   consumer.**
> - **GD-E** — **GD-11 stands.** Phase 3 instantiates no Mission and fabricates
>   no Mission state. With no Missions in canonical state the surface correctly
>   contains nothing manageable, and watch item **W4** keeps its owner-shaped
>   hole.
>
> §11's phase table, §12's scope exclusions and §16 are retained **unchanged**
> as written at the 2026-08-06 freeze (RFC-100 §9.2). Where §11 Phase 3 reads
> "Declaration surface", the frozen Phase 3 boundary additionally requires
> **supersession and withdrawal to be reachable by the operator** (**GD-H**) —
> the surface-layer application of §11.1's binding sequencing rule.

---

## 0. Naming and governance check *(Check 0 — performed before drafting)*

> ### Governor ruling GD-1 — **settled, 2026-08-06**
>
> **This mission is RFC-016 — Mission Target Framework.** *Asset Detail &
> Provenance Investigation* is **reassigned to RFC-017**, expressly amending
> RFC-015 ruling **G3**. The amendment is recorded in RFC-015 §0 and §18 and in
> [`index.md`](index.md); the displaced boundary keeps its subject, its rhythm
> and its successor status, and loses only its number.
>
> This is recommendation **R1** of §0.3 as ruled. The distinguishing fact
> against the RFC-013 governance debt holds: the displacement is **decided and
> recorded**, not silent. No boundary is lost, and RFC-014 (*Governed
> Corrections*) remains reserved and untouched.
>
> §0.1–§0.3 below are retained **unchanged** as the analysis that produced the
> ruling. They are a record of a question that is now closed, not an open
> question.

### 0.1 The number is already spoken for

RFC-015 §0 decomposed the displaced *Asset Registry & Provenance* boundary into
two successors and the Governor **accepted** that decomposition:

```text
RFC-015  Capture Target Registry                  shipped
RFC-016  Asset Detail & Provenance Investigation  successor; not proposed there
```

That acceptance is recorded three times in the repository: in
[`RFC-015-capture-target-registry.md`](RFC-015-capture-target-registry.md) §0
and §18 (ruling **G3**, "Accepted"), and in [`index.md`](index.md), which states
that the Governor "accepted the decomposition … into RFC-015 (capture target
registry — occasional curation) and a future RFC-016 (asset detail and
provenance investigation — rare investigation)."

This burn was briefed as **RFC-016 — Mission Target Framework**. Filing it under
that number displaces a boundary that a recorded Governor ruling assigned to it.

### 0.2 Why this cannot be resolved locally

RFC-015 §0 identified precisely this failure mode and named its cost: the
RFC-013 number was consumed by *Operations Capture Contracts*, the provisional
*Asset Registry & Provenance* boundary "was displaced **without a recorded
decision**", and that omission — not the renumbering itself — is the standing
governance debt. RFC-015 then declined to take RFC-014 on the grounds that doing
so "would repeat exactly the overwrite that produced the RFC-013 debt."

Two RFC-100 clauses apply and point the same way. §6.0 states that a Mission
Declaration in a brief "is a statement of fact, not a grant of authority" and
"never substitutes for a recorded Governor act (§9.4)"; a briefed number is
therefore not a ruling. §9.4 requires that a ruling be "recorded, dated and
attributable" — which G3 is, and which no later brief has superseded on the
record. EECOM has no authority to overwrite a recorded ruling (RFC-100 §2.4,
"Once frozen, may not reinterpret a contract — only the Governor may").

### 0.3 Recommendation

**Recommended (R1): keep this document at RFC-016 and re-earmark the
provenance-investigation boundary to RFC-017 by explicit, dated ruling
amending G3.**

The distinguishing fact against the RFC-013 precedent is that the displacement
would be *decided and recorded* rather than silent, and the displaced boundary
is unstarted, unbriefed and carries no architecture, no branch and no
implementation. The cost is one index row and one amendment line. The Governor's
evident current intent — expressed by commissioning this burn under this number —
is honoured without any boundary being lost.

**Alternative (R2): renumber this document to RFC-017** and leave RFC-016
reserved as G3 assigned it. This costs a file rename and a contradiction with
the brief, and is the correct outcome if the Governor judges that a recorded
ruling should not be amended for the convenience of a later brief.

**Either is acceptable. Neither may be assumed.**

> **Ruled: R1.** The Governor confirmed RFC-016 for this mission and reassigned
> the provenance-investigation boundary to RFC-017 (2026-08-06). The index row
> withheld by the drafting burn was added by the Phase 1A governance burn once
> the ruling existed.

> **Amendment — Governor ruling GD-1 of RFC-017, 2026-08-06.** The
> reassignment recorded above **no longer holds for the number, and holds
> entirely for the boundary.** RFC-017 is
> [*Value Provenance Framework*](RFC-017-value-provenance-framework.md);
> *Asset Detail & Provenance Investigation* is re-earmarked as an **unnumbered
> future consumer boundary**, keeping its subject, its rare-investigation rhythm
> and its successor status, and losing only its number — the second time this
> boundary has moved by recorded decision rather than silent consumption.
>
> **Nothing in RFC-016 changes.** This RFC remains *Mission Target Framework* at
> RFC-016; no contract, invariant, phase, acceptance criterion, event kind or
> other ruling is affected. The text above is retained verbatim as the record of
> the ruling as originally made (RFC-100 §9.2).

### 0.6 Scope ruling GD-11 — **settled, 2026-08-06**

> **RFC-016 governs Mission Targets attached to *existing* Missions. It does
> not instantiate Missions.**

The consequence is stated plainly rather than softened. §1.1 shows that a
deployed instance contains **no Mission entities at all** —
`declare_mission()` has no production caller. Under this ruling:

- A Mission Target is declarable only against a Mission that already exists.
  Creating Missions is **outside this boundary** in every phase, including
  Phase 3.
- This RFC is therefore **necessary but not sufficient** to make a deployed
  instance render four live missions. It gives intent a canonical home; it does
  not give the household a way to start a mission.
- Mission instantiation — how a locked `MissionDefinition` becomes a
  household's Mission entity — is a **successor boundary requiring its own
  architecture burn and its own number**. This RFC proposes no number for it
  and does not design it (§12, §16, watch item **W4**).

The ruling is the tighter of the two available boundaries, and it is the one
that keeps this RFC to a single subject: *what the household is trying to
achieve*, not *which missions the household runs*.

### 0.4 Is this the right boundary at all? — *Yes, and it is a different rhythm*

RFC-012 §2.8's rhythm test, applied here:

| Rhythm | Surface | User mode |
|---|---|---|
| **Rare, deliberate, consequential** | Declaring or revising where the household intends to arrive | "What are we actually trying to do?" |
| **Weekly** | Capture and confirmation (RFC-012/013/015) | "What changed this week?" |
| **Occasional curation** | What may Foundry record against (RFC-015) | "What can we measure?" |

Declaring a target is the rarest and highest-consequence act in the system: it
is the statement every assessment is judged against. It has no queue, no
cadence, no inbox and no weekly loop. It is correctly its own boundary, and it
is **not** a capture surface, an acquisition channel, or an assessment.

### 0.5 Naming discipline *(binding)*

The word *target* is already load-bearing in two other senses in this
repository. All three must remain distinguishable in code, documents and UI:

| Term | Owner | Meaning |
|---|---|---|
| **Capture target** | RFC-015, `core/capture_targets.py` | permission for one entity property to receive manual observations |
| **`MissionMilestone.target_value`** | RFC-006, `core/mission_assessment.py:200` | a policy band boundary, computed from `destination_value` or `lower_bound` |
| **Mission target** | **this RFC** | the household's declared destination for a mission |

**Rule.** This RFC's concept is always written *Mission Target* in prose and
`MissionTarget` in code, never the bare word "target" where either of the other
two could be read. The module is `core/mission_targets.py`. Renaming
`MissionMilestone.target_value` is a legitimate later cleanup and is **out of
scope here** (FR-004): it is a frozen RFC-006 contract with live consumers at
`src/foundry/mission_control.py:1723`, `:1806`, `:1876`, `:2075` and `:2149`.

---

## 1. Problem statement

Foundry renders four missions, computes trajectory, margin, confidence, ETA and
delta-v against a destination, and tells the household how it is doing. **It has
no canonical representation of what the household is trying to do.**

Three independent, verifiable defects produce that gap.

### 1.1 `core.mission.declared` has no production writer

`declare_mission()` (`src/foundry/core/entities.py:134`) is called from exactly
five places in the repository. One is synthetic demo data; four are tests:

```text
src/foundry/demo_data.py:537   Financial Resilience      synthetic_demo
src/foundry/demo_data.py:597   Financial Independence    synthetic_demo
src/foundry/demo_data.py:654   Pension Independence      synthetic_demo
src/foundry/demo_data.py:877   Mortgage Freedom          synthetic_demo
tests/…                        test fixtures only
```

There is no route, no form, no CLI command, no fixture and no bootstrap that
declares a Mission. The web application exposes `GET /missions` as a
placeholder (`src/foundry/mission_control.py:2417`), and the only mission
`POST` route in the application is … none: every `router.post` in
`src/foundry/` belongs to acquisition confirmation or Operations capture.

The consequence is visible on the deployed Flight Deck. When no Mission exists,
`src/foundry/mission_control.py:1186` renders:

> "Declare a Mission to give this Flight Deck something to steer by."

**Foundry instructs the operator to perform an act it provides no way to
perform.** This is the same class of defect RFC-015 §1 found one layer down —
a contract with no writer — and it is stated here with the same evidence
standard rather than as an assertion.

### 1.2 The declared target is not the authority for any mission

Where a Mission *does* exist, its target fields are not read as intent. Every
one of the four assessors validates the declared value against a constant it
already holds, and returns `unavailable` when they disagree:

| Mission | `target_metric` | `target_value` must be | `target_date` must be | Evidence |
|---|---|---|---|---|
| Financial Resilience | `finance.liquidity_runway` | **exactly `18.0`** (months) | **`None`** | `resilience_assessment.py:200-215` |
| Financial Independence | `finance.accessible_assets` | **exactly `750_000.0`** (GBP) | optional; schedule reference | `mission_assessment.py:236-243` |
| Pension Independence | `finance.pension_wealth` | **`None`** | **`None`** | `pension_assessment.py:227-236` |
| Mortgage Freedom | `finance.mortgage_balance` | **exactly `0.0`** | **exactly the derived original contractual ETA** | `mortgage_assessment.py:319-329`, `:418-423` |

Read together, these rows say something stronger than "targets are unused":

- **A household cannot declare a Financial Independence target other than
  £750,000.** Any other value makes the mission unassessable — the assessor
  returns "Mission target does not match the policy's Independent threshold".
- **A household cannot want 24 months of resilience.** 18.0 is required by
  `FinancialResiliencePolicy.destination_months` (`resilience_assessment.py:37`,
  `:168`).
- **A household cannot declare a mortgage-freedom date at all.** The target date
  must equal the contractual end date derived from mortgage evidence
  (`mortgage_assessment.py:418`). The demo mission is named *"Mortgage free
  ahead of the original contractual term"* — the household's actual intent
  survives only in a **display string**, while the typed field is pinned to the
  thing the household intends to beat.
- **Pension Independence forbids a target outright**, deriving its destination
  from evidence and its planning point from assumptions.

The declared target is therefore a **checksum against a Python constant**, not a
statement of intent. It can only agree or break the mission.

### 1.3 Intent that does exist has nowhere canonical to live

The household's real Financial Independence intent is `desired_annual_spending`
÷ `withdrawal_rate` inside an **Assumption Set** — £30,000 ÷ 0.04 = £750,000 in
the demo. Finance already knows this can diverge from the policy threshold and
handles the divergence by appending a sentence to the limitations list
(`src/foundry/finance/mission_assessment.py:349-355`):

> "Assumption-implied lifestyle capital differs from the configured Independent
> threshold; policy bands remain unchanged"

One intent, three representations — an Assumption Set input, a policy constant,
and an entity field — with divergence reported as prose rather than resolved.
That is the architectural defect this RFC exists to close.

### 1.4 Revision is unrepresentable

`EntityProjection._apply_mission` folds `core.mission.updated` by assigning
attributes in place (`src/foundry/core/entities.py:276-285`), so a revised
target overwrites its predecessor in the read model. It is moot today: **no
function anywhere writes `core.mission.updated`** — `entities.py` exposes
`declare_mission`, `achieve_mission` and `abandon_mission` and no
`update_mission`. The projection folds a verb nothing emits.

So the current state is the worst of both: revision is unimplemented, and the
only mechanism the model provides for it would destroy the very question the
platform exists to answer. [`../architecture.md`](../architecture.md), *Why
claims are events*:

> Mutable claims break traceability: you can answer *why do you believe this*
> but not *why did you stop believing that*.

"Why did we move Financial Independence from £750,000 to £900,000?" is exactly
the second question.

---

## 2. Domain concept: what is a Mission Target?

> **A Mission Target is the household-scoped, canonically-declared, immutable
> statement of where the household intends to arrive on one measured dimension,
> and by when — held separately from the policy that judges progress toward it
> and from the evidence that measures it.**

### 2.1 The three-way separation *(the spine of this framework)*

| | Owns | Answers | Declared by | Governed by |
|---|---|---|---|---|
| **Target** | destination, horizon, tolerance — typed | *where do we intend to arrive?* | the household | **this RFC** |
| **Policy** | bands, milestones, trajectory / margin / confidence rules | *how is progress judged?* | the domain | RFC-005…RFC-009 |
| **Evidence** | observations and their grades | *where are we now?* | acquisition | RFC-011/013/015 |

Today the first two are fused inside policy dataclasses, and part of the first
leaks into Assumption Sets (§1.3). Everything in this RFC follows from pulling
them apart and refusing to let them re-fuse.

### 2.2 A target binds

| Facet | Source | Notes |
|---|---|---|
| Household | declared on the target itself | **authoritative** — a `Mission` carries no household (§3.3) |
| Mission | `Mission.id` — canonical id, never a name | the target is *for* one mission |
| Measured dimension | `metric_id` | must match the mission's `target_metric` |
| Destination | typed quantity (§5) | value + unit + dimension, all declared |
| Direction | `destination_direction` | must equal the registered `MissionDefinition`'s |
| Horizon | horizon kind + optional date (§6) | `none` / `by_date` / `derived` |
| Tolerance | optional typed quantity, same dimension | the band the household accepts |
| Effective from | declared timestamp | drives as-of resolution (§7.3) |
| Basis | free text, non-authoritative | *why* this destination — recorded, never parsed |
| Provenance | actor + event id, already on every event | RFC-015 §8 precedent |
| Lifecycle | derived: active / superseded / withdrawn / dormant | §7 |

### 2.3 Decision: a target is a **declaration**, not a projection and not a field

Four shapes were considered. Unlike RFC-015 — where the join of two existing
declarations already carried every fact a capture target needed — no existing
canonical declaration carries a typed, revisable, household-owned destination.

| Shape | Verdict |
|---|---|
| Typed fields on `Mission`, revised via `core.mission.updated` | **Rejected** — in-place fold destroys lineage (§1.4); the verb has no writer; historical assessments become uninterpretable |
| A field on `MissionDefinition` | **Rejected** — RFC-006: a definition "contains no household state, target, threshold or assessment result"; a definition is programme metadata shared by every household |
| A key inside an `AssumptionSet` | **Rejected** — assumptions are *projection inputs*; Resilience and Pension have destinations but no forecast dependency; couples intent to forecast versioning |
| **A separately identified, immutable, versioned canonical declaration** | **Adopted** |

**Adopted shape.** A Mission Target is declared once and never mutated.
Revision means declaring a **successor** that names its predecessor; the
predecessor remains in the log, remains resolvable, and remains the target that
historical assessments were judged against.

This is not a new idea in this repository — it is the discipline
`declare_assumption_set` already documents at
`src/foundry/finance/entities.py:615-619`:

> "Declare immutable, versioned forecast assumptions. Revision means declaring a
> new set and archiving the old one. A historic forecast's reference therefore
> remains interpretable."

Same argument, same solution, applied to intent instead of assumptions.

---

## 3. Source of truth and canonical event set

### 3.1 Why existing events are insufficient — demonstrated, not asserted

| Need | Nearest existing event | Sufficient? |
|---|---|---|
| Record a destination | `core.mission.declared` | **No** — untyped scalars, no unit, no dimension, no horizon semantics, and the field set is already claimed as a policy checksum by four assessors (§1.2) |
| Revise a destination | `core.mission.updated` | **No** — folded by in-place assignment (`entities.py:276-285`); no writer exists; no supersession link |
| Withdraw a destination | `core.mission.closed` | **No** — closes the **mission**, is terminal, and carries `achieved`/`abandoned` from `vocab.MISSION_STATUS`. Withdrawing a target must not end a mission |
| Link a successor | `core.mission.linked` | **No** — `relate()` requires a member of `PARTY_RELATIONSHIP` (`grammar.py:75`); there is no relationship vocabulary for target supersession, and inventing one would put lineage in a relation while the payload lives elsewhere |
| Record attainment | `achieve_mission` | **Must not be used** — see §7.5 |

### 3.2 The authorised canonical event set *(Governor-approved — GD-2)*

```text
core.mission_target.declared
  payload: { entity_id, mission_id, household_id, metric_id,
             destination_value, destination_unit, destination_dimension,
             destination_direction,
             horizon_kind, horizon_at?,
             tolerance_value?, tolerance_unit?,
             effective_from, basis?, supersedes? }

core.mission_target.closed
  payload: { entity_id, reason }
```

Withdrawal is **generic closure with no `status` extra**, following
`close_party` (`src/foundry/core/entities.py:93-96`: "unlike Mission, Party has
no distinct terminal sub-states to record"). A Mission Target has exactly one
terminal state, so writing an unvalidated `"withdrawn"` string would put an
ungoverned value in the append-only log — what `grammar.relate()` refuses by
design (`grammar.py:75-78`) — and governing one value with a third vocabulary
would cost more than it protects.

**Two kinds, both instances of the existing shared grammar.** `declared` and
`closed` are two of the five verbs `core/grammar.py` already defines for every
`<prefix>.<type>` entity; this RFC introduces a new *entity type* within an
established grammar, not a new grammar. That is a materially smaller claim on
the canonical surface than RFC-015's bespoke `core.telemetry_stream.retired`,
and it is the reason no third kind is requested: supersession is carried by the
successor's own `supersedes` field, so a "superseded" event would be redundant
state.

**`core.mission_target.updated` is prohibited.** It is not merely unwritten: the
projection must **refuse** a target whose history contains it (§8, invariant 3),
because silently ignoring an unexpected canonical event would let a malformed or
forged event look benign — FR-009 requires refusal, not degradation.

### 3.3 Identity and household scoping *(corrected by self-review A3)*

Target identity is `grammar.new_id()` — `uuid4`, as every other entity
(`src/foundry/eventlog.py:66`). **No display name, mission name or slug is ever
an identity, a key or a lookup term** (RFC-015 invariant 1, upheld).

**A `Mission` carries no household.** `src/foundry/core/entities.py:56-69`
defines `id`, `name`, the target fields, `assessment_policy_id`,
`assumption_set_id`, `status`, provenance and history — and no party reference;
`declare_mission()` takes no household argument. The household reaches an
assessment only through `MissionAssessmentRequest.scope`, which Mission Control
resolves as **the most recently declared active household**
(`src/foundry/mission_control.py:185-191`) and pairs with **every** active
Mission in the log (`:194-198`).

Two consequences, both load-bearing:

1. **The target's own `household_id` is authoritative.** There is nothing on the
   mission to agree with, so the equality that can be enforced is
   `target.household_id == authenticated household`, and only that. Claiming a
   three-way check would specify a guard the model cannot support.
2. **First target binds.** Once one household holds an active target against a
   mission, a target from any *other* household against that mission is
   refused. Household scoping thereby becomes derivable from canonical state
   without changing the frozen `Mission` contract — but it binds only from the
   first target forward, and says nothing about missions that have none.

A target whose mission does not exist, whose household disagrees with the
session, or whose mission is already bound to another household is **dropped or
refused, never repaired** — the RFC-015 §3.3 discipline, applied to what this
model can actually check.

**Recorded, not fixed (W7).** That Mission Control assesses every active Mission
against the last-declared household is a pre-existing platform-wide gap. It is
not created by this RFC, is not fixable inside this boundary, and is named so it
is not later mistaken for something this RFC introduced.

### 3.4 Uniqueness and conflict

**Rule.** `(household_id, mission_id)` admits **at most one active target**, and
by §3.3 a mission admits at most one household.

Declaration refuses a second active target for the same mission. Any
pre-existing pair surviving in a log — two actives, two households, a
`supersedes` chain that forks, or a cycle — is a **conflict**: neither target is
offered, the mission resolves to *no active target*, and the conflict is
surfaced for operator resolution. Silently choosing one would make an arbitrary
decision about what a household is trying to achieve. This mirrors RFC-015 §3.4
exactly, including its reasoning.

---

## 4. Relationship to RFC-006 *(the boundary this RFC must not move)*

RFC-006 is merged and its contracts are load-bearing for four missions. **This
RFC changes none of them.** Stated precisely, so it is checkable:

| RFC-006 contract | Change |
|---|---|
| `MissionDefinition` | **none** — no target field is added; a definition remains household-free programme metadata |
| `MissionAssessmentRequest` | **none** — no target field is added (see §4.1) |
| `MissionAssessment` | **none** |
| `MissionMilestone` | **none** — bands remain policy-owned (§4.2) |
| `MissionAssessmentRegistry` validation | **none** |
| Trajectory / Margin / Confidence vocabularies | **none** — all three remain closed and unextended |

### 4.1 How an assessor reaches a target without touching a frozen contract

Every assessor already resolves its mission from a Core projection it holds:

```python
mission = self.core.missions.get(request.mission_id)   # EntityProjection
```

`src/foundry/finance/mission_assessment.py:228`, `resilience_assessment.py:194`,
`pension_assessment.py:~226`, `mortgage_assessment.py:~316`.

A Mission Target is resolved the same way, from a **sibling projection** the
assessor is constructed with:

```python
target = self.targets.in_force(request.mission_id, request.as_of)
```

This adds a constructor dependency to a **domain-owned** assessor — domain
property under RFC-100 P2 — and changes **no Core contract, no request envelope
and no registry validation**. Adding a `target` field to the frozen
`MissionAssessmentRequest` was considered and rejected: it buys no capability the
projection lacks, and it would put an FR-003 freeze breach at the centre of the
design.

**Recorded residual (W1).** Nothing in Core then *compels* a provider to consult
its target. Compliance is a per-domain obligation, defended by per-domain tests
(§10). A future amendment could add an envelope-level assertion; this RFC does
not, because doing so would change a frozen RFC-006 contract to enforce a rule
that RFC-006 does not own.

**Recorded residual (W6).** `MissionAssessmentRegistry.dispatch` wraps every
provider call in `except Exception` and returns "assessment provider failed
safely" (`src/foundry/core/mission_assessment.py:538-544`). A target-resolution
failure inside an assessor therefore surfaces as a generic provider failure,
with nothing telling the household that *intent*, rather than evidence, was
missing. That is an information-honesty cost (FR-008). It is named rather than
fixed, because fixing it means changing a frozen RFC-006 contract; Phase 4
should carry it to the Governor with a concrete case.

### 4.2 Targets do not move policy bands *(v1 rule)*

`MissionMilestone` bands are policy geometry. In v1 a declared target **does not
move a band**: the policy continues to own its milestone plan, and the registry
continues to validate that milestone direction agrees with the definition
(`core/mission_assessment.py:605-612`).

This leaves one genuine open question, which is **not resolved here**: Financial
Independence's *Independent* band boundary is numerically the same £750,000 that
the household would now declare as a target. If a household declares £900,000,
does the *Independent* band move with it? That is a change to a frozen RFC-005
policy and is a Governor decision at adoption (§11, **GD-6**), not an
architectural liberty this RFC may take.

### 4.3 The direction agreement rule

A target's `destination_direction` must equal the `destination_direction` of the
`MissionDefinition` its mission is bound to, resolved by
`assessment_policy_id`. Disagreement refuses the declaration. This is the same
rule the registry already applies to milestones — extended to targets rather
than invented for them.

---

## 5. Typed metric strategy *(decided)*

### 5.1 The problem, stated exactly

`Mission.target_value: float | None` carries a **currency amount** for Financial
Independence, a **duration in months** for Financial Resilience, and a
**currency amount that must be zero** for Mortgage Freedom — with no field
anywhere on the entity recording which. Comparison against evidence is currently
guarded, where it is guarded at all, by a *policy-declared* unit:
`current.unit_or_currency != self.policy.unit_or_currency` →
`unavailable` (`src/foundry/finance/mission_assessment.py:266-276`). The target
itself contributes nothing to that check.

### 5.2 Options considered

| Option | Verdict |
|---|---|
| Bare scalar plus a free-text unit string | **Rejected** — "GBP" vs "gbp" vs "£" is an ungoverned value reaching the append-only log; `grammar.relate()` already refuses exactly this class of input |
| Full dimensional analysis / unit algebra library | **Rejected** — a dependency and an inference engine to distinguish four dimensions; the platform's discipline is closed vocabularies, not inference |
| Infer the dimension from `MetricResult.unit_or_currency` at assessment time | **Rejected** — the field is `str \| None`, is per-result, and is `None` whenever the metric is `unavailable` or `unsupported` (`core/metrics.py:51`, `:79-83`). A target must be declarable and validatable while its metric is temporarily unavailable; inferring from a result makes declaration depend on today's evidence |
| **Typed quantity + closed dimension vocabulary + domain-owned metric descriptor** | **Adopted** |

### 5.3 The adopted strategy

**One.** A new Core **closed** vocabulary — closed, not extensible, for the same
reason `MISSION_TRAJECTORY` is closed: a dimension is Core semantics, and a
domain that could add one could redefine comparison.

```text
TARGET_DIMENSION = ClosedVocabulary("target_dimension",
    {"currency", "duration_months"})
```

**Two values, because the four locked missions need two** — currency (Financial
Independence, Mortgage Freedom) and duration_months (Financial Resilience);
Pension Independence declares no target value at all. Reserving `ratio` or
`count` "because a later mission will probably want them" is the same
speculation RFC-015 refused for extra event kinds. Adding a dimension is a
governed Core change (`core/vocab.py:58-62` — a `ClosedVocabulary` refuses
`extend()` outright), which is the correct cost for a new unit of meaning, not a
reason to pre-empt it *(self-review A4)*.

**Two.** A destination is a typed quantity, not a float:

```text
TargetQuantity(value: float, unit_or_currency: str, dimension: str)
```

with `value` finite (`_require_finite` discipline, `core/mission_assessment.py:49`),
`unit_or_currency` non-empty, and `dimension ∈ TARGET_DIMENSION`. A tolerance,
where declared, is a `TargetQuantity` of the **same dimension and unit**.

**Three.** Admissibility is decided by a **domain-owned metric descriptor**
behind a narrow protocol, so Core never learns that `finance.liquidity_runway`
is measured in months:

```text
MetricDescriptor(metric_id, dimension, unit_or_currency, destination_direction)

class TargetMetricResolver(Protocol):
    def describe(self, metric_id: str) -> MetricDescriptor | None: ...
```

This is exactly the seam RFC-015 §5.3 established and RFC-011 finding B1 forced
into existence: a neutral projection plus a domain-owned descriptor provider,
composed at the composition root. Core contains no Finance vocabulary, and the
FR-011 regression test that asserts this for `core.acquisition` extends
unchanged to `core.mission_targets`.

**Four — fail closed.** A declaration is refused when: the metric has no
descriptor; the declared dimension differs from the descriptor's; the declared
unit differs from the descriptor's; or the descriptor's direction differs from
the mission definition's. **A metric with no descriptor is unknown, never
assumed** (FR-008). No default currency, no inferred unit, no "probably GBP".

### 5.4 Why this is not over-built

The alternative that looks cheaper — one float and a unit string — is the state
that produced §1.2's four incompatible conventions. The typed quantity is three
fields and one closed vocabulary, and it makes the single question every
assessment asks ("is `value` past `destination`?") answerable without any
assessor re-deriving what the number means.

---

## 6. Horizon semantics

`target_date` currently means four different things (§1.2): forbidden
(Resilience, Pension), a schedule reference (FI), and a derived contractual fact
the household must restate exactly (Mortgage). A single nullable float cannot
distinguish them, which is why each assessor re-litigates it in bespoke
validation.

**Decision — a target declares what its horizon means**, from a closed
vocabulary:

```text
TARGET_HORIZON_KIND = ClosedVocabulary("target_horizon_kind",
    {"none", "by_date", "derived"})
```

| Kind | Meaning | `horizon_at` | Today's mission |
|---|---|---|---|
| `none` | a standing condition with no date; steady state | must be absent | Financial Resilience |
| `by_date` | the household intends to arrive **no later than** this date | required | Financial Independence; the *real* Mortgage Freedom intent |
| `derived` | the horizon is computed by the policy from evidence or assumptions | must be absent | Pension Independence (State Pension age) |

Three values, and the mapping above is complete for the four locked missions —
which is the test of whether the vocabulary is right, not a coincidence.

**`none` and `derived` are genuinely different, and there is a consumer.**
`InstrumentApplicability` (`core/mission_assessment.py:123-143`) requires every
instrument to be `applicable`, `not_applicable` or `unavailable`, and the
registry rejects an `applicable` instrument that is absent (`:697-703`). A
steady-state mission with no date must declare ETA `not_applicable`; a mission
whose date is computed from evidence must not. Collapsing the two kinds would
leave the assessor to guess which — the ambiguity §1.2 already documents
*(self-review A5)*.

**Consequence for Mortgage Freedom, stated and not acted on.** Under this model
the mortgage target is `destination = £0` with `horizon_kind = by_date` and a
household-chosen date; the *original contractual ETA* becomes what it actually
is — a policy-supplied reference derived from evidence, against which delta-v is
measured. The current rule at `mortgage_assessment.py:418`, requiring
`mission.target_date` to equal that derived ETA, is incompatible with a
household declaring a date it intends to beat. **This RFC does not change it.**
It is a frozen RFC-007 assessor rule; changing it requires a governed amendment
to RFC-007 at adoption (§11, **GD-7**).

---

## 7. Lifecycle and lineage

### 7.1 States — all derived, none stored

```text
target.state ⇔
    withdrawn   if core.mission_target.closed exists for it
    superseded  if another active target names it in `supersedes`
    dormant     if its mission's status is not "active"
    active      otherwise
```

`dormant` is derived, never written: a mission closed as `achieved` or
`abandoned` (`vocab.MISSION_STATUS`) takes its target out of current
interpretation without touching the target's own record — the same
"entity closure needs no new event" argument RFC-015 §4.2 made and won.

> **Implementation status — resolved 2026-08-12.** PR #48 merge `1a93407`
> implemented projection-level temporal dormancy: `in_force(as_of)` excludes a
> target at or after its Mission's earliest valid applicable canonical closure,
> while preserving correct answers strictly before closure. `DEBT-016-P3-01` is
> closed by the dated entry in
> [`../rfc-016-technical-debt.md`](../rfc-016-technical-debt.md); no new
> canonical event or migration was introduced.
>
> Two clarifications from that freeze bind any implementation and are recorded
> here rather than by editing the text above (RFC-100 §9.2):
>
> - **Dormancy is temporal, not a status check.** Because §7.3 makes `in_force`
>   an as-of query, dormancy is evaluated against the Mission's **earliest valid
>   applicable `core.mission.closed` timestamp**. A target remains resolvable for
>   any `as_of` strictly before that moment; closure never rewrites pre-closure
>   history.
> - **The closure event, not `Mission.status`, is the authority.**
>   `MISSION_STATUS` is extensible and a later malformed or duplicate Mission
>   declaration can make projected status appear active again, so the phrase
>   "its mission's status is not `active`" above must be read as "a valid
>   applicable canonical closure exists at or before `as_of`".
>
> The remediation introduced **no new canonical event** and required **no
> migration**. Its independent TELMU/SAFE evidence and post-merge closeout are
> recorded under `docs/reviews/`.

### 7.2 Lineage rules

1. A successor names exactly one predecessor via `supersedes`.
2. A predecessor may be superseded **at most once**. A second claim is a
   conflict (§3.4); neither is offered.
3. A successor must share the predecessor's `household_id` and `mission_id`.
   Cross-mission or cross-household supersession is refused.
4. A **withdrawn** target may not be superseded. Withdrawal is terminal;
   resuming means declaring a fresh target with no `supersedes`.
5. A `supersedes` chain must be acyclic and must terminate. A cycle is a
   conflict, detected at fold time, refused — never resolved by ordering.
6. Supersession never edits, hides or invalidates the predecessor. It remains in
   the log, remains resolvable by id, and remains the target that historical
   assessments were judged against.

### 7.3 As-of resolution *(load-bearing)*

```text
in_force(mission_id, as_of) →
    the unique target for that mission whose effective_from <= as_of,
    and which was not superseded or withdrawn as at as_of
```

**Resolution is by `effective_from`, not by event order**, and it is evaluated
*as at* the requested time. This is not a convenience: without it, raising a
target today silently rewrites how the household was performing last year, and
every historical trajectory point, ETA, margin and delta-v derived from it. That
is precisely the certainty inflation FR-008 forbids, and it is the reason
RFC-006 already rejects "any observation after the assessment time".

Three guards:

- `effective_from` may not precede the mission's own declaration.
- Backdating is permitted (a household may record in March a goal set in
  January) but is **disclosed**: where the target in force at `as_of` was
  *recorded* after `as_of`, the assessment carries an explicit limitation
  ("target was declared retrospectively"). Recording it silently would let the
  log assert foresight it did not have.
- Resolution is deterministic under replay and must be asserted under two
  distinct frozen clocks (FR-007).

### 7.4 What the world does, and what it costs

| Event in the world | Mechanism | New event? |
|---|---|---|
| Household raises its FI destination | declare successor with `supersedes` | no — §3.2 `declared` |
| Household abandons a goal but keeps the mission | `core.mission_target.closed` | no — §3.2 `closed` |
| Mission itself abandoned | `abandon_mission` (exists) | no |
| Mission achieved | **not an event** — see §7.5 | no |
| Target date slips | declare successor; predecessor records what was intended | no |
| Wrong dimension declared | withdraw, then declare correctly; both remain visible | no |
| Two active targets found in a log | conflict; neither offered (§3.4) | no |

### 7.5 Attainment is never an event *(invariant, and a trap avoided)*

`achieve_mission()` exists (`core/entities.py:159`), writes
`core.mission.closed` with `status="achieved"`, and is **terminal**. It is
tempting to fire it when a target is met. That would contradict a documented
property of this system. [`../architecture.md`](../architecture.md),
architecture observation 2:

> "Mission completion is an assessment outcome and is not necessarily monotonic.
> `MissionAssessment.mission_complete` is recomputed from the current read model
> … A steady-state mission can move from complete back to incomplete without an
> achievement or reversal event."

A household with 18 months of runway that falls to 16 has not *un-achieved* an
event; its assessment has changed. **A Mission Target is never marked met, and
no target event is written by any assessment, renderer, scheduler or model.**
Targets are written only by an authenticated operator act (§9).

---

## 8. Invariants

1. **A Mission Target is immutable.** It is declared once. Revision is
   supersession; `core.mission_target.updated` is prohibited.
2. **No display name, mission name or slug is ever an identity.** Intent is
   never expressed in a label (§1.2, Mortgage Freedom).
3. **The projection refuses what it does not understand.** An unrecognised or
   prohibited event in a target's history makes that target unavailable and
   surfaces a conflict; it is never ignored (FR-009).
4. **A target exists only where its own household equals the authenticated
   household and its mission exists.** A `Mission` carries no household, so that
   is the equality the model can enforce, and the limit is stated rather than
   overclaimed (§3.3).
5. **At most one active target per `(household_id, mission_id)`, and at most one
   household per mission — first target binds.** Ambiguity is refused, never
   resolved by guess (§3.3, §3.4).
6. **Intent, policy and evidence stay separate.** A target carries no band, no
   trajectory rule, no confidence rule and no observation; a policy declares no
   household intent (§2.1).
7. **A target is typed.** Value, unit and dimension are all declared, validated
   against a domain-owned descriptor. An undescribed metric is unknown, never
   assumed (§5.3, FR-008).
8. **Historical assessments resolve the target in force at their `as_of`.**
   Revision never rewrites the past (§7.3).
9. **Attainment is an assessment outcome, never an event** (§7.5).
10. **Target declaration writes `core.*` only.** It never writes `finance.*`,
    never appends an assessment, and no model may be on the write path (FR-012).
11. **This RFC changes no RFC-006 contract** (§4).
12. **The authorised canonical event set is exactly
    `core.mission_target.declared` and `core.mission_target.closed`.** Any
    further kind requires Governor approval.

---

## 9. Security by Design

Answered in full per FR-006 and
[`../security/security-checklist.md`](../security/security-checklist.md).
`N/A` is used where it is the honest answer.

### Security Considerations

- **Authentication.** No identity flow changes and no new public route. A
  declaration surface (Phase 3) requires the authenticated operator; there is no
  preview or demo bypass. Authentication and health routes remain the only
  public routes.
- **Authorisation.** Declaration is household-scoped: the server re-derives the
  household from the session and never trusts a submitted household id. A target
  naming another household's mission is refused, and its existence is not
  disclosed (RFC-015 §12 state 5 precedent). Foundry still has **no
  multi-member authorisation model**; this RFC narrows scope validation and does
  not claim to add one.
- **Sensitive data and secrets.** A target payload contains a number, a unit, a
  dimension, a date and an optional free-text `basis`. `basis` is the only
  operator-authored free text and is **stored and rendered, never parsed,
  interpreted or used in any decision**; it is escaped at render and
  length-bounded at declaration. It is also **irreversible**: the log is
  append-only and hash-chained, so a household that records a personal reason
  for a goal cannot retract it. A redaction precedent exists
  (`core.evidence.redacted`, `src/foundry/core/acquisition.py:356`) and this RFC
  deliberately does **not** extend it — extending a redaction mechanism to a new
  entity is its own decision, not a side effect of this burn. `basis` is
  therefore optional, and Phase 3's surface must say plainly that it is
  permanent *(self-review A6)*. No credential, no external identifier and no new
  persistence mechanism is introduced.
- **Auditability.** Every state change is an event: declaration, supersession
  (carried on the successor) and withdrawal. Actor and timestamp are already
  carried by `EventLog.append`. `effective_from` is an operator assertion and is
  labelled as one — §7.3 requires retrospective declaration to be disclosed, so
  a backdated intent can never masquerade as contemporaneous.

### Threat Assessment

- **Trust boundaries.** No outbound destination, connector, dependency or
  credential is added. The one new untrusted input is the declaration form
  (Phase 3), whose entity and metric inputs are **closed sets derived from
  canonical state**, re-validated server-side; only the numeric value, date and
  `basis` are free-form, and each is type- and range-checked before append.
- **Threat model.** **T4** (event-log modification) — targets are append-only
  and immutable by construction; the prohibition on `updated` removes the one
  mutation path. **T6** (authorisation failure) — narrowed by household equality
  across target, mission and session; the absence of a member-level
  authorisation model remains a stated residual risk, unchanged and not silently
  accepted. **T8** (malformed input) — every field is validated before append;
  an invalid declaration appends nothing. **T10** (operator error) — a wrong
  target is correctable by supersession or withdrawal *provided both exist
  before any real target is declared*, which is why §11 makes that a binding
  sequencing rule. **T1/T9** — `basis` is never interpreted, so no free text
  from this RFC reaches a model or a decision path.
- **Failure and abuse.** Malformed, cross-household, cyclic, duplicate and
  dimension-mismatched declarations all **refuse and append nothing** — a
  refusal never leaves partial state, because the single append is the last
  step. Repeated identical declaration is refused by the uniqueness rule, not
  deduplicated silently. A log containing a conflict yields *no active target*
  for that mission and surfaces the conflict; assessments degrade to their
  existing `unavailable` path rather than guessing.

### Validation

- **Evidence.** Named per-claim tests in §10, including household isolation,
  supersession lineage, cycle refusal, as-of resolution under two frozen clocks,
  dimension mismatch refusal, and an assertion that Core's target module
  contains no domain vocabulary.
- **Deferred work.** Member-level authorisation (T6 residual, unchanged);
  per-domain enforcement that a provider consults its target (watch item **W1**,
  §4.1). The Phase 3 declaration surface is now an implementation candidate;
  no Phase 4 consumer or assessor adoption is implemented.

The architecture burn required no assurance-register change because it moved no
runtime boundary. The Phase 3 candidate adds an authenticated write surface and
updates `security-assurance.md` in the same change. The threat-model boundary is
unchanged: it uses the existing authenticated operator, append-only event log
and single-household authority residual.

---

## 10. Testing strategy

- **Contract.** Typed quantity validation: non-finite value refused; empty unit
  refused; dimension outside `TARGET_DIMENSION` refused; tolerance of a
  different dimension or unit refused.
- **Descriptor seam.** A metric with no descriptor refuses declaration
  (unknown ≠ assumed); a dimension or unit disagreeing with the descriptor
  refuses; a direction disagreeing with the `MissionDefinition` refuses.
- **Neutrality.** Core's target module source contains no domain vocabulary —
  the FR-011 regression pattern established by
  `test_core_acquisition_contract_contains_no_finance_event_vocabulary`.
  Phase 1 is proven against a **mock domain only**.
- **Projection.** Household isolation; unknown mission dropped; a target whose
  household differs from the session dropped; **first target binds** — a second
  household's target against the same mission is refused, and a log containing
  both yields a conflict rather than a pick; two active targets for one mission
  yield a conflict; withdrawn target inactive; mission closure makes its target
  dormant without an event.
- **Lineage.** Supersession chain resolves; double supersession is a conflict;
  cyclic `supersedes` is a conflict; cross-mission and cross-household
  supersession refuse; a withdrawn target cannot be superseded.
- **As-of.** `in_force` returns the predecessor for a historical `as_of` and the
  successor for a current one; identical results under two distinct frozen
  clocks (FR-007); a retrospectively declared target produces the disclosure
  limitation of §7.3.
- **Immutability.** A log containing `core.mission_target.updated` makes that
  target unavailable and raises a conflict — asserted, not assumed.
- **No write path.** Assessment, rendering and replay append no
  `core.mission_target.*` event; asserted by log comparison across a full render.
- **Regression.** The existing suite passes **unmodified**. Declaring a target
  changes no current assessment result until a mission adopts one (Phase 4) —
  asserted directly, because a framework that silently altered four live
  missions would be a migration, not a foundation.

---

## 11. Implementation phases

The sequence below is Governor-approved. Each phase re-enters the lifecycle as
its own burn (RFC-100 §4.1); the freeze authorises Phase 1 and Phase 2 only.

| Phase | Status | Content | Rationale |
|---|---|---|---|
| **1** | Shipped | Core contract: `MissionTarget`, `TargetQuantity`, the two vocabularies, the two events, the projection, as-of resolution, **supersession and withdrawal**, conflict detection. Mock domain only | the foundation; nothing real is declared |
| **2** | Shipped | Domain descriptor seam: Finance `MetricDescriptor`s for the four mission metrics; admissibility. No assessor changes | proves the seam without touching a frozen policy |
| **3** | Candidate — TELMU / SAFE pending | Declaration surface: authenticated, household-scoped, closed-set inputs, CSRF with **its own purpose string**. Targets only — **it declares no Mission** (GD-11, §0.6), so its mission list is exactly the Missions that already exist | first real targets exist only here |
| **4** | Unauthorised | Per-mission adoption, one mission at a time, **each behind its own governed amendment** to that mission's RFC. Financial Independence first, then a mandatory Governor gate | changes frozen assessor validation; may not be done wholesale |
| **5** | Unauthorised | Deprecate `Mission.target_*` and the legacy scalar path | requires RFC-006's four stated removal conditions to be met |

### 11.1 Binding sequencing rule — supersession precedes declaration

**Withdrawal and supersession must ship in Phase 1, before any real target is
declared in Phase 3.** The log is append-only; a target declared without a
correction mechanism is permanent. A household that mistyped £7,500,000 for
£750,000 would have that number judged against, with no mechanism to retract it,
until a later phase shipped.

This is the same argument RFC-015 made about retirement preceding bootstrap, on
the same evidence and with the same conclusion — and it was approved there as
ruling **G6**. It is restated here because the sequencing failure it prevents is
identical, not because the earlier ruling carries over.

### 11.2 Phase 1 acceptance criteria *(proposed as binding)*

| # | Criterion |
|---|---|
| **T1-A** | Core's target module contains no domain vocabulary; Phase 1 is proven against a mock domain only (FR-011) |
| **T1-B** | A log containing `core.mission_target.updated` makes that target unavailable and raises a conflict — refusal, not tolerance (FR-009) |
| **T1-C** | `in_force(mission_id, as_of)` is deterministic and equal under two distinct frozen clocks (FR-007) |
| **T1-D** | At most one active target per `(household_id, mission_id)`; a duplicate refuses at declaration and a pre-existing pair surfaces as a conflict |
| **T1-E** | Cross-household and cross-mission supersession refuse; cycles and double supersession are conflicts; **first target binds** — a second household's target against a bound mission refuses |
| **T1-F** | Withdrawal and supersession are both implemented and tested **in this phase** (§11.1) |
| **T1-G** | Declaring a target changes no existing assessment result; the existing suite passes unmodified |
| **T1-H** | A metric with no descriptor, a dimension mismatch or a unit mismatch refuses declaration — unknown is never assumed (FR-008) |

---

## 12. Scope exclusions *(FR-004 — declared, not deferred debt)*

Excluded by scope, and their absence is not hidden implementation:

- **All implementation.** No source, test, fixture, template, CSS or runtime
  configuration is produced by this burn (FR-013, RFC-100 §3.1 rule 3).
- **Any route, form, CLI or UI.** The declaration surface is Phase 3 and is
  specified, not built.
- **Migration of the four missions.** Each is Phase 4, behind its own governed
  amendment.
- **The `statement_total`, RFC-013 numbering and RFC-014 questions.** Open
  elsewhere; untouched here.
- **Renaming `MissionMilestone.target_value`** (§0.5) — a frozen RFC-006
  contract with five live consumers.
- **Multi-member authorisation.** The T6 residual is unchanged; this RFC does
  not narrow or widen it beyond household equality.
- **New missions, including Children.** The four definitions are locked; this
  RFC adds none and changes none.
- **Mission instantiation** — turning a locked `MissionDefinition` into a
  household's Mission entity. **Excluded by Governor ruling GD-11** (§0.6), in
  every phase including Phase 3. It is a successor boundary with its own burn
  and its own number; this RFC proposes neither.
- **Assumption Set redesign.** §1.3 diagnoses the three-way split; resolving
  what an Assumption Set should own after targets exist is Phase 4 work per
  mission, raised as **GD-8**.

---

## 13. Rejected alternatives

| Alternative | Why rejected |
|---|---|
| Typed target fields on `Mission`, revised via `core.mission.updated` | in-place fold destroys lineage (`entities.py:276-285`); historical assessments become uninterpretable; the verb has no writer today, so nothing is preserved by using it |
| **Revision by declaring a new Mission and abandoning the old** — no new event at all | the strongest counter-proposal, and it fails on three counts. Trajectory, delta-v and margin are computed per `mission_id` (`core/mission_assessment.py:103`), so a new id **orphans the history the mission exists to show**; `mission_detail` fails closed when two active missions claim one policy (`mission_control.py:2341-2352`), so the abandon must land first — an ordering hazard on an append-only log with no transaction; and abandonment is a **terminal mission** state (`vocab.MISSION_STATUS`), whereas raising a target is not abandoning a mission *(self-review A1)* |
| Target on `MissionDefinition` | RFC-006: definitions carry "no household state, target, threshold or assessment result"; a definition is shared programme metadata |
| Target as an `AssumptionSet` key | assumptions are forecast inputs; Resilience and Pension have destinations and no forecast dependency; couples intent to forecast versioning |
| Status quo — intent as policy constants | evidenced failure: four incompatible conventions, no household may declare any target that differs (§1.2) |
| Target as a `claim.derived` Claim | Claims are witnessed beliefs with model provenance and confidence; intent is a household declaration, and routing it through a claim path puts a model-shaped route around a human decision (FR-012) |
| A new `core.goal.*` entity parallel to Mission | two canonical ids for one intent; the Mission already exists and is already bound to a definition and a policy |
| Free-text target ("mortgage free by 2040") | not machine-comparable; a display string is never an identity, which is exactly the defect §1.2 found in Mortgage Freedom |
| Dimensional-analysis library | a dependency and an inference engine to separate four dimensions a closed vocabulary already separates |
| `target_range` carried forward alongside destination + tolerance | two ways to state one thing produced today's ambiguity; no Finance mission consumes `target_range` — only the deprecated legacy scalar path does |
| Firing `achieve_mission` when a target is met | contradicts architecture observation 2: completion is recomputed and non-monotonic (§7.5) |
| Passing the target through `MissionAssessmentRequest` | changes a frozen RFC-006 contract for no capability the projection lacks (§4.1) |
| A third event kind for supersession | redundant: the successor's `supersedes` field already carries it, and RFC-015's precedent is that a new kind requires proof of insufficiency |
| Extending `MISSION_STATUS` with a target state | conflates mission lifecycle with target lifecycle; `MISSION_STATUS` is an extensible vocabulary and adding to it would let a mission be "on_track" against a target it no longer holds |

---

## 14. Governor decision register

### 14.1 Ruled — 2026-08-06

| # | Decision | Ruling |
|---|---|---|
| **GD-1** | The RFC number (§0) | **Settled — RFC-016.** *Asset Detail & Provenance Investigation* reassigned to **RFC-017**, expressly amending RFC-015 ruling G3. RFC-014 remains reserved for *Governed Corrections*. **Amended 2026-08-06 by ruling GD-1 of RFC-017:** RFC-017 is *Value Provenance Framework*; the investigation boundary becomes **unnumbered** (§0 amendment block). RFC-016's own number and every other RFC-016 decision are unaffected |
| **GD-11** | Whether this boundary instantiates Missions (§0.6) | **Settled — it does not.** RFC-016 governs targets attached to existing Missions. Mission instantiation is a successor boundary with its own burn and number |
| **W7** | Mission Control assesses every active Mission against the last-declared household | **Recorded as a watch item** (§15). Pre-existing and platform-wide; not created, not fixed and not owned by this RFC |

### 14.2 Governor freeze rulings — 2026-08-06

| # | Decision | Disposition |
|---|---|---|
| **GD-2** | Two canonical event kinds and the `…updated` prohibition | **Accepted.** The authorised set is exactly `core.mission_target.declared` and `core.mission_target.closed`; `core.mission_target.updated` is prohibited and refused. |
| **GD-3** | Supersession and withdrawal before real declaration | **Accepted.** Both ship in Phase 1; no real target may be declared first. |
| **GD-4** | Closed target vocabularies | **Accepted.** `TARGET_DIMENSION` and `TARGET_HORIZON_KIND` are closed and not extensible by a domain. |
| **GD-5** | RFC-006 boundary | **Accepted.** No RFC-006 contract changes; domain assessors use the sibling projection. W1 remains a watch item. |
| **GD-6** | Policy bands | **Accepted.** v1 targets do not move policy bands. Any change is a per-mission governed adoption amendment. |
| **GD-7** | Mortgage contractual ETA | **Accepted.** This RFC does not change the rule; adoption requires a governed RFC-007 amendment. |
| **GD-8** | FI assumption-implied destination | **Deferred.** The RFC-005 adoption amendment must decide whether a declared target becomes the policy authority. This does not authorise any current assessor change. |
| **GD-9** | Adoption order and gate | **Accepted.** Financial Independence is the reference adoption, followed by a mandatory Governor gate before the remaining missions. |
| **GD-10** | Household scoping | **Accepted.** Target household is authoritative and first-target-binds applies; W7 remains a pre-existing watch item. |

---

## 15. Watch items and technical debt

| # | Item | Disposition |
|---|---|---|
| **W1** | Nothing in Core compels a provider to consult its target (§4.1) | Watch item. Per-domain tests defend it; an envelope assertion would change a frozen RFC-006 contract |
| **W2** | `MissionMilestone.target_value` collides in name with this RFC's concept (§0.5) | Named, not fixed. Five live consumers; a later cleanup burn |
| **W3** | `core.mission.updated` remains foldable and unwritten (§1.4) | Untouched by this RFC. Phase 5 should decide whether to remove the fold or bind it to the deprecation |
| **W4** | Four missions remain unassessable in a deployed instance because no Mission exists at all (§1.1) | **Ruled out of scope by GD-11** (§0.6): RFC-016 governs targets attached to existing Missions and does not instantiate them. Mission instantiation is a successor boundary needing its own architecture burn and number. Recorded here so the gap keeps an owner-shaped hole rather than vanishing with the ruling |
| **W5** | The `basis` free-text field is the only operator-authored prose in a canonical target payload, and it is irreversible (§9) | Bounded, optional and never parsed; redaction deliberately not extended. If a later burn wants to interpret it, that is a new decision requiring FR-012 review |
| **W6** | The registry's blanket `except Exception` masks a target-resolution failure as a generic provider failure (§4.1) | Named, not fixed — fixing it changes a frozen RFC-006 contract. Phase 4 should carry it to the Governor with a concrete case |
| **W7** | Mission Control assesses **every** active Mission against the **last-declared** household (`mission_control.py:185-198`) | Pre-existing, platform-wide, and outside this burn (FR-004). Recorded so it is never mistaken for something this RFC introduced |

---

## 16. What this architecture does not fix

Stated plainly so the document is not read as more than it is:

- It does not make a deployed Foundry instance render four live missions. That
  needs Missions to exist at all (§1.1), and **GD-11 has ruled that creating
  them is outside this boundary** (§0.6). A successor burn owns it; this RFC
  neither designs it nor claims a number for it.
- It does not give a `Mission` a household. It makes one *derivable* from the
  first target (§3.3), which is narrower than it sounds and does nothing for a
  mission that has no target.
- It does not change any number any household currently sees. Adoption is
  Phase 4, per mission, per amendment.
- It does not resolve whether Assumption Sets should keep carrying
  `desired_annual_spending` once targets exist (GD-8).
- It does not add a multi-member authorisation model; T6 remains a residual
  risk.
- The architecture freeze itself did not authorise Phase 3. A subsequent
  Governor mission authorised the bounded Phase 3 candidate now awaiting TELMU
  and SAFE. Phases 4 and 5 retain their stated governed gates.
