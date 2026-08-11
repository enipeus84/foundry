# RFC-017 — Value Provenance Framework

**Status:** **ARCHITECTURE FROZEN — Phase 1 GO; Phase 1 implementation
REMEDIATION REQUIRED.** Governor rulings **GD-1** through **GD-10** are
recorded (2026-08-06); GD-8 and GD-9 remain explicitly deferred and **confer no
implementation authority**. The formal freeze record is
[`../reviews/RFC-017-architecture-freeze-record.md`](../reviews/RFC-017-architecture-freeze-record.md).
Implementation authority is granted for **Phase 1 only** — the Core Value
Provenance Framework, against acceptance criteria **P1-A through P1-H** (§11.1).
Phases 2 and 3 remain architecturally described and require subsequent Governor
authority; Phase 4 and later retain their stated gates.
**Post-freeze amendment (2026-08-10):** Governor rulings **GD-A1** through
**GD-A7** resolve **OBS-017-A** — see §9.1 (new) and §14.1 (new). The merged
Phase 1 implementation (`82f7310`) enforced a stricter rule than the frozen
architecture required; it remains fail-closed and is not unsafe, but requires a
bounded conformance remediation before Phase 2. Formal record:
[`../reviews/RFC-017-OBS-017-A-ruling.md`](../reviews/RFC-017-OBS-017-A-ruling.md).
**Burn:** Architecture Burn (RFC-100 §3), Effort **HIGH** (Core seam);
rulings applied by a governance burn, Effort **LOW**; OBS-017-A amendment
applied by a governance burn, Effort **MEDIUM**.
**Author:** EECOM (architecture Flight Controller role, Claude).
**Date:** 2026-08-06. **Amended:** 2026-08-06 (Governor rulings GD-1–GD-10);
2026-08-10 (Governor rulings GD-A1–GD-A7, OBS-017-A).
**Frozen:** 2026-08-06 (Governor freeze gate, head `b8cc0ed`).
**Number:** **settled — RFC-017** by Governor ruling GD-1 (2026-08-06,
**R1 approved**). *Asset Detail & Provenance Investigation* is re-earmarked as
an **unnumbered future consumer boundary**, expressly amending GD-1 of RFC-016
and, through it, RFC-015 ruling G3. See §0.
**Depends on:** RFC-001 (Core domain — Metric Provider contract, `Subject`,
event grammar, closed vocabularies), RFC-011 (Asset & Telemetry Acquisition —
canonical observations, evidence grades, bitemporal reads).
**Consumes, does not change:** RFC-006 (Mission Assessment), RFC-007/008/009
(the four Finance missions), RFC-015 (telemetry stream lifecycle), RFC-016
(Mission Targets).
**Self-review:** [`../reviews/RFC-017-architecture-self-review.md`](../reviews/RFC-017-architecture-self-review.md)
**Architecture report:** [`../rfc-017-architecture-report.md`](../rfc-017-architecture-report.md)

---

## Required architectural questions — where each is answered

The brief requires ten questions to be answered. This table is the reviewer's
index; it is not a summary and does not substitute for the sections.

| # | Question | Answered in |
|---|---|---|
| 1 | What constitutes a provenance record? | §4.2 |
| 2 | Is provenance canonical state or deterministic projection? | §3 — **deterministic projection** |
| 3 | How should recursive explanations work? | §5 |
| 4 | What types of contribution exist? | §4.3 |
| 5 | How are derived values distinguished from observed values? | §4.2, `PROVENANCE_NODE_KIND` |
| 6 | How is completeness represented? | §4.5 — **derived, never declared** |
| 7 | How are missing or partial explanations handled honestly? | §4.4, §4.5, §7.2 |
| 8 | How does provenance interact with immutable canonical events? | §3.3, §3.5 |
| 9 | What contracts should downstream RFCs consume? | §6 |
| 10 | What boundaries must remain outside RFC-017? | §6.4, §12 |

Governor rulings **GD-1 through GD-10** are recorded in §14 and applied
throughout. §0 carries the two that changed the document's own governance
position: the number (GD-1) and the programme sequence (GD-10).

---

## 0. Naming and governance check *(Check 0 — performed before drafting)*

> ### Governor ruling GD-1 — **settled, 2026-08-06**
>
> **This mission is RFC-017 — Value Provenance Framework.** Recommendation
> **R1** of §0.3 is approved. *Asset Detail & Provenance Investigation* is
> **re-earmarked as an unnumbered future consumer boundary**, expressly amending
> GD-1 of [RFC-016](RFC-016-mission-target-framework.md) and, through it,
> RFC-015 ruling **G3**.
>
> The displaced boundary keeps its subject, its rare-investigation rhythm and
> its successor status, and loses only its number. It is recorded as a
> **consumer** of this RFC — a surface that renders explanations, above a
> substrate that produces them — and it takes a number when a burn is
> commissioned for it.
>
> The amendment is recorded beside the text it amends, with the original wording
> retained verbatim in every case (RFC-100 §9.2): RFC-016 §0 and §14.1, RFC-015
> §0 and §18, and [`index.md`](index.md). This is the second recorded move of
> this boundary and the second time it has moved by decision rather than by
> silent consumption — the distinction that separates it from the standing
> RFC-013 governance debt.
>
> §0.1–§0.3 below are retained **unchanged** as the analysis that produced the
> ruling. They are a record of a question that is now closed, not an open
> question. The [`index.md`](index.md) row that §0.3 withheld was added by this
> governance burn once the ruling existed, closing the declared FR-017 gap.

### 0.1 The number is already spoken for, and the subject is adjacent

RFC-016 ruling **GD-1** (2026-08-06) reassigned the *Asset Detail & Provenance
Investigation* boundary from RFC-016 to **RFC-017**, expressly amending RFC-015
ruling G3. That reassignment is recorded in three places:
[`RFC-016-mission-target-framework.md`](RFC-016-mission-target-framework.md) §0
and §14.1, [`RFC-015-capture-target-registry.md`](RFC-015-capture-target-registry.md)
§0, and [`index.md`](index.md), which states: "**RFC-017 is reserved for *Asset
Detail & Provenance Investigation*.** … No architecture exists for RFC-017; it
requires its own burn and its own boundary challenge."

This burn was briefed as **RFC-017 — Value Provenance Framework**. Unlike the
RFC-016 collision — where the briefed subject (*strategic intent*) and the
reserved subject (*provenance investigation*) shared nothing — these two share
a word and a neighbourhood. That makes the question harder, not easier, and it
must be answered before the number is used.

### 0.2 Are they the same boundary? — *No, and the rhythm test says so*

RFC-012 §2.8 established the test, and RFC-015 §0 applied it to this very
boundary. Reapplied here:

| | Reserved boundary (GD-1) | This burn (briefed) |
|---|---|---|
| **Subject** | Asset Detail page, provenance timeline, audit browsing | the canonical contract by which any value is explained |
| **Rhythm** | rare investigation — "why does Foundry believe this?" | none — it is not a surface and has no rhythm |
| **Shape** | a **surface** | a **substrate** |
| **Deliverable** | routes, views, interaction | contracts, vocabularies, invariants |
| **Brief's own scope** | — | UI, Flight Deck, capture, editing, corrections, endpoints all **explicitly excluded** |

RFC-015 §0 already drew this exact line, in these words: registration
provenance "is an architectural property of the registration event", whereas
provenance *investigation* "is a **surface**". The briefed boundary is the
third thing neither document named: the **structure** an investigation surface
would render and which no part of the platform currently produces (§1).

The brief's own programme diagram places presentation at RFC-020 (Flight Deck
Intelligence), which is where a provenance-investigation surface belongs by
rhythm. So the reserved boundary is not deleted by this burn; it is
**decomposed**, exactly as RFC-015 decomposed the displaced *Asset Registry &
Provenance* boundary and the Governor accepted.

### 0.3 Recommendation — *the Governor rules; EECOM does not*

**Recommended (R1): file this document at RFC-017, and re-earmark the surface
half — Asset Detail, provenance timeline, audit browsing — to a successor
number by explicit, dated ruling amending GD-1.**

The distinguishing facts against the RFC-013 governance debt are the same two
that carried R1 in RFC-016 §0.3, and they hold here:

- The displacement would be **decided and recorded**, not silent.
- The displaced boundary is unstarted, unbriefed, and carries no architecture,
  no branch and no implementation.

