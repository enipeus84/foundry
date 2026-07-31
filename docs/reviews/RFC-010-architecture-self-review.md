# RFC-010 — Architecture Self-Review

Adversarial self-review performed by EECOM before commit, against the ten
challenges in the RFC-010 brief. Conducted on the draft of
[`../rfcs/RFC-010-mission-console-ux-framework.md`](../rfcs/RFC-010-mission-console-ux-framework.md)
at 2026-07-31.

**Outcome: six amendments made to the RFC as a result of this review.** Each is
recorded below with the challenge that produced it. Four challenges produced no
amendment and are recorded with the reasoning that cleared them.

---

## Challenge 1 — Is this genuinely domain-neutral?

**Largely yes, with one leak found and fixed.**

Clean: the five regions, trajectory contract, margin contract, burn states,
disclosure behaviour and view-model boundaries contain no domain concept,
mission slug, currency or mission-name conditional.

**Leak found.** The draft's canonical disclosure list named a section
"Contributions / Inflows" — a Finance concept promoted into a Core-owned
ordered slot. A Health or Learning mission has no contributions.

**Amendment A1.** Core-owned slots are renamed to domain-neutral function
names, with domain language supplied by providers through `display_group`:
*Supporting Telemetry* replaces *Contributions / Inflows*; *Scenario
Projections* replaces *Projection Scenarios*. Decision 7 and the Region 5
section were updated, and unresolved question Q3 now records the boundary
explicitly.

**Residual, accepted.** `TELEMETRY_FORMAT` is `{currency, percent, months,
number, plain}` — `currency` and `months` are Finance-leaning. A non-Finance
mission uses `number` plus a unit string, which works but is less expressive.
RFC-010 does not amend that vocabulary: doing so would be framework growth
ahead of a real second domain. Recorded as a watch item, not a defect.

---

## Challenge 2 — Does this over-engineer a UI problem?

**Partially justified concern; mitigation strengthened.**

The RFC adds a Mission Console Model layer, five view models, one closed
vocabulary and one margin amendment. That is real new surface. The defence is
that it retires four to six existing paths in the same Burn, and that
projection exists to make cardinality, emptiness and classification rules
unit-testable without HTTP, HTML or a seeded event log — which today is
impossible, and is the reason those rules do not exist.

**Weakness found.** Acceptance criterion AC-15 said "net rendering-path count
does not increase" without defining the measure, making it unfalsifiable.

**Amendment A2.** AC-15 now defines the measure concretely: the count of
distinct region-rendering functions in `mission_control.py`, plus the number of
`TELEMETRY_REGION` values, plus the number of deprecated contract fields still
read by the renderer, must be **strictly lower** after the Burn than before.
That is countable in a test.

---

## Challenge 3 — Is "Mission Margin" sufficiently universal?

**No — a real gap was found.**

Margin works for a surplus mission (Pension: £/year), a buffer mission
(Resilience: months) and a composite mission (Mortgage: LTV, liquidity,
fixed-rate protection, overpayment flexibility). It does **not** work for a
genuinely binary mission — a future Health mission whose destination is
"vaccinated" or a Household mission whose destination is "will executed" has no
meaningful tolerance. The draft forced such a mission to render margin as
`unavailable`, which dishonestly implies the value is missing rather than
inapplicable — precisely the conflation RFC-008 introduced applicability to
fix.

**Amendment A3.** `InstrumentApplicability` gains a fifth field, `margin`,
defaulting to `"applicable"` so all four shipped missions replay unchanged. A
mission may now declare margin `not_applicable`, and the console omits the slot
entirely rather than showing an absence. Consistency validation follows the
RFC-008 rule exactly: `not_applicable` ⇒ value must be absent; `unavailable` ⇒
absent with an explanation. Decision 4, the hero slot table and the acceptance
criteria were updated.

This raises the amendment count for RFC-010 from two contract changes to three.
That is accepted: without it the framework fails its own domain-neutrality test
on the first non-Finance mission.

---

## Challenge 4 — Does trajectory require new domain logic?

**No new calculation, but the new field is honestly low-yield at first.**

Every field in `MissionTrajectoryView` except `movement` aggregates an existing
provider output. `movement` requires a provider to classify whether its value
is advancing toward, holding at, or receding from its declared destination —
a classification over evidence the provider already folds, not a new
calculation.

**Honest limitation.** Two of the four live missions (Financial Resilience,
Pension Independence) declare trajectory history unavailable and would report
`movement: unknown` indefinitely. So the field yields real information for only
half the current estate.

**No amendment to remove it**, for two reasons: it closes RFC-008's deferred
G5/D2.3 debt in a domain-neutral way rather than by widening the
schedule-specific `DeltaV.direction`; and a steady-state mission is exactly the
case that today can express no movement at all.

