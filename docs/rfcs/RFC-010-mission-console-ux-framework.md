# RFC-010 — Mission Console UX Framework

**Status: Approved — architecture frozen.** Approved by the Governor on
2026-07-31. Architecture-only: no production code, tests, CSS, templates or
runtime configuration are changed by this RFC. Implementation proceeds as a
separate engineering Burn.

**The contracts in this document are frozen. Implementation must not change a
frozen contract without a new Governor decision.** Where implementation
discovers that a frozen contract cannot be built as specified, it stops and
returns to the Governor rather than adapting the contract in code.

Date: 2026-07-31

Author: EECOM (architecture Flight Controller role, Claude), commissioned by
the RFC-010 Mission Console UX Framework brief.

Base: `main` at `e2aa480` (CI green following hotfix PR #23).

**Governor architecture review completed 2026-07-31: GO WITH MINOR
AMENDMENTS.** Seven amendments were directed and are applied in this revision;
no scope was added and no concept redesigned:

| # | Amendment | Where applied |
|---|---|---|
| 1 | Seam renamed **Mission Console Model** (from "Console Projection") | Conceptual Architecture, throughout |
| 2 | Mission Margin is the architectural concept; missions may present a domain-specific label | Mission Margin Contract, Decision 4 |
| 3 | Hero five-second success criterion added as an architecture principle | Region 1, AC-17 |
| 4 | Mission Console Model owns ordering, grouping, visibility, disclosure placement and card priority; renderer owns presentation only | Conceptual Architecture, Decision 8, T21, AC-18 |
| 5 | Mission Console declared a **platform** capability, not a Finance one | Governing Principles (principle 0) |
| 6 | Disclosure ownership split: Core owns ordering, slot identity and behaviour; providers own titles, content and telemetry | Region 5 |
| 7 | Governor visual review made an explicit mandatory gate between reference mission and remaining migrations | Migration Plan, AC-19 |

## Governor Approval — Architecture Freeze

**Decision: GO — ARCHITECTURE FROZEN. Architecture-freeze date: 2026-07-31.**

All seven Governor amendments are complete. **No open architecture questions
remain**; the three previously unresolved questions are ruled below and the
region-ordering tension is accepted for V1.

### Approved contract amendments

Three additive amendments are approved, each with an inert default so all four
shipped missions replay and render unchanged:

| # | Approved amendment | Precise identifier |
|---|---|---|
| 1 | Essential telemetry classification | **`TELEMETRY_REGION` gains the value `essential`**, consumed through `TelemetryItem.display_region` |
| 2 | Trajectory movement axis | **`MissionTrajectoryView.movement`**, validated against the new `TRAJECTORY_MOVEMENT` closed vocabulary |
| 3 | Margin applicability | **`InstrumentApplicability.margin`** |

> **Recorded discrepancy, resolved in favour of this document.** The closeout
> brief listed the first amendment as `InstrumentApplicability.essential`.
> `essential` is a **telemetry display region**, not an applicability field:
> `InstrumentApplicability` carries `eta`, `delta_v`, `trajectory`, `forecast`
> and (by amendment 3) `margin`, while `essential` is a value in
> `TELEMETRY_REGION` read via `TelemetryItem.display_region`. The three
> approved amendments are otherwise exactly as listed and in the same order, so
> the intent is unambiguous and this is treated as a transcription slip. The
> identifiers frozen here are the ones implementation must build. Should the
> Governor have intended a genuine fourth concept on
> `InstrumentApplicability`, that is a new architecture decision and requires a
> new RFC.

### Governor rulings on the previously open questions

| # | Question | **Ruling** |
|---|---|---|
| Q1 | Retire the legacy scalar adapter and RFC-005 `phase`/`phases` aliases in the RFC-010 Burn, or separately? | **Retire during the RFC-010 implementation Burn.** Decision 15 items 5 and 6 move from *recommended* to **mandatory** |
| Q2 | Remove `MissionMargin`'s deprecated numerics in this Burn or after a compatibility release? | **Retain for one compatibility release.** `pace_percent` and `schedule_buffer_days` remain readable for one release after the Burn, then are removed as an explicit breaking change per the RFC-006 discipline |
| Q3 | Are disclosure section names Core-owned slots or provider-supplied? | **Core owns disclosure ordering, slot identity, stable IDs and behaviour; providers own titles, content and telemetry.** As applied in Region 5 |

### Region ordering — accepted for V1

The structural tension recorded under self-review A7 — that Essential Telemetry
sits between the answers to Q3 and Q4 — is **accepted for V1**. Regions 3 and 4
are **not** reordered in this architecture burn. The mitigations stand: the
hero's Next Burn preview is required, Region 3 is capped at six items, and
Region 3 is omitted entirely when empty. Revisiting the order is a future
Governor decision, not an implementation choice.

## Context

Foundry now carries four Finance missions, all four with live assessment
providers: Financial Resilience (RFC-008), Financial Independence (RFC-005),
Pension Independence (RFC-009) and Mortgage Freedom (RFC-007). All four render
through one generic authenticated `/missions/{slug}` route and one shared
renderer, with no mission-name branching — an architectural achievement worth
protecting.

Three RFCs shaped the current presentation. RFC-006 established the
domain-neutral Mission Assessment Framework with closed trajectory, margin and
confidence vocabularies. RFC-008 added per-instrument applicability so a
mission could declare an instrument meaningless rather than broken. RFC-009
added the telemetry display-region contract (`display_region`,
`display_group`), the D13 trajectory-state correction, and — as its
prerequisite — PR #21's extraction of `_MissionHeroView`, `_FlightAnalysisView`
and `_MissionDataView`.

Each step was individually sound. Together they produced a page whose
*information architecture* was never designed as a whole. RFC-010 designs it.

**A governing precedent is already recorded.** `docs/architecture.md`
observation 3 states that mission completion and trajectory answer different
questions. RFC-010 does not modify that principle; it makes the page obey it.

## Problem Statement

The Mission Detail page has become a financial report rather than an
operational console. Pension Independence demonstrates the failure mode most
clearly, but the causes are structural and shared:

1. **Equal visual weight.** Telemetry cards render identically whether they
   drive a decision or merely explain one. The page has no notion of primary
   versus supporting information beyond "in the hero" or "in the drill-down".
2. **Trajectory demoted.** The single most important operational fact — *am I
   on course?* — renders as a one-word tile of the same size as any other,
   despite the framework computing a rich trajectory state, tone, ETA, Δv,
   sensitivity envelope and confidence.
3. **Premature detail.** Contribution rates, projection scenarios and
   assumption-derived values appear at the same level as mission status.
4. **Competing recommendations.** "NEXT BURN" and "ESTIMATED Δv" sit as two of
   four equal instruments in the analysis rail, so the one action the Flight
   Director should surface is visually indistinguishable from a milestone
   percentage.
5. **Uneven regions.** The analysis rail assumes four instruments; when
   applicability omits some, the row is sparse. Nothing forbids an empty
   decorative cell.
6. **No console contract.** Nothing prevents the next mission from arranging
   its page differently, because there is no architecture to conform to — only
   a renderer to reuse.

This is not a Pension problem. It is the absence of an explicit, domain-neutral
Mission Console architecture.

### Evidence in the current contract

Two concrete domain-neutrality defects, found by inspection during this
architecture pass:

- **`MissionMargin` leaks schedule semantics.** Its numeric fields are
  `pace_percent` and `schedule_buffer_days`
  ([`core/mission_assessment.py`](../../src/foundry/core/mission_assessment.py)).
  Both were Financial Independence's schedule vocabulary. Financial Resilience
  (months of runway) and Pension Independence (£/year surplus) cannot express
  their margin through either field, so both are `None` and the real quantity
  survives only inside a prose `description`. A domain-neutral contract cannot
  require a schedule to express tolerance.
- **`display_region: "hero"` invites the defect it was meant to solve.**
  RFC-009 introduced it so a provider could promote telemetry; Pension promptly
  promoted four items, turning the hero into a second telemetry grid — the
  outcome the Design Constitution's "every pixel earns its place" forbids.

## Governing Principles

Encoded as architectural requirements, not styling guidance:

0. **Mission Console is a platform capability, not a Finance capability.**
   It belongs to Foundry, not to the Finance domain that happens to have
   populated it first. **Every future Foundry domain renders through the
   Mission Console unless an RFC explicitly approves an exception.** A domain
   that believes it needs its own page architecture must say so in an RFC and
   have that exception approved; it may not simply build one. This principle
   governs every other principle below.
1. **Four questions, in order.** Every console answers *Where am I? Where am I
   going? Am I on course? What burn should I make next?* — in that order, in
   the page's structural hierarchy.
2. **Operational first, analysis on request.** Primary operational information
   is immediately visible; supporting analysis lives behind progressive
   disclosure.
3. **Trajectory is first-class.** It is a composed instrument, never a status
   word.
4. **One Next Burn.** Exactly one recommendation is visually dominant.
5. **No decorative emptiness.** A region with nothing to say is omitted, never
   padded.
6. **No duplication without purpose.** A value repeated below the hero must add
   evidence, precision or visualisation.
7. **Domain neutrality is absolute.** No shared contract may name a domain
   concept, a mission slug, a currency, or branch on a mission name.
8. **Honesty over completeness.** Absent, stale or unavailable evidence renders
   as an explicit state; it is never filled, guessed or silently omitted.
9. **Accessible and responsive from the outset**, not retrofitted.
10. **Existing Foundry visual language is retained.** RFC-010 changes
    information architecture, not typography, palette or spacing tokens.

## Universal Information Hierarchy

The console presents five regions in **fixed order**. The order is universal;
only the values differ per mission.

| # | Region | Question answered | Required? |
|---|---|---|---|
| 1 | **Mission Hero** | *Where am I? Where am I going?* | Always |
| 2 | **Flight Analysis** | *Am I on course?* | Always (may render an explicit unavailable state) |
| 3 | **Essential Mission Telemetry** | *What else must I know to read the above?* | Optional — omitted entirely when empty |
| 4 | **Next Burn** | *What should I do next?* | Always (may render an explicit no-action state) |
| 5 | **Progressive Disclosure** | *Show me the working* | Always |

Missions may not invent regions, reorder regions, or render a region's content
in another region's slot. This is a testable structural invariant (T1–T3).

**Known structural tension, recorded openly** *(self-review A7)*. Mapping the
mandated order onto the four questions leaves Region 3 answering none of them:
Hero answers Q1 and Q2, Flight Analysis answers Q3, Next Burn answers Q4, and
Essential Telemetry sits between Q3 and Q4. The order is mandated by the brief
and RFC-010 does not change it. It is mitigated three ways: the hero's Next
Burn preview is **required** so Q4 is answerable without scrolling; Region 3 is
capped at six items; and Region 3 is omitted entirely when empty. A Governor
who wishes to remove the tension outright should reorder Regions 3 and 4 — that
is the only clean alternative, and it is a Governor decision, not an
implementation one.

## Conceptual Architecture

```text
Mission Definition            (domain: discovery metadata)
        ↓
Mission Engine / Provider     (domain: policy + deterministic calculation)
        ↓
MissionAssessment             (Core: frozen, validated, domain-neutral)
        ↓
Mission Console Model         (Core-shaped view models — NEW SEAM)
        ↓
Console Renderer              (shared regions; no domain knowledge)
```

The new seam is the **Mission Console Model**: a pure, deterministic mapping
from `MissionAssessment` to region view models. It performs no calculation, no
policy decision and no domain interpretation. Placing it between the contract
and the renderer is what allows cardinality rules, emptiness rules and
classification rules to be unit-tested without HTTP, HTML or a seeded event
log.

**Naming.** *Mission Console Model* was selected over *Mission Console View*,
*Mission View Model* and *Mission Presentation Model*. "View" is reserved for
the frozen data the Model produces (`MissionConsoleView` and the five region
views), so reusing it for the layer would collide. "Presentation" is precisely
what this layer does **not** own — the renderer does. "Model" states what it
is: the decision-making model of the console, sitting above presentation and
below policy. The Model is the layer; the View is its output.

### Responsibility split (normative)

| Concern | Owner |
|---|---|
| **Ordering** — of regions, groups, telemetry and disclosure sections | **Mission Console Model** |
| **Grouping** — which items belong to which group or section | **Mission Console Model** |
| **Visibility** — whether a region, slot or item renders at all | **Mission Console Model** |
| **Disclosure placement** — which content sits in which disclosure slot | **Mission Console Model** |
| **Card priority** — primary versus supporting classification and rank | **Mission Console Model** |
| Markup, tokens, spacing, typography, escaping, responsive behaviour | **Renderer** |

**The renderer owns presentation only, and must not make ordering decisions.**
It receives an already-ordered, already-grouped, already-filtered view and
renders it in the order given. A renderer that sorts, re-ranks, filters,
re-groups or chooses what to omit is a defect, asserted by test (T21).

Business logic remains outside the UI layer. The renderer continues to branch
only on declared contract fields.

## Component Contracts

### Region 1 — Mission Hero

**The hero is a fixed-slot instrument cluster, not a telemetry grid.** Slots
are structural; a provider cannot add one.

| Slot | Source | Required | Absent behaviour |
|---|---|---|---|
| Identity | `MissionDefinition.label`, `.definition` | Yes | — |
| Current position | `MissionAssessment.current_value` + presentation | Yes | Region degrades to unavailable console |
| Milestone / phase | `current_milestone.label` | Yes | `NOT EVALUABLE` |
| Destination | completing milestone `destination_value`, `unit_or_currency`, label | Yes | Omitted with stated reason |
| **Trajectory** | Trajectory contract (below) — **visually dominant slot** | Yes | Declared unavailable state |
| Mission Margin | Margin contract (below) | Yes, unless declared `not_applicable` | `not_applicable` ⇒ slot omitted; `unavailable` ⇒ declared absence |
| Confidence / evidence sufficiency | `MissionConfidence.state` | Yes | `Insufficient` |
| **Next Burn preview** | one-line summary of Region 4 | **Required whenever a primary burn exists** | Omitted only when no burn exists |

**Why the burn preview is required, not optional** *(amended by self-review
A7)*: Region 3 sits between the answer to *Am I on course?* and the answer to
*What burn next?*, so without a hero preview a reader must traverse three to
six telemetry values before Q4 is answered. The preview keeps all four
questions answerable within the hero. See
[Universal Information Hierarchy](#universal-information-hierarchy).

#### Hero success criterion

**A first-time user must be able to understand current position, destination,
trajectory and next action from the hero alone in approximately five seconds.**

This is an **architecture principle, not a measurement of human behaviour**:
Foundry runs no timing study and asserts no empirical claim. It is the design
constraint the hero is accountable to, and it is what the hero's slot list, its
prohibition on becoming a telemetry grid, and the required Next Burn preview
all exist to serve.

It is reviewable rather than automatically testable. Its structural proxies
*are* testable and are the enforceable form: the hero carries all four answers
(AC-17), it carries no telemetry list (AC-3), and trajectory occupies a
dominant slot (AC-4). The five-second criterion is the standard applied at the
Governor visual review gate.

**Destination requires no new domain logic.** It is the completing milestone's
`destination_value` with its `unit_or_currency` and label — already produced by
every live provider (RFC-007 exact zero, RFC-008 eighteen months, RFC-009 W\*).
Where no milestone declares `completes_mission`, the destination slot renders
an explicit "no declared destination" state.

**Cardinality:** the hero contains exactly these slots and no telemetry list.
`display_region: "hero"` is **deprecated** (see Retirement, below).

### Region 2 — Flight Analysis

**Decision: not four equal cards.** Presenting Current Position, Destination,
Trajectory and Mission Margin as four sibling cards would (a) duplicate four
values the hero has just stated, violating principle 6, and (b) reproduce the
equal-weight defect this RFC exists to remove.

**Recommendation: one composed Trajectory Panel plus a supporting rail.**

- **Trajectory Panel (dominant).** Current Position and Destination are the
  *endpoints* of the trajectory presentation, not separate cards. Trajectory is
  the path between them; Mission Margin annotates the gap. Where a provider
  supplies observed history or a forecast envelope, the existing trajectory SVG
  renders inside this panel; where it does not, the panel renders the declared
  unavailable or not-applicable state with its explanation.
- **Supporting rail (at most three instruments).** Recent movement (Δv),
  milestone completion, and intercept/schedule where the provider supplies
  reference metadata. Instruments are omitted — never blanked — when
  applicability says so.

The hero *states* the four concepts; Flight Analysis *evidences* them. That is
the "clear reason" principle 6 requires, and it is testable: the panel must
contain a visualisation or an explicit absence explanation, not merely repeat
hero text (T7).

### Region 3 — Essential Mission Telemetry

A new telemetry classification: `display_region: "essential"`.

**Selection rules.** A provider may classify an item as essential only if all
of the following hold. These are provider obligations, enforced structurally
where possible and by review where not:

1. **Operational relevance** — it is needed to interpret mission status now,
   not to explain how status was computed.
2. **Non-duplication** — it is not the current value, destination, margin,
   confidence or trajectory already in the hero.
3. **Actionability or interpretation change** — knowing it would change how a
   reader interprets trajectory, or what burn they would consider.
4. **Current evidence quality** — its `MetricResult.status` is `available` or
   `stale`. `unavailable` and `unsupported` items are never essential.
5. **Materiality** — it is not a constant, a restatement of policy, or a value
   that never moves.
6. **Cardinality** — the region holds **three to six** items.
7. **No padding** — where fewer than three qualify, the region renders the
   qualifying items only; where **zero** qualify, the region is **omitted
   entirely**. Decorative or placeholder cells are prohibited.

**Enforcement.** Registry envelope validation rejects an assessment declaring
more than six essential items (hard cap, T5). The three-item lower bound is a
*guideline, not a validation rule* — enforcing it would push providers to pad,
which is precisely the defect. Instead, a console-projection test asserts that
a region with fewer than three items still renders no empty cell, and the
self-review records this asymmetry deliberately.

**Pension Independence illustration (non-binding).** Current Pension Pot,
Required Retirement Wealth, Funding Ratio. This example informs the contract
and is written into no shared code.

### Region 4 — Next Burn

**Exactly one primary recommendation is visually dominant.** Where a provider
supplies several, the console renders `recommendations[0]` as primary and
relegates the remainder to the Alternative Burns disclosure section.

Primary burn communicates, where available: action, magnitude, expected mission
effect (Δv or margin delta), rationale, confidence or qualification, and
evidence freshness.

**Defined states** — each renders a distinct, explicit presentation:

| State | Condition | Presentation |
|---|---|---|
| **Burn available** | a supported recommendation exists | full primary burn |
| **No burn required** | mission on course and no improving action declared | explicit "no action required" with the reason; never blank |
| **Insufficient evidence** | recommendation exists but is incomplete or unsupported | states what is missing; never renders a partial action |
| **Mission complete** | `mission_complete` is true | states completion and, where the mission can deteriorate, what would change it |
| **Suppressed by another mission** | provider declares a precedence constraint | names the constraint with observed value, threshold value and human label — never an assumption key (the RFC-008 D7 standard) |
| **Advisory** | recommendation is qualitative, not deterministically modelled | rendered as advisory, with no fabricated Δv or magnitude |

The console never presents two actions with equal priority. Δv rendering
remains governed by `applicability.delta_v` (RFC-008 G8).

### Region 5 — Progressive Disclosure

Supporting material moves behind native disclosure sections.

**Canonical slots, in fixed order** (each rendered only when it has content).
Slot names are **domain-neutral functions**, not domain nouns; the displayed
name comes from the provider via `display_group` *(amended by self-review A1)*:

| # | Core slot (domain-neutral) | Example provider name |
|---|---|---|
| 1 | Scenario Projections | "Projection Scenarios" |
| 2 | Supporting Telemetry | "Contributions" |
| 3 | Assumptions | "Assumptions" |
| 4 | Historical Telemetry | "Historical Telemetry" |
| 5 | Sensitivity Analysis | "Sensitivity Analysis" |
| 6 | Alternative Burns | "Alternative Burns" |
| 7 | Calculation Method | "Calculation Method" |
| 8 | Evidence and Provenance | "Evidence and Provenance" |
| 9 | Mission Definition | "Mission Definition" |

**Ownership, normative** *(Governor amendment 6)*:

| Concern | Owner |
|---|---|
| Slot **ordering** — the fixed sequence above | **Core** |
| Slot **identity** — which slot a section is, and its stable deep-link `id` | **Core** |
| **Behaviour** — default open/closed, keyboard, focus, print, no-JS, warning hoisting | **Core** |
| Section **titles** — the displayed name | **Provider** |
| Section **content** | **Provider** |
| **Telemetry** within a section | **Provider** |

Core never owns a domain noun; providers never own ordering, identity or
behaviour. A provider cannot introduce a slot, reorder slots, change a slot's
`id`, or alter disclosure behaviour — it supplies the words and the values that
fill a slot Core defines.

**Behaviour contract:**

| Aspect | Decision |
|---|---|
| Default state | **Closed**, except any section containing a critical warning, which renders **open** and cannot be closed by default state |
| Semantics | Native `<details>` / `<summary>`; one `<section>` per disclosure group with an accessible name |
| Keyboard | Native `<details>` keyboard behaviour retained: `Tab` to summary, `Enter`/`Space` toggles. No custom key handlers |
| Focus | Visible focus ring on every summary; focus never moves implicitly on toggle; opening a section never steals focus |
| Screen-reader naming | Each `<summary>` carries the section's full name; `aria-expanded` is native and must not be hand-set |
| Deep-linking | Each section carries a stable `id`; a matching URL fragment opens it via `:target` CSS with no JavaScript |
| Print | `@media print` forces all sections open so a printed console is complete |
| No-JavaScript | Fully functional — `<details>` is native. **No disclosure behaviour may depend on JavaScript** |
| State persistence | **No persistence in V1** (see Decision 14) |
| Critical warnings | **Never placed inside a collapsed section.** Hoisted into the region they qualify |

**The safety rule, normative and mechanical** *(amended by self-review A5)*.
Information that changes the safety or validity of the primary recommendation
must never be disclosure-only. Because "would change whether a reader should
act" is a judgement, the enforceable form names three **contract fields**, all
of which must render in Region 4 alongside the burn and may never be
disclosure-only:

1. every string in the primary recommendation's own `limitations` tuple;
2. any confidence cap or downgrade reason named in `confidence_basis` whenever
   `confidence.state` is `Provisional` or `Insufficient`;
3. any precedence or suppression constraint that changed the recommendation.

The judgement-based sentence stands as intent; these three categories are what
implementation must satisfy, and they are assertable by test (T12).

## Trajectory Contract

Trajectory becomes a first-class composed instrument. **No new financial
calculation is introduced**; the contract aggregates outputs providers already
produce.

```text
core/vocab.py
  TRAJECTORY_MOVEMENT = ClosedVocabulary(
      "trajectory_movement", {"advancing", "holding", "receding", "unknown"})

core/mission_assessment.py
  @dataclass(frozen=True)
  class MissionTrajectoryView:
      state: str | None                  # existing MISSION_TRAJECTORY
      tone: str                          # existing trajectory_tone
      movement: str = "unknown"          # NEW, TRAJECTORY_MOVEMENT
      destination_direction: str = "higher_is_better"   # from milestones
      history: str = "unavailable"       # from applicability.trajectory
      forecast: str = "unavailable"      # from applicability.forecast
      intercept_at: float | None = None  # existing eta
      intercept_label: str = ""
      recent_change: DeltaV | None = None            # existing delta_v
      confidence_state: str = "Insufficient"         # existing confidence
      evidence_note: str = ""            # why unavailable/stale, if so
```

**Representation coverage:**

| Required representation | Source |
|---|---|
| Direction of travel | `destination_direction` (milestone contract, existing) |
| Current trajectory state | `state` (existing closed vocabulary) |
| Expected destination / intercept | `intercept_at` + label (existing `eta`) |
| Recent movement | `recent_change` (existing `DeltaV`) |
| Acceleration / deceleration | `recent_change.direction` (existing `accelerated`/`delayed`) |
| **Value movement toward/away** | `movement` — **the one new field on this contract** |
| Historical trend availability | `history` (existing applicability) |
| Confidence | `confidence_state` (existing) |
| Evidence sufficiency / stale / conflicting | `evidence_note` + contributing `MetricResult.status` |
| Unavailable trajectory | `state is None` with `evidence_note` populated |

**Why `movement` is the minimum amendment.** `DeltaV.direction` is closed to
`accelerated`/`delayed` — *schedule* movement. A steady-state mission such as
Financial Resilience has no schedule, so it can express no movement at all
today. RFC-008 recorded exactly this as deferred debt (ruling G5, decision
D2.3: extending `DeltaV.direction` with strengthened/weakened was deferred
because no mission then justified it). RFC-010 closes that debt **without**
widening a schedule-specific field: `movement` is a separate, domain-neutral
axis meaning "the mission value is moving toward / holding / away from its
declared destination", computed by the provider from evidence it already folds.

**`unknown` is a legitimate permanent state** *(amended by self-review A4)*. A
mission that never carries observed history — Financial Resilience and Pension
Independence both declare trajectory history unavailable — reports
`movement: unknown` indefinitely. The console **must not** render `unknown` as
degradation, a warning, missing evidence or a fault. It means the axis does not
apply to this mission's evidence, not that something is wrong.

**Completion and trajectory remain independent.** Per `docs/architecture.md`
observation 3, the console must render all four combinations honestly:

| Completion | Trajectory | Console presentation |
|---|---|---|
| Incomplete | on course | destination not yet reached; trajectory `Nominal`/`Accelerated`; burn optional |
| **Complete** | **deteriorating** | completion stated **and** `movement: receding` shown prominently; margin drives the warning |
| Incomplete | off course | trajectory `Constrained`/`Divergent`/`Critical`; burn emphasised |
| Complete | stable | completion stated; trajectory `Complete`; "no burn required" |

The second row is the one current presentation handles worst and is a required
acceptance test (T8).

## Mission Margin Contract

**Definition boundary.** Mission Margin is *the declared tolerance between the
current trajectory and mission success* — surplus, deficit, buffer, headroom or
remaining gap. It is explicitly **not**:

- **completion** (achieved or not — an observed predicate);
- **confidence** (quality of the evidence behind the assessment);
- **trajectory** (direction and expected arrival);
- **progress** (distance travelled, which the milestone contract carries).

It answers: *how much room does this mission have before success is at risk?*

**Architectural concept versus presentation language.** Mission Margin is the
**underlying architectural concept** and the contract is universal; the
**displayed label may be domain-specific**, because "Mission Margin" is
platform vocabulary and rarely the clearest word for a given mission's user:

| Mission | Concept | Presented label |
|---|---|---|
| Financial Resilience | Mission Margin | *Runway* |
| Pension Independence | Mission Margin | *Income Gap* |
| Mortgage Freedom | Mission Margin | *LTV Buffer* |
| A future Health mission | Mission Margin | *Recovery Reserve* |

Mechanism: `MissionMargin` gains an optional provider-supplied
`label: str = ""`, defaulting to the platform term when empty. The label is
plain text, escaped at render, and length-bounded like every other
provider-supplied display string. **It changes presentation only** — the state
vocabulary, the value, the band derivation and every consumer of margin remain
universal, and no renderer or Core code may branch on the label. One concept,
one contract, many words.

**Amendment 1 — replace schedule-specific numerics with a domain-neutral
quantity.** `MissionMargin.pace_percent` and `.schedule_buffer_days` are
deprecated. Additive replacements:

```text
MissionMargin gains:
    value: float | None = None
    unit_or_currency: str | None = None
    format_kind: str = "plain"          # existing TELEMETRY_FORMAT vocabulary
```

Existing fields remain with their current defaults so Financial Independence
replays and renders unchanged; new consumers read `value`/`unit_or_currency`/
`format_kind`. Removal of the deprecated pair follows the RFC-006 removal
discipline (every consumer migrated, one compatibility release, explicit
breaking change).

This is what lets Financial Resilience express "6.2 months of buffer" and
Pension Independence "+£2,000 per year" through one contract, and a future
Health mission express "3 sessions per week of headroom" without amendment.

**Amendment 2 — margin must be declarable inapplicable** *(added by
self-review A3)*. A genuinely binary mission has no meaningful tolerance: a
future Health mission whose destination is "vaccinated", or a Household mission
whose destination is "will executed", has no surplus, buffer or gap. Forcing
such a mission to render margin as `unavailable` would dishonestly imply the
value is missing rather than inapplicable — exactly the conflation RFC-008
introduced applicability to fix.

```text
InstrumentApplicability gains:
    margin: str = "applicable"     # validated against INSTRUMENT_APPLICABILITY
```

Additive with an inert default, so all four shipped missions replay and render
unchanged. Consistency validation follows the RFC-008 rule exactly:
`applicable` ⇒ margin present; `not_applicable` ⇒ margin absent and the hero
slot **omitted entirely**; `unavailable` ⇒ margin absent with an explanation.

This raises RFC-010 to **three** additive contract amendments — telemetry
region `essential`, trajectory `movement`, applicability `margin`. Each has an
inert default and a stated reason no smaller alternative suffices.

## Data / View-Model Contracts

```text
@dataclass(frozen=True) MissionConsoleView
    hero:        MissionHeroView
    analysis:    FlightAnalysisView
    essential:   EssentialTelemetryView | None     # None ⇒ region omitted
    next_burn:   NextBurnView
    disclosure:  tuple[DisclosureSectionView, ...]
```

**Boundary rules, normative:**

1. **Plain text by default, trusted markup by type** *(amended by self-review
   A6)*. Every view field is plain text and is escaped by the renderer. A field
   carrying pre-rendered markup **must** be (a) named with an `_html` suffix
   and (b) typed as a distinct `TrustedHtml` wrapper rather than `str`, and may
   be constructed **only** by Mission Control.

   The naming rule descends from the correction applied after PR #21, where a
   view docstring claimed all inputs were escaped while half were raw
   fragments. A suffix and a docstring are human signals; the type is the
   enforcement, making "pass a provider string where a fragment is expected" a
   type error rather than a silent XSS. `TrustedHtml` is introduced with the
   console primitives, not deferred — adding it later means migrating every
   view field twice.
2. **Provider-derived strings are never trusted.** Labels, qualifiers, group
   names, descriptions, rationales and evidence notes are escaped at render.
3. **View models contain no HTML-bearing provider input.** A provider cannot
   supply an `_html` field, directly or indirectly.
4. **Frozen and pure.** The Mission Console Model is deterministic and side-effect
   free: no I/O, no clock read, no event append, no model call.
5. **Maximum cardinalities are contract-enforced**, not conventions — see
   Acceptance Criteria.

## Accessibility

Requirements are stated so each is testable:

| # | Requirement |
|---|---|
| ACC-1 | One `<h1>`-equivalent page title; each region is a `<section>` with `aria-labelledby` pointing at its own heading; heading levels descend without skipping |
| ACC-2 | Regions are landmarks with unique accessible names; the console exposes exactly five region landmarks (omitted regions expose none) |
| ACC-3 | All interactive controls reachable and operable by keyboard in DOM order; no positive `tabindex` |
| ACC-4 | Visible focus indicator on every focusable element, meeting contrast requirements |
| ACC-5 | Disclosure uses native `<details>`/`<summary>`; `aria-expanded` is native, never hand-set; no custom key handling |
| ACC-6 | Every region provides a screen-reader summary composed from declared state — never a fixed template asserting facts the assessment does not carry (the RFC-008 accessible-summary rule, generalised) |
| ACC-7 | `prefers-reduced-motion` honoured; no essential information conveyed only by motion |
| ACC-8 | Text and meaningful non-text contrast meets WCAG 2.2 AA |
| ACC-9 | Status is never communicated by colour alone; trajectory, margin and confidence each carry a text label alongside tone |
| ACC-10 | Usable at 200% zoom and 320 CSS px width without horizontal scrolling of the page body |
| ACC-11 | Every trajectory visualisation has an equivalent text description conveying the same facts |
| ACC-12 | SVG is `role="img"` with an accessible name, or `aria-hidden` when a text equivalent already conveys it — never both announced |
| ACC-13 | No repeated or verbose announcements: a value stated in the hero is not re-announced verbatim by the analysis summary |
| ACC-14 | Visual and accessible instrument sets match exactly — an omitted instrument is omitted from both |

## Security

RFC-010 introduces no new route, dependency, connector, credential, outbound
destination, write path or authentication change. Assessed areas:

- **Authentication and household scope:** unchanged. The session check remains
  the first statement of the mission route, before definition lookup, scope
  selection and dispatch. The Mission Console Model receives an already-scoped
  assessment and cannot widen scope.
- **Collapsed content is still delivered.** Progressive disclosure is a
  *presentation* control, not an access control. Every disclosed value is
  present in the HTML source regardless of open state. **Nothing may be placed
  behind disclosure on the assumption that it is thereby protected.** Any value
  a household must not see must not enter the assessment at all.
- **Client-side disclosure state:** none in V1 (Decision 14). No cookie,
  `localStorage`, `sessionStorage` or query parameter carries console state, so
  no financial signal is written to client storage.
- **URL and fragment exposure:** deep-link fragments name *sections*, never
  values or identifiers. Fragments are not transmitted to the server and must
  never encode household, scope or evidence data.
- **Page metadata:** `<title>` carries the mission label only — never a value,
  status or amount, since titles leak into history, tab bars and screenshots.
- **Logging:** unchanged; no telemetry value, evidence string or provider
  exception text enters application logs.
- **Evidence provenance:** unchanged. Every rendered figure remains traceable
  to event ids; assessment stays read-only and appends nothing.
- **Trusted HTML boundaries:** governed by the `_html` naming rule above.
  Provider-derived labels, groups, qualifiers, rationales and evidence notes
  are escaped at render.
- **Injection in labels, groups and evidence:** all provider strings escaped;
  `display_group` remains length-bounded (80 chars, RFC-009). Essential and
  disclosure names inherit the same bound.
- **Maximum field lengths:** every provider-supplied display string is
  length-bounded at the contract, so a hostile or malformed provider cannot
  produce unbounded output.
- **Fail-closed rendering:** an assessment failing envelope validation renders
  the existing NOT EVALUABLE console for that mission only; a malformed region
  never partially renders. A Mission Console Model failure is contained by the
  existing dispatch boundary.

## Deterministic Testing

**Mandatory, and the direct lesson of PR #23.** RFC-009's route goldens seeded
fixtures with `build(log)`, taking event timestamps from `time.time()`. Those
timestamps became Mission Control's `as_of`, so calendar projections moved when
the date rolled over: the goldens passed on the day they were written and broke
`main` the following morning. CI on a single day cannot detect this.

**Requirements:**

| # | Requirement |
|---|---|
| DET-1 | Every fixture capable of affecting rendered projections, dates, labels or golden hashes uses an **explicit deterministic clock**. No fixture calls `time.time()` transitively |
| DET-2 | Event-log clocks are monkeypatched to a fixed, monotonically stepped sequence; `build()` receives an explicit `as_of` |
| DET-3 | Golden hashes normalise **only** genuinely volatile operational metadata, and each normalisation is justified in a comment |
| DET-4 | No test asserts behaviour that depends on the current calendar date, month boundary, or year boundary |
| DET-5 | Two runs of the same suite on different simulated dates produce identical goldens — enforced by a test that runs a console render under at least two distinct frozen clocks and asserts hash equality |
| DET-6 | A guard test fails if any test module constructs demo data without an explicit `as_of`, so the PR #23 defect cannot silently return |

DET-5 and DET-6 are the additions that would have caught PR #23 before merge.

## Testing Architecture

| # | Test | Asserts |
|---|---|---|
| T1 | Universal ordering | The five regions appear in fixed order for every live mission |
| T2 | Required regions | Hero, Flight Analysis, Next Burn and Disclosure always present |
| T3 | Optional region omission | Zero essential items ⇒ region absent from DOM **and** accessible tree |
| T4 | No empty cells | No region renders a cell without content, for any applicability combination |
| T5 | Cardinality | Essential ≤ 6 rejected at contract level; hero has no telemetry list; supporting rail ≤ 3 |
| T6 | Trajectory prominence | Trajectory renders in the hero's dominant slot and in the analysis panel; never as a bare word |
| T7 | Non-duplication with purpose | The analysis panel contains a visualisation or an explicit absence explanation, not merely hero text |
| T8 | Four completion/trajectory states | All four combinations render honestly, including complete-but-deteriorating |
| T9 | One Next Burn | Exactly one primary recommendation; extras appear only under Alternative Burns |
| T10 | Burn states | Each of the six defined burn states renders its distinct presentation |
| T11 | Classification | Essential versus supporting classification derives only from `display_region` |
| T12 | Disclosure semantics and safety rule | Native `<details>`; closed by default; critical-warning sections open; deep-link `id`s stable; **and the three safety-rule categories (recommendation `limitations`, `confidence_basis` on Provisional/Insufficient, precedence constraints) render in Region 4 and are never disclosure-only** |
| T13 | Keyboard | Every summary reachable and operable; focus visible; no custom handlers |
| T14 | Trusted fragments | No provider string reaches an `_html` field; AST test on view construction |
| T15 | Escaping | Hostile strings in labels, groups, qualifiers, rationales and evidence notes are escaped; no double-escaping |
| T16 | Domain neutrality | No mission slug, label, policy id or domain term in Core or the renderer (extends the RFC-008 A22 assertion) |
| T17 | No mission-name branching | AST test over renderer and Mission Console Model |
| T18 | Route goldens | Normalised hashes stable for all four missions |
| T19 | Responsive | Console renders without body horizontal scroll at 320px and at 200% zoom |
| T20 | Determinism | DET-1 … DET-6 above |
| T21 | Renderer makes no ordering decision | The renderer performs no sort, re-rank, filter, re-group or omission choice; regions, groups and items render in the order the Mission Console Model supplied. Asserted by feeding a deliberately unsorted view and requiring the rendered order to match input order exactly |

## Renderer Architecture and Retirement

**Minimum evolution, not a rewrite.** PR #21 already extracted three region
views. RFC-010 extends that seam rather than replacing it.

**Retained:** the generic `/missions/{slug}` route, `_render` page shell,
navigation, footer, Earthrise treatment, trajectory SVG and geometry, all
formatting helpers, all design tokens and CSS variables.

**Evolved:** `_MissionHeroView` gains fixed destination/confidence/burn-preview
slots and loses its telemetry list; `_FlightAnalysisView` becomes the composed
Trajectory Panel plus a bounded rail; `_MissionDataView` is replaced by
`EssentialTelemetryView` plus ordered `DisclosureSectionView`s.

**Decision 15 — renderer paths to retire**, in this order:

1. **`display_region: "hero"`** — superseded by fixed hero slots plus
   `essential`. Deprecate on landing; remove once all four missions are
   migrated.
2. **The `analysis-rail` "NEXT BURN" and "ESTIMATED Δv" instruments** —
   superseded by Region 4. Their instrument slots are removed, not restyled.
3. **The monolithic `_MissionDataView` drill-down** — superseded by ordered
   disclosure sections.
4. **`MissionMargin.pace_percent` / `.schedule_buffer_days`** — superseded by
   the domain-neutral margin quantity.
5. **`_legacy_scalar_mission_status`** (RFC-006 deprecated adapter) — its four
   removal preconditions are now met for every live mission.
6. **RFC-005 `phase` / `phases` aliases and `phase_thresholds`** — superseded
   by `milestones` since RFC-006.

**Items 5 and 6 are mandatory**, per the Governor's Q1 ruling of 2026-07-31:
both are retired during the RFC-010 implementation Burn.

Item 4 is the one exception to same-Burn removal: per the Q2 ruling,
`MissionMargin.pace_percent` and `.schedule_buffer_days` are **deprecated but
retained for one compatibility release**, then removed as an explicit breaking
change.

## Migration Plan

The sequence is gated at one mandatory point *(Governor amendment 7)*:

```text
Reference Mission
        ↓
Governor Visual Review        ← MANDATORY GATE
        ↓
Remaining Mission Migration
```

| Step | Gate |
|---|---|
| 1 | Freeze the Mission Console contract (this RFC, on approval) |
| 2 | Build shared console primitives and the Mission Console Model, with mock providers only — **no Finance code** |
| 3 | Prove domain neutrality and cardinality against mock providers (T1–T17) |
| 4 | Capture route goldens for all four missions under deterministic clocks (DET-1–DET-6) |
| 5 | Implement the **reference mission** console |
| 6 | Produce a **live web preview**; screenshots only if a live preview is genuinely unavailable |
| 7 | **GOVERNOR VISUAL REVIEW — MANDATORY GATE. No remaining mission may be migrated until this gate passes.** |
| 8 | Migrate the remaining missions: Financial Resilience (the absence-path validator) first, then Mortgage Freedom, then Financial Independence |
| 9 | Remove retired renderer paths (Decision 15, items 1–4; 5–6 if authorised) |
| 10 | Accessibility and structural validation (ACC-1…ACC-14, T1…T20) |
| 11 | Full deterministic suite on Python 3.10–3.13 |
| 12 | SAFE review, then Governor review |
| 13 | Merge |
| 14 | **Confirm the first post-merge `main` workflow passes before declaring the Burn complete** |

Step 14 is explicit because RFC-009 was declared complete before its post-merge
run failed.

## Reference Implementation Recommendation

**Recommended: Pension Independence.**

Justification:

1. **It is the stated failure case.** Success is measurable as a before/after
   on the mission that motivated the RFC; any other choice leaves the original
   defect unaddressed until later.
2. **It exercises the widest surface** — every region is non-empty: hero with a
   destination (W\*), forecast envelope, ETA, Δv, margin with three factors,
   candidate essential telemetry, a burn with a cross-mission precedence
   constraint, and material for at least six disclosure sections.
3. **It forces no new domain logic.** RFC-009 froze its contract on 2026-07-30
   and shipped it; the console can be built entirely against existing outputs.
4. **It is the newest code**, so migrating it first risks the least
   regression to long-settled missions.

**Mandated second migration: Financial Resilience.** It is the framework's
absence-path validator — trajectory `unavailable`, ETA and Δv `not_applicable`,
no forecast — and the console must not be declared proven until a mission with
those declarations renders honestly and without empty cells. Financial
Resilience is the better *maturity* exemplar but the weaker *reference*, since
as reference it would leave the framework's populated paths unexercised.

## Alternatives Considered

| Alternative | Disposition |
|---|---|
| **Four equal Flight Analysis cards** | Rejected — duplicates hero values and reproduces the equal-weight defect |
| **Per-mission page templates** | Rejected — abandons the domain-neutral renderer, the platform's strongest current property |
| **Keep telemetry promotion as the only mechanism** (extend `display_region` with more regions and no fixed hero slots) | Rejected — providers would keep composing their own page architecture, which is the root cause |
| **A client-side component framework** | Rejected — explicit non-goal; server-rendered HTML with native `<details>` meets every requirement including no-JS |
| **Mission archetypes** (trajectory vs steady-state console variants) | Rejected — RFC-008 G3 already ruled against archetypes; applicability plus omission rules cover the same ground without a taxonomy |
| **Widening `DeltaV.direction`** to carry value movement | Rejected — conflates schedule and value axes; `movement` is a separate domain-neutral field |
| **Persisting disclosure state** | Rejected for V1 — see Decision 14 |
| **Enforcing a three-item minimum on essential telemetry** | Rejected — would incentivise padding, the exact defect being removed |

## Risks

| # | Risk | Consequence | Control |
|---|---|---|---|
| R1 | The Mission Console Model becomes a second policy layer | Domain logic leaks into presentation | Projection is pure classification/ordering/formatting; T11, T17 |
| R2 | Providers game `essential` to promote everything | Region 3 becomes the old telemetry wall | Hard cap 6 at contract level (T5); selection rules reviewed at Gate |
| R3 | Progressive disclosure hides safety-relevant information | Reader acts on an invalidated recommendation | Safety rule is normative; critical warnings hoisted; T12 |
| R4 | Migration lands all four missions at once | Regressions hidden in a large diff | Reference-first sequence with a Governor gate at step 7 |
| R5 | `movement` becomes a second trajectory status | Two competing status models | `movement` is one axis of the trajectory contract, never rendered as an independent status word |
| R6 | Margin amendment breaks Financial Independence | Shipped mission regresses | Additive fields, existing defaults retained, goldens captured first |
| R7 | Determinism regression returns | `main` breaks after a date change | DET-5 and DET-6 |
| R8 | Trusted-fragment discipline erodes as views grow | XSS via a provider string | `_html` naming rule + T14 AST test |
| R9 | Console over-abstracts a UI problem | Complexity relocated, not reduced | Retirement list (Decision 15) is part of the same Burn; net path count must not increase |

## Non-Goals

RFC-010 does not: change financial calculations; add Finance metrics; alter
completion semantics; alter mission policy; change event sourcing; change
authentication; redesign global navigation; introduce a frontend framework; add
mission-specific renderer branches; perform production implementation; migrate
mission pages during this architecture phase; modify runtime tests; or modify
CSS or templates.

## Acceptance Criteria

Blocking for the implementation Burn:

| # | Criterion |
|---|---|
| AC-1 | The five regions render in fixed order for all four Finance missions (T1, T2) |
| AC-2 | A region with no content is omitted from DOM and accessible tree; no empty or decorative cell exists under any applicability combination (T3, T4) |
| AC-3 | Essential telemetry is capped at six by contract validation; the hero carries no telemetry list (T5) |
| AC-4 | Trajectory renders as a composed instrument in both hero and analysis, never as a bare status word (T6, T7) |
| AC-5 | All four completion/trajectory combinations render honestly (T8) |
| AC-6 | Exactly one primary Next Burn; all six burn states render distinctly (T9, T10) |
| AC-7 | Disclosure is native, closed by default, keyboard-operable, deep-linkable, print-complete and functional without JavaScript (T12, T13) |
| AC-8 | No safety-relevant information is disclosure-only (T12) |
| AC-9 | No provider string reaches a trusted fragment; all provider strings escaped without double-escaping (T14, T15) |
| AC-10 | No domain term, mission slug or mission-name branch in Core, the Mission Console Model or renderer (T16, T17) |
| AC-11 | ACC-1 … ACC-14 pass |
| AC-12 | DET-1 … DET-6 pass, including two-frozen-clock hash equality |
| AC-13 | Route goldens stable for all four missions; Financial Independence, Mortgage Freedom and Financial Resilience show no unintended behavioural change (T18) |
| AC-14 | Console renders without body horizontal scroll at 320px and 200% zoom (T19) |
| AC-15 | Retired paths (Decision 15 items 1–4) are removed, not merely bypassed. **Countable measure** *(self-review A2)*: `(distinct region-rendering functions in mission_control.py) + (TELEMETRY_REGION values) + (deprecated contract fields still read by the renderer)` must be **strictly lower** after the Burn than before, asserted by test |
| AC-16 | Full suite green on Python 3.10–3.13; Architecture and Security Gates approve; first post-merge `main` workflow passes |
| AC-17 | The hero carries all four answers — current position, destination, trajectory and next action — for every mission, including when margin is `not_applicable` and trajectory is `unavailable` (structural proxy for the five-second criterion) |
| AC-18 | The renderer makes no ordering, grouping, visibility, disclosure-placement or priority decision; all five belong to the Mission Console Model (T21) |
| AC-19 | The Governor visual review gate is passed on the reference mission **before** any remaining mission is migrated; migrating early is a process failure, not a schedule optimisation |

## Required Decisions — Recommendations

| # | Decision | Recommendation |
|---|---|---|
| 1 | Universal section contract | Five regions, fixed order, universal; missions may not add, reorder or relocate |
| 2 | Minimum hero content | Identity, current position, milestone, destination, trajectory (dominant), margin, confidence, optional burn preview — fixed slots, no telemetry list |
| 3 | Trajectory presentation | Composed `MissionTrajectoryView`; one new field (`movement`) and one new closed vocabulary; all else aggregates existing outputs |
| 4 | Mission Margin boundary | Tolerance between trajectory and success; not completion, confidence, trajectory or progress. Deprecate schedule-specific numerics for a domain-neutral value/unit/format, **and add `margin` to `InstrumentApplicability`** so a binary mission can declare it inapplicable. Mission Margin is the architectural concept; a provider-supplied `label` may present it as Runway, Income Gap, LTV Buffer or Recovery Reserve without changing the contract |
| 5 | Primary telemetry selection | Seven rules; `essential` region; hard cap 6; three-item lower bound is guidance, not validation; zero ⇒ region omitted |
| 6 | One-Next-Burn rule | Exactly one primary; extras to Alternative Burns; six defined states |
| 7 | Disclosure structure | Nine ordered **domain-neutral** Core slots; provider supplies displayed names; native `<details>`; closed by default; warnings hoisted |
| 8 | Shared view-model boundaries | **Mission Console Model** owns ordering, grouping, visibility, disclosure placement and card priority; the renderer owns presentation only. `MissionConsoleView` + five region views; plain text default; `_html` suffix **and** a `TrustedHtml` type for Mission-Control-only fragments |
| 9 | Renderer migration | Extend the PR #21 seam; strangler migration behind a **mandatory** Governor visual gate between the reference mission and the remaining migrations; retire superseded paths in the same Burn |
| 10 | Reference mission | **Pension Independence**, with Financial Resilience mandated as the second migration |
| 11 | Accessibility | ACC-1 … ACC-14, each testable |
| 12 | Deterministic fixtures | DET-1 … DET-6; explicit clocks mandatory |
| 13 | Critical warnings | Never disclosure-only; hoisted into the region they qualify; sections containing them render open |
| 14 | Disclosure persistence | **No persistence in V1.** Server-rendered HTML with no client state; persistence would add storage, a privacy surface and cross-device inconsistency for negligible benefit. Revisit only with evidence of user need |
| 15 | Paths to retire | Hero telemetry region; analysis-rail burn instruments; monolithic drill-down; **legacy scalar adapter and RFC-005 phase aliases — all mandatory** per the Q1 ruling. Margin schedule numerics are deprecated but retained for one compatibility release per the Q2 ruling |

## Unresolved Questions — none remaining

**All architecture questions raised by this RFC are ruled and closed.** Q1, Q2
and Q3 were each ruled by the Governor on 2026-07-31 and are recorded in
[Governor Approval — Architecture Freeze](#governor-approval--architecture-freeze).
The region-ordering tension is accepted for V1.

Questions arising after this point are not open questions against RFC-010; they
require a new Governor decision.

## References

- [`../architecture.md`](../architecture.md) — constitutional invariants;
  observation 3 (completion vs trajectory)
- [`../design/design-constitution.md`](../design/design-constitution.md) —
  Information Honesty, Mission Telemetry, "every pixel earns its place"
- [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md)
- [`../engineering/review-gates.md`](../engineering/review-gates.md)
- [`../security/security-checklist.md`](../security/security-checklist.md)
- [`../security/threat-model.md`](../security/threat-model.md)
- [`../rfc-006-mission-assessment-framework.md`](../rfc-006-mission-assessment-framework.md)
  — closed vocabularies, removal discipline
- [`../rfc-007-mortgage-freedom-architecture.md`](../rfc-007-mortgage-freedom-architecture.md)
- [`../rfc-008-financial-resilience-architecture.md`](../rfc-008-financial-resilience-architecture.md)
  — applicability, G5 delta-v debt, D7 precedence copy standard
- [`../rfc-009-pension-independence-architecture.md`](../rfc-009-pension-independence-architecture.md)
  — display regions, D13, hierarchy precedent
- [`index.md`](index.md) — RFC index