The additional fact this case has and RFC-016's did not: the substrate is
**prerequisite** to the surface. An Asset Detail page built before this
contract exists would have to invent a decomposition in the renderer — the
RFC-012 R9 failure mode ("the console silently becomes a computation layer with
no provenance"). Sequencing substrate before surface is the correct order
regardless of which number each takes.

**Alternative (R2): renumber this document to the next free number and leave
RFC-017 reserved as GD-1 assigned it.** This costs a file rename and a
contradiction with the brief, and is correct if the Governor judges that a
ruling one week old should not be amended for a later brief's convenience.

**Either is acceptable. Neither may be assumed.** EECOM has no authority to
overwrite a recorded ruling (RFC-100 §2.4). Per RFC-100 §6.0 a briefed number
"is a statement of fact, not a grant of authority" and "never substitutes for a
recorded Governor act". This document therefore carries the briefed number for
legibility and **does not amend [`index.md`](index.md)**; the index row is
withheld until the number is ruled, exactly as RFC-016's Phase 1 burn withheld
its own. The resulting FR-017 coherence gap is declared, not hidden (see the
architecture report).

### 0.4 The programme sequence — collisions confirmed and ruled

> ### Governor ruling GD-10 — **settled, 2026-08-06**
>
> **The programme-number collision is confirmed. RFC-018, RFC-019 and RFC-020
> are not reserved numbers and must not be cited as such.**
>
> | Briefed as | Ruled |
> |---|---|
> | RFC-018 — Mission Target Capture | **Not a new boundary.** It is adoption of the RFC-016 contract — that RFC's own Phase 3 declaration surface — **unless a future architecture burn proves a genuinely new boundary** |
> | RFC-019 — Mission Assessment | **Already belongs to RFC-006**, merged, with four live providers |
> | RFC-020 — Flight Deck Intelligence | **Unnumbered.** Future Flight Deck intelligence takes a number when a burn is commissioned for it |
>
> **RFC-014 remains reserved for *Governed Corrections*.** Beyond it, no number
> is reserved for future programme work.

The brief positioned this RFC in a numbered programme sequence. Restated under
the ruling, with the numbers removed and only the ordering retained — because
the *ordering* was the useful part and the numbering was the collision:

```text
Telemetry Acquisition              RFC-011   merged
Value Provenance                   RFC-017   this document
Mission Targets                    RFC-016   merged
Mission Target capture             ——        RFC-016 adoption (Phase 3)
Mission assessment                 RFC-006   merged
Flight Deck intelligence           ——        unnumbered future boundary
Asset detail & provenance          ——        unnumbered future consumer (GD-1)
```

**This RFC claims no number but its own, designs for none of these, and depends
on none of them.** The dependency runs the other way: each is a potential
consumer of the contract in §6, and a consumer that cannot obtain a
decomposition does not compute one (RFC-012 R9, §6.1).

One boundary relationship survives the ruling and is worth keeping in view:
**corrections and provenance meet.** "This contribution is wrong" is a
correction, not an explanation, and §12 excludes corrections from this RFC for
that reason. RFC-014 is where that lands.

### 0.5 Naming discipline *(binding)*

The bare word **provenance** already carries four distinct meanings in this
repository. All five senses must remain distinguishable in code, documents and
UI:

| Term | Owner | Meaning |
|---|---|---|
| `Claim.provenance` / `kernel.why()` | RFC-001 | the source event ids behind one Claim (`canon.py:39`, `kernel.py:200`) |
| Entity `provenance` lists | RFC-001/002 | the event ids that shaped one entity (`finance/entities.py:90` and twelve siblings) |
| Acquisition provenance chain | RFC-011 | `evidence_id → proposal_id → confirming actor` on a canonical observation (`core/acquisition.py:937`) |
| Registration provenance | RFC-015 §8 | declaration-event metadata on a capture target |
| **Value Provenance** | **this RFC** | the structured explanation of how one observable value came to have its magnitude |

**Rule.** This RFC's concept is always written *Value Provenance* in prose and
`ValueProvenance` / `ProvenanceNode` in code, never the bare word "provenance"
where any of the other four could be read. The module is
`core/value_provenance.py`. Renaming any existing `provenance` field is **out
of scope** (FR-004): they are live contracts on merged RFCs.

This is the RFC-016 §0.5 discipline, applied to a word that is four times more
overloaded than *target* was.

---

## 1. Problem statement

Foundry reports values. `finance.pension_wealth`, `finance.accessible_assets`,
`finance.net_worth`, `finance.property_current_equity` and twenty more resolve
to a number, a unit and a status, and the Flight Deck renders them.

**No value in Foundry can be decomposed into what produced it.** The platform
can say *which events were touched* while computing a number. It cannot say
*which part of the number each event produced*, *whether the parts add up*, or
*what was left out*.

Six independent, verifiable defects produce that gap. Each is stated with a
file and line, not asserted.

### 1.1 References are a bag, not a structure

`MetricResult` (`src/foundry/core/metrics.py:48-64`) carries
`input_references`, `evidence_references` and `assumption_references` — three
flat, unordered `tuple[str, ...]` of event ids. The contract answers "which
events were consulted?" and cannot answer "which part of the value did each
support?", because the association between a reference and a portion of the
value is not in the type.

The rendered consequence is at `src/foundry/mission_control.py:1566` and
`:2012`, where the honesty signal a household actually sees is:

```text
{len(result.input_references)} INPUT EVENT(S)
```

A count. Not a composition.

### 1.2 The decomposition is computed and then discarded

`FinanceMetricProvider._store_total`
(`src/foundry/finance/metrics.py:528-550`) walks each owned entity, values it,
converts it, and accumulates:

```python
total += converted          # metrics.py:546
refs.extend(value_refs)     # :547
...
return total, refs, limitations   # :550
```

At line 546 the per-entity contribution is known exactly. At line 550 it is
gone: what returns is a scalar and a flattened reference list. The same shape
recurs in `_attributed_value` (`:552-581`), `_position_totals` (`:583-602`) and
`_average_essential_outflow` (`:613-640`).

`FinancePensionMetricProvider._pension_wealth`
(`src/foundry/finance/pension_metrics.py:102-184`) is the sharpest instance,
because it discards *three* structures at once:

```python
total += converted * weight            # pension_metrics.py:156
refs.extend(latest.provenance)         # :158
if conversion_ref: refs.append(...)    # :160
...
tuple(sorted(set(refs)))               # :180  — deduplicated and re-sorted
```

- **Which account contributed how much** is discarded at `:156`.
- **The multiplicative factors are unreferenced.** `weight` comes from the
  account's ownership links (`:153`). The ownership declaration that halves a
  jointly-held pension **never enters `refs`**. A household asking why the
  pension is £82,000 is shown valuation events and an exchange rate, and is not
  shown the fact that determined half of the answer.
- **`sorted(set(refs))` at `:180`** destroys even the ordering that might have
  allowed a consumer to guess the association.

### 1.3 Explanation exists — as presentation

Foundry already ships the exact decomposition the brief names as a success
criterion. `MortgageFreedom` telemetry
(`src/foundry/finance/mortgage_assessment.py:716-732`) emits property equity as
a flat list of sibling cards:

```text
"EQUITY COMPOSITION · PRINCIPAL REPAID"      qualifier "INITIAL MORTGAGE − CURRENT BALANCE"
"EQUITY COMPOSITION · VALUATION MOVEMENT"    qualifier "CURRENT VALUE − PURCHASE PRICE"
"PROPERTY ACQUISITION · INITIAL DEPOSIT"
```

The relationship between the whole and its parts survives **only in a display
string** — a `display_group` prefix and an English `qualifier`
(`core/mission_assessment.py:251-257`). Nothing machine-readable states that
these three are components of `finance.property_current_equity`. A second
consumer — an API, an export, a different renderer, an audit — would have to
parse the label to recover the structure, which is precisely the defect RFC-016
§1.2 found when a mortgage household's intent survived only in a mission name.

The source comment at `:716-717` states the intent plainly and shows how far
the code can carry it:

> "These observations explain current equity; they do not determine mission
> policy or correct one another."

The intent is right. There is no contract to express it in.

### 1.4 Completeness is prose

`mortgage_assessment.py:816-824` computes the residual between the components
and the whole — and then writes it into English:

```python
attributed_equity = initial_deposit + principal_repaid + valuation_movement
difference = current_equity - attributed_equity
if not math.isclose(difference, 0.0, abs_tol=.01):
    limitations.append(
        "The explanatory components differ from current equity "
        f"by £{abs(difference):,.2f}; …")
```

This is the right *behaviour* — honest, non-correcting, visible — in the wrong
*medium*. A `limitations` entry is a `tuple[str, ...]` (`core/metrics.py:62`).
It cannot be tested against, filtered, aggregated, or rendered as anything but
a sentence, and it exists for exactly one metric in one assessor.

One typed precedent exists and proves the shape is buildable:
`Reconciliation` (`core/acquisition.py:979-987`) carries `derived_total`,
`supplied_total` and a typed `difference`. It applies to one case — a container
against a supplied statement total — and to nothing else.

### 1.5 Evidence is over-attributed

`PensionAssessment._contribution_items`
(`src/foundry/finance/pension_assessment.py:1184-1241`) accumulates **one**
reference list across every contribution field:

```python
for field in RATE_FIELDS:            # employee, employer, salary sacrifice
    record = self.evidence.latest(account_id, field, request.as_of)
    if record is None: continue
    refs.append(record.event_id)     # :1197  — one shared list
```

and then attaches `tuple(refs)` (`:1213`) to **all three** emitted metrics:
`finance.pension_employee_contributions`,
`finance.pension_employer_contributions` and
`finance.pension_total_contributions`.

A household drilling into *employee* contributions is therefore shown the
*employer* contribution evidence as support for that figure. The number is
correct; the explanation is false. Under FR-008 that is a defect, and it is not
fixable inside the current contract, because the contract has one bag per
result and no place to put a per-component association.

### 1.6 Exclusions disappear, and the headline does not say so

`_store_total` skips an entity that cannot be valued (`metrics.py:540-541`),
one valued only after `as_of` (`:504`, `:513-515`), and one with no available
exchange rate (`:543-545`). Each appends a prose limitation. The total is then
returned through `_available` (`:644-651`), which sets:

```python
status="available"
```

unconditionally. **A partial sum is presented with the same status as a
complete one.** "Accessible Assets £198,000" carries no structural indication
of whether it summed seven assets or four.

`pension_metrics.py` is worse in one specific place. Four exclusion paths
append a limitation (`:131`, `:138`, `:149`, and the DB conflict at `:129`),
and one does not:

```python
weight = self._weight(links, attribute_to)
if weight <= 0:
    continue                       # pension_metrics.py:154-155
```

An account excluded because the scope holds no share of it is dropped with **no
limitation, no reference and no trace**. Nothing anywhere in the system records
that it was considered and rejected.

### 1.7 What these six add up to

Foundry's constitutional thesis is that "provenance is preserved throughout the
system" ([`../architecture.md`](../architecture.md), *The thesis*), and at the
Claim layer it is: `kernel.why()` (`kernel.py:200`) returns source events,
extraction actor, evidence and revision history for any claim.

**No equivalent exists for a value.** RFC-011 §AC-7 asserted the goal —
"for any canonical figure, `why()` reaches interpreter id + version and evidence
`payload_hash` without gaps" — and the `why()` that exists resolves claims, not
figures. The gap is not that the platform lost provenance. It is that **value
provenance was never given a shape**, so each provider re-invents a partial one
in display strings and prose, and no two agree.

---

## 2. Domain concept: what is a Value Provenance?

> **A Value Provenance is the deterministic, reproducible explanation of one
> observable value: the contributions that produce it, each anchored in
> immutable canonical facts, together with a derived and unfalsifiable
> statement of how completely those contributions account for it.**

### 2.1 The three-way separation *(the spine of this framework)*

RFC-016 §2.1 separated intent, policy and evidence, and refused to let them
re-fuse. The same move, one layer down:

| | Owns | Answers | Owner |
|---|---|---|---|
| **Evidence** | canonical observations and their grades | *what was observed?* | RFC-011 / RFC-015 |
| **Calculation** | the rule that turns evidence into a number | *what is the value?* | the domain (Metric Providers, assessors) |
| **Explanation** | the structure of that number's composition | *where did it come from?* | **this RFC** |

Today the third is fused into the second and leaks into presentation (§1.3).
Everything below follows from pulling them apart.

**The framework never computes a value.** It receives a value that a domain
already produced, and the parts that domain says produced it, and it verifies
the relationship between them. If the domain's arithmetic is wrong, the
framework will say the parts do not add up; it will not fix them, and it will
not compute an alternative.

### 2.2 What a Value Provenance answers, and what it must never answer

| Question | Answered? |
|---|---|
| What is this value composed of? | **yes** |
| Which canonical facts support each component? | **yes** |
| Do the components account for the whole? | **yes**, and the answer cannot be faked (§4.5) |
| What did the rule want and not get? | **yes** (§4.4) |
| Can each component itself be explained? | **yes**, on request (§5) |
| Is this value good, bad, on track, at risk? | **never** — assessment, RFC-006 |
| Is this value correct? | **never** — a provenance reports a residual; it does not adjudicate |
| Should this value be different? | **never** — corrections, RFC-014 reserved |
| Why did the household choose this? | **never** — intent, RFC-016; `basis` is prose and is never parsed |
| How should this be displayed? | **never** — presentation, outside this RFC |

### 2.3 Domain agnosticism, stated as a testable property

The framework must contain no finance concept. The test is not "does it read
neutrally" but the FR-011 regression already established for
`core.acquisition`: **the module source contains no domain vocabulary**, and
Phase 1 is proven against a **mock domain only** (§10).

Concretely, the framework must never learn:

- that money adds and percentages do not;
- that a deposit precedes a mortgage;
- what an exchange rate is;
- that a pension is illiquid;
- what any `finance.*` metric id means.

Everything domain-shaped enters through one seam (§6.2) and one free-text,
never-parsed label (§4.2).

---

## 3. Canonical state or deterministic projection?

**Decision: a Value Provenance is a deterministic projection. It is never
canonical state, and this RFC introduces zero canonical events.**

This is the load-bearing decision of the framework and the one most likely to
be argued, so the alternatives are stated before the answer.

### 3.1 Options considered

| Option | Verdict |
|---|---|
| **Canonical events recording each explanation** (`core.value_provenance.declared`) | **Rejected** — see §3.2 |
| Provenance stored as fields on `MetricResult` | **Rejected** — `MetricResult` is a frozen RFC-001 contract (000 §13.3) with live consumers at `mission_control.py:1554-1556`, and a value that is not a metric (a telemetry component, an assessment intermediate) could then never be explained |
| Provenance as a `Claim` in the Canon | **Rejected** — a Claim is a *witnessed belief* with model provenance and a confidence (`canon.py:34-48`); an arithmetic decomposition is neither witnessed nor believed, and routing it through `claim.derived` would put a model-shaped path around a deterministic fold (FR-012) |
| **A deterministic projection over canonical state, computed on request** | **Adopted** |

### 3.2 Why canonical events are wrong here — three arguments, in order of force

**One. It would put a fold's output back into its own input.**
[`../architecture.md`](../architecture.md) invariant 2 states that "the Canon
has no write path of its own — it is a fold over the log and is always
rebuildable". A provenance is by construction the *explanation of a
derivation*: it is downstream of every projection it describes. Writing it to
the log would create a second source of truth for something the first source
already determines, and the two could disagree — at which point the platform
would have to decide which to believe, and no rule can be right.

**Two. It would make historical explanation *less* durable, not more.** If an
explanation is stored, then improving a calculation leaves every stored
explanation stale and wrong, and the only remedies are rewriting history
(forbidden) or accumulating explanations that contradict the values they
explain. If an explanation is computed, asking with a historical `known_at`
reproduces the historical answer from immutable inputs (§3.3).

**Three. It is the category the platform has already ruled on.**
[`../architecture.md`](../architecture.md) architecture observation 1:

> "Mission assessments are observations derived from evidence; facts live in
> the append-only event log. … An assessor and its renderer have no event-log
> write path, so an assessment never becomes canonical observed state merely by
> being shown."

An explanation of a value is in exactly that category, and for exactly that
reason. Making provenance canonical would mean that *looking at* a value
changes the log — the failure this observation exists to forbid.

### 3.3 What "immutable" then means — and why it is a stronger guarantee

The brief requires that "historical explanations must never be rewritten". A
projection satisfies this more completely than storage does: **there is nothing
to rewrite.** What must be guaranteed instead is **reproduction**:

> Same log · same `as_of` · same `known_at` · same declared calculation version
> ⇒ byte-identical provenance.

The mechanism already exists and is adopted rather than invented. Every
provenance query is **bitemporal**, carrying both:

| Parameter | Meaning | Precedent |
|---|---|---|
| `as_of` | valid time — the world as at this instant | `MetricRequest.as_of` (`core/metrics.py:40`) |
| `known_at` | transaction time — using only facts the log held by this instant | `CanonicalObservationProjection.observations(..., known_at=)` (`core/acquisition.py:946-949`) |

`known_at` is what makes historical explanation honest. Without it, a
retrospectively-recorded observation would silently improve last year's
explanation, and the log would assert foresight it did not have — the same
certainty inflation RFC-016 §7.3 refused for target resolution, and the reason
`CanonicalObservationProjection` filters `event["ts"] > known_at` at `:949`
before anything else.

**Consequence, stated as a rule.** A provenance query that omits `known_at`
defaults to *now* and must be labelled as a current-state explanation. It may
never be presented as the explanation that was given at an earlier time.

### 3.4 The honest limit: calculation code is not in the log

Determinism under replay has a boundary and the framework must not overstate
it. The event log holds facts; it does not hold the arithmetic. If a domain
changes how a value is composed, replaying an old log through today's code
produces **today's explanation of yesterday's facts** — which is not the same
thing as yesterday's explanation.

This is pre-existing (it is why `MetricResult.calculation_version` exists,
`core/metrics.py:56`) and is not created or solved by this RFC.

**Storing explanations would not solve it — it would relocate it.** A stored
explanation survives a calculation change intact, and then *contradicts* the
value the current code produces from the same log. The platform would hold two
irreconcilable answers with no rule that can pick correctly between them. A
computed explanation at least fails in the honest direction: it is either
reproducible or refused. This is the strongest argument for canonical storage
and it is why it still loses *(self-review A1)*.

Three rules contain the drift:

1. Every `ProvenanceNode` carries the `calculation_version` of the rule that
   produced it. An explanation without one is refused.
2. A provenance requested at a `known_at` whose recorded calculation version
   differs from the version the explainer can produce is reported as
   **`unavailable` at that version** — never silently re-derived under the
   current rule and presented as historical.
3. Retaining executable historical calculation versions is a **separate
   boundary** this RFC does not claim (watch item **W3**).

Rule 2 is the FR-008 position: an explanation that cannot be reproduced is
unknown, and unknown is never assumed.

### 3.5 Zero canonical events *(invariant)*

**This RFC authorises no event kind, amends no payload, and adds no writer.**
Not "none in Phase 1" — none, ever, within this boundary. Any future need for a
canonical provenance fact is a new Governor decision under a different RFC.

Three consequences follow and are each testable:

- No module in this framework imports `EventLog.append`, directly or
  transitively.
- Rendering, exporting, replaying or querying a provenance appends nothing —
  asserted by log comparison across a full render (§10).
- A provenance is deletable and rebuildable, like `Canon` and every other
  projection, and nothing outside the log is load-bearing.

---

## 4. The domain model

Five shapes and four vocabularies. The Governor's guidance was to prefer "small,
durable abstractions over comprehensive modelling", so §4.6 states explicitly
what was left out and why.

### 4.1 `ValueReference` — what is being explained

```text
ValueReference(
    subject:      Subject,        # reuses core/scope.py:21 — party, employer,
                                  # mission, or a domain-declared resource kind
    value_id:     str,            # domain-owned identifier of the quantity
                                  # (e.g. a metric_id); opaque to Core
    as_of:        float,
    known_at:     float,
)
```

`value_id` is **opaque**. Core never parses it, never pattern-matches on a
prefix, and never infers meaning from it. It is the routing key to an explainer
(§6.2) and nothing else — the `MetricRegistry` discipline
(`core/metrics.py:103-105`: "No business calculation logic lives here — routing
only"), reused rather than re-derived.

**No display name, label or slug is ever a `value_id`, an identity or a lookup
term.** This is RFC-015 invariant 1 and RFC-016 §8 invariant 2, upheld
unchanged.

### 4.2 `ProvenanceNode` — the provenance record

> **Question 1: what constitutes a provenance record?** This.

```text
ProvenanceNode(
    reference:            ValueReference,
    kind:                 PROVENANCE_NODE_KIND,   # observed | derived
    status:               METRIC_STATUS,          # reused, not re-invented
    quantity:             float | None,
    unit_or_currency:     str | None,
    calculation_version:  str,
    anchors:              tuple[str, ...],        # canonical event ids
    contributions:        tuple[Contribution, ...],
    exclusions:           tuple[Exclusion, ...],
    completeness:         EXPLANATION_COMPLETENESS | None,   # derived — §4.5
    residual:             float | None,                      # derived — §4.5
    label:                str,                        # domain-owned, never parsed
)
```

**`completeness` is `None` for an `observed` node**: a terminal fact makes no
claim about coverage, and forcing it into one of three decomposition states
would be a category error. It is `None` in one further case — whenever
`quantity` is `None`, because there is then no magnitude for the parts to
account for (§4.5) *(self-review A2, A8)*.

**Contribution and exclusion ordering is part of the contract.** An explainer
must emit them in an order that is deterministic under replay, and the
framework **never reorders them** — ordering by significance, magnitude or
label is presentation and belongs to a consumer. Without this rule, byte-identical
reproduction (§3.3) does not hold *(self-review A10)*.

**`kind` answers exactly one question: does the explanation continue here?**

| Kind | Meaning | Structural rule |
|---|---|---|
| `observed` | the quantity is asserted by canonical state; the explanation terminates | **≥1 anchor, zero contributions** |
| `derived` | the quantity is produced from contributions under a stated rule | **≥1 anchor or ≥1 contribution**, and a non-empty `calculation_version` |

```text
PROVENANCE_NODE_KIND = ClosedVocabulary("provenance_node_kind",
    {"observed", "derived"})
```

**Two values, deliberately.** `observed` is a statement about *where the
explanation stops*, not about epistemic quality. Quality is already modelled:
`EVIDENCE_GRADE` (`core/vocab.py:90-93`) grades a fact as `authoritative`,
`declared`, `confirmed`, `extracted` or `assumed`, and this RFC neither
duplicates nor replaces it. A value sourced from a forecast assumption is
`observed` at this layer — its explanation genuinely terminates at the
assumption's declaration event — and is graded `assumed` by the existing
vocabulary. Adding a third node kind for "assumed" would put one fact in two
vocabularies, which is the ambiguity RFC-016 §13 rejected for `target_range`.

**`kind` is declared by the explainer and verified by Core, not inferred.**
Inferring `observed` from "has no contributions" would mislabel the honest case
in §4.5 — a value the domain knows is composite but cannot decompose — as a
terminal fact, which is a lie about where the explanation ends.

**`status` reuses `METRIC_STATUS`** (`core/vocab.py:124-127`:
`available · unavailable · unsupported · stale · error`) unchanged and
unextended. A near-identical parallel vocabulary would be two ways to say one
thing.

**`label`** is domain-authored display text, carried so a consumer need not
reverse-engineer meaning from a `value_id`. It is **stored and rendered, never
parsed, never an identity, and never used in any decision** — the `basis`
discipline of RFC-016 §9, applied here. Unlike `basis` it is not
household-authored and therefore carries no irreversibility hazard: it is
produced by domain code at read time and is not in the log.

### 4.3 `Contribution` — the edge, and the only contribution types that exist

> **Question 4: what types of contribution exist?** Three, and they describe
> arithmetic roles, not domain meanings.

```text
Contribution(
    role:        CONTRIBUTION_ROLE,
    quantity:    float | None,     # required for increases/decreases, in the
                                   # parent's unit (§6.3); MUST be absent for
                                   # contextual
    contributor: ValueReference,   # expandable; the recursion point (§5)
    expandable:  bool,             # whether an explainer exists for it
)

CONTRIBUTION_ROLE = ClosedVocabulary("contribution_role",
    {"increases", "decreases", "contextual"})
```

**`quantity` carries one meaning only: the share this contributor takes of the
explained quantity.** A `contextual` contributor takes no share, so it carries
no quantity — its own magnitude is obtained by expanding it (§5.1). The
first draft let `quantity` mean "share" for additive roles and "magnitude" for
contextual ones, which is one field with two meanings and the ambiguity §1.3
exists to remove *(self-review A5)*.

| Role | Meaning | Quantity | Counts toward completeness? | Repository instance |
|---|---|---|---|---|
| `increases` | carries a positive share of the explained quantity | required, parent's unit | **yes** | each account in `_store_total` (`metrics.py:546`) |
| `decreases` | carries a negative share of it | required, parent's unit | **yes** | liabilities in `_net_worth` (`metrics.py:188-192`) |
| `contextual` | required to produce the quantity but carries **no share** of it | **absent**; any unit | **no** | the exchange rate at `aggregation.py:127-134`; the ownership `weight` at `pension_metrics.py:156`; the unit price at `acquisition.py:996-1000` |

**Why three and not two.** A signed quantity was considered and rejected
(§13): it conflates "a £300,000 liability" with "minus £300,000", makes
`decreases` with a negative quantity ambiguous, and cannot express `contextual`
at all. `contextual` is not optional decoration — it is the only honest way to
express that the ownership share which determined **half of §1.2's pension
figure** participated in the answer without being a part of it. Today that
factor appears nowhere at all.

**Why not more.** No role for "derived from", "adjusted by", "netted against"
or any of the twenty domain relationships a finance modeller would want.
Adding one is a governed Core change (`core/vocab.py:58-62` — a
`ClosedVocabulary` refuses `extend()` outright), which is the correct cost for
a new unit of meaning, and is the reasoning RFC-016 §5.3 used to cut
`TARGET_DIMENSION` from four values to two.

### 4.4 `Exclusion` — what the rule wanted and did not get

> **Question 7, part one.**

```text
Exclusion(
    subject:  Subject,             # the contributor that could not be used
    reason:   EXCLUSION_REASON,
)

EXCLUSION_REASON = ClosedVocabulary("exclusion_reason",
    {"unobserved", "out_of_period", "incommensurable"})
```

| Reason | Meaning | Repository instance |
|---|---|---|
| `unobserved` | in scope, but no supporting observation exists | `metrics.py:515` "no valuation observed"; `pension_metrics.py:136-141` |
| `out_of_period` | supported only by facts outside the requested `as_of` / `known_at` window | `metrics.py:504`, `:513`; `pension_metrics.py:137-140` |
| `incommensurable` | supported, but not expressible in the parent's unit | `metrics.py:544` "no exchange rate"; `pension_metrics.py:148-152` |

An `Exclusion` carries **no quantity**, because if the quantity were known the
item would not be excluded. Attaching an estimate would be exactly the
inference FR-008 forbids.

**An exclusion is structurally "a contributor the rule could not quantify".**
Folding it into `Contribution` — an additive role with no quantity — was
considered and rejected (§13): it would delete a shape and a vocabulary, and it
would delete the *reason*, which is the honest part. §1.6 shows a platform that
already loses the reason, and in one path loses the fact entirely
*(self-review A9)*.

**Binding distinction — an exclusion is not a scope boundary.** An exclusion is
a contributor *the rule wanted and could not use*. A value the rule never
included is **not an exclusion and must never be reported as one**.
`finance.accessible_assets` deliberately excludes pensions, property and
vehicles by definition (`metrics.py:378-387`); those are not exclusions, they
are the metric's meaning. Without this rule every value would report the whole
estate as missing, and the completeness signal would be worthless.

**The silent-drop case is closed by construction.** `pension_metrics.py:154-155`
drops a zero-weight account with no limitation and no reference. Under this
contract that account is either a `contextual`-weighted contributor with
quantity zero, or an `Exclusion` — and an explainer that emits neither, while
its own arithmetic considered the account, produces a residual it must then
disclose. There is no third path in which the account simply vanishes.

> **Amendment — Governor ruling GD-P2-A, 2026-08-11 (Pension Phase 2 blocker
> clarification).** `EXCLUSION_REASON` gains a fourth closed value,
> `conflicting`, added beside the original three, which are retained
> unamended:
>
> ```text
> EXCLUSION_REASON = ClosedVocabulary("exclusion_reason",
>     {"unobserved", "out_of_period", "incommensurable", "conflicting"})
> ```
>
> | Reason | Meaning | Repository instance |
> |---|---|---|
> | `conflicting` | the contributor is relevant, canonical evidence exists, but two or more canonical facts about it disagree and the domain cannot safely arbitrate between them | `pension_metrics.py:129-134` — an account carrying both DB entitlement evidence and pot-valuation evidence |
>
> **Normative boundary, binding.** `conflicting` **MUST** be used only when
> the contributor is relevant, canonical evidence exists, two or more
> canonical facts disagree, and the domain cannot safely arbitrate between
> them. It **MUST NOT** be used where evidence is simply absent (`unobserved`),
> outside the requested temporal window (`out_of_period`), or expressed in an
> incompatible unit (`incommensurable`) — those three retain their original,
> unamended meaning. No further exclusion values are authorised by this
> amendment; a fifth requires its own Governor ruling. This closes the gap
> identified against `pension_metrics.py:129-134` (§1.6, §7.2): that path
> excludes an account for evidential contradiction, not absence, and none of
> the original three reasons describe that condition without overloading it —
> the option this framework's own alternatives register (§13) already refuses
> for the same reason it refused folding `Exclusion` into `Contribution`.
> Ruling record: [`../reviews/RFC-017-GD-P2-ruling.md`](../reviews/RFC-017-GD-P2-ruling.md).
>
> **What this amendment does not authorise.** No change to `Exclusion`'s
> shape, to any other vocabulary, to the resolver, or to any other frozen
> contract. No Finance explainer. No Phase 2 implementation authority.

### 4.5 Completeness — derived by the framework, never declared by the domain

> **Questions 6 and 7.** This is the most important rule in the document.

```text
EXPLANATION_COMPLETENESS = ClosedVocabulary("explanation_completeness",
    {"complete", "partial", "indivisible"})
```

**A domain never supplies its own completeness.** It supplies the explained
quantity, the contributions and the exclusions. The framework computes the
rest:

```text
if kind = observed  or  node.quantity is None:
    completeness = None                       # no coverage claim is being made
    residual     = None

elif contributions ≠ ∅ and every contribution is contextual:
    completeness = indivisible                # no additive claim is being made
    residual     = None

else:
    attributed   = Σ quantity(increases) − Σ quantity(decreases)
    residual     = node.quantity − attributed
    completeness = complete   if |residual| ≤ tolerance and exclusions = ∅
                   partial    otherwise
```

**A node with no quantity has no completeness.** A `derived` node whose status
is `unavailable` or `unsupported` carries `quantity = None`, and there is
nothing for the parts to account for. Reporting `partial` there would imply an
unexplained magnitude that does not exist *(self-review A8)*.

Three consequences, each load-bearing:

1. **Completeness is unfalsifiable.** A provider cannot claim to have explained
   a value it has not explained, because it does not get to make the claim. In
   a platform whose thesis is honesty about what it knows, a self-reported
   completeness flag would be the first thing to rot.
2. **Zero contributions is representable and honest.** A `derived` node with no
   contributions yields `residual = quantity` and `completeness = partial` —
   "this value is composite and none of it is explained". No fourth vocabulary
   value is needed, and no provider is forced to invent a decomposition in order
   to participate.
3. **`indivisible` is a real state, not an escape hatch.** `units × price`
   (`acquisition.py:996-1000`) and a currency conversion
   (`aggregation.py:108-134`) are fully explained and have no additive
   decomposition. Reporting them as `partial` with a residual equal to the
   whole would be false. `indivisible` requires **at least one** contribution,
   so it cannot be used to mean "I have nothing to say" — that case is
   `partial`.

**Tolerance is declared, never defaulted.** The comparison tolerance is
supplied by the domain descriptor seam (§6.2). **Absent a declared tolerance,
comparison is exact**, so floating-point drift reports `partial`. This is the
correct direction of error: the framework over-discloses and never over-claims.
The shipped precedent for a declared tolerance is
`math.isclose(difference, 0.0, abs_tol=.01)` at `mortgage_assessment.py:820`.

**`residual` is `None` for `observed` and `indivisible` nodes**, because no
additive claim is being made. A residual of `None` is never rendered as zero.

### 4.6 What was deliberately not modelled

Named so the omissions read as decisions, not oversights:

| Not modelled | Why |
|---|---|
| A dimension vocabulary | RFC-016's `TARGET_DIMENSION` is closed at `{currency, duration_months}` for intent. Reusing it would force provenance to inherit a target vocabulary and would refuse to explain a ratio. `unit_or_currency` matching (§6.3) is sufficient and adds nothing |
| Confidence or quality on a node | `EVIDENCE_GRADE` and `MISSION_CONFIDENCE` already exist and belong to their owners. A provenance carries anchors; a consumer reads grades from them |
| Time series / trajectory of an explanation | "how did this composition change?" is answered by asking twice with two `known_at` values. A stored series would be canonical state (§3) |
| Weights, percentages, or "share of total" | derivable by a consumer from quantities. Storing both invites disagreement |
| Contribution ordering or significance | presentation |
| A "correction" or "dispute" edge | RFC-014 (*Governed Corrections*), reserved |
| Domain contribution taxonomies (deposit, growth, interest, relief) | the explicit instruction of the brief, and the reason §7's examples carry their finance meaning entirely in `label` |

### 4.7 Attribution-weighted contributions — Governor clarification GD-P2-B/C, 2026-08-11

*(New subsection. Clarifies existing §4.3/§5.1 mechanics for the Pension
Phase 2 blocker; no Core shape changes.)*

A resource's **intrinsic observed value** (e.g. a pension account's raw pot
valuation) and its **scope-attributed contribution** to a particular parent
calculation (e.g. that account's value as attributed to one household
member's fractional ownership) are not the same semantic value once the
parent's scope weights the resource. Requiring an expanded additive child to
report the parent's declared attributed quantity would force the resource's
own node to lie about its intrinsic value; requiring it to report its
intrinsic value would violate the additive-agreement rule (§5.1, "Loop 2")
against the parent's declared attributed quantity. **Neither corruption is
acceptable, and neither is necessary** — the existing contract already
expresses this distinction without a new shape:

```text
Attributed additive edge (increases/decreases):
    quantity    = the exact scope-attributed amount used by the parent
                  calculation
    expandable  = false        # a deliberate terminal calculation edge,
                                # never an unimplemented child

Contextual sibling — raw resource value:
    role        = contextual   (quantity absent)
    expandable  = true         # resolves independently to the resource's
                                # own observed value, unweighted

Contextual sibling — ownership / weighting fact:
    role        = contextual   (quantity absent)
    expandable  = true         # resolves to the observed share or weight
```

**Normative, binding:**

- An attribution-weighted additive contribution **MUST** carry
  `expandable = false`. It **MUST NOT** be expanded into a node whose
  intrinsic quantity disagrees with the parent's declared attributed
  quantity — this is not a relaxation of §5.1's additive-agreement rule, it
  is avoidance of triggering it, by construction.
- The resource's raw, attribution-independent value and its ownership or
  weighting fact **MUST** be represented as separate `contextual`
  contributions (`quantity = None`), never as the expansion of the attributed
  edge itself.
- Every contextual sibling **MUST** carry the resource's own `Subject`
  (§9.1 VP-SCOPE-4 already permits a contributor's `Subject` to differ from
  its parent's). A consumer **MAY** associate a contextual sibling with its
  owning attributed edge by matching `Subject`, since both name the same
  resource.
- The non-expandable attributed edge's `ValueReference.value_id` **MAY** be a
  stable, deliberately unregistered identifier — an intentional terminal
  calculation edge, not an unimplemented one (§6.2's registry consistency
  check, `expandable = false` paired with a registered explainer for the same
  `value_id`, remains invalid and unchanged).
- This clarification **MUST NOT** be read as adding attribution or
  calculation-context fields to `ValueReference`, or as encoding attribution
  into `Subject`. `Subject` continues to mean identity only (§9.1, OBS-017-A);
  attribution is expressed entirely through which `Contribution`s a node
  chooses to emit and how it sets `expandable`, both already-frozen fields.

No field on `ValueReference`, `Contribution`, `ProvenanceNode`, or `Exclusion`
changes. No resolver logic changes: `_verify_expanded_contribution` is
already, structurally, only invoked for expanded, non-`contextual`
contributions — this clarification changes no code path, only which shape a
domain explainer chooses to emit. Ruling record:
[`../reviews/RFC-017-GD-P2-ruling.md`](../reviews/RFC-017-GD-P2-ruling.md).

---

## 5. Recursive explanation

> **Question 3.**

### 5.1 Recursion is by request, and always bounded

Every `Contribution.contributor` is a `ValueReference`, so asking for its
provenance is the same operation applied one level down. There is no separate
"child" type and no depth built into the record.

**Expansion is lazy and bounded.** A query carries a `max_depth`; the resolver
expands no further. `Contribution.expandable` states whether an explainer
exists for a contributor, so a consumer can distinguish **"this is a leaf"**
from **"this is where you stopped"** — a distinction a truncated tree cannot
express.

**Expansion is also a verification step.** When an additive contributor is
expanded, its node's `quantity` must equal the contribution's declared
`quantity`, in the same unit and within the same tolerance. A disagreement is a
**conflict**: the parent's provenance becomes `unavailable` rather than
presenting a decomposition whose parts do not agree with themselves. Without
this rule a domain could declare a contribution of £61,200 from a node that
reports £122,400, and nothing would notice *(self-review A6)*. Contributors that
are not expanded — beyond the depth bound, or with no explainer — are not
verified, and the framework does not claim they are.

The failure mode being designed against is in the repository.
`ValuationLenses.market_value` (`core/acquisition.py:1002-1015`) recurses
eagerly over the whole containment tree and flattens every level's inputs into
one tuple at `:1007`:

```python
observations = tuple(item for part in parts for item in part["inputs"])
```

By the time it returns, the tree that produced the number is gone and only a
flat bag of observations remains — §1.1's defect, generated by the recursion
itself. Bounded, lazy expansion preserves the structure precisely because it
never has to flatten it.

Explaining `finance.accessible_assets` at unbounded depth would otherwise walk
every account, every transaction and every position in the household — a real
cost on a platform whose per-request replay has no caching policy
([`PROJECT_STATUS.md`](../../PROJECT_STATUS.md), *Open Architectural Debt*).

### 5.2 A graph, not a tree — diamonds are legal, cycles are refused

The same contributor may legitimately support several parents: one exchange-rate
observation is `contextual` to every conversion in a household total. So the
overall structure is a **directed acyclic graph**, and any single explanation is
a **tree walked over that graph**. Node identity is `ValueReference`, so a
consumer can deduplicate; the framework never claims double counting merely
because a reference appears twice.

**A cycle is a conflict, not a truncation.** If expansion reaches a
`ValueReference` already on the current path, that node's provenance is
**`unavailable` and the conflict is surfaced**. It is never resolved by
stopping at an arbitrary depth, because a silently truncated cycle renders as a
plausible, wrong tree. This is RFC-016 §7.2 rule 5 and RFC-015 §3.4, applied
unchanged: ambiguity is refused, never resolved by guess.

### 5.3 Double counting — what is detectable, and what is not

Stated precisely, because overclaiming here would be the easiest way for this
framework to become untrustworthy.

**Detectable and refused:** the same `ValueReference` appearing more than once
under `increases`/`decreases` edges **of one node**. That is a decomposition
that counts something twice, and it is refused at verification.

**Not detectable, and not claimed:** double counting across independently
produced decompositions — two sibling explainers that both legitimately include
a jointly-held asset at full value. Foundry already guards this in the domain
where it belongs: `FinanceAggregationService.owned_entities`
(`aggregation.py:64-81`) returns each owned entity **once**, and
`resolve_scope`'s docstring (`core/scope.py:44-53`) warns in terms that this
RFC does not weaken:

> "Do not reuse this as household financial-aggregation logic. … naively summing
> 'each member's individually-attributed value' over the members this function
> returns double-counts anything jointly held."

**The framework does not become a second aggregation authority.** Union rules
are domain property and stay there (watch item **W2**).

---

## 6. Contracts and boundary ownership

> **Questions 9 and 10.**

### 6.1 The resolver is routing and verification — never calculation

```text
ProvenanceResolver
    explain(reference: ValueReference, *, max_depth: int) -> ProvenanceNode | None
```

Core-owned, neutral, and permitted to do exactly four things:

1. **Route** a `value_id` to a registered explainer, or return `None`.
2. **Verify** structure — node-kind rules (§4.2), unit agreement on additive
   roles (§6.3), quantity presence per role (§4.3), expanded-contributor
   agreement (§5.1), repeat-contribution refusal (§5.3), cycle detection
   (§5.2), a non-empty `calculation_version`.
3. **Compute** the residual and completeness (§4.5) — addition and comparison
   over domain-supplied quantities already expressed in one unit.
4. **Bound** expansion depth.

Everything else is refused. Core never values, prices, converts, weights,
applies a rule, or supplies a missing part. **A `value_id` with no registered
explainer yields no provenance — never an invented one.** This is the RFC-012
R9 mitigation restated: a missing lens is a domain change under domain
governance, or the view is not built; the framework has no arithmetic path to
fall back on.

Step 3 is the one place Core touches numbers, and its bound is stated so it can
be tested: **Core may sum and compare quantities in a single unit; Core may not
transform one.**

### 6.2 The domain explainer seam

```text
class ValueExplainer(Protocol):
    def explainable_value_ids(self) -> frozenset[str]: ...
    def explain(self, reference: ValueReference) -> ProvenanceNode | None: ...

ExplanationDescriptor(value_id, unit_or_currency, tolerance: float | None)
```

This is the same seam RFC-015 §5.3 established and RFC-016 §5.3 reused: a
neutral Core projection plus a **domain-owned descriptor provider**, composed at
the composition root. Registration is explicit, duplicate ownership fails closed,
and dispatch is the only path to a domain's explanation — the
`MetricRegistry` contract (`core/metrics.py:103-142`) applied to explanations
rather than to values.

**An explainer is a read path with no write path**, is deterministic, and — like
`MetricProvider.calculate` (`core/metrics.py:98-100`, "Deterministic. No model
call may ever be part of this") — may never reach a model. FR-012 is satisfied
by absence: nothing in the framework imports `foundry.models`, and there is no
path from a `ValueReference` to a `ModelAdapter`.

### 6.3 Units: Core refuses to sum across units

**An `increases` or `decreases` contribution whose unit differs from its
parent's is refused**, not converted. Core has no exchange rate, no unit
algebra and no business acquiring either.

**The rule binds only the additive roles.** A `contextual` contributor may
carry any unit or none — an exchange rate is dimensionless, a unit price is
per-share, an ownership weight is a fraction. Applying unit agreement to
contextual contributors would refuse every legitimate factor in §7, which is
what the first draft did *(self-review A4)*.

**A useful second-order property.** Because units must agree exactly where the
arithmetic happens, the commonest modelling error is caught structurally: a
domain that declares a ratio's numerator as `increases` (GBP into a
`ratio`-unit parent) is refused rather than producing a nonsense residual. The
framework verifies internal consistency, not modelling correctness — but this
is the one class of modelling error it does catch *(self-review A3)*.

The consequence is the point rather than a restriction: a domain that needs to
combine currencies must convert *before* contributing, and must represent the
conversion as an `indivisible` node whose `contextual` contributor is the rate
observation. **The exchange rate that today appears only as a bare event id in
a flat bag (`metrics.py:548-549`) becomes a first-class, traceable
participant.** That is not extra machinery; it is the machinery that makes
§1.2's missing factors visible.

### 6.4 Ownership matrix

| RFC | Owns | Must not own | Interaction with RFC-017 |
|---|---|---|---|
| **RFC-011** Telemetry Acquisition | evidence artefacts, canonical observations, evidence grades, interpretation, confirmation | what any value means; whether a value is complete | supplies the **anchors** a node terminates in; unchanged |
| **RFC-015** Capture Target Registry | which properties may receive observations; stream lifecycle and retirement | value composition | a retired stream's historical observations remain valid anchors at a historical `known_at`; unchanged |
| **RFC-016** Mission Targets | the household's declared destination; supersession lineage | how an observed value is composed | a Mission Target is itself an explainable value whose node is `observed` and terminates in its declaration event. **This RFC changes no RFC-016 contract and requires no target change** |
| **RFC-017** *(this)* | the shape of an explanation; completeness and residual; recursion; the explainer seam | any value; any judgement; any presentation; any event | — |
| **RFC-006** Mission Assessment | trajectory, margin, confidence, milestones, ETA | value composition | **unchanged.** An assessor may consume provenance; nothing compels it to, and no RFC-006 contract is touched (watch item **W1**) |
| **RFC-016 Phase 3** Mission Target capture | the operational surface that declares intent | explanation | none. **Not a separate boundary** — GD-10 |
| **RFC-014** *(reserved)* Governed Corrections | disputing or correcting a fact | explanation | a residual is a **disclosure**, never an adjustment. "This contribution is wrong" lands here, not in §4 |
| **Unnumbered** — Asset Detail & Provenance Investigation | the rare-investigation surface: asset detail, provenance timeline, audit browsing | composition, arithmetic, completeness | **a consumer of this RFC** (GD-1). It renders what §4 produces; RFC-012 R9 applies — a surface that cannot obtain a decomposition does not compute one |
| **Unnumbered** — future Flight Deck intelligence | presentation, interaction, disclosure order | composition, arithmetic, completeness | as above; the disclosure order of a provenance tree is presentation and is outside §4 entirely |

**Frozen contracts this RFC does not touch, stated so it is checkable:**
`MetricRequest`, `MetricResult`, `MetricProvider`, `MetricRegistry`,
`MissionDefinition`, `MissionAssessmentRequest`, `MissionAssessment`,
`MissionMilestone`, `TelemetryItem`, `MissionTarget`, `TargetQuantity`, and
every vocabulary in `core/vocab.py`. Nothing is added to any of them, and the
four new vocabularies are additive.

---

## 7. Worked examples

The brief's two success criteria, expressed in the contract. **The framework
sees roles, quantities and anchors. Every finance word below lives in `label`.**

### 7.1 Property value — a complete explanation

The decomposition already exists in code
(`mortgage_assessment.py:716-732`, `:816-824`); this is the same information in
a shape a second consumer can read.

```text
ProvenanceNode
  reference    (party:household, "finance.property_current_equity", as_of, known_at)
  kind         derived
  quantity     515_000.00   GBP
  label        "Property Value"
  anchors      [ mortgage-evidence event ids ]
  contributions
    increases   85_000.00  → (resource:obligation, "finance.mortgage_initial_deposit")
                             label "Initial Deposit"          expandable: true
    increases  120_000.00  → (resource:obligation, "finance.mortgage_principal_repaid")
                             label "Mortgage Principal Repaid" expandable: true
    increases  310_000.00  → (resource:asset, "finance.property_valuation_movement")
                             label "Market Appreciation"       expandable: true
  exclusions   ()
  residual          0.00                  ← derived, not declared
  completeness complete                   ← derived, not declared
```

Expanding *Mortgage Principal Repaid* one level (§5.1):

```text
ProvenanceNode
  kind         derived
  quantity     120_000.00 GBP
  label        "Mortgage Principal Repaid"
  contributions
    contextual  (no quantity) → "finance.mortgage_initial_advance"   expandable: true
    contextual  (no quantity) → "finance.mortgage_balance"           expandable: true
  completeness indivisible
  residual     None
```

Expanding either contextual contributor yields an `observed` node — £300,000
and £180,000 respectively, each anchored in its mortgage-evidence event, each
with `completeness = None`.

The English qualifier `"INITIAL MORTGAGE − CURRENT BALANCE"`
(`mortgage_assessment.py:727`) becomes structure. Note that the framework does
**not** learn subtraction: it learns that two facts were required and that
neither carries a share of the result.

### 7.2 Pension — an honest partial explanation

This is the example that matters, because Foundry does **not** hold the
evidence the brief's illustration implies. `pension_evidence.py:8-23` records
employee, employer and salary-sacrifice contribution rates and payments — and
**no tax relief and no investment growth**. `_pension_wealth`
(`pension_metrics.py:102-184`) computes the pot from account valuations, not
from contributions.

The correct output is therefore not the brief's four-part decomposition. It is
this:

```text
ProvenanceNode
  reference    (party:household, "finance.pension_wealth", as_of, known_at)
  kind         derived
  quantity     82_431.00  GBP
  label        "Pension"
  contributions
    increases   61_200.00 → (resource:account, pension_account_1)   expandable: true
    increases   21_231.00 → (resource:account, pension_account_2)   expandable: true
  exclusions
    (resource:account, pension_account_3)   out_of_period
  residual          0.00
  completeness partial            ← because an exclusion exists, not because of the residual
```

and one level down, where §1.2's invisible factors become visible:

```text
ProvenanceNode
  reference    (resource:account, pension_account_1, …)
  kind         derived
  quantity     61_200.00 GBP
  contributions
    contextual  (no quantity) → account valuation   (expands to observed 122_400.00 GBP,
                                                     anchor = valuation event)
    contextual  (no quantity) → ownership share     (expands to observed 0.50 ratio,
                                                     anchor = ownership link event)
  completeness indivisible
  residual     None
```

Three things this makes true that are not true today:

- **The ownership share is in the provenance.** Today it determines half the
  answer and appears nowhere (§1.2).
- **The excluded account is a typed fact.** Today it is a sentence — or, for
  the zero-weight path at `pension_metrics.py:154-155`, nothing at all.
- **`partial` is reported even though the residual is zero.** Completeness is
  not only arithmetic: a decomposition that balances while having discarded a
  contributor is not complete, and §4.5's rule says so without any provider
  having to remember to.

**If a household later records tax relief and growth evidence**, those become
two more `increases` contributions and the node's completeness is recomputed —
with no framework change, no new vocabulary value and no schema migration. That
is the test of whether the abstraction is the right size.

> **Governor affirmation — GD-A1, 2026-08-10 (OBS-017-A).** §7.1 and §7.2 are
> **affirmed as correct, unamended.** Both worked examples depict contributors
> whose `Subject` differs from the explained value's — `resource:obligation`,
> `resource:asset`, `resource:account` beneath a `party:household` value — and
> that was always the intended shape. The merged Phase 1 implementation could
> not express it; the framework's own examples were never wrong. §9.1 states
> the rule that makes them expressible.

### 7.3 Sequence — resolving a bounded query

```text
Consumer            Resolver (Core)          Explainer (domain)     Log/projections
   │                     │                          │                     │
   │ explain(ref, d=2)   │                          │                     │
   ├────────────────────►│                          │                     │
   │                     │ explainer_for(value_id)  │                     │
   │                     ├── none ──► return None ──┤  (never invented)   │
   │                     │                          │                     │
   │                     │ explain(ref)             │                     │
   │                     ├─────────────────────────►│ read as_of/known_at │
   │                     │                          ├────────────────────►│
   │                     │                          │◄────────────────────┤
   │                     │◄── node (parts, exclusions, anchors) ──────────┤
   │                     │                          │                     │
   │                     │ verify: kind · units · repeats · cycle · version
   │                     │ compute: residual · completeness               │
   │                     │ expand each contribution while depth < 2       │
   │                     │   └─ recurse ───────────►│                     │
   │◄── ProvenanceNode ──┤                          │                     │
```

**Refusal points, all fail-closed (FR-009):** no explainer → `None`; unit
mismatch → refused; repeated additive contributor → refused; cycle → node
`unavailable` + conflict; empty `calculation_version` → refused; version
mismatch at a historical `known_at` → `unavailable` at that version (§3.4).

### 7.4 Sequence — the same value, asked about the past

```text
   │ explain(ref, known_at = T₀)                  │
   ├────────────────────►│                        │
   │                     │ explain(ref)           │
   │                     ├───────────────────────►│ observations(known_at = T₀)
   │                     │                        ├──── filters event["ts"] > T₀
   │                     │                        │     (acquisition.py:949)
   │                     │◄── node as at T₀ ──────┤
   │◄── identical to the answer given at T₀ ──────┤
```

No stored explanation is consulted, because none exists. The guarantee is
reproduction from immutable inputs, and it holds exactly as far as §3.4 says it
does — no further.

---

## 8. Invariants

1. **A Value Provenance is a projection.** It is computed from canonical state
   on request, is deletable and rebuildable, and has no write path.
2. **This framework authorises zero canonical events** and adds no writer, in
   any phase (§3.5).
3. **The framework never computes a value.** It receives one, receives its
   parts, and verifies the relationship. A missing explainer yields no
   provenance, never an invented one.
4. **Completeness and residual are derived, never declared.** No domain may
   assert how completely it explained a value (§4.5).
5. **An `observed` node terminates.** It carries at least one canonical anchor
   and zero contributions; `derived` carries a non-empty `calculation_version`.
6. **Contributions are typed by arithmetic role, never by domain meaning.**
   Domain meaning lives only in `label`, which is never parsed and is never an
   identity.
7. **Core refuses to sum across units.** Additive contributions must match the
   parent's unit; contextual contributors carry no quantity and any unit.
   Conversion is a domain act and is itself explainable (§6.3).
8. **Exclusions are typed, and a scope boundary is not an exclusion** (§4.4).
9. **Every query is bitemporal.** `as_of` and `known_at` are both required;
   omitting `known_at` yields a current-state explanation that may never be
   presented as a historical one (§3.3).
10. **Recursion is bounded and lazy; a cycle is a refusal, not a truncation**
    (§5). The authorising household, `as_of` and `known_at` are carried down
    unchanged and are never broadened by the resolver. *(Clarified by Governor
    ruling GD-A1–GD-A5, 2026-08-10, §9.1: "scope" here has always meant the
    authority envelope the resolver dispatches within, never a requirement that
    every contributor's `Subject` equal its parent's — see §9.1 VP-SCOPE-2/4.)*
11. **A repeated additive contributor within one decomposition is refused; an
    expanded additive contributor must agree with its declared contribution;
    cross-decomposition double counting is not claimed to be detected** (§5.1,
    §5.3).
12. **Ordering is deterministic and never rearranged by the framework** (§4.2).
13. **An explanation that cannot be reproduced is unavailable**, never
    re-derived under a different calculation version and presented as
    historical (§3.4).
14. **No model is on any provenance path**, and `label` is never interpreted
    (FR-012).
15. **This RFC changes no frozen contract** — not `MetricResult`, not any
    RFC-006 shape, not `MissionTarget` (§6.4).

---

## 9. Security by Design

Answered in full per FR-006 and
[`../security/security-checklist.md`](../security/security-checklist.md). `N/A`
is used where it is the honest answer.

### Security Considerations

- **Authentication.** No identity flow changes and **no new route** — this burn
  designs no surface at all (§12). A future consumer surface inherits the
  existing authenticated-session requirement; authentication and health routes
  remain the only public routes.
- **Authorisation.** A provenance query resolves through the same `Subject`
  scope every metric request already uses (`core/scope.py:21`). Recursive
  expansion is exactly the shape of an inadvertent disclosure, so the guarantee
  is split into the part Core can enforce and the part it cannot — stated
  separately rather than claimed as one rule *(self-review A7)*:

  | Guarantee | Enforced by | Basis |
  |---|---|---|
  | **No scope substitution** — the requesting `Subject`, `as_of` and `known_at` are carried down every expansion unchanged; the resolver never broadens them | **Core** | structural; asserted by P1-F |
  | **Scope containment** — a contributor is one the requesting scope could itself have read | **the domain explainer** | Core cannot check it: `resolve_scope` explicitly accepts caller-resolved resource ids and takes no view on domain ownership (`core/scope.py:29-53`) |

  The second is a **per-domain obligation defended by per-domain tests**, not a
  Core guarantee. Claiming otherwise would specify a rule the model cannot
  support — the error RFC-016's self-review found in its own draft (A3, on a
  `Mission` having no household) and the reason it is stated this way here.
  Foundry still has **no multi-member authorisation model**; this RFC neither
  adds nor narrows one (residual, unchanged).

  > **Amendment — Governor ruling GD-A6, 2026-08-10 (OBS-017-A).** Row one
  > (**No scope substitution**) is unchanged and remains a **clarification**:
  > it always constrained the resolver's dispatch behaviour, never contributor
  > `Subject` identity, and §9.1 restates it in those terms.
  >
  > Row two (**Scope containment … Core cannot check it**) is **superseded as a
  > normative claim.** It is **factually incomplete**, not merely permissive:
  > Core owns a second canonical authority the original text did not survey —
  > `AssetRegistry` (`core/acquisition.py:266-334`) — which binds
  > `subject_id → household_id` neutrally, already refuses cross-household
  > containment (`:317-318`), and has a production writer
  > (`finance/runtime_bootstrap.py:121`, applied `:183`, itself gated on
  > canonical Finance ownership being a subset of Core household membership).
  > **Core can and must verify household-level containment.** Finer-grained
  > containment — which resource within a household a caller may read — remains
  > a per-domain obligation, unchanged. See §9.1 for the resulting contract.
  >
  > This block is retained beside the original text per RFC-100 §9.2; the
  > original is not deleted. Ruling record:
  > [`../reviews/RFC-017-OBS-017-A-ruling.md`](../reviews/RFC-017-OBS-017-A-ruling.md).

### 9.1 Subject authority — Governor amendment GD-A1–GD-A6, 2026-08-10

*(New subsection. Resolves OBS-017-A. Normative unless marked otherwise.)*

The frozen text above never required a contributor's `Subject` to equal its
parent's — every occurrence of `Subject` in this RFC is a field declaration or
a constraint on the **resolver's dispatch behaviour**, and §7.1/§7.2 positively
depict contributors whose subject differs from the explained value's. The
Phase 1 implementation read `as_of`/`known_at`/`Subject` as one combined
equality rule; that reading is safe but conflates two different concerns.
**Subject is part of a value's identity. `as_of` and `known_at` are the query's
temporal envelope. Requiring identity to be constant across a decomposition
forbids decomposition.** This subsection separates them and states the
authority rule Core actually enforces.

**VP-SCOPE-1 — temporal coordinates.** For recursive provenance resolution,
`as_of` and `known_at` **MUST** remain identical to the parent reference. Core
**MUST NOT** alter, widen, default, or accept provider substitution of either
temporal coordinate. *(Restates §9 row one and P1-F; no change in substance —
R1 and SAFE-017-02's temporal guarantee is unchanged.)*

**VP-SCOPE-2 — root authority.** One **authorising household MUST** be derived
from canonical Core state for the root resolution, and **MUST NOT** change for
the entire resolution. Ambiguous or unresolvable root authority **MUST**
refuse.

**VP-SCOPE-3 — child authority.** Every contributor and exclusion `Subject`
**MUST** independently resolve, through canonical Core authority state, to the
root authorising household. A `Subject` that is unknown, unregistered,
ambiguous, or bound to another household **MUST** be refused. There is no
"unknown means probably the same household" behaviour.

**VP-SCOPE-4 — identity is not authority.** A contributor's or exclusion's
`Subject` **MAY** differ from its parent's. Literal `Subject` equality **MUST
NOT** be required or treated as the authority test.

**VP-SCOPE-5 — the authority source.** The explainer **MUST NOT** declare,
assert, override or supply the household authority used to admit a traversal.
Core **MUST** derive it solely from canonical state established independently
of the explainer — the currently-identified source is `AssetRegistry` plus Core
party membership (`members_of`). This is a **structural** requirement, not
merely a convention: an explainer that could assert its own authority would
reintroduce exactly what R1 and SAFE-017-02 refuse — a provider choosing the
coordinates Core resolves.

**VP-SCOPE-6 — the boundary this does not claim.** RFC-017 guarantees
**household isolation** at this boundary and nothing finer. Whether a caller
may query a given household at all remains the caller's authorisation problem,
unchanged; Foundry has no intra-household privilege boundary, and this
amendment does not create one (T6 residual, unchanged).

**Implementation constraint (binding on the remediation, not new architecture).**
The resolver **MUST NOT** gain a direct dependency on `AssetRegistry`,
`EventLog`, or any Finance module — `AssetRegistry` imports `EventLog`, and
P1-B is asserted **structurally**. The authority binding **MUST** arrive through
a narrow, read-only, Core-neutral protocol injected at the composition root,
following the descriptor-seam pattern already used for `TargetMetricResolver`
(RFC-016 §5.3) and `ExplanationDescriptor` (§6.2) — for example, conceptually,
`SubjectAuthority.household_for(subject) -> str | None`. The exact name is not
frozen by this amendment.

**What this amendment does not authorise.** No canonical event. No new
vocabulary value. No shape change to `ValueReference`, `ProvenanceNode`,
`Contribution` or `Exclusion`. No change to the query signature. No general
authorisation or capability subsystem. No Finance explainer. No Phase 2.

- **Sensitive data and secrets.** A provenance carries no new data. It carries
  event ids that already exist, quantities the domain already computed, and a
  domain-authored `label` produced at read time. **Nothing is written**, so
  nothing here is irreversible — the material difference from RFC-016 §9, where
  operator-authored `basis` text entered the append-only log permanently. No
  credential, external identifier or persistence mechanism is introduced.
  `redact_credentials` and the `EvidenceVault` redaction path
  (`core/acquisition.py:105`, `:385`) are untouched and unextended.
- **Auditability.** The framework improves it: today a value's support is a
  deduplicated bag of ids (§1.2); under this contract every anchor is attached
  to the specific component it supports, and every excluded contributor is a
  typed record rather than a sentence. Because provenance is a projection, the
  audit trail remains the log itself — there is no second record to fall out of
  step with it.

### Threat Assessment

- **Trust boundaries.** No outbound destination, connector, dependency or
  credential is added, and no new untrusted input exists: every input is either
  canonical state or domain-produced.
- **Threat model.** **T4** (event-log modification) — unaffected; the framework
  is read-only by construction and invariant 2 makes that structural rather
  than conventional. **T6** (authorisation failure) — the recursive-expansion
  scope-widening risk above; contained by P1-F and refused rather than
  degraded. **T8** (malformed input) — a malformed explanation is refused at
  verification and yields no provenance; it can never yield a partial or
  plausible one. **T10** (operator error) — no operator write path exists.
  **T1/T9** — no model may be reached from a provenance path, and `label` is
  never interpreted, so no free text from this RFC reaches a model or a
  decision.
- **Failure and abuse.** Every gate refuses: unknown `value_id`, unit mismatch,
  repeated additive contributor, cycle, missing calculation version,
  irreproducible historical version. A refusal yields *no provenance*, never a
  partial tree presented as whole. **Denial of service by depth** is the one
  novel abuse shape — an adversarial or accidental deep graph — and the depth
  bound (§5.1) is the mitigation; it is mandatory, not advisory.

### Validation

- **Evidence.** Named per-claim tests in §10, including scope non-widening,
  cycle refusal, unit-mismatch refusal, completeness non-declarability,
  bitemporal reproduction under two frozen clocks, and an assertion that Core's
  provenance module contains no domain vocabulary.
- **Deferred work.** Multi-member authorisation (unchanged residual); whether
  assessors must consult provenance (watch item **W1**); executable historical
  calculation versions (**W3**); any consumer surface (outside this RFC).
  Nothing here is described as implemented.

`security-assurance.md` and `threat-model.md` require **no change from this
burn**: no documented control is modified and no trust boundary moves. The
first burn that adds a provenance route must update the assurance register in
the same change.

---

## 10. Testing strategy

- **Neutrality (FR-011).** Core's provenance module source contains no domain
  vocabulary — the regression pattern established by
  `test_core_acquisition_contract_contains_no_finance_event_vocabulary`. Phase
  1 is proven against a **mock domain only**.
- **Contract.** `observed` with a contribution refused; `observed` with no
  anchor refused; `observed` carrying a completeness refused; `derived` with an
  empty `calculation_version` refused; an **additive** contribution in a
  different unit refused; a **contextual** contribution carrying a quantity
  refused; a contextual contribution in a *different* unit **accepted**;
  `indivisible` with zero contributions refused.
- **Completeness is not declarable.** A node asserting its own completeness is
  rejected by the type; the resolver's computed value governs. Balanced parts
  with an exclusion yield `partial`, **not** `complete` — the §7.2 case,
  asserted directly.
- **Residual.** A residual outside a declared tolerance yields `partial`; with
  no declared tolerance, comparison is exact; a `float` sum that drifts reports
  `partial` rather than rounding to `complete`.
- **Exclusions.** Each of the three reasons round-trips; an exclusion carries
  no quantity; a scope boundary is asserted **not** to be reported as an
  exclusion (§4.4).
- **Recursion.** Depth bound honoured; `expandable` distinguishes a leaf from a
  stop; a diamond resolves without a double-count claim; a cycle makes the node
  `unavailable` and raises a conflict; a repeated additive contributor within
  one node is refused; an expanded additive contributor whose node quantity
  disagrees with its declared contribution makes the **parent** `unavailable`.
- **Ordering.** Two resolutions of the same query emit contributions and
  exclusions in identical order; the resolver is asserted not to sort them.
- **Quantity absence.** A `derived` node with `quantity = None` reports
  `completeness = None` and `residual = None`, not `partial`.
- **Bitemporality (FR-007).** The same query at two distinct frozen clocks
  produces identical provenance; a fact recorded after `known_at` does not
  appear; a version mismatch at a historical `known_at` yields `unavailable`
  rather than a re-derived answer.
- **Isolation.** Expansion never surfaces a contributor outside the requesting
  scope (P1-F).
- **No write path.** Resolving, expanding and rendering a provenance appends no
  event — asserted by log comparison across a full render, the RFC-016 §10
  pattern.
- **Regression.** The existing suite passes **unmodified**. No metric value,
  assessment result or rendered figure changes, because nothing consumes
  provenance until a phase that adopts it. Asserted directly: a framework that
  silently altered a shipped number would be a migration, not a foundation.

---

## 11. Implementation phases

Each phase re-enters the lifecycle as its own burn (RFC-100 §4.1). **The
2026-08-06 freeze authorises Phase 1 only**
([freeze record](../reviews/RFC-017-architecture-freeze-record.md)).

| Phase | Content | Authority | Why here |
|---|---|---|---|
| **1** | Core contract: the five shapes, the four vocabularies, the resolver, verification, completeness derivation, bounded recursion, cycle refusal. **Mock domain only** | **GO** — frozen 2026-08-06, against P1-A…P1-H | the foundation; nothing real is explained |
| **2** | First domain explainer: **property equity** (RFC-007). The decomposition already exists in code (`mortgage_assessment.py:716-732`) and moves out of display strings | **Not authorised** — requires subsequent Governor authority | proves the seam without inventing evidence; the one case where the target output is already known to be correct |
| **3** | Second explainer: **pension wealth** — chosen because it is *partial* (§7.2). Exercises exclusions, contextual factors and the ownership share that is invisible today | **Not authorised** — requires subsequent Governor authority | proves the honesty machinery on a real gap rather than a clean case |
| **4** | Consumer adoption, one consumer at a time, each behind its own governed amendment | **Not authorised** — retains its stated gates | any consumer that renders provenance changes what a household sees |
| **5** | Whether `MetricResult`'s flat reference bag is superseded by anchors | **Not authorised** — GD-9 deferred, conferring nothing | **changes a frozen RFC-001 contract** (000 §13.3) with live consumers at `mission_control.py:1554-1556`. A Governor decision, not a cleanup |

**Sequencing rule — binding, ruled GD-7.** Phase 3 (a partial explanation)
**must** ship before any Phase 4 consumer. A surface that only ever meets
`complete` explanations will be built assuming completeness is normal, and will
then present `partial` as an error. RFC-004.2's information-honesty pass and
RFC-015's "retirement before bootstrap" ruling (G6) are the precedents: the
honest state must exist before the surface that must handle it.

### 11.1 Phase 1 acceptance criteria *(binding — the frozen criteria for the authorised burn)*

| # | Criterion |
|---|---|
| **P1-A** | Core's provenance module contains no domain vocabulary; proven against a mock domain only (FR-011) |
| **P1-B** | No module in the framework can append an event; asserted structurally, not by convention (§3.5) |
| **P1-C** | Completeness and residual are computed by the resolver and cannot be supplied by an explainer (§4.5) |
| **P1-D** | Identical provenance under two distinct frozen clocks; a fact recorded after `known_at` is absent (FR-007) |
| **P1-E** | Every refusal path refuses: unknown `value_id`, unit mismatch, cycle, repeated additive contributor, empty calculation version (FR-009) |
| **P1-F** | **No scope substitution**: the requesting `Subject`, `as_of` and `known_at` are carried unchanged through every expansion. Domain scope containment is a per-domain obligation and is **not** claimed as a Core guarantee (§9) |
| **P1-G** | A `derived` node with zero contributions reports `partial` with `residual = quantity` — not `complete`, not `observed` (FR-008) |
| **P1-H** | The existing suite passes unmodified; no shipped value or rendered figure changes |

> **Amendment — Governor ruling GD-A1–GD-A6, 2026-08-10 (OBS-017-A).**
> **Clarification, retained beside the original.** P1-F was satisfied by the
> merged Phase 1 implementation and remains satisfied: literal `Subject`
> equality is a valid, stricter reading of "no scope substitution." Read
> forward from this date, P1-F's `Subject` clause means **VP-SCOPE-2 through
> VP-SCOPE-5** (§9.1) — the authorising household is fixed at the root and
> verified by Core against canonical state — not literal equality. `as_of` and
> `known_at` equality is unchanged in both readings (VP-SCOPE-1). The bounded
> Phase 1 conformance remediation is evaluated against the amended reading.

---

## 12. Scope exclusions *(FR-004 — declared, not deferred debt)*

Excluded by scope. Their absence is not hidden implementation:

- **All implementation.** No source, test, fixture, template, CSS or runtime
  configuration is produced by this burn (FR-013, RFC-100 §3.1 rule 3).
- **Schema changes.** None. No dataclass, event payload or vocabulary in the
  repository is modified.
- **Event definitions.** None, in any phase (§3.5).
- **UI, Flight Deck, any route, form or CLI.** No surface is designed. How a
  provenance is rendered, ordered, paginated or progressively disclosed is
  outside this boundary.
- **Mission Assessment.** No RFC-006 contract changes and no assessor changes.
- **Capture, editing, correction and manual attribution workflows.** A
  household asserting "this contribution is wrong" is *Governed Corrections*
  (RFC-014, reserved), not provenance. A household asserting a contribution
  directly is *capture* (RFC-011/012/013).
- **API endpoints and implementation classes.** The shapes in §4 and §6 are
  contracts, not classes; module and signature choices belong to the
  implementation burn within these contracts.
- **Retrofitting existing metrics.** No shipped metric gains an explainer by
  this document. Phases 2–3 name two candidates and authorise neither.
- **Caching, invalidation or a performance envelope.** Per-request replay cost
  is a pre-existing platform-wide debt; this RFC neither worsens it structurally
  nor fixes it (**W4**).
- **Cross-decomposition double-count detection** (§5.3) — domain property.
- **The RFC-013 numbering debt, RFC-014, and mission instantiation.** Open
  elsewhere; untouched here.
- **Every consumer boundary named in §0.4 and §6.4.** No architecture is
  proposed for any of them, numbered or unnumbered — including the *Asset Detail
  & Provenance Investigation* surface that GD-1 re-earmarked, which requires its
  own burn and its own boundary challenge.

---

## 13. Rejected alternatives

| Alternative | Why rejected |
|---|---|
| **Provenance as canonical events** | puts a fold's output into its own input; creates a second truth that can disagree with the first; makes historical explanation stale on every calculation change (§3.2) |
| Provenance fields added to `MetricResult` | a frozen RFC-001 contract with live consumers (`mission_control.py:1554-1556`); and a value that is not a registered metric — an equity component, an assessment intermediate — could then never be explained |
| Provenance as a `Claim` | a Claim is a witnessed belief with model provenance and a confidence (`canon.py:34-48`); an arithmetic decomposition is neither witnessed nor believed, and the route would put a model-shaped path around a deterministic fold (FR-012) |
| **Signed quantities instead of `CONTRIBUTION_ROLE`** | the strongest simplification, and it fails three ways: it conflates "a £300,000 liability" with "minus £300,000"; `decreases` with a negative quantity is ambiguous; and it cannot express `contextual` at all — so the ownership share that determines half of §1.2's pension figure would remain invisible |
| Domain contribution taxonomies (deposit / growth / relief / interest) | the explicit instruction of the brief, and unbounded: every domain would extend it, and the vocabulary would become a finance schema wearing a neutral name |
| Provider-declared completeness | a self-reported honesty flag is the first thing to rot; §4.5 makes the claim unfalsifiable by removing the provider's ability to make it |
| A fourth completeness value for "no explanation offered" | redundant — a `derived` node with zero contributions already yields `residual = quantity` and `partial`, which says the same thing with no new vocabulary |
| **Folding `Exclusion` into `Contribution`** (an additive role with no quantity) | the second-strongest simplification: it deletes one shape and one vocabulary. Rejected because it deletes the **reason** — `unobserved` / `out_of_period` / `incommensurable` — and the reason is the honest part. §1.6 is a platform that already lost the reason and, at `pension_metrics.py:154-155`, the fact |
| Eager full-graph expansion | `ValuationLenses.market_value` (`acquisition.py:1002-1015`) already does this and flattens the structure at every level (`:1007`) — the defect being fixed, reproduced by the fix |
| Truncating a cycle at max depth | renders a plausible, wrong tree. RFC-015 §3.4 and RFC-016 §7.2: ambiguity is refused, never resolved by guess |
| Core performing unit conversion | Core would need an exchange rate and a unit algebra, and the conversion would become invisible again — the §1.2 defect, relocated into Core |
| Reusing RFC-016's `TARGET_DIMENSION` for provenance quantities | it is closed at `{currency, duration_months}` for *intent*; a ratio or a count could then never be explained, and provenance would inherit a target vocabulary it does not own |
| A new `provenance_status` vocabulary | `METRIC_STATUS` already carries `available / unavailable / unsupported / stale / error`; a near-identical parallel is two ways to say one thing (RFC-016 §13 precedent) |
| Extending `kernel.why()` to values | `why()` resolves a `claim_id` through `Canon.explain` (`canon.py:122-138`) and returns source events and revision history for a *belief*. A value has no claim id, and overloading the function would make one name mean two incompatible things |
| Building the Asset Detail surface first and deriving the contract from it | the RFC-012 R9 failure mode: the renderer becomes the computation layer, and the contract is then shaped by one view's needs (§0.3) |

---

## 14. Governor decisions required

None of the following is ruled. Each carries an EECOM recommendation; none may
be assumed.

**All ten are disposed. Nothing in this register is open.** The verdict was
**GO WITH RULINGS** (2026-08-06). Freeze remains a separate Governor gate.

| # | Decision | Ruling |
|---|---|---|
| **GD-1** | The RFC number (§0) | **Settled — RFC-017 is Value Provenance Framework.** R1 approved. *Asset Detail & Provenance Investigation* is re-earmarked as an **unnumbered future consumer boundary**, amending GD-1 of RFC-016 and, through it, RFC-015 G3. Recorded in RFC-016 §0/§14.1, RFC-015 §0/§18 and [`index.md`](index.md) |
| **GD-2** | Provenance is a **deterministic projection with zero canonical events**, in every phase (§3) | **Approved as recommended** |
| **GD-3** | The four closed vocabularies — `PROVENANCE_NODE_KIND`, `CONTRIBUTION_ROLE`, `EXPLANATION_COMPLETENESS`, `EXCLUSION_REASON` — and their eleven values (§4) | **Approved as recommended.** Extension is a governed Core change |
| **GD-4** | **Completeness is derived, never declared** (§4.5) | **Approved as recommended** |
| **GD-5** | Core's arithmetic bound: sum and compare within one unit; never transform one (§6.1, §6.3) | **Approved as recommended** |
| **GD-6** | Bounded, lazy recursion with cycle refusal; no unbounded expansion (§5) | **Approved as recommended** |
| **GD-7** | Sequencing: a **partial** explanation ships before any consumer surface (§11) | **Approved as recommended** |
| **GD-8** | Whether an assessor may be *required* to consult provenance — an RFC-006 boundary question (**W1**) | **Deferred as recommended.** Requiring it changes a frozen contract. This authorises no assessor change and no RFC-006 amendment |
| **GD-9** | Whether `MetricResult`'s flat reference bag is superseded by anchors (§11 Phase 5) | **Deferred as recommended.** A frozen RFC-001 contract with live consumers; not a cleanup. Phase 5 remains unauthorised |
| **GD-10** | The programme sequence (§0.4) | **Collision confirmed.** RFC-018/019/020 are **not reserved numbers**. Mission Target capture is RFC-016 adoption unless a future burn proves a new boundary; mission assessment belongs to RFC-006; Flight Deck intelligence is unnumbered |

**No decision blocks the freeze gate.** GD-2 through GD-6 — the storage model,
the vocabularies, the honesty rule, Core's arithmetic bound and the recursion
rule — are all settled, so Phase 1 requires no architectural invention. The
FR-013 failure mode this register existed to prevent is closed.

**What the rulings do not authorise.** Freeze is a separate gate and has not
been given. No implementation is authorised. GD-8 and GD-9 are deferred, not
granted: neither authorises an assessor change, an RFC-006 amendment or any
change to `MetricResult`.

### 14.1 Post-freeze amendment — OBS-017-A, 2026-08-10

**All seven are disposed.** Raised by EECOM's bounded architecture
investigation ([`../reviews/RFC-017-OBS-017-A-clarification.md`](../reviews/RFC-017-OBS-017-A-clarification.md),
evidence only — not itself a ruling) and independent SAFE confirmation of
merged Phase 1. Formal ruling record:
[`../reviews/RFC-017-OBS-017-A-ruling.md`](../reviews/RFC-017-OBS-017-A-ruling.md).

| # | Decision | Ruling |
|---|---|---|
| **GD-A1** | OBS-017-A determination and §7.1/§7.2 status | **Accepted — REAL ARCHITECTURE CONTRADICTION**, root cause: identity/authority conflation plus an incomplete survey of Core's own authority state. §7.1/§7.2 **affirmed**, unamended |
| **GD-A2** | `as_of` for recursive resolution | **Accepted — MUST equal parent, unchanged** (VP-SCOPE-1) |
| **GD-A3** | `known_at` for recursive resolution | **Accepted — MUST equal parent, unchanged** (VP-SCOPE-1) |
| **GD-A4** | Root authority | **Accepted** — one authorising household, derived from canonical Core state, fixed for the resolution; ambiguous or unresolvable refuses (VP-SCOPE-2) |
| **GD-A5** | Child authority | **Accepted** — every contributor/exclusion `Subject` independently resolves to the root household via canonical state; unknown, unregistered, ambiguous or foreign refuses (VP-SCOPE-3, VP-SCOPE-4). Also disposes **SAFE-017-04: MUST close before the next consumer**, folded into the same remediation as W4's corrected disposition |
| **GD-A6** | Authority source | **Accepted** — the explainer MUST NOT assert household authority; Core derives it independently via `AssetRegistry` and party membership (VP-SCOPE-5). Does **not** authorise a direct `AssetRegistry` dependency from the resolver — a narrow read-only seam is required |
| **GD-A7** | Phase 2 implementation authority | **Deferred.** Remains **NONE**. No Finance explainer or production provenance consumer is authorised by these rulings |

**Phase 1 disposition: REMEDIATION REQUIRED, not unsafe.** The merged
implementation (`82f7310`) is fail-closed and satisfied every stated Phase 1
acceptance criterion; it enforced a rule **stricter** than the frozen
architecture required. This is a **contract-conformance remediation**, not
repair of an active disclosure vulnerability — no SAFE property (R1, R2, R3,
R4, Loop 2, SAFE-017-01, SAFE-017-02, SAFE-017-03) is weakened by this
amendment; VP-SCOPE-1 preserves R1's temporal half verbatim, and VP-SCOPE-3–5
replace only SAFE-017-02's `Subject` predicate with a Core-verified one.

**No other RFC is amended.** RFC-011 and RFC-015 are read for evidence
(`AssetRegistry`, `runtime_bootstrap.py`), not changed.

### 14.2 Post-freeze amendment — Pension Phase 2 blocker clarification, 2026-08-11

**Both disposed.** Raised by EECOM's bounded pre-implementation contract
validation of the first proposed Phase 2 explainer (`finance.pension_wealth`)
and BOOSTER's `RETURN TO GOVERNOR` finding against it — evidence, not itself a
ruling. Formal ruling record:
[`../reviews/RFC-017-GD-P2-ruling.md`](../reviews/RFC-017-GD-P2-ruling.md).

| # | Decision | Ruling |
|---|---|---|
| **GD-P2-A** | Add `conflicting` to `EXCLUSION_REASON` (§4.4) | **Accepted.** Normative amendment, additive only; original three values unamended |
| **GD-P2-B** | Attribution-weighted additive contributions use `expandable = false` with the attributed quantity, plus contextual siblings for raw value and weighting (§4.7) | **Accepted.** Clarification of existing §4.3/§5.1 mechanics; no shape change |
| **GD-P2-C** | A stable, deliberately unregistered leaf `value_id` may identify an attribution-weighted terminal edge | **Accepted.** The §6.2 registry consistency rule (`expandable = false` with a *registered* explainer is invalid) is unchanged and still governs |
| **GD-P2-D** | Binding acceptance requirement: DB/pot-conflict → `conflicting`; missing valuation → `unobserved` | **Accepted** as a binding Phase 2 acceptance criterion, not a new architectural rule |
| **GD-P2-E** | Binding acceptance requirement: `known_at`-filtered replay for any Phase 2 pension explainer must include ownership-link (`finance.account.linked`) events, not only valuation/declaration events | **Accepted** as a binding Phase 2 acceptance criterion. Does not amend RFC-011 or any event semantics |
| **GD-P2-F** | RFC-017 provenance explains the existing canonical `finance.pension_wealth` calculation; it does not alter pension ownership selection or weighting to satisfy a provenance expectation. **Supersedes** the prior zero-weight-specific framing of acceptance criterion P2-L | **Accepted, 2026-08-11.** See replacement P2-L below and [`../reviews/RFC-017-GD-P2-ruling.md`](../reviews/RFC-017-GD-P2-ruling.md) |

**Replacement P2-L (supersedes the prior zero-weight-specific criterion):**

```text
P2-L

The provenance explanation MUST faithfully reproduce the ownership
attribution actually applied by finance.pension_wealth for the requested
Subject.

The explanation MUST expose the canonical ownership evidence relevant to
that attribution.

Provenance MUST NOT change, correct, infer, or reinterpret the metric's
weighting semantics.

Where the existing metric genuinely computes an attributed value of zero,
provenance MUST represent zero honestly. Where the existing metric computes
a full or fractional value, provenance MUST represent that exact result.
```

This is a binding Phase 2 acceptance criterion, not a change to any Phase 1
Core shape — `GD-P2-B`'s attribution architecture (non-expandable attributed
edge; raw valuation and ownership evidence as contextual siblings) is
unchanged; the attributed additive quantity it carries is simply whatever
`finance.pension_wealth` actually computes for the requested `Subject`, never
a provenance-side reinterpretation of it. A related Finance-domain
observation about person-scoped weighting is recorded separately, outside
RFC-017's boundary, as `OBS-PENSION-01`
([`../rfc-009-technical-debt.md`](../rfc-009-technical-debt.md)).

**What these rulings do not authorise.** No change to `ValueReference`,
`Contribution`, `ProvenanceNode`, the resolver, the explainer registry, or
`SubjectAuthority`. No Finance explainer. No Phase 2 implementation
authority — it remains **NONE**.

---

## 15. Watch items and technical debt

| # | Item | Disposition |
|---|---|---|
| **W1** | Nothing compels a consumer to publish or consume provenance. A provider may keep discarding its decomposition (§1.2) and remain compliant | Watch item. Compelling it changes a frozen RFC-006/RFC-001 contract. Per-domain tests are the available defence — the same residual RFC-016 recorded as its own W1 |
| **W2** | The framework cannot detect double counting across independently produced decompositions (§5.3) | Named, not fixed. Union rules are domain property (`aggregation.py:64-81`); adopting them into Core would make Core an aggregation authority |
| **W3** | Executable historical calculation versions are not retained, so an old explanation is reproducible only while its version is still producible (§3.4) | Pre-existing and platform-wide. Contained by refusing rather than re-deriving; retention is a successor boundary |
| **W4** | Recursive expansion multiplies an already-uncached per-request replay cost | ~~Bounded by mandatory depth limits. A caching and invalidation policy is a platform-wide gap already on the debt register and is not created by this RFC~~ **Corrected by Governor ruling GD-A5, 2026-08-10 (OBS-017-A, SAFE-017-04).** Depth limits alone do **not** bound total work — measured at up to 2,396,745 explainer resolutions for a legal, acyclic shape (`rfc-017-technical-debt.md`). Same-authority traversal (§9.1) is what makes a real household graph traversable, so this **must close in the Phase 1 conformance remediation**, before any consumer, via per-resolution memoisation keyed by `ValueReference` |
| **W5** | Over-attribution in shipped code (`pension_assessment.py:1184-1241`) will persist until a phase adopts provenance for those metrics | Named, not fixed. Fixing it inside the current contract is impossible — there is one bag per result and nowhere to put a per-component association. That is the defect, not an oversight |
| **W6** | Four existing meanings of the word *provenance* (§0.5) now have a fifth neighbour | Contained by binding naming discipline. Renaming existing fields is out of scope: they are live contracts on merged RFCs |
| **W7** | `MissionAssessmentRegistry.dispatch` wraps every provider call in `except Exception` (`core/mission_assessment.py:538-544`), so a provenance failure inside an assessor would surface as a generic provider failure | Pre-existing; recorded by RFC-016 as its W6 and unchanged here. Named so it is not mistaken for something this RFC introduced |
| **W8** | ~~Core cannot verify **domain scope containment** during expansion (§9); it can only refuse to substitute a broader scope~~ **Superseded by Governor ruling GD-A6, 2026-08-10 (OBS-017-A).** Narrowed, not withdrawn: Core **can and must** verify **household-level** containment, via canonical `AssetRegistry` state (§9.1 VP-SCOPE-2/3/5) — the original survey of Core's authority was incomplete. **Finer-than-household** containment (which resource *within* a household a caller may read) remains a per-domain obligation, unchanged | Original: `resolve_scope` takes no view on domain ownership by design (`core/scope.py:29-53`) — true of `resolve_scope`, incomplete as a statement about Core. §9.1 states the corrected boundary; per-domain tests remain the defence for what Core still does not check |
| **W9** | Core cannot verify that a node's anchors genuinely support its quantity — only that an `observed` node has at least one | Accepted limit. Verifying it would require Core to re-derive the value, which is the boundary §6.1 exists to hold |

---

## 16. What this architecture does not fix

Stated plainly, so the document is not read as more than it is.

- **It explains nothing on its own.** It is a contract. Until a domain
  implements an explainer, every value in Foundry remains exactly as
  explainable as it is today — which is to say, a bag of event ids and a count.
- **It does not correct any shipped number**, and must not. The residual in
  §7.1 is a disclosure, never an adjustment.
- **It does not fix the over-attribution in `pension_assessment.py`** or the
  silent drop in `pension_metrics.py:154-155`. It makes both *expressible* as
  defects and gives a later burn somewhere honest to put the fix.
- **It does not make historical explanation immune to code change.** §3.4
  states the boundary exactly; the mitigation is refusal, not a guarantee.
- **It does not detect double counting across decompositions** (§5.3, W2).
- **It does not add a multi-member authorisation model**, and it does not make
  Core able to check domain scope containment. Core guarantees only that it
  never substitutes a broader scope; whether a contributor is one the requester
  could have read is a per-domain obligation, stated as such rather than
  overclaimed (§9).
- **It does not give provenance a surface.** Nothing a household can see
  changes until a consumer burn, which this document neither designs nor
  authorises.
- **The freeze authorises Phase 1 and nothing else.** Phase 1 is a Core
  contract proven against a mock domain: it explains no real value, changes no
  number a household sees, and adds no surface. Phases 2 and 3 — the first real
  explainers — require subsequent Governor authority, and GD-8 and GD-9 remain
  deferred, conferring none.
- **It does not give the re-earmarked investigation surface an architecture.**
  GD-1 kept that boundary alive and unnumbered; it needs its own burn and its
  own boundary challenge, and this document is its prerequisite, not its
  design.