**Amendment A4.** The RFC now states explicitly that `movement: unknown` is a
legitimate permanent state for a mission, and that the console must not render
it as degradation, a warning, or missing evidence. Without that rule an
implementer would plausibly render "unknown" as a fault.

---

## Challenge 5 — Could progressive disclosure hide important information?

**Yes — and the draft's protection was unenforceable.**

The draft stated that information changing "the safety or validity of the
primary recommendation" must not be disclosure-only. That is a correct
principle and an untestable one: it relies on a reviewer's judgement about
which limitation matters.

**Amendment A5.** The safety rule is now mechanical. Three categories must
render in Region 4 alongside the burn, never disclosure-only:

1. every string in the primary recommendation's own `limitations` tuple;
2. any confidence cap or downgrade reason named in `confidence_basis` where
   confidence is `Provisional` or `Insufficient`;
3. any precedence or suppression constraint that changed the recommendation.

All three are contract fields, so the rule is assertable by test (T12 extended).
The judgement-based sentence is retained as intent, but the enforceable rule is
what implementation must satisfy.

---

## Challenge 6 — Does the view model leak HTML?

**The draft's protection was a naming convention, not a type.**

The `_html` suffix rule descends from the correction applied after the PR #21
review, where `_MissionHeroView`'s docstring claimed all inputs were escaped
while half were raw fragments. A suffix plus a docstring is better than
nothing, and an AST test (T14) raises the cost of violating it — but the type
system still says `str` for both trusted and untrusted fields, so the compiler
permits exactly the mistake the convention forbids.

**Amendment A6.** Decision 8 now recommends a distinct `TrustedHtml` wrapper
type for pre-rendered fragments, so that passing a plain provider string where
a fragment is expected is a type error rather than a silent XSS. The `_html`
naming rule is retained as the human-readable signal; the type is the
enforcement. Recorded as part of the console primitives step, not deferred —
introducing it later means migrating every view field twice.

---

## Challenge 7 — Is the four-question model actually reflected in the hierarchy?

**Not exactly — and the discrepancy is structural, not cosmetic.**

Mapping the mandated region order to the four questions:

| Region | Question |
|---|---|
| 1 Mission Hero | Q1 *Where am I?* + Q2 *Where am I going?* |
| 2 Flight Analysis | Q3 *Am I on course?* |
| 3 Essential Telemetry | **none** |
| 4 Next Burn | Q4 *What burn next?* |
| 5 Disclosure | none (by design) |

Region 3 interrupts the four-question sequence: a reader must pass three to six
telemetry values before reaching the answer to Q4. The brief mandates this
order, so RFC-010 does not change it.

**Amendment A7.** The RFC now records this tension explicitly rather than
leaving it implicit, and states the mitigation as a *requirement* rather than
an option: the hero's **Next Burn preview slot is the reason Q4 remains
answerable at a glance**, and it is therefore required whenever a primary burn
exists — previously it was marked "optional". Region 3's cap and its
omit-when-empty rule limit how far it can push Q4 down the page.

This is the amendment I would most want a Governor to scrutinise, because it
accepts a structural compromise imposed by the mandated order.

---

## Challenge 8 — Are the cardinality rules testable?

**Yes, with one deliberate asymmetry.**

Testable: essential ≤ 6 (contract validation); hero carries no telemetry list
(structural — the field does not exist); supporting rail ≤ 3; five regions in
fixed order; omitted regions absent from DOM and accessible tree; no rendered
cell without content.

**Deliberately not enforced:** the three-item lower bound on essential
telemetry. Enforcing a minimum would incentivise padding, which is the defect
the region exists to remove. The RFC states this asymmetry openly and enforces
the *consequence* instead — no empty or decorative cell, for any count. No
amendment; the reasoning is now recorded in the RFC rather than only here.

---

## Challenge 9 — Does this reduce complexity or relocate it?

**Net reduction, now measurable.** See Amendment A2. Before the Burn the
renderer carries: three region view models, three `TELEMETRY_REGION` values,
the analysis-rail burn instruments, the monolithic drill-down, two deprecated
margin numerics, the legacy scalar adapter and the RFC-005 phase aliases.
After, it carries five region view models against a retirement list of four
mandatory and two recommended paths. The count must fall, and AC-15 now says so
in countable terms.

**Honest caveat.** If the Governor declines to authorise the retirements
(unresolved question Q1), RFC-010 becomes a net addition. The RFC should not be
implemented with the retirement list removed; that combination is the
over-engineering outcome challenge 2 warns about, and it is now stated as such.

---

## Challenge 10 — Can future domains comply without mission-specific branches?

**Yes, after Amendment A3.** Walkthrough of a hypothetical binary Health
mission with no forecast and no history:

