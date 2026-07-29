# RFC-008 — Financial Resilience Mission

Status: **Approved — not implemented.** This document is the canonical
architecture for implementation. No RFC-008 source code, tests or framework
changes exist yet.

Date: 2026-07-29

Authors: Lead Systems Architect role (Claude, Opus 5), under governor rulings
G1–G10 and U1–U3 issued by the project maintainer. Architecture approved at
Revision 4; this document reproduces that revision as repository record.

## Context

Financial Resilience is the first mission in the fixed Finance hierarchy
(`financial-resilience`, canonical order 1) and the last of the four to gain an
assessment provider. It is currently registered as an honest metadata-only
`MissionDefinition` with no `assessment_policy_id`
([`finance/missions.py`](../src/foundry/finance/missions.py)); RFC-008 fills
exactly that slot.

Three RFCs precede it. RFC-005 introduced the domain-neutral Mission Assessment
seam and wired Financial Independence to it. RFC-006 generalised that seam into
the Mission Assessment Framework: definition discovery, direction-aware
milestones, closed trajectory/margin/confidence vocabularies, isolated provider
dispatch with hard envelope validation, and a generic authenticated
`/missions/{slug}` route. RFC-007 proved the framework by adding Mortgage
Freedom as a second provider wholly within Finance, together with the manual
evidence-envelope pattern this RFC reuses.

RFC-007 also established the cross-mission constraint pattern RFC-008 depends
on: Mortgage Freedom dispatches `finance.liquidity_runway` as an ordinary
metric, compares it against a floor declared in its own Assumption Set, and
suppresses its overpayment recommendation when liquidity is insufficient —
recording that Financial Resilience takes precedence. No assessor calls another
assessor.

## Problem Statement

The mission question is:

> Can this household continue operating safely through unexpected disruption
> without being forced into damaging financial decisions?

Two problems stand between that question and an honest answer.

### The framework cannot yet express a steady-state mission

Financial Independence and Mortgage Freedom are journeys with an arrival date.
Financial Resilience is not: its destination is a sustained condition. The
contract encodes *inapplicable* and *unavailable* identically — `eta = None`
means "not reachable inside the horizon" for FI and Mortgage Freedom, and would
mean "no arrival exists" for Resilience — and the shared renderer resolves that
ambiguity as failure.

The renderer contains no mission-name branching, and therefore passes every
RFC-006 test, but it emits unconditional trajectory-mission prose. The
accessible summary asserts *"The solid historical path reaches…"* and *"The
dashed expected forecast continues through a widening low to high sensitivity
range toward the configured milestones"*; `schedule_summary` appends *"Expected
destination is …"*, where a `None` ETA renders as **`NOT IN HORIZON`**; the
trajectory region falls back to *"Trajectory unavailable."*; the delta-v
instrument renders **`NOT AVAILABLE`**
([`mission_control.py`](../src/foundry/mission_control.py)). Rendered against a
steady-state mission's honest nulls, that is three false assertions to a
screen-reader user plus two degradation states for instruments that are not
degraded — an Information Honesty defect under the
[Design Constitution](design/design-constitution.md).

The renderer is name-agnostic but shape-committed. RFC-006's proof case was
Mortgage Freedom, which is also a trajectory mission; the framework was proved
against two instances of one shape. Financial Resilience is the first genuine
shape-neutrality test.

### Resilience is not a calculator

A calculator answers a closed arithmetic question from one formula over one
input set. RFC-008 adds four such calculators as metrics. The mission is none of
them and is not their sum. **Resilience is an emergent property of evidence,
assumptions and policy**, for four reasons:

1. **No single balance answers the question.** It resolves only by composing
   liquid holdings, an essential-outflow basis, declared near-term commitments,
   income concentration, and protection — the last of which is entirely
   unmodelled and must be represented as a visible absence rather than omitted.
2. **The same evidence yields different answers under different declared
   policy.** An identical household is Secure against a 6-month floor and
   incomplete against the 18-month destination. That relativity cannot live in a
   metric identifier whose meaning is append-only, which is precisely why
   `MissionAssessment` exists
   ([`core/mission_assessment.py`](../src/foundry/core/mission_assessment.py)):
   *"Putting those fields on `MetricResult` would make a scalar dispatch
   contract own product orchestration it cannot understand."*
3. **Evidence quality is part of the answer.** A calculator returns a number or
   an error. Resilience must additionally distinguish *not applicable*,
   *unavailable*, *stale*, *degraded-by-exclusion*, and *capped because
   protection is unmodelled* — and render each honestly. Confidence and
   limitations are load-bearing outputs, not decoration.
4. **It publishes a constraint other missions consume.**
   `finance.deployable_surplus` exists so other missions can be told what
   capital may safely be committed. That is a policy contract with provenance
   and rationale, not a number.

The calculators are the inputs. The mission is what makes them answerable,
explainable, and honest about what it does not know.

## Architectural Decisions

### Single mission model; no archetypes

The Trajectory/State distinction is real as design language and is **not**
introduced as an abstraction. Nothing in Core, `MissionDefinition`, `Mission`,
routing, provider registration or policy identity gains an archetype. The
classification would be violated by the next mission in the queue: Pension
Independence is a trajectory mission before pension-access age and a state
mission afterwards, and Financial Independence has the same latent structure
past its completing band. Archetype is a property of a mission's current phase,
not a stable property of a mission.

**Design-language note (Design Constitution only, never code):** *Financial
Resilience is an orbital station mission — success means maintaining a stable
operating orbit, not arriving once at a destination.*

### One narrow framework amendment

Per-instrument applicability is added for exactly four instruments — `eta`,
`delta_v`, `trajectory`, `forecast`. Additive, defaulting to all-applicable, so
Financial Independence and Mortgage Freedom replay and render byte-identically.
No `MissionDefinition` change, no re-registration, no event migration, and no
policy-id or calculation-version bump for shipped missions.

### Composition

```text
web.py (composition root — structure unchanged)
  ├─ MetricRegistry
  │     ├─ FinanceMetricProvider                  (8 existing metrics — untouched)
  │     └─ FinanceResilienceMetricProvider  [NEW] (M1–M4)
  └─ MissionAssessmentRegistry
        ├─ register_finance_mission_definitions   (resilience gains policy id + definition)
        ├─ FinancialIndependenceAssessor          (untouched; defaults ⇒ all applicable)
        ├─ MortgageFreedomAssessor                (untouched logic; D7 copy amendment only;
        │                                          still reads finance.liquidity_runway
        │                                          + its own floor)
        └─ FinancialResilienceAssessor      [NEW] (declares D2.2 applicability)
              ↑ reads: MetricRegistry, FinanceEntityProjection, EntityProjection,
                       ResilienceEvidenceProjection
              ✗ never: MissionAssessmentRegistry, another assessor, a model, an append
```

