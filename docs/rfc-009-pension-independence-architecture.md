# RFC-009 — Pension Independence Mission

Status: **Approved at Revision 3 by the project maintainer on 2026-07-30.**
All rulings are closed and recorded in
[Governor Approval](#governor-approval). This document is the implementation
specification for the Codex engineering Burn, subject to the Architecture Gate
and Security Gate. **The architecture is frozen: no further architectural
change may be made without a new RFC amendment.**

Date: 2026-07-30

Authors: Architecture lead role (Claude, Fable 5), commissioned by the project
maintainer's Pension Independence architecture brief; revised under the
Governor Change Request and finalised under the Governor Finalisation brief,
all dated 2026-07-30.

Revision history:

| Rev | Change |
|---|---|
| 1 | Initial architecture. Mission value: derived secured retirement income. |
| 2 | Governor Change Request: reality → forecast → consequence → judgement hierarchy; observed pension value as mission value; telemetry display regions; contribution telemetry; visible State Pension composition. |
| 3 | Governor Finalisation: completion semantics resolved (Option A) with the three-concept separation made explicit; trajectory-state rendering defect identified and corrected (D13); framework amendment re-reviewed and hardened; full consistency review with every implementation ambiguity closed. Approved at this revision. |

## Governor Approval

Approved at Revision 3 on 2026-07-30 by the project maintainer. All open
questions are ruled and closed; no decision in this document remains open.
Every ruling was approved as recommended. Rulings are identified by their
question number rather than a separate G/U series, so that each one resolves
directly to the analysis that produced it.

| Ruling | Decision |
|---|---|
| **Q1** | Milestone bands 0.25 / 0.50 / 0.75 / 1.00 × W* approved as declared, configurable policy values; labels Dependent / Foundation / Building / Approaching / Pension Independent, with `completes_mission` on Pension Independent only. |
| **Q3** | Planning point is the latest State Pension age declared among active household members, overridable by `planning_age`. Bridging income before that point is unmodelled and disclosed as a standing limitation. |
| **Q4** | Margin factors F1 (projected surplus), F2 (sensitivity robustness) and F3 (State Pension reliance) approved under worst-factor-wins. Weight coefficients are forbidden in the policy dataclass. |
| **Q5** | Defined benefit schemes are pension Accounts carrying `db_*` envelope evidence. No new entity type. A DB/DC conflict on one account excludes it from both P1 and P4 with a limitation and a `Provisional` confidence cap. |
| **Q6** | V1 recommendations are limited to contribution increases from declared structured Scenarios. Fee switching and retirement-age changes are deferred behind the regulated-advice boundary. |
| **Q7** | `currency_per_period` is deferred. Per-year semantics are carried in labels and qualifiers, guarded by A20. |
| **Q8** | `required_retirement_income_annual` is an Assumption Set key, not evidence. A declared goal never carries an evidential confidence. |
| **Q9** | Dated `contribution_payment_employee` and `contribution_payment_employer` fields approved as the sole basis for tax-year contribution telemetry. Payment fields accumulate; rate fields supersede. No figure is ever pro-rated from a rate. |
| **Q10** | The trajectory-state rendering correction (D13) is approved **as a renderer defect fix, not a policy change**. Governor's reasoning, recorded: *`trajectory_state` represents the Governor's computed judgement; `applicability.trajectory` represents the availability of historical trajectory evidence. Those are different concepts and should not suppress one another.* The resulting change to Financial Resilience's rendered detail hero is approved and separately pinned. The RFC-008 debt register is amended accordingly. |
| **Q11** | **Mission completion is Option A: `finance.pension_wealth ≥ W*` — fully funded today.** Current Funding Position, Expected Mission Outcome and Mission Completion remain three separate, separately rendered concepts. Governor's reasoning, recorded: *mission completion must remain evidence-based. Forecast assumptions must influence trajectory, ETA and Mission Margin; they must not influence Mission Completion. Keeping completion dependent only on observed evidence preserves a single consistent meaning of `mission_complete` across the Mission Engine.* |

**Retired:** Q2 (secured-income compounding basis), dissolved by the
Revision 2 mission-value change. The numbering gap is deliberate and preserved
so that prior review correspondence remains resolvable.

**Governor refinement applied at approval:** the completion/trajectory
distinction is stated explicitly as a general Mission Engine rule — see
[Mission Engine principle](#mission-engine-principle--completion-and-trajectory-answer-different-questions).

## Context

Pension Independence is the third mission in the fixed Finance hierarchy
(`pension-independence`, canonical order 3) and the last of the four to gain an
assessment provider. It is currently registered as an honest metadata-only
`MissionDefinition` with no `assessment_policy_id`
([`finance/missions.py`](../src/foundry/finance/missions.py)); RFC-009 fills
exactly that slot — the same slot-filling move RFC-008 made for Financial
Resilience.

Four RFCs precede it. RFC-005 introduced the domain-neutral Mission Assessment
seam and wired Financial Independence to it. RFC-006 generalised that seam into
the Mission Assessment Framework: definition discovery, direction-aware
milestones, closed trajectory/margin/confidence vocabularies, isolated provider
dispatch with hard envelope validation, and the generic authenticated
`/missions/{slug}` route. RFC-007 proved the framework with Mortgage Freedom
and established the manual evidence-envelope pattern. RFC-008 added Financial
Resilience, the per-instrument applicability amendment, and the
cross-mission-constraint discipline (metrics plus consumer-local thresholds,
never assessor-to-assessor calls).

RFC-008 explicitly anticipated this mission when it rejected mission
archetypes: *"Pension Independence is a trajectory mission before
pension-access age and a state mission afterwards."*

The Finance specification already reserves the domain model this RFC needs.
Spec 001 §18: *"An `Account` with `account_type: pension`, `tax_wrapper:
pension_wrapper`, employee and employer contributions as two separate
Recurring Series, an access age, and retirement assumptions as an Assumption
Set. Projected value is a Financial Projection output, never stored, and must
always expose the Assumption Set it used."* Acceptance criterion 19 of that
specification — **exposed assumptions** — is a standing constraint on every
number this mission renders.

## Problem Statement

The mission question is:

> Will the household be financially independent from pension age onwards?

Pension Independence is **not a pension balance tracker** and **not a
retirement calculator**. It is a Governor assessment of long-term retirement
capability. Three problems stand between the question and an honest answer.

### The answer is a composition, and the composition must be shown in the user's order

A pension pot value answers nothing by itself. The question resolves only by
composing DC pension wealth, contribution flow, accrued defined-benefit
entitlements, the State Pension, declared retirement need, and declared
economic assumptions. Revision 1 collapsed that composition into a single
derived mission value and led with it. The Governor's review identified the
defect: technically correct, but backwards against the user's mental model,
which runs:

1. *How much do I currently have?*
2. *What is it likely to become?*
3. *What income will that produce?*
4. *Am I on track?*

That ordering is not a presentation preference; it is a restatement of a core
Foundry principle: **the Governor interprets reality — it does not replace
it.** The pension pot is the reality. The projection is the forecast. The
retirement income is the consequence. The Mission Margin is the Governor's
judgement. The architecture carries that layering explicitly, so the page
tells the story in that order without the UI inventing any of it (see
[Information Hierarchy](#information-hierarchy)).

### Most of the truth is in the future, and the future must not be faked

Pension Independence's destination sits decades away, behind market returns,
contribution continuity, legislation and longevity — none of which Foundry can
observe. The Design Constitution's Information Honesty rule therefore does the
heaviest lifting in this RFC:

- No probability is ever computed or rendered. The forecast is a deterministic
  **Conservative / Expected / Optimistic** sensitivity envelope under declared
  assumptions — the Governor's confirmed language for the platform's existing
  low/base/high mechanics. The Expected path is the stated default view. A
  "success probability" telemetry item was considered and **rejected**, a
  removal the Governor has endorsed (see
  [Rejected telemetry](#rejected-telemetry)).
- Every projected figure is labelled as projected and traceable to the
  Assumption Set that produced it (Spec 001 §18/AC-19).
- Uncertainty the model does not carry (tax, longevity, pension policy,
  State Pension legislation) caps Mission Confidence and is named in
  limitations rather than silently absorbed.

### The mission changes shape at pension age

Before pension access the mission is a journey: capability accumulates toward
a destination. After access it becomes a sustained condition: income must keep
covering need. V1 implements the **accumulation epoch only** and declares this
boundary openly. The decumulation epoch is named successor work, and the
per-instrument applicability contract means the same mission can later change
which instruments it declares without any framework change. No archetype is
introduced; RFC-008's single-mission-model ruling stands.

## Information Hierarchy

This section is normative. The Mission Detail experience presents four layers,
in this order, and every telemetry item in this RFC is assigned to exactly one
layer. The layers are the RFC's honesty classification made visible: layer 1
is observed fact, layer 2 is projection, layer 3 is projected consequence,
layer 4 is Governor judgement.

| Layer | Question answered | Content | Epistemic class |
|---|---|---|---|
| **1 — Current Position** | *Where am I today?* | Current Pension Value; This Tax Year's Contributions; Employer Contributions; Personal Contributions | Observed evidence |
| **2 — Future Projection** | *What is it likely to become?* | Projected Pension Value at Retirement — Conservative, **Expected (default)**, Optimistic | Deterministic projection under declared assumptions |
| **3 — Retirement Income** | *What income will that produce?* | Sustainable Pension Income; State Pension (always a visible separate component, never hidden inside a calculation); Defined Benefit income where present; Combined Retirement Income | Projected consequence |
| **4 — Mission Assessment** | *Am I on track?* | Mission Status; Mission Margin; Mission Confidence; Δv; Recommendations | Governor judgement, interpreting layers 1–3 |

Three rules make the hierarchy architectural rather than cosmetic:

1. **Judgement never displaces reality.** Mission Margin remains the
   Governor's interpretation; Current Pension Value and Projected Pension
   Value remain first-class telemetry that the margin interprets but never
   replaces.
2. **Each layer cites the one below it.** Layer 4 values carry references to
   the layer 2/3 projections they judge; layers 2–3 carry the assumption
   references that produced them; layer 1 carries event provenance only.
3. **No layer may be silently empty.** A layer whose evidence is unavailable
   renders an honest absence with its reason; it is never omitted in a way
   that makes the story appear complete.

## Mission Completion Semantics

### Mission Engine principle — completion and trajectory answer different questions

**This is a general Mission Engine rule, not a Pension Independence rule. It
governs every mission in every domain.**

> **Mission Completion answers: *"Have we achieved the destination today?"***
> It is a predicate over observed evidence at `as_of`.
>
> **Trajectory answers: *"Are we expected to achieve the destination by the
> planning point?"*** It is a judgement over declared assumptions and the
> deterministic forecast they produce.

Neither may substitute for the other, and neither may suppress the other.
Forecast assumptions must influence **trajectory, ETA and Mission Margin**;
they must **never** influence `mission_complete`. A mission may therefore be
simultaneously incomplete and on course, and that combination is a truthful
reading of two different questions rather than a contradiction to be resolved.

Two consequences follow, and both are already load-bearing in shipped code:

1. **`mission_complete` keeps one meaning across the Mission Engine.** A
   consumer can interpret the field without knowing which mission produced it,
   because every mission's completion is a predicate over observed evidence —
   Financial Independence at an observed threshold, Mortgage Freedom at an
   observed zero balance, Financial Resilience at observed runway, and Pension
   Independence at an observed pot.
2. **A mission whose observed history is unavailable may still hold a fully
   valid trajectory judgement.** Availability of historical evidence and
   availability of the judgement are independent; conflating them suppresses a
   conclusion the Governor has actually reached. That is the separation D13
   restores in the renderer.

This principle is promoted into [`architecture.md`](architecture.md)'s
architecture observations during the implementation Burn's documentation step,
alongside the two observations RFC-008 added there, because it constrains
every future mission rather than this one.

### The Pension Independence decision

The Governor Finalisation brief asks whether *current funding position*,
*expected mission outcome* and *mission completion* should remain separate,
and which definition completion should take.

### Recommendation: Option A — completion is fully funded today, and the three concepts must remain separate

**`mission_complete` is true when, and only when, the observed pension pot
reaches the required retirement wealth: `P1 ≥ W*`.** The three concepts are
distinct, all three are first-class, and each has a defined home:

| Concept | Definition | Epistemic class | Where it renders |
|---|---|---|---|
| **Current Funding Position** | `P1 ÷ W*` (Funding Ratio) plus the current milestone band | Observed ÷ derived-from-declared | Hero milestone; analysis group *Current Funding Position* |
| **Expected Mission Outcome** | Which of the Conservative / Expected / Optimistic paths reach W* by the planning point, and when — carried by `trajectory_state` and ETA | Projection-derived judgement | Hero TRAJECTORY tile (see D13) and ETA tile; margin factor F2 |
| **Mission Completion** | `P1 ≥ W*` — binary, derived, reversible | Observed | `mission_complete`; Pension Independent milestone |

Under this split, the Governor's worked example resolves cleanly and without
contradiction:

> Pot £62,000 · Required wealth W* £735,000 · Expected terminal pot £785,000
>
> - **Current Funding Position:** 8.4% funded; current milestone **Dependent**
>   (band 0 → £183,750), 33.7% through that band.
> - **Expected Mission Outcome:** trajectory **Nominal** — the Expected path
>   reaches W* by State Pension age. ETA is the projected fully-funded month.
> - **Mission Completion:** **incomplete** — the household does not yet hold
>   the wealth.
> - **Mission Margin:** **Adequate Margin**, +£2,000/year projected surplus.
>
> The page therefore says, truthfully and simultaneously: *you have 8.4% of
> what you need, you are on track to get there, and you are not there yet.*

Nothing is hidden by this arrangement; the apparent tension the Governor
identified was never a conflict between definitions, but a **rendering
defect** that suppressed the on-track signal. That defect is real, is present
in shipped code, and is fixed by D13.

### Justification

**Consistency with the existing Mission Engine.** All three shipped providers
define completion as an observed-state predicate, with no forecast term:

- Financial Independence — entering the `Independent` band on observed
  `finance.accessible_assets` completes the mission (RFC-005).
- Mortgage Freedom — *"only an observed zero balance marks the mission
  complete"* (RFC-007).
- Financial Resilience — `mission_complete` is computed as
  `runway_months ≥ 18` on the current read model (RFC-008).

Option B would make Pension Independence the only mission in the platform
whose completion is forecast-derived. That is not a local inconsistency; it
would mean `MissionAssessment.mission_complete` no longer has one meaning
across the Flight Deck, and no consumer could interpret the field without
knowing which mission produced it.

**Consistency with Financial Independence.** FI has exactly the same latent
structure, and RFC-008 said so when rejecting archetypes: a household with
£400,000 of accessible assets and a healthy projection is *not* Financially
Independent; it completes at the observed threshold. Adopting Option B for
Pension Independence would either leave two sibling missions with
contradictory completion semantics, or imply an unrequested breaking change to
a shipped mission. Both are worse than the status quo.

**User mental model.** This is the only axis on which Option B has surface
appeal, and it does not survive inspection. *"Am I on track?"* and *"Have I
achieved it?"* are different questions that users ask in sequence, and the
hierarchy answers both in the order they are asked. Telling a household with
£62,000 that it has **achieved Pension Independence** would not match any
user's mental model — it would read as a system error and destroy trust in
every other number on the page.

**Architectural integrity.** `mission_complete` is derived and explicitly
non-monotonic (architecture.md, Observation 2). A completion predicate over an
observed balance moves only when evidence moves. A completion predicate over a
forecast moves whenever any assumption moves — and would flip on ordinary
market noise between two annual statements.

**Avoidance of hidden assumptions.** This is decisive. Under Option B, a
household could **complete Pension Independence by editing an assumption** —
raising `base_real_return` from 3% to 5% would convert an incomplete mission
into a completed one with no change in evidence whatsoever. Completion would
become a function of optimism rather than of fact. Option A's completion
predicate contains no growth assumption at all: `P1` is a pure observation,
and `W*` moves only when the household's own declarations move. Every
remaining assumption sits in layers 2–3, where it is labelled, and in the
margin, where it is attributed to the Governor.

### Why the rejected options are inferior

**Option B — completion means the expected destination is achieved. Rejected.**
It breaks the Mission Engine's single meaning of `mission_complete`; it
contradicts FI, Mortgage Freedom and Financial Resilience; it makes completion
assumption-editable (the hidden-assumption failure above); it makes completion
flip on market noise, producing an unstable and untrustworthy binary; and it
violates Information Honesty by asserting an achievement the household has not
made. Its only genuine benefit — visibility of the on-track signal — is fully
delivered by D13 at a fraction of the cost.

**Option C — a different definition. Considered and rejected in three
variants.**

- *Dual completion flags* (e.g. `funded_complete` plus `on_track_complete`):
  requires a Core contract change to express a distinction the framework
  already carries in `trajectory_state`, and gives every renderer two booleans
  to reconcile. Rejected as framework growth for a solved problem.
- *Completion at a policy fraction of W\** (e.g. 90% funded, on the reasoning
  that residual growth closes the gap): smuggles a growth assumption into a
  supposedly observed predicate, and makes the completion threshold a second,
  invisible policy value competing with the milestone bands. Rejected as a
  hidden assumption wearing an observation's clothes.
- *Completion when the Conservative path reaches W\** (the most defensible
  forecast variant, since the Conservative path is the prudent one): still
  assumption-dependent, still editable, still forecast-derived, and still
  inconsistent with three shipped missions. It is Option B with better
  manners. Rejected for the same reasons.

**Governor ruling requested: Q11.**

## Relationship to Other Missions

The four Finance missions answer four disjoint questions:

| Mission | Question | Value basis | Time frame |
|---|---|---|---|
| Financial Resilience | Can the household absorb a shock? | Liquid reserves vs essential outflow | Now, steady-state |
| Financial Independence | Is work optional **before** pension access? | `finance.accessible_assets` — **excludes pensions** by tested structural policy | Pre-access years |
| **Pension Independence** | Is the household independent **from pension age onwards**? | Pension wealth, DB entitlements, State Pension vs required retirement income | Post-pension-age |
| Mortgage Freedom | Is the primary residence owned outright? | `finance.mortgage_balance` | Journey to zero |

Non-duplication is structural, and each rule is testable:

1. **Asset-basis disjointness.** `finance.accessible_assets` excludes pension
   accounts (RFC-005, tested); `finance.pension_wealth` (P1) includes *only*
   pension accounts. No account can contribute to both. Net Worth continues to
   include both bases and is unchanged — P1 is a subset view of evidence Net
   Worth already folds, not a new valuation basis.
2. **Need-declaration independence.** FI's `desired_annual_spending`
   (pre-access lifestyle) and PI's `required_retirement_income_annual`
   (post-access lifestyle) are separate declared assumptions. Neither is
   derived from the other; both are visible.
3. **Telemetry namespace disjointness.** Every RFC-009 metric id is new; no
   existing metric is redefined, forked or re-based.
4. **Completion-semantics consistency.** All four missions define completion
   as an observed-state predicate (see
   [Mission Completion Semantics](#mission-completion-semantics)).
5. **Constraint transport.** Pension recommendations respect Financial
   Resilience through the established pattern only: dispatching
   `finance.liquidity_runway` as an ordinary metric and comparing it against a
   floor declared in **Pension Independence's own Assumption Set**. No
   assessor calls another assessor.

## Architectural Decisions

### Composition — extends, never forks, the Mission Engine

```text
web.py (composition root — structure unchanged)
  ├─ MetricRegistry
  │     ├─ FinanceMetricProvider              (8 existing metrics — untouched)
  │     ├─ FinanceResilienceMetricProvider    (M1–M4 resilience — untouched)
  │     └─ FinancePensionMetricProvider [NEW] (P1–P7)
  └─ MissionAssessmentRegistry
        ├─ register_finance_mission_definitions  (pension-independence gains
        │                                         policy id + definition text)
        ├─ FinancialIndependenceAssessor         (untouched)
        ├─ MortgageFreedomAssessor               (untouched)
        ├─ FinancialResilienceAssessor           (untouched logic; D13 renders
        │                                         its existing trajectory state)
        └─ PensionIndependenceAssessor     [NEW] (declares V1 applicability)
              ↑ reads: MetricRegistry, FinanceEntityProjection,
                       EntityProjection, PensionEvidenceProjection
              ✗ never: MissionAssessmentRegistry, another assessor,
                       a model, an event append
```

New Finance modules: `finance/pension_evidence.py`,
`finance/pension_metrics.py`, `finance/pension_assessment.py`. The
`finance/missions.py` order-3 entry gains a policy id and definition text.
Policy id `finance.pension_independence.v1`; assessment calculation version
`pension-v1`; metric calculation version `pension-metrics-v1`.

**Two changes outside Finance, both narrow and both separately gated:**

1. **One additive contract amendment** — telemetry display regions (D12),
   specified in [Telemetry Region Contract](#telemetry-region-contract).
2. **One renderer correction** — the trajectory-state tile (D13), which
   changes one shipped mission's rendered output and therefore carries its own
   Governor ruling and its own pinned expected string, exactly as RFC-008's D7
   Mortgage copy amendment did.

No other Core, routing, vocabulary or substrate change is made. `eventlog.py`,
`canon.py` and `kernel.py` are untouched.

**Layer discipline.** The existing separation is preserved exactly:

```text
Mission Definition  (finance/missions.py — discovery metadata)
        ↓
Mission Engine      (finance/pension_assessment.py — policy + calculation)
        ↓
Telemetry Projection (MissionAssessment — frozen, validated envelope)
        ↓
Mission UI          (mission_control.py — shared renderer)
```

No business logic exists in the UI layer; the shared renderer continues to
contain no Finance mission name, slug, or policy-id branching. The renderer
branches only on contract fields.

### Decision Record

**D1 — Mission value is the observed current pension value.** `current_value`
is P1 `finance.pension_wealth`: the dated, share-weighted total of the
household's DC pension pot valuations, in GBP. The pot is the reality the
whole page interprets, and the mission value is a pure observation — no
assumption enters it.

*Superseded (Revision 2):* Revision 1's "secured retirement income", which
baked compounding, withdrawal-rate and planning-point assumptions into the
headline number. Its concept survives as recorded future drill-down work.

**D2 — The destination is the required retirement wealth W\*, in real terms.**

```text
W* = max(0, (required_retirement_income_annual
             − state_pension_income_annual
             − defined_benefit_income_annual)
            ÷ sustainable_withdrawal_rate)
```

Because every quantity in this RFC is expressed in today's-money real terms
and growth assumptions are declared as *real* returns, W* is stable across
assessments (it moves only when the household's declarations move), the
current pot and W* are directly comparable, and the forecast paths approach W*
on one axis. Completion at `P1 ≥ W*` has a plain-language meaning: *the pot
already holds the full real wealth requirement — sufficient even with zero
further real growth.* State Pension and DB entitlements are subtracted in the
W* derivation **and** always shown as separate visible components in layer 3 —
the derivation is inspectable, never hidden.

**D3 — V1 epoch boundary: accumulation only.** The assessment models capability
up to the planning point. Decumulation (post-access drawdown sustainability,
sequencing risk, annuitisation) is successor work. Consistent with RFC-008's
no-archetype ruling, nothing in code marks the mission "trajectory-shaped".

**D4 — Planning point.** V1 planning point = the **latest State Pension age
declared among active household members** (the date from which every modelled
income component is active), overridable by an explicit `planning_age`
assumption. Income arising between earlier access ages and the planning point
is deliberately not modelled and is disclosed as a limitation (the bridging
problem). **Open question Q3.**

**D5 — Defined benefit schemes are pension Accounts carrying entitlement
evidence, not pot valuations.** A DB scheme is represented as an `Account`
(`account_type: pension`) whose provision is declared through `db_*` evidence
fields rather than `Valuation` events. An account presenting **both** pot
valuations and DB entitlement declarations at assessment time is
contradictory: that account's provision is excluded from both P1 and P4 with a
mandatory limitation and a confidence cap at `Provisional`. No new entity type
is created. **Open question Q5.**

**D6 — V1 applicability declarations:**

| Instrument | State | Justification |
|---|---|---|
| `eta` | `applicable`; `unavailable` when the Expected path never reaches W* within the horizon | An arrival exists: the date the pot is fully funded |
| `delta_v` | `applicable`; `unavailable` when no deterministic lookback assessment exists | Schedule movement is meaningful in the accumulation epoch |
| `forecast` | `applicable` | Deterministic Conservative/Expected/Optimistic pot-value paths to the planning point |
| `trajectory` | **`unavailable`** | The observed *history series* could exist, but pension valuations are sparse (typically annual statements) and the platform's undated-revision reconstruction debt makes an honest historical path unavailable today. Fixable — therefore not `not_applicable`, exactly the RFC-008 reasoning |

The `trajectory` instrument governs the **observed points series only**.
`trajectory_state` — the Nominal/Constrained/… judgement — is computed and
rendered regardless; D13 makes that separation true in the renderer as well as
in the contract.

**D7 — No probability, ever.** No Monte Carlo, no success percentage, no
confidence interval presented as probability, and no fraction or count of
paths that could be read as a frequency. Deterministic sensitivity envelope
only — labelled Conservative / Expected / Optimistic, with Expected stated as
the default view. Endorsed by the Governor Change Request. Blocking criterion
(A24).

**D8 — Contribution evidence comes through the pension evidence envelope;
`RecurringSeries` and transactions are cross-check evidence only.** The
RFC-008 repository finding stands: `RecurringSeries` carries no cadence or
next-due date, and no cadence is ever inferred. Declared annual contribution
figures arrive through the envelope with effective date, confidence, source
and lineage. Material divergence between declared contributions and observed
`pension_contribution` transaction flow beyond a declared tolerance raises a
limitation and downgrades confidence — it never silently replaces the declared
basis.

**D9 — Taxation is out of scope and visibly so.** All incomes are gross,
real-terms figures. The required income is declared gross. V1 performs no tax
calculation (Spec 001 explicitly defers full tax law) and renders a standing
limitation saying so. Tax-free lump sums, annual/lifetime allowance effects
and salary-sacrifice NI effects are recorded as technical debt, not silently
approximated.

**D10 — Longevity is carried by the withdrawal basis and named as such.** V1
expresses sustainability through the declared `sustainable_withdrawal_rate`;
no mortality table or explicit horizon-age model exists. The limitation names
longevity as unmodelled.

**D11 — Tax-year contributions are declared dated payments; annual rates are
the planning basis.** Two contribution quantities exist and are never
conflated:

- **P2 — declared annual contribution rates** (employee, employer, salary
  sacrifice): the planning inputs that drive the projection.
- **P7 — tax-year contributions to date**: the sum of **dated contribution
  payments** declared through the envelope whose effective dates fall inside
  the current tax year, resolved from the household's declared Tax
  Jurisdiction Configuration (Spec 001 §19).

Observed `pension_contribution` transactions are cross-check evidence only,
because employer and salary-sacrifice payments never appear in the
household's transaction feed. **No payment is ever pro-rated or inferred from
an annual rate.** Absent payment declarations make P7 `unavailable` with a
limitation; nothing is estimated. This is the evidence substrate future
annual-allowance monitoring will consume. **Open question Q9.**

**D12 — Telemetry display regions are the one contract amendment.** Specified
in [Telemetry Region Contract](#telemetry-region-contract). Rejected
alternatives, recorded so they are not revisited: renderer branching on
mission identity (forbidden by RFC-006/008 discipline and tests); overloading
`qualifier` strings as placement semantics (stringly-typed, invisible to
validation); positional convention such as "the first N items are hero"
(implicit and untestable); a pension-specific page (forbidden by the Design
Constitution and every engineering brief).

**D13 (new in Revision 3) — Correct the trajectory-state tile so a computed
judgement is never suppressed by an unavailable history.** A verified defect
exists in shipped code:

- [`mission_control.py:1265`](../src/foundry/mission_control.py) — the
  **homepage lane** renders `assessment.trajectory_state` with no
  applicability check.
- [`mission_control.py:2226`](../src/foundry/mission_control.py) — the
  **detail-page hero tile** renders `NOT AVAILABLE` / *"Trajectory history is
  not available for this mission"* whenever
  `applicability.trajectory == "unavailable"`, discarding the
  `trajectory_label` computed one line group earlier at
  [`mission_control.py:2055`](../src/foundry/mission_control.py).

Financial Resilience declares `trajectory="unavailable"`
([`resilience_assessment.py:44`](../src/foundry/finance/resilience_assessment.py))
**and** computes a full `trajectory_state`
([`resilience_assessment.py:445,540`](../src/foundry/finance/resilience_assessment.py)).
The same assessment therefore reports **NOMINAL on the homepage and NOT
AVAILABLE on its own detail page** today. One field is being asked to govern
two different things: the availability of an observed *history series*, and
the availability of a computed *state judgement*.

Left unfixed, Pension Independence inherits this exactly: it would compute a
Nominal trajectory and render "TRAJECTORY · NOT AVAILABLE" in the hero,
deleting the Governor's *"Am I on track?"* answer and the Mission Status
element the Change Request requires in the hero.

**Correction, renderer-scope only, no contract change:** the hero tile renders
`trajectory_state` whenever the provider supplied one. `applicability
.trajectory` continues to govern the observed-history SVG region and the
accessible-summary history clause, unchanged. When a state is present *and*
history is unavailable, the tile shows the state and retains the honest
sub-line explaining that history is unavailable. When no state was computed,
today's `NOT AVAILABLE` behaviour is unchanged.

Impact, exhaustively:

| Mission | Today | After D13 |
|---|---|---|
| Financial Independence | State word (trajectory applicable) | **Byte-identical** |
| Mortgage Freedom | State word (trajectory applicable) | **Byte-identical** |
| Financial Resilience | `NOT AVAILABLE` + history sub-line | **State word + history sub-line** — separately pinned |
| Pension Independence | — | State word + history sub-line |

This is a deliberate, approved behavioural-copy amendment to one shipped
mission, executed and pinned inside RFC-009 exactly as RFC-008's D7 amended
Mortgage Freedom's precedence copy. It is a strict Information Honesty
improvement: Financial Resilience currently says *"not available"* about a
judgement it has in fact made. **Governor ruling requested: Q10.**

**D14 (new in Revision 3) — Expected Mission Outcome introduces no new
telemetry.** The Governor asked for an *Expected Mission Outcome* concept
expressed through Conservative/Expected/Optimistic scenarios. The framework
already expresses precisely this: `trajectory_state`'s deterministic rules are
defined by *which paths reach W\* by the planning point*. Adding a numeric
"paths reaching destination: 2 of 3" telemetry item was considered and
**rejected** — a count over three declared scenarios is not a sample, and
rendering it as a fraction would invite exactly the probability reading D7
forbids. The path-coverage detail is instead visible as evidence: the
Conservative and Optimistic projected pension values sit beside W* in the
*Projection* and *Current Funding Position* analysis groups, and the margin
description states F2's coverage in words. No new machinery, no probability
bait.

## Mission Semantics

- **Mission:** Pension Independence (order 3, slug `pension-independence`).
- **Definition text (for `finance/missions.py`):** *"The household's pension
  provision can sustain its required retirement income from pension age
  onwards, without depending on continued work."*
- **Destination:** current pension value ≥ W*.
- **Completion:** `P1 ≥ W*` (entry to **Pension Independent**). Derived and
  **reversible** (Observation 2, architecture.md): a market fall, a revised
  valuation, or a raised required income moves the mission back out of
  completion at the next assessment. No event is appended; `Mission.status`
  remains `active`.
- **Failure conditions:** the mission has no terminal failure state. Failure
  is surfaced honestly as the combination of `Critical` trajectory state,
  `Negative Margin`, and the explicit shortfall telemetry — never a hidden
  flag.
- **Planning horizon:** assessment date to the planning point (D4). No
  projection beyond the planning point exists in V1.
- **`current_value`:** P1 `finance.pension_wealth`, unit GBP.
- **Evidence requirements:** see [Evidence model](#evidence-model).

### Milestones and completion

Milestone bounds are computed at assessment time from W* — the
evidence-derived-bounds pattern Mortgage Freedom uses with the original
advance. The band fractions are declared, configurable policy values.

| Order | Milestone | Lower (GBP) | Upper (GBP) | Capability meaning | `completes_mission` |
|---|---|---|---|---|---|
| 0 | **Dependent** | 0 | 0.25 × W* | Retirement would depend almost entirely on future work or the state | no |
| 1 | **Foundation** | 0.25 × W* | 0.50 × W* | A quarter of the requirement is banked | no |
| 2 | **Building** | 0.50 × W* | 0.75 × W* | Half the requirement is banked; the plan is load-bearing | no |
| 3 | **Approaching** | 0.75 × W* | 1.00 × W* | Independence is within reach of remaining contributions and growth | no |
| 4 | **Pension Independent** | 1.00 × W* | *(none)* | The requirement is fully banked at zero further real growth | **yes** |

Contract-field specifications, pinned to remove implementation ambiguity:

- `destination_direction = "higher_is_better"` on every milestone, matching the
  registered definition (registry validation rejects any disagreement).
- `unit_or_currency = "GBP"` — required, because
  [`mission_control.py:1795`](../src/foundry/mission_control.py) selects
  `months` formatting only when the unit is literally `"months"` and currency
  formatting otherwise.
- `destination_value = W*` on the completing milestone;
  `destination_value = lower_bound` on the others, following FI's convention
  ([`mission_assessment.py:443`](../src/foundry/finance/mission_assessment.py)).
- `completion` follows the shipped FI convention exactly
  ([`mission_assessment.py:410-435`](../src/foundry/finance/mission_assessment.py)):
  `1.0` for bands entirely at or below P1; `0.0` for bands entirely above;
  `(P1 − lower) ÷ (upper − lower)` within the current band; `1.0` for the
  open-ended top band once entered; clamped to `[0, 1]`.
- `is_complete` mirrors that convention; exactly one milestone carries
  `is_current`.
- `estimated_at` is the Expected-path date the forecast first reaches each
  band's lower bound, and `None` where it never does.

**Open question Q1** covers the band fractions and labels.

### Trajectory state

Deterministic rules over the sensitivity paths and the planning point
(tolerances are declared policy values):

- **Complete** — P1 ≥ W* at `as_of`.
- **Accelerated** — the Expected path reaches W* at least
  `accelerated_threshold_months` before the planning point.
- **Nominal** — the Expected path reaches W* by the planning point (not
  Accelerated).
- **Constrained** — the Expected path does not reach W* by the planning point,
  but the Optimistic path does.
- **Divergent** — no path reaches W* by the planning point, but the Expected
  path's terminal value is at least `divergent_floor_fraction × W*`
  (default 0.75).
- **Critical** — the Expected path's terminal value is below
  `divergent_floor_fraction × W*`.

The Conservative path reaching W* raises margin factor F2 but does not by
itself change the trajectory state; the state tracks the Expected path, which
is the declared default view. Presentation tone is returned explicitly by the
policy (green for Complete/Accelerated/Nominal, amber for
Constrained/Divergent, red for Critical); Mission Control never derives colour
from trajectory.

### ETA

ETA is the first month the **Expected** path reaches W* — the projected
fully-funded date. When no Expected-path crossing exists within the horizon,
the provider declares `eta` `unavailable` with the reason — never a fabricated
date, never `None` under an `applicable` declaration.

## Canonical Input Model

### Observed facts (events in the log — layer 1)

| Input | Source | Notes |
|---|---|---|
| Pension accounts | `Account` entities, `account_type: pension`, `tax_wrapper: pension_wrapper`, ownership links | Spec 001 §18; DC pots and DB schemes (D5) |
| DC pot values | Existing `Valuation` events (`subject_id` = account id) | Dated; staleness per declared threshold; converted via cited Exchange Rate events |
| Declared annual contribution rates | Envelope, account-scoped (employee / employer / salary sacrifice) | D8; planning basis |
| Dated contribution payments | Envelope, account-scoped, employee/employer | D11; tax-year telemetry basis |
| Scheme fees | Envelope `annual_fee_percent`, account-scoped | Absent → declared assumption default plus limitation |
| DB accrued entitlement | Envelope `db_annual_income_accrued`, `db_normal_pension_age`, account-scoped | Statement figures; real-constant in V1 |
| State Pension forecast | Envelope `state_pension_annual`, `state_pension_age`, `state_pension_basis`, party-scoped | `forecast_with_continuing_contributions` adds a limitation |
| Tax year boundaries | Declared Tax Jurisdiction Configuration (Spec 001 §19) via `tax_resident_in` | Required only for P7 |
| Household composition, reporting currency | Existing Core/Finance entities | Required |

### Assumptions (pension Assumption Set — validated on load, fail closed)

| Key | Meaning | Indicative default |
|---|---|---|
| `required_retirement_income_annual` | Declared gross real annual income required from the planning point | household-declared; no default |
| `planning_age` *(optional)* | Overrides the latest-State-Pension-age planning rule (D4) | — |
| `low_real_return` / `base_real_return` / `high_real_return` | Conservative / Expected / Optimistic net-of-inflation growth, validated ordered | 0.01 / 0.03 / 0.05 |
| `sustainable_withdrawal_rate` | Withdrawal basis converting pot wealth to sustainable income; validated in `(0, 1]` | 0.04 |
| `assumed_annual_fee_percent` | Fee drag where no fee evidence exists (with limitation) | 0.0075 |
| `contribution_stale_after_days` | Freshness bound on contribution declarations | 400 |
| `valuation_stale_after_days` | Freshness bound on pot valuations | 550 |
| `evidence_crosscheck_tolerance` | Declared-vs-observed contribution divergence tolerance | 0.20 |
| `accelerated_threshold_months` | Accelerated/Nominal boundary | 12 |
| `divergent_floor_fraction` | Divergent/Critical boundary | 0.75 |
| `milestone_fractions` | The four band boundaries as fractions of W* | 0.25 / 0.50 / 0.75 / 1.00 |
| `surplus_high_fraction` / `shortfall_low_fraction` | Margin factor F1 bands | 0.20 / 0.10 |
| `sp_reliance_limits` | Margin factor F3 band boundaries | 1/3, 1/2, 2/3 |
| `delta_v_lookback_days` | Δv comparison window | 90 |
| `recommendation_liquidity_floor_months` | Consumer-local Financial Resilience precedence floor | 6 |

Contribution continuity — declared rates assumed to continue at constant real
value until the planning point — is itself an assumption and is named in the
standing limitations.

### Projected values (layers 2–3, computed, never stored)

Conservative/Expected/Optimistic pot-value paths and terminal values at the
planning point; sustainable pension income; combined retirement income; ETA.
Every projected value carries `assumption_references` (Spec 001 AC-19).

### Derived judgement (layer 4, computed at `as_of`)

W*; funding ratio; projected annual surplus/shortfall; milestone; trajectory
state; margin band; confidence state.

## Calculation Flow

All arithmetic is deterministic, monthly-grid, real-terms, and reproducible
from `(event log, policy id, calculation version, assumption event ids)`.
**Conventions are pinned here so two implementations cannot differ:**

- **Grid:** calendar months from `as_of` to the planning point inclusive.
- **Compounding:** monthly rate `r_m = (1 + r_annual_net)^(1/12) − 1`, applied
  once per month to the opening balance.
- **Fee application:** per account, `r_annual_net = r_declared −
  fee_account`, where `fee_account` is the account's declared
  `annual_fee_percent` or `assumed_annual_fee_percent` where absent (with
  limitation). Fee is subtracted from the return before conversion to a
  monthly rate; it is never applied as a separate balance deduction, so it is
  applied exactly once.
- **Contribution timing:** end-of-month. Monthly contribution is the summed
  declared annual rates ÷ 12, added **after** that month's growth is applied.
- **Contribution real-constancy:** declared annual rates are held constant in
  real terms for the whole horizon. No escalation, indexation or career
  progression is modelled; this is a named standing limitation.
- **Account aggregation:** projected per account (because fees differ per
  account), then summed. Contributions are applied to the account they are
  declared against.
- **Rounding:** no intermediate rounding; presentation rounding only.

Steps:

1. **Resolve scope and planning point** (D4). Validate the Assumption Set;
   fail closed on any missing or invalid required key.
2. **Fold evidence**: pot valuations, envelope declarations, tax-jurisdiction
   configuration, cross-check sources. Classify each per the evidence model;
   accumulate limitations.
3. **Layer 1 — observe:** P1, P2 (with employee/employer/sacrifice split), P7.
4. **Layer 2 — project:** per the conventions above, producing
   `ForecastPoint(at, low=Conservative, base=Expected, high=Optimistic)`,
   ordered, never before `as_of`. Terminal values are the Projected Pension
   Values at Retirement.
5. **Layer 3 — translate:** sustainable pension income = terminal pot ×
   `sustainable_withdrawal_rate` per path; combined retirement income = that
   plus P3 plus P4, with each component exposed separately.
6. **Layer 4 — judge:** W* and milestones; trajectory state; ETA; Δv; margin;
   confidence; recommendations.
7. **Assemble** the frozen `MissionAssessment` with D6 applicability, display
   regions per the telemetry table, full provenance references, and every
   standing limitation. Registry envelope validation applies unchanged.

Steps never append an event, never call a model, and never read another
assessor.

## Evidence Model

**Required — absence fails closed to `unavailable`:** active household Party
and reporting currency; a pension Assumption Set containing
`required_retirement_income_annual` and valid ordered returns; a resolvable
planning point (declared `state_pension_age` evidence or `planning_age`); at
least one provision source (a pension account with a valuation, a DB
entitlement declaration, or a State Pension declaration).

**Optional — degrades honestly, never defaults favourably:**

- State Pension declarations — absent for a member ⇒ that member's SP term is
  zero **with a mandatory limitation**; never estimated from legislation.
- Contribution rate declarations — absent ⇒ the projection carries no
  contribution growth, with a mandatory limitation.
- Contribution payment declarations — absent ⇒ P7 `unavailable` with a
  limitation; the mission itself is unaffected.
- Tax Jurisdiction Configuration — absent ⇒ P7 `unavailable` (no tax-year
  boundary is guessed).
- Fee evidence — absent ⇒ `assumed_annual_fee_percent` with a limitation.
- DB entitlements — absent ⇒ simply not part of provision.
- Freshness — stale valuations or declarations propagate `stale` status and a
  confidence downgrade; staleness never improves a band.

**Future — explicitly unassessed, named in every assessment:** taxation and
annual-allowance position (D9/D11); longevity beyond the withdrawal basis
(D10); pension policy/legislative change; bridging income between access ages
and the planning point (D4); decumulation (D3). Missing future-scope evidence
can never raise a band, and its absence is rendered as *not assessed*, never
as a favourable or unfavourable inference.

### Envelope mechanism

Event kind `finance.pension_evidence.recorded`, following RFC-007/RFC-008
exactly: `field`, `value`, `effective_at`, `confidence`, `source`, `lineage`,
optional `unit_or_currency`, plus a subject reference (account id for
account-scoped fields, party id for member-scoped fields). Closed field
whitelist:

| Field | Subject | Unit | Semantics |
|---|---|---|---|
| `employee_contribution_annual` | account | GBP/yr | Declared rate (planning basis) |
| `employer_contribution_annual` | account | GBP/yr | Declared rate |
| `salary_sacrifice_annual` | account | GBP/yr | Declared rate |
| `contribution_payment_employee` | account | GBP | Dated payment occurrence (D11) |
| `contribution_payment_employer` | account | GBP | Dated payment occurrence (D11) |
| `annual_fee_percent` | account | fraction | Scheme charge |
| `db_annual_income_accrued` | account | GBP/yr | DB statement figure |
| `db_normal_pension_age` | account | years | DB scheme age |
| `state_pension_annual` | party | GBP/yr | Forecast statement figure |
| `state_pension_age` | party | years | Forecast statement age |
| `state_pension_basis` | party | enum | `accrued_to_date` \| `forecast_with_continuing_contributions` |

**Disjointness rules, normative** (each asserted by test, because each is a
double-count trap):

- `salary_sacrifice_annual` is a **separate declaration**, never a subset of
  `employee_contribution_annual`. A household recording both is declaring two
  distinct flows; the total is their sum. Documentation for the manual writer
  must state this explicitly.
- `contribution_payment_*` (dated occurrences) and `*_contribution_annual`
  (rates) are **never summed together** and never derived from one another.
- Employer payment declarations feed P7 only; they are never inferred from
  transactions, because employer contributions do not appear in the
  household's transaction feed.

**Supersession semantics:** rate, fee, DB and State Pension fields supersede by
latest `effective_at` per field per subject; **payment fields accumulate** —
each payment is a distinct dated occurrence and is never superseded by a later
one. Equal-time ties resolve by event-log order, never UUID.

Validation occurs **before append**; malformed, non-finite, unknown-field or
hostile envelopes never partially mutate the log. The projection is tolerant:
invalid envelopes attributable to the household remain quarantined and
visible, downgrading confidence rather than disappearing. Hostile strings in
`source`, `lineage` and descriptions are escaped on render. **No prose is ever
parsed for a number**; a field's meaning comes from its whitelisted key. The
manual writer inherits the RFC-007 deprecated-bridge status and its removal
criteria.

## Metric Definitions

Common to all seven: **scope** is the household Party subject routed through
existing scope rules; **provenance** requires `input_references` naming every
contributing event and conversion reference, plus `assumption_references`
wherever a policy value is applied; **`calculation_version`** is
`pension-metrics-v1`; **no model call, no event append**; unsupported request
shapes return `unsupported`, never a silently-baseline answer.

### P1 — `finance.pension_wealth` *(mission value — layer 1)*

| Attribute | Specification |
|---|---|
| **Description** | Current total DC pension wealth: the latest dated valuation at or before `as_of` for each active pension account holding pot valuations, converted to GBP, share-weighted by household-member ownership. |
| **Unit** | GBP |
| **Freshness** | `stale` when any contributing valuation exceeds `valuation_stale_after_days` |
| **Missing evidence** | No pension account with a valuation → `unavailable`. Never defaulted. |
| **Non-duplication** | Structurally disjoint from `finance.accessible_assets` (asserted in both directions); a subset view of Net Worth's existing evidence, not a new valuation basis. |

### P2 — `finance.pension_contributions_annual` *(layer 1, planning basis)*

Sum of declared employee, employer and salary-sacrifice annual rates across
active pension accounts (latest effective declaration per field per account).
Unit GBP/yr. Absent → `unavailable` (the assessor treats absence as
zero-growth planning with a limitation). Cross-checked against observed
`pension_contribution` transaction flow per D8. The employee, employer and
sacrifice components are separately retrievable for telemetry — the split is
declared evidence, never an allocation guess.

### P3 — `finance.state_pension_income_annual` *(layer 3 component)*

Sum of members' declared State Pension annual amounts. Unit GBP/yr. Absent for
all members → `unavailable`; absent for some → value carries a limitation
naming the uncovered member(s). A `forecast_with_continuing_contributions`
basis on any contributing declaration adds a limitation.

### P4 — `finance.defined_benefit_income_annual` *(layer 3 component)*

Sum of accrued DB annual entitlements across DB scheme accounts (D5). Unit
GBP/yr. Treated as real-constant from the planning point (declared V1
simplification; revaluation modelling is debt).

### P5 — `finance.retirement_income_required` *(declared target)*

The declared `required_retirement_income_annual`, published as a metric so the
target is inspectable with provenance. Unit GBP/yr. Missing or invalid →
`unavailable`, and the whole assessment fails closed because the key is
required.

### P6 — `finance.retirement_wealth_required` *(the destination, W\*)*

| Attribute | Specification |
|---|---|
| **Frozen definition** | `max(0, (P5 − P3 − P4) ÷ sustainable_withdrawal_rate)` — the real pot wealth required at the planning point so that pension income plus State Pension plus DB income meets the required income. |
| **Unit** | GBP |
| **Assumption exposure** | Carries `assumption_references` for the withdrawal-rate and required-income keys plus the SP/DB evidence references — the derivation is fully inspectable (AC-19). |
| **Missing evidence** | P5 `unavailable` → `unavailable`. Absent P3/P4 terms per the evidence model (zero with limitation). |
| **Zero case** | Where declared SP and DB income already meet or exceed the required income, W* is zero: the mission is complete at any pot value. This is correct and must render honestly, with the derivation visible; it is not clamped away or treated as an error. |

### P7 — `finance.pension_contributions_tax_year` *(layer 1)*

| Attribute | Specification |
|---|---|
| **Description** | Contributions paid so far in the current tax year: the sum of dated `contribution_payment_*` declarations whose `effective_at` falls within the tax year containing `as_of`. |
| **Unit** | GBP |
| **Tax-year resolution** | From the Tax Jurisdiction Configuration linked to the household via `tax_resident_in` (Spec 001 §19). Where active members are resident in **different** jurisdictions with different tax-year boundaries, P7 returns `unsupported` with a reason naming the conflict — it never picks one jurisdiction silently. |
| **Single basis** | Declared payments only (D11). Observed `pension_contribution` transactions are cross-check evidence; divergence beyond tolerance ⇒ limitation + confidence downgrade, never substitution. No annual rate is ever pro-rated into a payment. |
| **Missing evidence** | No payment declarations, or no declared tax jurisdiction → `unavailable` with a limitation. Never estimated. |
| **Future use** | The evidence substrate for annual-allowance monitoring (recorded debt, not claimed). |

### Metric reconciliation

```text
   pension accounts (account_type = pension)
        │
        ├── pot valuations ───────────► P1 finance.pension_wealth (GBP)
        │                                   = current_value — layer 1 reality
        │                                   = the completion predicate's LHS
        ├── declared annual rates ────► P2 (GBP/yr) — planning basis
        ├── dated payments ───────────► P7 (GBP, tax-year to date)
        ├── db_* evidence ────────────► P4 (GBP/yr) ─┐
   members ── state pension ────────► P3 (GBP/yr) ─┤
        │                                          ▼
   assumption set ── required income ► P5 (GBP/yr) ─► P6 W* = (P5−P3−P4)/SWR
                                                          (GBP — destination)
                                                          = completion RHS

   Assessment-computed projections (never registry metrics, never stored):
   Conservative/Expected/Optimistic pot paths → terminal pot at planning point
   → sustainable pension income (× SWR) → + P3 + P4 → combined retirement income
```

Invariants, each asserted by test: P1 and `finance.accessible_assets` are
disjoint over accounts; P2 (rates) and P7 (payments) never combine into one
figure; the surplus/shortfall quantity exists only in the assessment's margin
telemetry; no existing metric's formula, version, unit or ownership changes;
derivation is acyclic. Projected pot and income values are assessment outputs
exposed as telemetry with assumption references — publishing forecasts as
registry metrics was considered and rejected, because a forecast under one
mission's assumptions must not look like a household fact to another consumer.

## Mission Telemetry

Every telemetry item defines meaning, calculation, evidence source, confidence
treatment, display purpose, hierarchy layer and display region. Qualifiers
carry the honesty labels; no raw metric id or assumption key renders.
Annual-income items carry a per-year label or qualifier (A11).

| Telemetry | Layer | Region · group | Meaning | Calculation | Display purpose |
|---|---|---|---|---|---|
| Current Pension *(current value)* | 1 | hero | Observed pot today | P1 | *Where am I today?* |
| Projected Pension at Retirement | 2 | hero | Expected-path terminal pot | Step 4 (Expected); qualifier `PROJECTED · EXPECTED PATH · NOT A GUARANTEE` | *What is it likely to become?* |
| Estimated Retirement Income | 3 | hero | Combined income consequence | Step 5 (Expected); per-year qualified | *What income will that produce?* |
| This Tax Year's Contributions | 1 | hero | Money added this tax year | P7 | Current-position context |
| Required Retirement Wealth (W*) | 4 | analysis · *Current Funding Position* | Pot-denominated destination | P6 | The completion threshold, made visible |
| Funding Ratio | 4 | analysis · *Current Funding Position* | Share of W* banked | P1 ÷ P6 (percent) | Current funding position |
| Conservative Projected Pension | 2 | analysis · *Projection* | Low-sensitivity terminal pot | Step 4 (Conservative) | Uncertainty made visible |
| Optimistic Projected Pension | 2 | analysis · *Projection* | High-sensitivity terminal pot | Step 4 (Optimistic) | Uncertainty made visible |
| Sustainable Pension Income | 3 | analysis · *Retirement Composition* | Income from the pot alone | Terminal pot × SWR (Expected) | Composition line 1 |
| State Pension | 3 | analysis · *Retirement Composition* | State component, always separate | P3 | Composition line 2 — never hidden inside a calculation |
| Defined Benefit Income *(where present)* | 3 | analysis · *Retirement Composition* | DB component | P4 | Composition |
| Combined Retirement Income | 3 | analysis · *Retirement Composition* | The consequence, summed | Step 5 | Composition result |
| Employee Contributions | 1 | analysis · *Contribution Analysis* | Declared personal rate | P2 split | Contribution analysis |
| Employer Contributions | 1 | analysis · *Contribution Analysis* | Declared employer rate | P2 split | Contribution analysis |
| Total Contributions | 1 | analysis · *Contribution Analysis* | Declared annual total | P2 | Contribution analysis |
| Tax Year Total | 1 | analysis · *Contribution Analysis* | Paid this tax year | P7 | Contribution analysis; future allowance monitoring |
| Required Retirement Income | 4 | drilldown | The declared need | P5 | Judgement basis |
| Projected Surplus / Shortfall | 4 | drilldown | Annual gap at planning point | Combined income (Expected) − P5, signed, never clamped | Margin factor F1 |
| State Pension Reliance | 4 | drilldown | Policy-risk exposure | P3 ÷ combined income (percent) | Margin factor F3 |
| Mission Margin / Confidence / Status / Δv | 4 | *(existing hero and Flight Analysis slots)* | Governor judgement | Their sections | *Am I on track?* |

The drill-down grid remains the complete telemetry record: hero and analysis
placement duplicates into it and never subtracts from it.

### Rejected telemetry

**Success probability** is deliberately excluded, and the Governor Change
Request confirms the removal. Foundry's forecast is a deterministic
sensitivity envelope under declared assumptions; presenting any
percentage-likelihood figure would assert a calibrated probability model the
platform does not have. Conservative / Expected / Optimistic plus Mission
Confidence carry the honest uncertainty story.

**Path-coverage counts** ("2 of 3 paths reach the destination") are excluded
for the same reason (D14): a count over three declared scenarios is not a
sample, and a fraction invites a frequency reading. Coverage is stated in
words in the margin description and evidenced by the visible Conservative and
Optimistic values beside W*.

## Telemetry Region Contract

### Re-review against the Governor's four tests

**Minimum viable framework change?** Yes, confirmed. The Governor's hierarchy
requires a provider to say *which* telemetry is prominent. The renderer is
forbidden from deciding by mission identity (RFC-006/008, test-enforced), so
the information must come from the contract. Two additive optional fields on
an existing dataclass is the smallest carrier that is explicit, validated and
type-safe. Every smaller alternative was considered and rejected in D12; every
larger alternative (a layout contract, a per-mission template, a section
model) would give Core presentation authority it must not have.

**Domain-neutral?** Yes. The vocabulary contains no financial term; `hero`,
`analysis` and `drilldown` name surfaces of the shared mission page that
already exist for every domain. `display_group` carries a domain-supplied
label, exactly as `TelemetryItem.label` already does — Core knows the shape,
never the meaning.

**Future-proof?** Yes, on the RFC-008 pattern. `TELEMETRY_REGION` is a
`ClosedVocabulary`, extendable additively if a fourth surface appears;
defaults keep every existing provider inert; grouping is a label rather than a
closed set, so no domain must ask Core's permission to name a section.

**Consistent with RFC-008 applicability?** Yes, and deliberately parallel:
additive fields with all-inert defaults; closed domain-neutral vocabulary
validated in `__post_init__` and at the registry envelope; presentation-scope
only, never able to change a value or state; renderer forbidden from inferring
placement; an empty-diff regression gate before any consuming mission code
lands.

**Conclusion: retained unchanged in scope, with two hardenings added below.**

### Specification

```text
core/vocab.py
  TELEMETRY_REGION = ClosedVocabulary(
      "telemetry_region", {"hero", "analysis", "drilldown"})

core/mission_assessment.py
  TelemetryItem gains:
      display_region: str = "drilldown"   # validated against TELEMETRY_REGION
      display_group:  str = ""            # optional section label,
                                          # e.g. "RETIREMENT COMPOSITION"
```

Semantics:

- **`hero`** — rendered as additional tiles in the existing
  `mission-hero-meta` grid, after the shipped instruments, using the existing
  tile markup and tokens.
- **`analysis`** — rendered in the Flight Analysis section using the existing
  telemetry-card component, grouped under `display_group` headings, groups and
  items both in declaration order.
- **`drilldown`** — today's behaviour; the default.

Rules, each asserted by test:

1. **Additive and inert by default.** Shipped providers declare nothing; their
   assessments replay and render **byte-identically** (empty-diff gate).
2. **Presentation metadata only.** Regions may never change a value, band,
   status, completion flag, confidence state, or validation outcome.
3. **Domain-neutral.** Any mission in any domain may promote telemetry the
   same way.
4. **No renderer inference.** The renderer places items only by declared
   region — never by mission identity, label text, value truthiness or
   position.
5. **The drill-down is always complete.** Hero/analysis placement duplicates
   into, and never subtracts from, the drill-down record.
6. **Hardening — hero cap.** Contract validation rejects an assessment
   declaring more than **four** `hero` telemetry items. The mission hero is a
   fixed-width instrument cluster; an unbounded region field would let a
   provider destroy a shared layout, and "every pixel earns its place" is a
   Design Constitution rule, not a preference.
7. **Hardening — group validation.** `display_group` must be empty for `hero`
   and `drilldown` items; for `analysis` items it is optional, and where
   supplied must be non-blank text, length-bounded and escaped on render like
   every other provider string.

## Mission Margin

**Primary Mission Margin: the projected annual retirement surplus or
shortfall** — Expected-path combined retirement income at the planning point
minus required income, in GBP per year, signed and never clamped. The margin
description leads with it (e.g. *"£2,000 per year projected surplus at State
Pension age on the Expected path"*) and states F2's path coverage in words.

Its position in the hierarchy is explicit: Mission Margin is **layer 4 — the
Governor's interpretation** of the layer 1 pot and the layer 2/3 projections.
It does not replace Current Pension or Projected Pension Value; those remain
first-class telemetry that the margin cites (hierarchy rule 2).

The margin **state** is worst-factor-wins over discrete integer bands — the
RFC-008 pattern; weight coefficients are forbidden in the policy dataclass:

| Factor | Band 3 | Band 2 | Band 1 | Band 0 |
|---|---|---|---|---|
| F1 Projected surplus (Expected path) | ≥ +20% × P5 | ≥ 0 | ≥ −10% × P5 | < −10% × P5 |
| F2 Sensitivity robustness | Conservative path reaches W* by planning point | Expected path does | only Optimistic path does | none |
| F3 State Pension reliance | ≤ 1/3 of combined income | ≤ 1/2 | ≤ 2/3 | > 2/3 |

`min == 0 → Negative Margin`; `min == 1 → Low Margin`; `all == 3 → High
Margin`; otherwise `Adequate Margin`. Every factor's evidence is
independently visible telemetry, and each factor is named with its value in
the margin description, so the band is reconstructable by inspection. A factor
excluded for absent evidence is dropped from `min()` **and** named in
limitations — never a silent raise or lower.

## Mission Confidence

Confidence measures the assessment's evidential footing, never the outcome,
and is independent of trajectory and margin:

| State | Condition |
|---|---|
| `Established` | **Unreachable in V1** — manual uncorroborated declarations, plus unmodelled tax, longevity and pension-policy risk (D9/D10). A V1 policy limitation stated in the rationale, not a permanent framework rule (the G6 pattern). |
| `Supported` | All required evidence present and fresh; every present optional declaration fresh and uncontradicted; no excluded factor; no cross-check divergence; State Pension declared for every active member on an accrued basis. |
| `Provisional` | Any of: stale valuations or declarations; missing member State Pension declaration; missing fee evidence; contribution cross-check divergence; a `forecast_with_continuing_contributions` SP basis; a D5 DB/DC conflict; quarantined invalid envelopes present. |
| `Insufficient` | Fail-closed (`MissionAssessment.unavailable`) — required evidence or policy absent. |

The Governor can always explain the state: the confidence basis names the
specific downgrading facts, and every cap is visible in rationale or
limitations — a silent cap is a contract-test failure. P7's availability
affects only its own telemetry and the cross-check, never the mission's
evaluability.

## Δv

Δv keeps the established Finance meaning: **schedule change, expressed as
time**. The Expected-path fully-funded date (ETA) at `as_of` is compared with
the same date from a deterministic re-assessment at
`as_of − delta_v_lookback_days`; the difference renders at month resolution
with direction `accelerated`/`delayed`, including the honest "less than one
month" state. Raw day figures remain in the drill-down for audit only. Where
either ETA is absent, `delta_v` is declared `unavailable` — never fabricated.

Contributors that move Δv — increased contributions, improved employer
matching, salary sacrifice, lower fees, market movement in valuations, a
changed planning age, improved tax efficiency (once modelled) — all act
through evidence or assumption changes and are visible through the same
deterministic re-assessment. None is a special case in code.

**Reference-schedule metadata** (Core-owned optional fields, RFC-007 pattern).
The `Mission` entity carries **no declaration timestamp**
([`core/entities.py`](../src/foundry/core/entities.py) — `Mission` has no
`declared_at` field), so `reference_start_at` is resolved deterministically
from the timestamp of the Mission's **first provenance event**;
`reference_start_label` is `PLAN DECLARED`. `reference_destination_at` is the
planning point, labelled `STATE PENSION AGE`, or `PLANNED RETIREMENT` when
`planning_age` overrides. If the first provenance event cannot be resolved,
**both** reference fields are omitted together — the contract validates the
time/label pair jointly, and the schedule lane then simply does not render.

## Recommendations Engine

A recommendation is a read-only `RecommendationAssessment` derived from a
declared, structured Finance `Scenario` — never parsed from prose, never
invented by the assessor, never persisted as an action. V1 supports one action
type: **increase pension contributions**, via a structured
`monthly_pension_contribution_delta` adjustment (the FI
`monthly_contribution_delta` pattern, pension-namespaced).

Every recommendation carries, and the drill-down renders:

- **Rationale** — why this burn improves the mission, phrased against the
  hierarchy (e.g. the Expected path misses W* at the planning point by £X).
- **Expected Mission Margin impact** — the re-projected surplus/shortfall
  delta at the planning point, in GBP/yr.
- **Expected Δv** — re-projected fully-funded-date change, month resolution.
- **Confidence** — inherits the assessment's confidence and names any
  scenario-specific limitation.
- **Dependencies** — the liquidity precedence check and the policy values in
  play, rendered as values with human labels, never key names.
- **Evidence used** — Scenario and Assumption Set event ids as lineage.

Recommendations follow evidence in one direction only: a recommendation exists
because a declared Scenario exists, and its modelled impact is produced by
re-running the same deterministic projection with the same declared
adjustment. The assessor never authors a Scenario, never ranks products, and
never recommends an amount it computed itself.

**Financial Resilience precedence.** No contribution-increase recommendation
is emitted when `finance.liquidity_runway` is absent, unevaluable, or below
the declared `recommendation_liquidity_floor_months`. The suppression copy
follows the RFC-008 D7 standard: observed runway value, declared floor value
with a human label, and the rationale that Financial Resilience takes
precedence. The check dispatches the metric through `MetricRegistry` and
compares against Pension Independence's **own** declared floor — no assessor
dependency.

**Regulated-advice boundary.** Foundry reports the deterministic arithmetic of
scenarios the household itself declared, with full evidence lineage. It must
never recommend or rank pension transfers, consolidation, opt-outs, product or
provider selection, or DB-to-DC transfers, and must never present projections
as advice. A standing limitation states that Foundry provides factual
modelling, not regulated financial advice. Action types whose arithmetic is
safe but whose framing risks crossing this line (fee-reduction switching,
retirement-age changes) are deferred with this boundary recorded — **open
question Q6.**

## Mission Control Rendering — UI Reuse

**No new dashboard, page, route, layout, or pension-specific visual
language.** Pension Independence renders through the existing authenticated
`/missions/pension-independence` route and the shared Mission Detail
experience: Earthrise hero with milestone-arc SVG (higher-is-better geometry
via the validated milestone contract), the hero KPI meta grid, the Mission
Margin stat in its existing position, the Flight Analysis section (including
the schedule lane relocated there by PR #20), the drill-down telemetry grid,
existing typography, spacing, design tokens, navigation and responsive
behaviour. The page must feel identical to Financial Resilience, Financial
Independence and Mortgage Freedom — only the telemetry changes, placed through
the domain-neutral region contract.

### Hero — at a glance

| Existing hero element | Pension Independence content |
|---|---|
| Title / definition | Definition metadata from `finance/missions.py` |
| CURRENT MILESTONE | Dependent → Pension Independent band |
| TRAJECTORY tile *(Mission Status)* | The computed trajectory state — **visible because of D13** — with the honest sub-line that observed history is unavailable |
| ETA tile | `ETA · PENSION INDEPENDENT` — Expected-path fully-funded month/year, or the honest `unavailable` state |
| MISSION MARGIN stat | Margin state + surplus/shortfall description |
| Hero telemetry *(region contract)* | **CURRENT PENSION** · **PROJECTED PENSION AT RETIREMENT** (Expected, qualified) · **ESTIMATED RETIREMENT INCOME** (per-year qualified) · **THIS TAX YEAR'S CONTRIBUTIONS** |

The hero therefore answers, at a glance: current pension, projected pension at
retirement, estimated retirement income, mission status, mission margin, this
year's contributions — the Change Request's six elements, in the user's order,
leading with information users expect rather than abstract capability metrics.

### Flight Analysis

| Existing element | Pension Independence content |
|---|---|
| Trajectory SVG (hero-anchored) | **Projection**: Conservative / Expected / Optimistic pot paths toward the milestone arc; Expected emphasised as the default path, Conservative→Optimistic the labelled sensitivity envelope — the existing forecast-band rendering, relabelled by provider-supplied telemetry labels only |
| Schedule lane | Plan declared → Current position (pot) → Expected destination (fully-funded date) → Planning point |
| Δv instrument | Month-resolution schedule change |
| MILESTONE COMPLETION | Existing band-completion figure |
| NEXT BURN | Contribution recommendation or honest absence |
| ESTIMATED Δv | Modelled recommendation impact |
| Analysis telemetry *(region contract)* | Groups in declaration order: **CURRENT FUNDING POSITION** (Required Retirement Wealth, Funding Ratio) · **PROJECTION** (Conservative, Optimistic) · **RETIREMENT COMPOSITION** (Sustainable Pension Income, State Pension, DB where present, Combined Retirement Income) · **CONTRIBUTION ANALYSIS** (Employee, Employer, Total, Tax Year Total) |

The renderer continues to branch only on declared contract fields. The
drill-down remains the complete record: full telemetry grid, assumptions,
limitations, provenance counts, confidence basis.

### Formatting: annual income

`TELEMETRY_FORMAT` is unchanged (`currency`, `percent`, `months`, `number`,
`plain`). The mission value is a plain balance. Annual-income telemetry
(layer 3, P2, P5) uses `currency` format with per-year semantics carried in
labels and qualifiers; blocking criterion A11 requires every rendered annual
figure to carry a per-year label or qualifier so income never reads as a
balance. A `currency_per_period` format kind remains recorded future work
(**open question Q7**).

### Illustrative values

RFC examples and the synthetic demonstration household use values of this
shape, per the Change Request. They are internally consistent, which is the
point: a reader can verify the whole calculation chain from them.

| Figure | Illustrative value | Derivation |
|---|---|---|
| Current Pension (P1) | £62,000 | observed |
| Required Retirement Income (P5) | £40,000 / year | declared |
| State Pension (P3) | £10,600 / year | declared |
| Required Retirement Wealth (W*, P6) | £735,000 | (40,000 − 10,600) ÷ 0.04 |
| Projected Pension at Retirement (Expected) | £785,000 | projection |
| Sustainable Pension Income | £31,400 / year | 785,000 × 0.04 |
| Estimated Retirement Income | £42,000 / year | 31,400 + 10,600 |
| Projected surplus (margin headline) | +£2,000 / year | 42,000 − 40,000 |
| Funding Ratio | 8.4% | 62,000 ÷ 735,000 |
| Current milestone | Dependent, 33.7% through band | band 0 → £183,750 |
| This Tax Year's Contributions (P7) | £11,500 | declared payments |

These figures are **illustrative only**: they appear solely as synthetic demo
evidence and documentation examples, carry the synthetic-marker discipline,
and must never become hard-coded assumptions, defaults, or test-oracle magic
numbers divorced from declared fixture evidence.

## Security Considerations

**Classification.** Pension values, contribution levels and payment dates, DB
entitlements, State Pension forecasts, tax-jurisdiction linkage and planning
ages are *personal-confidential*: in aggregate they disclose lifetime
earnings, employer history, age, and long-term financial vulnerability.
Projected values, incomes and margins are *derived-sensitive*; applicability
and display-region metadata are *derived-non-sensitive*. Nothing derived is
persisted.

**Identifier hygiene.** The closed field whitelist has no free-form identifier
field; National Insurance numbers, policy numbers and provider references must
not be recorded in `source`/`lineage` prose, and the manual writer's
documentation must say so. Hostile strings in envelope text — including
`display_group` labels — are escaped on render; payload and exception text are
never exposed.

**Authentication.** No identity flow changes. The generic mission route
performs the existing session check before definition lookup; authentication
and health routes remain the only public routes.

**Authorisation and household boundaries.** Assessment accepts only an active
household `Subject`; pension accounts and declarations must belong to active
members of that household; cross-household or member-scope reuse fails closed
through the existing scope-envelope validation. This is representation and
fail-closed validation, not a claim of a multi-user authorisation model — the
RFC-006 object-level authorisation debt is unchanged and re-recorded.

**Auditability and reproducibility.** Every rendered figure traces to event ids
and assumption references. Each assessment is reconstructable from
`(log, policy id, calculation version, assumption event ids)`. No assessment is
appended; completion is derived and reversible, so projections never masquerade
as observed facts. The layered hierarchy strengthens auditability: each layer's
provenance class is explicit at the contract level, and the completion
predicate contains only observed and declared terms.

**Hostile and malformed manual inputs.** Validated before append; quarantined
but visible on replay with a confidence downgrade; deterministic ordering by
log position; future-dated evidence (`effective_at > as_of`) is excluded and
disclosed, never silently dropped. Payment-field accumulation cannot be abused
to inflate P7 silently: every payment is a visible dated event with
provenance, and the transaction cross-check discloses divergence. No prose
parsing, no policy inference from labels or display text.

**Future pension provider integrations.** Any live connector (pensions
dashboard, provider APIs) is out of scope and must arrive as its own governed
RFC meeting these preconditions: credentials never enter the event log;
read-only ingestion with source, effective date, confidence and lineage
preserved; provider identity as provenance; the manual envelope retired only
per the RFC-007 removal criteria. RFC-009 itself adds no file parsing, no
network access, no credentials, no dependencies, no outbound destinations.

**Deterministic failure behaviour.** Missing required evidence → `unavailable`
with a distinct reason; provider exception → contained by dispatch as one NOT
EVALUABLE lane with the deck intact; malformed provider output → rejected by
contract validation. Nothing retries, fabricates, or degrades silently.

**Demonstration data.** Synthetic pension evidence carries the existing
synthetic-marker discipline so a seeded log can never be mistaken for a real
household.

### Threat Assessment

- **Trust boundaries:** one narrow manual in-process evidence envelope
  (RFC-007 pattern); no external boundary moves. Route slug and provider
  output remain the RFC-006 untrusted envelopes; display regions and group
  labels are provider output validated by the registry like every other
  contract field.
- **Threat model:** T6 (authorisation failure) — narrowed by scope validation,
  residual multi-user debt unchanged; T8 (hostile manual input) — controls
  above; T10 (operator error on permanent manual records) — validation before
  append plus visible conflicts; T1 (poisoned content) — no document parsing
  exists, statement values are typed manual declarations. No residual risk is
  silently accepted.
- **Failure and abuse:** malformed, hostile, repeated, future-dated, stale or
  cross-scope evidence behaves deterministically as specified; existing events
  are never mutated; assessment performs no append and no partial write.

This section answers every question in
[`security/security-checklist.md`](security/security-checklist.md) and is the
Security Gate input.

## Acceptance Criteria

**A1–A34 are blocking.**

### Framework and isolation

| # | Criterion |
|---|---|
| A1 | The only changes outside Finance are the telemetry-region amendment (D12) and the trajectory-tile correction (D13). No other change to `core/`, `mission_control.py`, `eventlog.py`, `canon.py`, `kernel.py`, or any existing Finance module except the `finance/missions.py` order-3 entry and composition-root registration. |
| A2 | No assessor references the registry or another assessor (AST test); constructors accept metric registry and projections only; independently executable with other assessors unregistered. |
| A3 | Determinism: two assessments of one log are equal; two renders byte-identical; reproducible from log + policy id + calculation version + assumption event ids. |
| A4 | Read-only: log length and hash unchanged across assessment and render; no event appended, including no `achieve_mission`. |

### Region amendment (D12)

| # | Criterion |
|---|---|
| A5 | **Empty-diff gate:** with the region amendment landed and no Pension code present, FI, Mortgage Freedom and Financial Resilience assessments, detail routes and homepage lanes are byte-identical to pre-amendment golden pins. |
| A6 | Region validation: unsupported region values rejected; default is `drilldown`; flipping any region changes no value, band, status, completion flag or confidence state. |
| A7 | Renderer places items only by declared region — no mission-name, slug, policy-id, truthiness or ordering inference. |
| A8 | The drill-down grid contains every telemetry item regardless of region; hero and analysis placement duplicate, never subtract; accessible tree and visual layout have instrument-set parity. |
| A9 | Hero cap enforced: an assessment declaring five or more `hero` telemetry items fails contract validation. `display_group` is rejected on `hero`/`drilldown` items and escaped on render for `analysis` items. |

### Trajectory-tile correction (D13)

| # | Criterion |
|---|---|
| A10 | FI and Mortgage Freedom detail-route output is **byte-identical** across the correction (their trajectory is `applicable`). |
| A11 | Financial Resilience's detail hero renders its computed trajectory state instead of `NOT AVAILABLE`, retaining the honest history sub-line — asserted with its own separately pinned expected string, every other byte identical. |
| A12 | Homepage lane output is unchanged for all shipped missions; detail-page and homepage trajectory words now agree for the same assessment (the defect regression test). |
| A13 | A provider supplying no `trajectory_state` still renders today's `NOT AVAILABLE` tile; the observed-history SVG region and accessible history clause remain governed by `applicability.trajectory` alone. |

### Regression — shipped missions

| # | Criterion |
|---|---|
| A14 | Golden pins for all three shipped missions and the homepage captured before any RFC-009 work, and re-asserted after each of: the region amendment, the trajectory correction, and Pension registration. The Pension homepage lane moves from planned to live through the existing definition-association path only. |

### Completion semantics and hierarchy

| # | Criterion |
|---|---|
| A15 | `mission_complete` is exactly `P1 ≥ W*`. A fixture whose Expected path reaches W* but whose pot does not returns `mission_complete = False` **with** trajectory `Nominal` — the Governor's worked example, asserted as one test. |
| A16 | Completion contains no growth assumption: changing `base_real_return`, `low_real_return` or `high_real_return` alone changes forecast, ETA, trajectory and margin but **never** `mission_complete` or `current_value`. |
| A17 | Completion is reversible: P1 ≥ W* ⇒ `True`; a lowered valuation or raised requirement ⇒ `False` at the next assessment with milestone and trajectory following; no event appended; `Mission.status` still `active`. |
| A18 | `current_value` is P1 and carries no assumption references; removing all contribution, return or income evidence changes forecasts and judgements but never the current value's amount. |
| A19 | Hero telemetry is exactly the four declared layer-1/2/3 items; every projected figure carries a projection qualifier naming its path; the Expected path is identified as the default in rendered labelling. |
| A20 | Every rendered annual-income figure carries a per-year label or qualifier; no annual figure renders as a bare balance; no raw metric id or assumption key renders. |
| A21 | State Pension renders as a separate Retirement Composition component whenever declared, and its absence for any member produces the mandatory limitation — never netted invisibly into W* alone. Illustrative demo values exist only as synthetic fixture evidence, never as code defaults. |

### Mission behaviour

| # | Criterion |
|---|---|
| A22 | Milestones are exactly Dependent / Foundation / Building / Approaching / Pension Independent; bounds derived from W*; `unit_or_currency = "GBP"`; `completion`, `is_complete`, `destination_value` and `estimated_at` follow the pinned conventions; `completes_mission` on Pension Independent only; direction matches the registered definition. |
| A23 | W* zero case: declared SP and DB income meeting the required income yields W* = 0, mission complete at any pot value, derivation visible, no clamping error. |
| A24 | **No probability language anywhere** — no percentage likelihood, no "chance of success", no probability qualifier, and no path-count or fraction that could be read as a frequency; Conservative/Expected/Optimistic sensitivity labelling asserted. |
| A25 | Trajectory states follow the deterministic W*-crossing rules; tone supplied by policy; renderer never derives colour. |
| A26 | ETA is the first Expected-path W* crossing month; no crossing ⇒ `eta` declared `unavailable` with reason, remaining assessment intact. |
| A27 | Δv computed against the deterministic lookback re-assessment; month resolution with honest sub-month state; absent either ETA ⇒ `delta_v` `unavailable`, not fabricated; reference start resolved from the Mission's first provenance event, and both reference fields omitted together when unresolvable. |
| A28 | Margin is worst-factor-wins with no weight coefficients; each factor's evidence independently visible and named with its value in the description; excluded factors dropped from `min()` and named in limitations; the description cites the pot and projection it interprets. |
| A29 | Confidence: `Established` unreachable in V1 with the cap visible; each `Provisional` trigger produces `Provisional` with a naming basis; missing required evidence fails closed to `Insufficient`; P7 unavailability never degrades mission evaluability. |

### Evidence and metrics

| # | Criterion |
|---|---|
| A30 | Envelope whitelist closed; malformed/hostile input rejected at append, quarantined-but-visible on replay with confidence downgrade; hostile strings escaped; future-dated evidence excluded and disclosed; rate fields supersede, payment fields accumulate; equal-time ties resolve by log order. |
| A31 | Disjointness: P1 vs `finance.accessible_assets` asserted in both directions; salary sacrifice never treated as a subset of employee contributions; rates and payments never summed; no existing metric formula, version, unit or ownership changes. |
| A32 | Single-basis rules: P7 derives only from dated payment declarations (no pro-rating, no transaction substitution); rate/observed divergence beyond tolerance ⇒ limitation + downgrade; mixed-jurisdiction households return `unsupported` for P7 rather than choosing silently; no cadence inferred from `RecurringSeries`. |
| A33 | Projection conventions pinned: monthly compounding from the annual net rate, fee subtracted from return exactly once, end-of-month contributions, real-constant contributions, per-account projection then summation — asserted by a worked fixture reproducing the illustrative chain. Missing optional evidence per the evidence model produces its mandatory limitation and can never raise a band; missing required evidence produces distinct fail-closed reasons; a D5 DB/DC conflict excludes that account from P1 and P4 with limitation and `Provisional` cap. |
| A34 | Lineage on every available telemetry item; assumption references wherever policy is applied; W* and every projected figure expose their Assumption Set (Spec 001 AC-19); layer-1 items carry event provenance only. Liquidity precedence suppresses the recommendation below the declared floor with observed value, floor value and human-label rationale and no key leakage; no transfer/consolidation/product language appears in any rendered recommendation; the factual-modelling limitation always renders. Full suite green on Python 3.10–3.13; both Gates APPROVE; completed checklist in the PR. |

### Risks and controls

| # | Risk | Consequence | Control |
|---|---|---|---|
| R1 | Mission drifts into balance tracking | Pot shown without judgement | Hierarchy layers 2–4 mandatory; A19, A28 |
| R2 | Projection rendered as fact or probability | False precision | D7, D14, A19, A24 |
| R3 | Completion redefined as forecast-derived | Assumption-editable achievement | A15, A16 |
| R4 | Judgement displaces reality | Margin replaces pot/projection telemetry | Hierarchy rule 1; A19, A28 |
| R5 | Favourable defaults for missing evidence | Household told it is safer than evidence supports | A33 |
| R6 | Advice-boundary breach | Regulated-advice exposure | A34 |
| R7 | Assessor coupling or framework growth beyond D12/D13 | Second engine by stealth | A1, A2 |
| R8 | Hostile/malformed envelopes | Corruption or silent disappearance | A30 |
| R9 | Region metadata abused as a status system, or hero flooded | Silent second status model; broken shared layout | A6, A7, A9 |
| R10 | Weighted opaque margin | Unexplainable band | A28 |
| R11 | Completion treated as terminal | Reversibility broken | A4, A17 |
| R12 | Trajectory state suppressed by unavailable history | *"Am I on track?"* unanswerable | D13, A11, A12 |
| R13 | Δv fabricated on first assessment | Invented movement | A27 |
| R14 | NI/policy numbers in lineage prose | Sensitive identifier persistence | Identifier hygiene + writer docs |
| R15 | Per-request replay cost with four assessors | Latency | Benchmark step; recorded envelope |
| R16 | Rates and payments conflated, or salary sacrifice double-counted | Fabricated or inflated contribution figures | D11, A31, A32 |
| R17 | Illustrative values hard-coded | Demo numbers become policy | A21 |
| R18 | Projection conventions differ between implementations | Non-reproducible figures | A33 |

## Consistency Review (Revision 3)

A full pass was made over Revision 2 against the Governor's six consistency
tests. Findings and dispositions:

| Test | Finding | Disposition |
|---|---|---|
| Terminology internally consistent | Revision 2 mixed "base path" with "Expected path" | Swept to Conservative/Expected/Optimistic throughout; `ForecastPoint.low/base/high` remains the Core field name and is identified as such once |
| Mission Margin consistently defined | Consistent across D-record, margin section and telemetry table | No change; hierarchy position now stated explicitly |
| Projections separated from observations | Sound, but the *rendered* separation was undermined by the trajectory-tile defect | Fixed by D13; layer classification now carried per telemetry item |
| Recommendations follow evidence | Sound | Made explicit ("in one direction only") |
| No hidden pension assumptions | **Five found:** fee application point; contribution timing and real-constancy; per-account vs aggregate projection; salary-sacrifice/employee overlap; multi-jurisdiction tax-year selection | All pinned — Calculation Flow conventions, envelope disjointness rules, P7 jurisdiction rule; A31–A33 defend them |
| No implementation ambiguity | **Four found:** milestone `completion`/`is_complete`/`destination_value` conventions; milestone `unit_or_currency` (affects formatting at `mission_control.py:1795`); Δv `reference_start` with no `Mission.declared_at` field; W* zero case | All pinned against shipped code; A22, A23, A27 defend them |

Deliberate residue: the open-question numbering skips **Q2**, retired when the
Revision 2 mission-value change dissolved it. Renumbering would break
references in the revision history and prior review correspondence; the gap is
recorded rather than closed.

## Technical Debt (recorded by RFC-009, deliberately not fixed)

Decumulation-epoch assessment (drawdown sustainability, sequencing risk);
bridging income between access ages and the planning point; taxation model
(gross/net, lump sums, allowances); **annual-allowance monitoring on the P7
evidence substrate**; explicit longevity/annuity bases; DB revaluation and
escalation modelling; contribution escalation/indexation; multi-tranche income
timing (per-member State Pension ages); multi-jurisdiction tax-year handling;
historical pension trajectory reconstruction; secured-income drill-down
telemetry (Revision 1's concept, preserved as future work);
`currency_per_period` telemetry format; additional recommendation action types
(fees, retirement age) behind the advice boundary; pension provider
connectors; manual envelope retirement per RFC-007 criteria; per-request
replay cost; multi-user and object-level authorisation (inherited).

**RFC-008 debt-register amendment required:** record that
`InstrumentApplicability.trajectory` governed both the observed history series
and the trajectory-state tile, that this produced a homepage/detail
disagreement for Financial Resilience, and that RFC-009 D13 closed it.

## Open Questions — none remaining

Every question raised by this RFC has been ruled and closed. Q1 and Q3–Q11
were each approved as recommended on 2026-07-30; the decisions and the
Governor's recorded reasoning are in
[Governor Approval](#governor-approval). **No decision in this document is
open.**

Q2 (secured-income compounding basis) was retired in Revision 2, dissolved by
the mission-value change; no growth assumption enters the headline value or
the completion predicate. The numbering gap is deliberate and preserved so
that prior review correspondence remains resolvable.

Questions arising after this point are not open questions against RFC-009;
they require a new RFC amendment.

## Codex Implementation Sequence

**Pre-flight:** clean `main` matching `origin/main`; record the green baseline;
branch `rfc-009-pension-independence-mission`; read this document plus the
RFC-006/007/008 architectures and debt registers.

**Mandated opening — in this exact order (the RFC-008 discipline):**

1. **Capture golden pins** for FI, Mortgage Freedom, Financial Resilience and
   the homepage — A5, A10–A12 and A14 must be able to fail before anything
   changes.
2. **Land the region amendment** (D12) — vocabulary, `TelemetryItem` fields,
   contract validation including the hero cap and group rules, region-aware
   renderer placement.
3. **Prove renderer neutrality with mock providers** — fixtures declaring each
   region, asserting A6–A9. No Finance code involved.
4. **Verify the empty diff** — A5 passes byte-identically. **Gate: do not
   proceed otherwise.**
5. **Land the trajectory-tile correction** (D13) — with Financial Resilience's
   new expected string separately pinned (A11) and FI/Mortgage byte-identical
   (A10). **Gate: A10, A12, A13 pass before proceeding.**

**Thereafter:**

6. `finance/pension_evidence.py` — validated envelope (rates supersede,
   payments accumulate), tolerant projection, deterministic ordering,
   disjointness rules, hostile-input handling (A30).
7. `FinancePensionMetricProvider` — P1–P7 frozen definitions; composition-root
   registration; disjointness, single-basis, jurisdiction, cross-check,
   provenance and fail-closed tests (A31–A34).
8. `PensionIndependenceAssessor` — policy, W*, projection conventions,
   milestones, trajectory, ETA, Δv, margin, confidence, D6 applicability,
   region declarations, reversible completion (A15–A29).
9. **Demonstration evidence** — synthetic pension Assumption Set and evidence
   reproducing the illustrative chain, with the synthetic-marker discipline
   (A21).
10. **Recommendation behaviour** — scenario modelling, liquidity precedence
    copy, advice-boundary limitation (A34).
11. `finance/missions.py` order-3 policy id + definition text; verify the
    planned→live homepage transition (A14).
12. **Rendering assertions** — hierarchy placement, per-year labelling,
    projection qualifiers, accessible parity (A19–A21).
13. **Four-assessor performance benchmark** — record the envelope in the
    implementation report; no pre-emptive optimisation (R15).
14. **Full regression, Architecture Gate, Security Gate, documentation** —
    implementation report, `rfc-009-technical-debt.md`, the RFC-008
    debt-register amendment, CHANGELOG entry, version bump,
    [`rfcs/index.md`](rfcs/index.md) row, and the completion/trajectory
    [Mission Engine principle](#mission-engine-principle--completion-and-trajectory-answer-different-questions)
    promoted into [`architecture.md`](architecture.md)'s architecture
    observations.

**Explicit non-goals:** no decumulation modelling; no bridging-income
modelling; no tax or annual-allowance calculation; no Monte Carlo, probability
output or path-count fraction; no annuity quotes; no DB transfer analysis; no
pension connectors or credentials; no new routes, pages, layouts or
pension-specific components; no Core change beyond D12; no renderer change
beyond D13; no change to any existing metric or assessor's logic; no changes
to `eventlog.py`, `canon.py` or `kernel.py`; no `RecurringSeries`/`Obligation`
schema changes; no cadence or payment inference; no authorisation changes.

## Future Implementation Considerations

- **Decumulation epoch:** when built, the same mission flips its declared
  applicability without framework change — the payoff of RFC-008's
  per-instrument design.
- **Annual-allowance monitoring:** consumes the P7 payment-evidence substrate
  plus a tax-rules contract; its own governed work under D9's boundary.
- **Pension provider / dashboard connectors:** must meet the Security
  Considerations preconditions and retire the manual envelope per RFC-007
  criteria.
- **Property Valuation Canon** (RFC-007 successor work) is the model for a
  future **Retirement Income Canon** if income bases multiply across missions.
- **Stochastic modelling**, if ever pursued, is its own governed RFC with a
  calibration story — not an incremental toggle on this policy.

## References

- [`architecture.md`](architecture.md) — constitutional invariants and
  observations
- [`design/design-constitution.md`](design/design-constitution.md) —
  Information Honesty, Mission Telemetry, Apollo mission hierarchy
- [`specifications/000-core-domain-model.md`](specifications/000-core-domain-model.md)
- [`specifications/001-finance-domain-model.md`](specifications/001-finance-domain-model.md)
  — §16 projections, §18 pension model, §19 tax model, AC-19 exposed
  assumptions
- [`rfc-005-financial-independence-architecture.md`](rfc-005-financial-independence-architecture.md)
  — observed-threshold completion precedent
- [`rfc-006-mission-assessment-framework.md`](rfc-006-mission-assessment-framework.md)
- [`rfc-007-mortgage-freedom-architecture.md`](rfc-007-mortgage-freedom-architecture.md)
  — evidence envelope, reference schedule, precedence patterns, observed-zero
  completion
- [`rfc-008-financial-resilience-architecture.md`](rfc-008-financial-resilience-architecture.md)
  — applicability contract, margin/confidence patterns, constraint transport,
  additive-amendment and D7 pinned-copy precedents
- [`rfc-008-financial-resilience-implementation-report.md`](rfc-008-financial-resilience-implementation-report.md)
- [`security/threat-model.md`](security/threat-model.md) — T1, T6, T8, T10
- [`security/security-checklist.md`](security/security-checklist.md)
- [`engineering/review-gates.md`](engineering/review-gates.md)
- [`rfcs/index.md`](rfcs/index.md)