| Region | Rendering |
|---|---|
| Hero | identity; current position "not completed"; destination "completed"; trajectory declared unavailable with reason; **margin declared `not_applicable` and omitted** (A3); confidence `Provisional` |
| Flight Analysis | explicit unavailable panel with its explanation; rail omits Δv and intercept |
| Essential telemetry | two items; region renders both, pads nothing |
| Next Burn | one advisory recommendation with no fabricated Δv |
| Disclosure | Assumptions, Evidence and Provenance, Mission Definition |

No renderer branch, no Core amendment, no domain term. Before A3 this mission
would have rendered a misleading "margin unavailable" slot.

---

## Amendments Applied

| # | Amendment | Section changed |
|---|---|---|
| A1 | Disclosure slot names made domain-neutral; provider supplies domain language | Region 5, Decision 7, Q3 |
| A2 | AC-15 complexity measure made concrete and countable | Acceptance Criteria |
| A3 | `InstrumentApplicability` gains `margin`, allowing not-applicable margin | Mission Margin Contract, hero slots, Decision 4, AC |
| A4 | `movement: unknown` declared a legitimate permanent state, never rendered as degradation | Trajectory Contract |
| A5 | Safety rule made mechanical: three contract-field categories must render with the burn | Region 5, Region 4, T12 |
| A6 | `TrustedHtml` wrapper type recommended over naming convention alone | Decision 8, view-model contracts |
| A7 | Region 3's break in the four-question flow recorded; hero burn preview promoted to required | Universal hierarchy, Region 1 |

## Residual Risks Accepted

1. `TELEMETRY_FORMAT` retains Finance-leaning values; deferred until a real
   second domain exists.
2. `movement` yields no information for two of four current missions; accepted
   because it closes a recorded debt and serves steady-state missions.
3. The three-item essential minimum is unenforced by design.
4. Region 3 sits between Q3 and Q4 by mandate; mitigated, not removed.
5. RFC-010's value depends on the retirement list being authorised; if Q1 is
   declined, the RFC should be reconsidered rather than implemented as a pure
   addition.

## Self-Review Disposition

The architecture is coherent, domain-neutral after A1 and A3, and reduces net
rendering complexity provided the retirement list is authorised. Three contract
amendments are proposed — telemetry region `essential`, trajectory `movement`,
and applicability `margin` — each additive with inert defaults, each with a
stated reason no smaller alternative suffices.

**Ready for Governor architecture review.**

---

## Governor Review Outcome — 2026-07-31

**GO WITH MINOR AMENDMENTS.** Seven amendments were directed and applied; none
redesigned a concept or added scope. The self-review findings above stand
unchanged — no Governor amendment reversed or superseded any of A1–A7.

Two amendments touched conclusions reached in this review:

- **Governor amendment 1** renamed the seam this review had called a "Console
  Projection layer" (challenge 2) to the **Mission Console Model**. The
  challenge and its answer are unaffected; only the name changed.
- **Governor amendment 4** made explicit what challenge 9 argued implicitly —
  that the value of the seam is owning ordering, grouping, visibility,
  disclosure placement and card priority. The responsibility split is now
  normative and test-backed (T21) rather than inferred.

Governor amendment 2 (domain-specific margin labels) refines, and does not
weaken, challenge 3's finding: the contract stays universal and only the
displayed word varies. Challenge 10's binary-mission walkthrough remains valid
because the `margin` applicability field from A3 is retained.

---

## Architecture Freeze — 2026-07-31

**Decision: GO — ARCHITECTURE FROZEN.**

- **All seven Governor amendments are complete.** Each was applied to the RFC
  and verified present before commit; none redesigned a concept or added scope.
- **No open architecture questions remain.** Q1, Q2 and Q3 are ruled and
  recorded in the RFC's Governor Approval section, and the region-ordering
  tension identified by challenge 7 (amendment A7) is **accepted for V1** —
  Regions 3 and 4 are not reordered in this burn.
- **Implementation must not change the frozen contracts without a new Governor
  decision.** Where implementation finds a frozen contract cannot be built as
  specified, it stops and returns to the Governor rather than adapting the
  contract in code.

The residual risks recorded above are accepted as stated. Two remain worth
carrying into the implementation Burn as watch items rather than defects:
`TELEMETRY_FORMAT` retains Finance-leaning values until a real second domain
exists, and `movement` yields no information for two of the four current
missions.

One clarification was made at freeze: the closeout brief transcribed the first
approved amendment as `InstrumentApplicability.essential`. `essential` is a
`TELEMETRY_REGION` value read through `TelemetryItem.display_region`, not an
applicability field. The RFC records the accurate identifier; the discrepancy
is noted there in full.