New Finance modules: `finance/resilience_evidence.py`,
`finance/resilience_metrics.py`, `finance/resilience_assessment.py`. The
`finance/missions.py` order-1 entry gains a policy id and definition text.
Policy id `finance.financial_resilience.v1`; calculation version
`resilience-v1`.

**Constraint transport, normative.** Constraints travel only as (a) a
`MetricResult` dispatched through `MetricRegistry`, plus (b) a threshold
declared in the *consuming* mission's own Assumption Set. **No
assessor-to-assessor dependency is permitted.** Mortgage Freedom does not
migrate to `finance.deployable_surplus` in RFC-008.

### Constitutional observations

Two observations, each supported by shipped repository behaviour. They are
**consistent with the five existing invariants in
[`architecture.md`](architecture.md), not additions to them**.

**Observation 1 — Mission assessments are observations derived from evidence;
facts live in the append-only event log.** Invariants 1–2 hold that the log is
append-only and the sole source of truth, and that the Canon has no write path
of its own. Spec 000 §13.4 requires that a provider never writes a derived
metric value into canonical observed state. `MissionAssessment` is a frozen
dataclass returned by a read-only `assess` call; no assessor appends an event,
and Mission Control is a consumer that never appends. Every resilience figure —
runway, reserve target, gap, surplus, milestone state, margin band, confidence,
stress results — is an observation computed from the log at `as_of`, never a
fact recorded into it.

**Observation 2 — Mission completion is an assessment outcome and is not
necessarily monotonic.** Completion already lives in two architecturally
separate places. `MissionAssessment.mission_complete` is a derived field on the
read model. The `Mission` entity's lifecycle is independent and event-sourced —
`active` / `achieved` / `abandoned` via `achieve_mission` and `abandon_mission`
([`core/entities.py`](../src/foundry/core/entities.py)) — reachable only by an
explicit user-actor event, and **no assessor calls either function**. The
separation exists in shipped code; RFC-008 relies on it rather than introducing
it. Trajectory missions happen to be monotone in practice; that is a property of
those missions, never of the framework. **No consumer may assume
`mission_complete` is monotonic.**

## Decision Record

### D1 — Published metrics

Four Finance-owned metrics registered through a second provider
(`FinanceResilienceMetricProvider`) at the composition root. `MetricRegistry`
keys by `metric_id` and rejects duplicate ownership, so two Finance providers
coexist safely. Full specifications are in
[Metric Definitions](#metric-definitions).

**Single-basis lock.** The reserve target is never computed from a second
denominator. `finance.essential_outflow_monthly` publishes precisely the
denominator `finance.liquidity_runway` already uses. Declared `RecurringSeries`
is **cross-check evidence only**: material divergence beyond
`outflow_crosscheck_tolerance` raises a limitation and downgrades confidence,
and must never silently replace the published basis.

### D2 — Mission shape

Financial Resilience is a steady-state mission; that is a property of the
*assessment*, not a mission type.

**D2.1 — Why the amendment is required.** See
[Problem Statement](#problem-statement).

**D2.2 — Applicability declarations, V1:**

| Instrument | State | Justification |
|---|---|---|
| `eta` | `not_applicable` | No arrival exists; the mission maintains a condition |
| `delta_v` | `not_applicable` | Movement is months-of-runway, not schedule; `DeltaV.direction` is closed to `accelerated`/`delayed` |
| `forecast` | `not_applicable` | No deterministic time projection in scope; adverse stresses are never forecast points |
| `trajectory` | **`unavailable`** | A history *could* exist; the averaging-window artifact in the essential-outflow denominator makes it dishonest today. Fixable — therefore not `not_applicable` |

That fourth row is why applicability is per-instrument rather than per-mission: a
mission-level tag would mark trajectory inapplicable and permanently mislabel a
fixable data limitation.

**D2.3 — Delta-v vocabulary.** Extension of `DeltaV.direction` with
`strengthened`/`weakened` is deferred. No Core vocabulary expansion is justified
by RFC-008. Recorded as technical debt.

**D2.4 — Reserve bands, completion and reversibility.** See
[Mission Semantics](#mission-semantics).

### D3 — Evidence model

Disposition rule: missing **required** → `unavailable` assessment; missing
**optional** → limitation, confidence downgrade and exclusion from margin, never
a favourable default; **future** → declared absent, capped confidence, never
scored. Detailed in [Mission Semantics](#evidence-model).

### D4 — Mission Margin

Worst-factor-wins over discrete integer bands, mirroring the Mortgage Freedom
pattern. Weight coefficients are **forbidden** in the policy dataclass.
Detailed in [Mission Semantics](#mission-margin).

### D5 — Runway identity

Reuse `finance.liquidity_runway`; do not fork it; do not redefine it. Its
formula, `CALCULATION_VERSION`, unit and provider ownership are untouched. A
guard test asserts it remains the sole runway identifier and that
`liquid ÷ M1` reproduces it.

### D6 — Applicability contract

See [Applicability Contract](#applicability-contract).

### D7 — Mortgage Freedom precedence copy

A **deliberate RFC-007 behavioural-copy amendment**, executed inside RFC-008 and
separately pinned — not a silent incidental edit.

Current copy states that Financial Resilience takes precedence and that
liquidity runway is below the declared recommendation floor, but withholds both
the observed value and the floor. Required: expose **observed liquidity
runway**, **declared recommendation floor**, and **rationale**; expose **no raw
internal identifiers and no assumption keys**. Approved style:

> *Overpayment is not recommended because current liquidity runway is 4.2
> months, below Mortgage Freedom's declared 6-month recommendation floor.
> Preserve emergency liquidity before deploying additional capital.*

Constraints therefore render the threshold **value with a human label**, never
the key name. This is the **only** approved change to Mortgage Freedom's
rendered output; every other byte must be identical.

## Mission Semantics

- **Mission:** Financial Resilience (order 1, slug `financial-resilience`).
- **Destination:** *"The household can absorb a serious, unexpected disruption
  from its own liquid resources — 18 months of essential outflow held in reserve
  — without being forced into a damaging financial decision."*
- **Completion:** runway ≥ 18 months (**Fortified**). Derived and reversible.
  Protection is unassessed and caps confidence without preventing numeric
  completion.
- **Minimum operational resilience:** 6 months (entry to **Secure**) — a
  reported threshold, not completion.
- **`current_value`:** `finance.liquidity_runway`, unit **`months`**. No
  synthesised score, no index.

### Milestones and completion

| Order | Milestone | Lower (months) | Upper (months) | `completes_mission` |
|---|---|---|---|---|
| 0 | **Exposed** | 0 | 1 | no |
| 1 | **Fragile** | 1 | 3 | no |
| 2 | **Buffered** | 3 | 6 | no |
| 3 | **Secure** | 6 | 18 | no |
| 4 | **Fortified** | 18 | *(none)* | **yes** |

Units are months of essential outflow; `destination_direction =
"higher_is_better"`, matching the registered definition or provider-envelope
validation rejects the result. Bounds satisfy the contract's
`upper_bound > lower_bound` rule; the open-ended top band uses
`upper_bound = None`.

Locked mission intent: *"Financial Resilience — 18 months and protections."* For
V1 the quantitative destination is 18 months and protection is unassessed.

### Reversible completion

No new machinery is required, because completion is *derived*, never *declared*
(Observation 2):

- `mission_complete` is computed at assessment time as `runway_months ≥ 18`, on
  an immutable read model, recomputed every request.
- The `Mission` entity lifecycle is untouched. No `achieve_mission` /
  `core.mission.closed` event is ever appended by an assessment.
  `Mission.status` remains `active` indefinitely, so the mission never enters
  the terminal `achieved` state the entity projection cannot leave.
- If runway later falls to 16 months, the next assessment computes
  `mission_complete = False`, the current milestone moves Fortified → Secure,
  and `trajectory_state` moves `Complete` → `Nominal` or `Constrained` by the
  same deterministic rules. Nothing is "un-achieved", because nothing was
  recorded as achieved.
- The append-only log is not violated: no completion fact was appended.
  Completion is a projection over evidence — the Canon-is-a-fold discipline
  applied to mission state.

### Trajectory state

`Complete` = runway ≥ 18 and no factor at band 0; `Nominal` = target met, or gap
within policy tolerance; `Constrained` = gap open with non-negative surplus;
`Divergent` = gap widened over the declared lookback; `Critical` = runway below
`critical_floor_months`, or negative surplus with recognised commitments due
inside the horizon.

### Mission Margin

Worst-factor-wins over discrete integer bands; no weights.

| Factor | Band 3 | Band 2 | Band 1 | Band 0 |
|---|---|---|---|---|
| Reserve coverage (months) | ≥ 18 (Fortified) | ≥ 6 (Secure) | ≥ 3 (Buffered) | < 3 |
| Income concentration | ≤ policy limit, ≥ 2 sources | ≤ limit | > limit | single source, no reserve |
| Commitment coverage (surplus ÷ commitments) | ≥ 2× | ≥ 1× | ≥ 0.5× | < 0.5× |
| Obligation headroom | no near-term unfunded | minor | material | breach |

`min == 0 → Negative Margin`; `min == 1 → Low Margin`; `all == 3 → High
Margin`; otherwise `Adequate Margin`. Every factor is an independently visible
`TelemetryItem` and is named with its value in the margin description, so the
band is reconstructable by inspection. Excluded-because-absent factors are
dropped from `min()` **and** named in limitations — an absent factor can neither
raise nor lower the band silently.

### Mission Confidence

| State | Condition |
|---|---|
| `Established` | **Unreachable in V1** — protection and insurance evidence are entirely unmodelled |
| `Supported` | All required evidence present, fresh, high-confidence; no factor excluded |
| `Provisional` | Any factor excluded, evidence stale, low-confidence evidence, invalid envelopes present, or an outflow cross-check divergence |
| `Insufficient` | Fail-closed (`MissionAssessment.unavailable`) |

The `Established`-unreachable cap is a **V1 policy limitation, not a permanent
framework rule**, and must be stated as such in the rationale or limitations — a
silent cap is a contract-test failure. Confidence follows the
`min(record.confidence)` plus staleness pattern established by Mortgage Freedom.

### Evidence model

**Required — absence fails closed:** active household Party and reporting
currency; liquid / near-liquid holdings; essential-outflow basis (M1);
resilience Assumption Set.

**Optional — degrades honestly:** income sources and concentration
(`finance.employer_concentration`); **near-term commitment declarations**
(absent ⇒ term 0 **with mandatory limitation**); debt obligations and headroom;
evidence freshness.

**Future — protection and insurance.** No entity, event kind or vocabulary
exists in the repository. Rules, all testable:

1. Protection is **explicitly unassessed** and named as such in every
   assessment.
2. Missing protection evidence is **never favourable** — it cannot raise a band,
   contribute a factor, or improve trajectory state.
3. **Absence of protection evidence is not evidence of absence.** Rendered
   language must say protection is *not assessed*, never that the household is
   *unprotected*. Both inferences are prohibited.
4. Protection **caps Mission Confidence at `Supported`**.
5. **The cap must be visible** in the confidence rationale or limitations.
6. Protection is never inferred from transaction descriptions, account names,
   series descriptions, or any display text.

**Envelope mechanism.** Event kind `finance.resilience_evidence.recorded`,
following the RFC-007 pattern: `field`, `value`, `effective_at`, `confidence`,
`source`, `lineage`, optional `unit_or_currency`; closed field whitelist;
**validated before append**; tolerant projection keeping invalid envelopes
visible and downgrading confidence rather than dropping them; deterministic
tie-breaking by event-log order, never UUID. Whitelisted fields cover
essential-outflow declarations (cross-check), income-source declarations,
**near-term commitment declarations with due dates**, and protection
declarations **reserved but unscored in V1**.

### Assumption Set keys

Validated on load; fail closed on missing or invalid: `reserve_target_months`
(18), `secure_floor_months` (6), `critical_floor_months`,
`income_concentration_limit`, `commitment_horizon_months` (12),
`outflow_crosscheck_tolerance` (0.20), `evidence_stale_after_days`,
`movement_lookback_days`, plus per-stress magnitudes.

### Limitations always rendered

Protection not assessed, with the confidence cap stated; affordability not
assessed; the essential-outflow basis and its derivation; stresses are
deterministic arithmetic, not probabilities; why trajectory is unavailable
rather than inapplicable; absent near-term commitment evidence where applicable.

### Recommendation architecture

**Mission-local recommendations; published constraints.** Rejected and recorded:
a cross-mission constraint registry in Core (Core owns shapes and routing only);
Mission Control mediation (it imports no domain); Resilience vetoing another
mission (requires assessor-to-assessor calls, breaks independent
executability).

**Every recommendation constraint must expose** its evidence (metric result and
references), the **threshold value with a human label** (never the assumption
key), and a rationale naming which mission's requirement took precedence.

**Financial Resilience recommendations:** render action, amount, cadence where
applicable, rationale, evidence, policy threshold, and **reserve-gap effect
where the current contract supports it**; **omit Estimated Delta-v entirely**
(governed by `delta_v` applicability). A generic non-schedule impact abstraction
is deferred debt.

**Stress scenarios are not `Scenario` entities.** A `Scenario` is a proposed
action; an adverse event is not. Deterministic stresses — income reduction,
unexpected expenditure, rate shock, temporary unemployment — render as
`TelemetryItem`s with a qualifier (for example `RUNWAY · 3-MONTH INCOME LOSS`,
`DETERMINISTIC STRESS · NOT A PROBABILITY`). No probability language; no stress
value in `forecast`, which for Resilience is `not_applicable` and must stay
empty.

### Mission Control rendering

**Scope finding:** confined to the **detail route**. The homepage lane renders
only current value, current milestone, mission margin and trajectory state — no
ETA, delta-v or forecast prose. **The homepage lane requires no change** and is
pinned unchanged.

**The renderer branches on declared applicability — never on value truthiness or
tuple emptiness.**

| Surface | `applicable` | `not_applicable` | `unavailable` |
|---|---|---|---|
| ETA hero tile | as today | **omitted entirely** — no em dash, no "not in horizon" | honest absence + explanation |
| Delta-v instrument | as today | **omitted entirely** | "NOT AVAILABLE" + description |
| Estimated Delta-v instrument | as today | **omitted** (governed by `delta_v`) | as today |
| Trajectory region | SVG | **omitted** — no "unavailable" wording | "Trajectory unavailable." + reason |
| `schedule_summary` | as today | sentence **omitted entirely** | states absence honestly |
| Forecast prose | as today | clause **omitted entirely** | clause states absence |

A state mission must not appear to be a broken trajectory mission. Rendering a
not-applicable instrument as an em dash, as unavailable, as failed, or as
insufficient evidence is a blocking defect.

### Accessibility

- The accessible summary is **composed from applicability metadata**, not a
  fixed template. Clauses for trajectory, forecast and schedule appear only when
  their instrument is `applicable`; `unavailable` instruments contribute an
  honest absence clause; `not_applicable` instruments contribute **nothing at
  all**.
- No fabricated historical-path prose; no forecast prose where forecast is not
  applicable; no "not in horizon" wording for a not-applicable ETA.
- Omitted instruments are omitted from the accessible tree as well as the visual
  layout — parity asserted, so screen-reader and sighted users receive the same
  instrument set.
- Keyboard and focus parity with the shipped mission page is retained.
- Month-unit values are announced with their unit ("6 months", never "£6").

## Metric Definitions

Common to all four: **scope** is a Party subject routed through existing scope
rules; **provenance** requires `input_references` naming every contributing
event and conversion reference, plus `assumption_references` wherever a policy
value is applied; **`calculation_version`** is `resilience-metrics-v1`; **no
model call, no event append**; unsupported request shapes (`horizon`,
`scenario_id`) return `unsupported` rather than a silently-baseline answer.

### M1 — `finance.essential_outflow_monthly`

| Attribute | Specification |
|---|---|
| **Stable ID** | `finance.essential_outflow_monthly` |
| **Owner** | Finance — `FinanceResilienceMetricProvider` |
| **Description** | Average monthly essential and committed household outflow. **This is precisely the denominator `finance.liquidity_runway` already uses**, published so it can be inspected rather than inferred. |
| **Unit** | Household reporting currency (GBP), per month |
| **Formula** | Byte-equivalent to the existing `_average_essential_outflow`: for each owned account, take transactions with `ts ≤ as_of` whose `transaction_category` is in the essential/committed category set; negate the amount (net, not absolute — a refund reduces the burn it refunds); convert to reporting currency; weight by ownership share for a person scope, full value for a household union; sum; divide by the count of **distinct observed calendar months**. |
| **Source evidence** | `finance.transaction.*`; account ownership links; `finance.exchange_rate.*` |
| **Freshness rule** | Derived from transactions at or before `as_of`. When the most recent contributing transaction is older than `evidence_stale_after_days`, status is `stale` — value returned and flagged. |
| **Missing-evidence disposition** | No contributing transactions, or net total ≤ 0 → `unavailable`, reason *"no net essential or committed monthly outflow observed"*. **Never defaulted, never estimated.** |
| **Provenance** | `input_references` = every contributing transaction's provenance plus conversion references |
| **Consumable by other missions** | Yes |

### M2 — `finance.emergency_reserve_target`

| Attribute | Specification |
|---|---|
| **Stable ID** | `finance.emergency_reserve_target` |
| **Owner** | Finance — `FinanceResilienceMetricProvider` |
| **Description** | The cash reserve the household is aiming to hold — the mission's quantitative destination expressed in money. |
| **Unit** | GBP |
| **Formula** | `reserve_target_months × finance.essential_outflow_monthly`, where `reserve_target_months` is declared in the resilience Assumption Set and is **18**. |
| **Source evidence** | M1's evidence plus the Assumption Set event |
| **Freshness rule** | Inherits M1's status exactly; `stale` propagates |
| **Missing-evidence disposition** | M1 `unavailable`, or `reserve_target_months` missing or invalid → `unavailable`. Never defaulted. |
| **Provenance** | M1's references plus `assumption_references` = Assumption Set provenance |
| **Consumable by other missions** | Yes |

### M3 — `finance.emergency_reserve_gap`

| Attribute | Specification |
|---|---|
| **Stable ID** | `finance.emergency_reserve_gap` |
| **Owner** | Finance — `FinanceResilienceMetricProvider` |
| **Description** | Signed shortfall against the reserve target. Positive = short by that amount; zero or negative = target met or exceeded. |
| **Unit** | GBP |
| **Formula** | `emergency_reserve_target − liquid_holdings`, where `liquid_holdings` is the union (household) or share-weighted (member) value of Accounts and Assets classified `liquid` or `near_liquid` — the identical numerator `finance.liquidity_runway` uses. **Signed, never clamped** — the deficit lives here, exclusively. |
| **Source evidence** | M2's evidence plus contributing valuations and ownership links |
| **Freshness rule** | `stale` if M2 or any contributing valuation is stale |
| **Missing-evidence disposition** | M2 `unavailable`, or no liquid-holdings evidence → `unavailable` |
| **Provenance** | Union of M2 references and every contributing holding's provenance |
| **Consumable by other missions** | **Yes — the metric a consumer needing a less conservative gate than M4 should use**, together with M1, applying its own declared threshold |

### M4 — `finance.deployable_surplus`

| Attribute | Specification |
|---|---|
| **Stable ID** | `finance.deployable_surplus` |
| **Owner** | Finance — `FinanceResilienceMetricProvider` |
| **Frozen definition** | **Liquid assets remaining above the full 18-month Financial Resilience reserve target after recognised near-term commitments.** |
| **Description** | **A resilience stock, not an income flow.** Capital that may be committed elsewhere — overpayment, investment, any other mission — without breaching the reserve target or leaving a recognised near-term commitment unfunded. It is **not** monthly disposable income, **not** free cash flow, **not** a spending allowance. |
| **Unit** | GBP — a stock at `as_of`, never period-denominated |
| **Formula** | `max(0, liquid_holdings − emergency_reserve_target − recognised_near_term_commitments)`. Clamped at zero: a shortfall is never expressed here because M3 carries the signed deficit. Encoding the deficit twice with opposite signs would be a correctness trap. |
| **Source evidence** | M2 and M3 evidence plus declared near-term commitment evidence |
| **Freshness rule** | `stale` if any contributing input is stale |
| **Missing-evidence disposition** | Any contributing metric `unavailable` → `unavailable`. **Absent commitment evidence never defaults silently:** the term is taken as 0 **with a mandatory limitation** naming that no near-term commitments are recorded, so a surplus can never be inflated by unrecorded obligations without the reader being told. |
| **Provenance** | Union of all contributing references plus commitment evidence event ids |
| **Consumable by other missions** | **Yes — this is the constraint metric.** Mortgage Freedom does **not** consume it in RFC-008. |

**Conservatism is intended and must not be softened.** Measuring above the
**full 18-month target** means this metric will frequently return zero until the
mission destination is reached. That is correct behaviour, not a defect: before
a household holds its full reserve, there is by definition no capital deployable
without eroding resilience. **Implementers must not weaken, rebase, or add a
"partial surplus" variant** because zero appears often. A future consumer
needing a less conservative gate composes M3 and M1 with its own declared
threshold — the metric set already supports this without changing M4's frozen
meaning, which is append-only.

**Near-term commitments — source of the term.** The repository inspection is
accepted: `RecurringSeries` carries `recurring_commitment_type`, `amount`,
`currency`, `description`, `status` and **no cadence, frequency or next-due
date**; `Obligation` carries category, currency, amount and **no due date**
([`finance/entities.py`](../src/foundry/finance/entities.py)). Therefore
`recognised_near_term_commitments` is supplied **solely through the RFC-008
resilience evidence envelope**, carrying effective date, confidence, source and
lineage, summing declared commitments due within `commitment_horizon_months` of
`as_of`. **Cadence and due dates are never inferred.** RFC-008 modifies no
entity, event schema or projection. Richer commitment entities are recorded as
technical debt.

### Metric reconciliation

```text
                     liquid_holdings  (union / share-weighted; liquid + near_liquid)
                              │
        ┌─────────────────────┼──────────────────────────────┐
        │                     │                              │
finance.liquidity_runway      │                    finance.emergency_reserve_gap  (M3)
  = liquid ÷ M1               │                      = M2 − liquid        [signed]
  UNIT: months                │                              │
  EXISTING — UNCHANGED        │                              │
        │                     │                              │
        └──── denominator ────┴── finance.essential_outflow_monthly (M1)  UNIT: GBP/month
                                        │   (the same denominator, now published)
                                        │
                              × reserve_target_months (18)
                                        │
                              finance.emergency_reserve_target (M2)  UNIT: GBP
                                        │
                     liquid − M2 − recognised_near_term_commitments
                                        │
                              finance.deployable_surplus (M4)  UNIT: GBP, clamped ≥ 0
```

Invariants, each asserted by test:

1. **`finance.liquidity_runway` is not redefined** — formula,
   `CALCULATION_VERSION`, unit and provider ownership untouched.
2. **One outflow basis** — `liquid_holdings ÷ M1` reproduces
   `finance.liquidity_runway` within floating tolerance.
3. **One numerator** — M3 and `finance.liquidity_runway` use the identical
   liquid-holdings set.
4. **No duplicate quantity** — runway is the only months-denominated survival
   duration; M4 the only deployable stock; the deficit exists only in M3.
5. **Acyclic derivation** — M1 → M2 → M3/M4; runway depends on M1's computation,
   not on M2–M4.

## Applicability Contract

```text
core/vocab.py
  INSTRUMENT_APPLICABILITY = ClosedVocabulary(
      "instrument_applicability", {"applicable", "not_applicable", "unavailable"})

core/mission_assessment.py
  @dataclass(frozen=True)
  class InstrumentApplicability:
      eta:        str = "applicable"
      delta_v:    str = "applicable"
      trajectory: str = "applicable"
      forecast:   str = "applicable"
      # __post_init__ validates each against INSTRUMENT_APPLICABILITY

  MissionAssessment:
      applicability: InstrumentApplicability = <frozen all-applicable default>
```

Semantics:

- **`applicable`** — the instrument is conceptually meaningful for the current
  assessment or phase.
- **`not_applicable`** — the instrument has no valid meaning for the current
  assessment or phase.
- **`unavailable`** — the instrument is meaningful, but cannot currently be
  produced because of missing evidence, insufficient history or unsupported
  capability.

Four named fields rather than a mapping: explicit, type-safe,
closed-vocabulary validated, impossible to typo silently. Frozen, so a shared
default instance is safe. Domain-neutral — the vocabulary contains no financial
term.

**Rejected representations, recorded so they are not revisited:** attaching
state to each instrument (breaks existing `assessment.eta` reads and both
shipped providers — a breaking change for a presentation concern); a frozenset
of not-applicable names (collapses three states to two, cannot express
`unavailable`, not type-safe); inferring from value presence (reproduces the
exact defect being fixed).

**Consistency validation in provider-envelope validation:**

| Declared | Requirement |
|---|---|
| `applicable` | Corresponding value **must be present** — `eta is not None`; `trajectory`/`forecast` non-empty |
| `not_applicable` | Corresponding value **must be absent** — `eta is None`; tuples empty |
| `unavailable` | Corresponding value **must be absent**, **and** an explanation must exist |

**The `unavailable` explanation rule.** An `unavailable` instrument may never be
a silent empty state. Satisfied by either (a) a relevant limitation attached to
the assessment — the provider's responsibility; or (b) a **deterministic generic
explanation supplied by the renderer** when the provider supplies none, a fixed
non-fabricating string per instrument (for example *"Trajectory history is not
available for this mission."*). The renderer fallback guarantees (b) always
exists, so silence is structurally impossible.

**Scope discipline.** Applicability is presentation metadata only. It may never
change a value, band, status, completion flag, or confidence state.

**Coupled rule.** The assessment-level `delta_v` applicability governs
`RecommendationAssessment` ETA-change rendering. A generic non-schedule
recommendation-impact abstraction is deferred debt.

## Security Considerations

**Classification.** Liquid holdings, essential outflow, income sources and
near-term commitments are *personal-confidential*; in aggregate they disclose
when a household is least able to absorb loss. Protection declarations (future)
are equally sensitive. Stress results are *derived-sensitive*; applicability
metadata is *derived-non-sensitive*. Neither is persisted.

**Provenance and auditability.** Every rendered figure traces to event ids. Each
assessment is reconstructable from (log, policy id, calculation version,
assumption event ids). No assessment is appended — projections never masquerade
as observed facts, and reversible completion depends on exactly this property.

**Hostile and malformed manual inputs.** Validated before append; malformed
envelopes quarantined **and visible**, downgrading confidence rather than
disappearing; hostile strings in `source`, `lineage` and `description` escaped
on render. **No prose is ever parsed for a number**, and **no policy is invented
from labels or display text** — a field's meaning comes from its whitelisted
key, never its description.

**Stale and future-dated evidence.** Evidence with `effective_at > as_of` is
excluded from the assessment and its existence disclosed rather than silently
dropped. Stale evidence propagates `stale` status and a confidence downgrade;
staleness may never improve a band.

**Scope isolation.** Scope is derived server-side from replayed entities; the
slug selects a Mission, the Mission determines scope. Core already rejects
cross-scope evidence; resilience telemetry must pass that unchanged.

**No object-level authorisation expansion.** No new authorisation surface, no
new route beyond the existing generic authenticated mission route, no sharing,
no multi-user capability. The single-configured-account reality and RFC-006's
object-level authorisation debt are unchanged.

**No hidden inference of protection.** Protection status is never derived from
transactions, account names, series descriptions or display text — enforced by
the closed field whitelist and asserted by test.

**Future live providers.** The manual writer remains a documented deprecated
bridge (RFC-007 debt). Any live provider must preserve source, effective date,
confidence, lineage, scope and immutable provenance before replacing it.
RFC-008 adds no file parsing, no network access, no credentials, no secrets.

**Deterministic failure behaviour.** Missing required evidence → `unavailable`
with a distinct reason; provider exception → contained by dispatch as one NOT
EVALUABLE lane, deck intact; malformed provider output → rejected by contract
validation. Nothing retries, nothing fabricates, nothing degrades silently.

**Demonstration data.** Resilience demo evidence carries the existing
synthetic-marker discipline so a seeded log can never be mistaken for a real
household.

This section is the input to the Security Gate and answers every question in
[`security/security-checklist.md`](security/security-checklist.md).

## Acceptance Criteria

**A1–A40 are blocking.**

### Framework and isolation

| # | Criterion |
|---|---|
| A1 | No `MissionAssessmentProvider` implementation references `MissionAssessmentRegistry` or imports another assessor (AST test). Constructors accept metric registry and projections only. |
| A4 | Each assessor is **independently executable**: assessing one mission with the others unregistered succeeds or fails closed — never raises, never order-dependent. |
| A13 | Determinism: two assessments of one log are equal; two renders byte-identical; `generated_at` excluded. |
| A14 | Read-only: log length and hash unchanged across assessment and render; **no event appended**, including no `achieve_mission`. |

### Regression — shipped missions

| # | Criterion |
|---|---|
| A2 | **Financial Independence behaviourally unchanged** — golden pins on status, trajectory state, margin, milestones, delta-v, ETA, recommendations. |
| A19 | **FI detail-route rendering byte-identical** across the amendment. |
| A3 | **Mortgage Freedom behaviourally unchanged** — same field pins. |
| A20 | **Mortgage detail-route rendering byte-identical except the approved D7 precedence copy**, separately pinned with its own expected string. |
| A27 | **Existing providers default to all-applicable** — FI and Mortgage supply no applicability and validate as `applicable` on all four instruments. |
| A31 | **Homepage lane output unchanged** for FI and Mortgage, byte-identical. |

### Applicability contract

| # | Criterion |
|---|---|
| A21 | **Applicable-but-missing fails validation**; **not-applicable-with-data fails**; **unavailable-with-data fails**. Three separate assertions. |
| A22 | **No applicability decision derives from a mission slug, label or policy id** anywhere in the renderer, and none derives from value truthiness or tuple emptiness. |
| A23 | **Applicability is presentation-scope only** — flipping any state changes no value, band, status, completion flag or confidence state. |
| A33 | **`unavailable` is never a silent empty state** — with no provider limitation, the renderer emits its deterministic generic explanation. |

### Rendering and accessibility

| # | Criterion |
|---|---|
| A24 | **No fabricated historical-path prose** — no "solid historical path", "dashed expected forecast", or "widening low to high sensitivity range" where trajectory is not applicable or unavailable. |
| A25 | **No "not in horizon" wording and no em dash for a not-applicable ETA** — the instrument is omitted; likewise delta-v. |
| A26 | **`unavailable` and `not_applicable` trajectory render differently** — two fixtures differing only in declared state. |
| A35 | **No forecast prose where forecast is not applicable.** |
| A36 | **Accessible summaries generated from applicability metadata**, with visual and accessible instrument-set parity. |
| A9 | Months-unit milestones and current value render with month units, never currency; no mission-name branching. |
| A10 | **No raw metric identifier renders** in user-facing output. |
| A38 | **No assumption key renders** in user-facing output — including the D7 copy, which shows value and human label only. |

### Financial Resilience behaviour

| # | Criterion |
|---|---|
| A5 | Declares `eta`, `delta_v`, `forecast` `not_applicable` and `trajectory` `unavailable`; returns `eta is None`, `delta_v is None`, `forecast == ()`, `trajectory == ()`. **No stress value in `forecast`.** No probability language. |
| A6 | Milestone direction matches the registered definition; exactly one `is_current`; ids and orders unique — dispatch returns the provider's result, not the fail-closed envelope. |
| A7 | Worst-factor-wins: no weight coefficient in the policy dataclass; one degraded factor drives the band down; every factor is its own `TelemetryItem`, named with its value. |
| A8 | Missing protection evidence never improves the result; confidence cannot reach `Established`; **the cap is visible** in rationale or limitations. |
| A34 | Protection is **never inferred** from transaction descriptions, account names, series descriptions or display text; rendered language says *not assessed*, never *unprotected*. |
| A11 | No adverse stress is represented as a Finance `Scenario` entity. |
| A12 | Missing **required** evidence fails honestly with a distinct reason per row; missing **optional** evidence degrades and **never** raises a band. |
| A32 | **Reversible completion**: 18+ months ⇒ `mission_complete=True`; the same household at 16 months ⇒ `False`, with milestone (Fortified → Secure) and trajectory state following, **no event appended**, `Mission.status` still `active`. |
| A37 | **Estimated Delta-v omitted** from Resilience recommendation rendering, while action, amount, cadence, rationale, evidence and threshold still render. |
| A40 | Milestone labels are exactly **Exposed / Fragile / Buffered / Secure / Fortified**, with `completes_mission` set on **Fortified** only. |

### Metrics

| # | Criterion |
|---|---|
| A28 | **One outflow basis** — `liquid_holdings ÷ finance.essential_outflow_monthly` reproduces `finance.liquidity_runway` within tolerance; runway's `CALCULATION_VERSION` and formula unchanged. |
| A29 | **`finance.deployable_surplus` is a stock** — GBP, clamped ≥ 0, never period-denominated; the deficit appears only in `finance.emergency_reserve_gap`. |
| A39 | **`deployable_surplus` is measured above the full 18-month target** — a fixture below the destination returns exactly zero, with no partial-surplus variant and no rebased threshold. |
| A30 | **Absent near-term commitment evidence produces a mandatory limitation**, never a silent zero. |
| A15 | Lineage on every `available` telemetry item; assumption references wherever policy is applied. |
| A16 | Every recommendation constraint renders evidence, **threshold value with human label**, and rationale. |

### Process

| # | Criterion |
|---|---|
| A17 | Hostile manual evidence: rejected at append, quarantined-but-visible on replay, reflected as confidence downgrade; hostile strings escaped. |
| A18 | Full suite green on Python 3.10–3.13; Architecture Gate and Security Gate APPROVE; completed Security by Design checklist in the pull request. |

### Risks and controls

| # | Risk | Consequence | Control |
|---|---|---|---|
| R1 | Assessor-to-assessor coupling | Cycles swallowed as "failed safely"; missions not independently assessable | A1; frozen constructor signature |
| R2 | Applicability used as a status system | A second, silent status model | A23 |
| R3 | Protection absence read as favourable **or** as evidence of absence | Household told it is resilient because fragility was never recorded — or told it is unprotected without evidence | A8, A34 |
| R4 | Opaque weighted score | Unexplainable band | A7 |
| R5 | Runway forked or redefined | Conflicting figures; Mortgage behaviour changes silently | A2, A28, D5 guard |
| R6 | Months rendered as currency | "£3–£6" | A9 |
| R7 | Stress values in forecast or `Scenario` entities | Adverse events shown as plans or probability envelopes | A5, A11 |
| R8 | Raw metric ids or assumption keys rendered | Implementation vocabulary leaks into product language | A10, A38 |
| R9 | Hostile or malformed manual evidence | Corruption or silent disappearance | A17 |
| R10 | Per-request replay cost with three assessors | Latency | Benchmark step; recorded envelope, not pre-optimisation |
| R11 | Providers declare `not_applicable` to avoid work | Instruments silently disappear | A21; default is `applicable` |
| R12 | Renderer infers applicability from value truthiness | Reintroduces the conflation being fixed; FI's degraded ETA silently becomes "not applicable" | A22, A26 |
| R13 | Amendment silently changes FI/Mortgage output | Regression in two shipped missions | A19, A20 pins captured first |
| R14 | Two outflow bases | Runway and reserve target mutually inconsistent on one page | A28 |
| R15 | `deployable_surplus` read as disposable income, **or softened because it is often zero** | A resilience stock spent as an allowance; or the frozen definition weakened | A29, A39 |
| R16 | Near-term commitments silently defaulted to zero | Surplus inflated by unrecorded obligations | A30 |
| R17 | Completion treated as terminal | A steady-state mission that cannot re-open; or an achievement event appended | A32, A14 |

## Technical Debt

Recorded by RFC-008, deliberately not fixed: protection and insurance model;
income-verification contract; **richer commitment entities — `RecurringSeries`
cadence and next-due semantics, `Obligation` due dates**; runway denominator
redesign; per-instrument applicability reason strings; generic non-schedule
recommendation-impact abstraction; `DeltaV.direction` extension; historical
resilience reconstruction; dead drill-down routes for synthesised telemetry ids
(inherited from RFC-007); per-request replay cost; legacy scalar adapter
removal; multi-user and object-level authorisation.

**RFC-006 debt-register amendment required:** widen the "generic trajectory
value formatting" entry in [`rfc-006-technical-debt.md`](rfc-006-technical-debt.md)
to record that the renderer assumed trajectory-mission *shape*, and that the
applicability amendment closed it.

## Codex Implementation Sequence

**Pre-flight:** confirm a clean `main` matching `origin/main`, record the green
baseline, branch `rfc-008-financial-resilience-mission`, and read this document
together with the RFC-006 and RFC-007 architecture documents and debt
registers.

**Mandated opening — in this exact order:**

1. **Capture current FI and Mortgage golden outputs** — detail-route HTML,
   homepage lane HTML, assessment field values. A2/A3/A19/A20/A31 must be able
   to fail before anything changes.
2. **Add the domain-neutral applicability vocabulary and structure** —
   `INSTRUMENT_APPLICABILITY`, `InstrumentApplicability`,
   `MissionAssessment.applicability` defaulting to all-applicable.
3. **Add contract validation** — three consistency rules plus the
   `unavailable`-explanation rule (A21, A33).
4. **Prove renderer shape-neutrality with mock providers** — fixtures declaring
   each state, asserting A22, A24, A25, A26, A33, A35, A36. **No Finance code
   involved.**
5. **Verify zero FI/Mortgage output drift** — A19, A20 (pre-D7), A27, A31 pass
   with an empty diff. **Gate: do not proceed otherwise.**
6. **Only then implement Financial Resilience.**

**Thereafter:**

7. `finance/resilience_evidence.py` — validated envelope, tolerant projection,
   deterministic ordering, hostile-input handling (A17).
8. `FinanceResilienceMetricProvider` — M1–M4 with the frozen definitions;
   registered at the composition root. Tests: A28, A29, A39, A30, A15,
   fail-closed, scope routing, duplicate-registration rejection, runway-identity
   guard.
9. `FinancialResilienceAssessor` — policy, deterministic stress engine, D2.2
   applicability, milestones and reversible completion, margin, confidence.
   Tests: A5–A8, A12, A32, A34, A40.
10. **Demonstration evidence and assumptions** — resilience Assumption Set and
    evidence for the synthetic household, carrying the existing
    synthetic-marker discipline.
11. **Months-unit formatting** — milestone and current-value rendering via
    format metadata, no mission-name branching (A9).
12. **Recommendation behaviour** — action, amount, cadence, rationale, evidence
    and threshold rendered; Estimated Delta-v omitted (A37, A16).
13. **Narrow Mortgage precedence-copy correction (D7)** — implemented last among
    behavioural changes, with its own pinned expected string; A20's remaining
    bytes identical; A38 asserts no assumption key leaks.
14. **Three-live-mission performance benchmark** — measure and record
    per-request assessment and render cost with FI, Mortgage and Resilience all
    registered. Record the envelope in the implementation report; do not
    optimise pre-emptively.
15. **Full regression suite** — every pin re-asserted; any drift stops the Burn.
16. **Architecture Gate.**
17. **Security Gate** — with the completed checklist drawn from
    [Security Considerations](#security-considerations).
18. **Documentation and debt updates** — implementation report with adversarial-
    review disposition table, `docs/rfc-008-technical-debt.md`, the RFC-006
    debt-register amendment, CHANGELOG entry, version bump,
    [`rfcs/index.md`](rfcs/index.md) row, and the two constitutional
    observations added to [`architecture.md`](architecture.md) commentary.

**Explicit non-goals:** no insurance or protection entity or scoring; no
Mortgage migration to `deployable_surplus`; no redefinition of
`finance.liquidity_runway`; **no `RecurringSeries`, `Obligation`, event-schema
or projection change**; no cadence or due-date inference; no affordability
assessment; no static mission archetypes; no `MissionDefinition` change; no
`DeltaV.direction` extension; no per-instrument reason strings; no Pension or
Children work; no historical resilience trajectory; no caching or persisted
snapshots; no authorisation changes; no changes to `eventlog.py`, `canon.py` or
`kernel.py`.

### Architecture Gate pre-mortem

1. **Landing the amendment and the mission together**, hiding FI/Mortgage
   regressions in a large diff. Prevented by the six-step opening with an
   empty-diff gate at step 5 and pins captured at step 1.
2. **Inferring applicability in the renderer** — `if not assessment.eta: omit`.
   Reintroduces the exact conflation being fixed: FI's genuinely-degraded ETA
   would silently render as "not applicable" and stop reporting degradation.
   Prevented by A22 and A26.
3. **Deriving near-term commitments from `RecurringSeries`** by assuming a
   cadence the entity does not carry, or defaulting the term to zero silently.
   Prevented by A30 and the D1 ruling.
4. **Treating unknown protection as favourable, or as evidence of absence** —
   the two opposite dishonesty modes. Prevented by A8 and A34.
5. **Softening `deployable_surplus` because it returns zero before the
   destination**, or treating completion as terminal. Prevented by A39, A32 and
   A14.

## Governor Decisions

All decisions below are ruled and closed. No decision in this document is open.

| Ruling | Decision |
|---|---|
| **G1** | Four Finance-owned metric IDs approved; exact definitions frozen in [Metric Definitions](#metric-definitions). `finance.deployable_surplus` is defined unambiguously as a resilience quantity, not ordinary monthly disposable income. |
| **G2** | Mortgage Freedom retains its own liquidity-floor policy and does not migrate to `finance.deployable_surplus`. Constraints travel through metrics plus consumer-local policy thresholds. No assessor-to-assessor dependency. |
| **G3** | Single mission model approved. Financial Resilience V1: ETA `not_applicable`, delta-v `not_applicable`, forecast `not_applicable`, trajectory `unavailable`. No archetypes in Core, `MissionDefinition`, `Mission`, routing, provider registration or policy identity. The orbital-station analogy is a design-language aid only. |
| **G4** | Dedicated frozen applicability structure with four named fields approved, with the stated consistency validation and the rule that `unavailable` may never be a silent empty state. |
| **G5** | Any extension of `DeltaV.direction` is deferred. No Core vocabulary expansion is justified. |
| **G6** | Financial Resilience V1 maximum confidence is `Supported`; `Established` is unreachable while protection and insurance evidence are unmodelled. A V1 policy limitation, not a permanent framework rule. |
| **G7** | Reserve bands corrected. 6 months is minimum operational resilience; **18 months is the mission destination**; completion occurs at 18 months. Completion is reversible. |
| **G8** | Assessment-level delta-v applicability governs recommendation ETA-change rendering. Estimated Delta-v is omitted for Financial Resilience; action, amount, cadence, rationale, evidence, threshold and reserve-gap effect still render. |
| **G9** | Not-applicable instruments are omitted entirely from the detail layout — no em dashes, no unavailable language. The renderer branches on declared applicability, never on value truthiness or tuple emptiness. |
| **G10** | Narrow Mortgage Freedom rendered-copy correction approved within RFC-008, separately pinned. It exposes observed runway, declared floor and rationale, and no raw identifiers or assumption keys. |
| **U1** | Band names: Exposed, Fragile, Buffered, **Secure** (6 to below 18 months), **Fortified** (18 months or more, completes the mission). |
| **U2** | `finance.deployable_surplus` frozen as *liquid assets remaining above the full 18-month Financial Resilience reserve target after recognised near-term commitments*. Deliberately conservative and append-only; not to be weakened merely because it will often be zero before the destination is reached. |
| **U3** | The reserve target uses the same single published essential-outflow basis that underpins `finance.liquidity_runway`. No second denominator. `RecurringSeries` is cross-check evidence only. |

**Repository constraint accepted by ruling:** `RecurringSeries` lacks cadence and
next-due-date fields and `Obligation` lacks a due date, so recognised near-term
commitments are supplied through the RFC-008 resilience evidence envelope. No
cadence or due date is inferred, and no entity, event schema or projection is
modified.

## References

- [`architecture.md`](architecture.md) — constitutional invariants
- [`design/design-constitution.md`](design/design-constitution.md) — Information
  Honesty and Mission Telemetry rules
- [`specifications/000-core-domain-model.md`](specifications/000-core-domain-model.md)
  — Mission, Metric Provider contract, Flight Deck contract
- [`specifications/001-finance-domain-model.md`](specifications/001-finance-domain-model.md)
  — Finance entities and vocabularies
- [`rfc-005-financial-independence-architecture.md`](rfc-005-financial-independence-architecture.md)
  — original Mission Assessment seam
- [`rfc-006-mission-assessment-framework.md`](rfc-006-mission-assessment-framework.md)
  — the framework this RFC amends
- [`rfc-006-technical-debt.md`](rfc-006-technical-debt.md) — includes the entry
  RFC-008 must widen
- [`rfc-007-mortgage-freedom-architecture.md`](rfc-007-mortgage-freedom-architecture.md)
  — evidence-envelope and precedence patterns reused here
- [`rfc-007-technical-debt.md`](rfc-007-technical-debt.md) — manual evidence
  adapter removal criteria
- [`security/threat-model.md`](security/threat-model.md) — T6, T8, T10
- [`security/security-checklist.md`](security/security-checklist.md) — Security
  Gate input
- [`engineering/review-gates.md`](engineering/review-gates.md) — gate process
  this RFC must pass before merge
- [`rfcs/index.md`](rfcs/index.md) — RFC index
