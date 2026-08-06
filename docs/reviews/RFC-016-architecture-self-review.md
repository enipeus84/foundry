# RFC-016 — Mission Target Framework: Architecture Self-Review

Adversarial review of [`../rfcs/RFC-016-mission-target-framework.md`](../rfcs/RFC-016-mission-target-framework.md),
performed by EECOM against its own draft before commit, per RFC-100 §2.4 and
precedent **P9** ("a self-review that produces no amendment and no recorded
residual has not been performed").

Every claim below is grounded in a cited repository line, not in the RFC's own
assertions.

**Outcome: eight amendments applied before commit; five residuals recorded and
not fixed.** One amendment (**A3**) corrects a factual error in the draft that
would have specified an unenforceable security rule.

> **Subsequent ruling, 2026-08-06 (Phase 1A).** Residual **R4** ("the RFC number
> is unresolved") is **closed** by Governor ruling GD-1: the number is RFC-016,
> and the provenance-investigation boundary is reassigned to RFC-017. Ruling
> GD-11 additionally placed mission instantiation outside this boundary, which
> converts residual **R2** from an open architectural gap into a **ruled scope
> exclusion** with a successor burn to own it. The review text below is retained
> unchanged as the record of the review as performed.

---

## Part 1 — Current-state analysis

### 1.1 Where strategic intent lives today

| Representation | Location | Is it authoritative? |
|---|---|---|
| `Mission.target_value` / `target_date` / `tolerance` / `target_range` | `src/foundry/core/entities.py:56-69` | **No** — validated against a policy constant by every assessor (§1.2 below) |
| Policy dataclass constants | `mission_assessment.py:52`, `resilience_assessment.py:37`, `mortgage_assessment.py:271`, `pension_assessment.py:203` | **Yes, in practice** |
| `AssumptionSet` values | `finance/entities.py:612` | **Partly** — FI's implied destination is `desired_annual_spending ÷ withdrawal_rate` |
| Mission display name | `demo_data.py:598`, `:878` | **No, and it should never be** — yet it is the only place "ahead of the contractual term" survives |

### 1.2 The four assessors' target contracts, verified line by line

| Mission | `target_value` | `target_date` | Line |
|---|---|---|---|
| Financial Resilience | must equal `18.0` | must be `None` | `resilience_assessment.py:200-215` |
| Financial Independence | must equal `750_000.0` | optional | `mission_assessment.py:240-243` |
| Pension Independence | must be `None` | must be `None` | `pension_assessment.py:227-236` |
| Mortgage Freedom | must equal `0.0` | must equal the derived contractual ETA | `mortgage_assessment.py:319-329`, `:418-423` |

Each returns `MissionAssessment.unavailable(...)` on mismatch. The draft's
central claim — that a household cannot express intent — is therefore not
rhetorical: it is four `if` statements.

### 1.3 Whether the writers exist

```text
declare_mission()          src/foundry/core/entities.py:134
  callers: demo_data.py:537,597,654,877 (synthetic_demo) + tests only
update_mission()           does not exist
core.mission.updated       folded at entities.py:276-285; written by nothing
achieve_mission()          entities.py:159; called only by tests
POST route for missions    none — every router.post in src/ is acquisition or Operations capture
```

Verified by exhaustive grep over `src`, `tests`, `scripts` and `examples`.

### 1.4 The revision precedent that already exists

`declare_assumption_set` (`finance/entities.py:612-619`) documents immutable,
versioned declaration with archival supersession, for exactly the reason a target
needs it: "A historic forecast's reference therefore remains interpretable." The
draft adopts this rather than inventing a lineage model.

---

## Part 2 — Challenges, answered adversarially

### C1. Should this be a projection, like RFC-015? — **No, and the reason is specific**

RFC-015 chose a projection because `TelemetryStream ⋈ AssetRegistration` already
carried every fact a capture target needed. Here the nearest candidate —
`core.mission.declared` — carries untyped scalars whose meaning is already
claimed by four assessors as a policy checksum. There is nothing to project.

**The strongest counter-proposal, and why it fails.** Revision could be
expressed with *no new event at all*: declare a new Mission with the new target
and `abandon_mission` the old one. It fails on evidence:

- Trajectory, delta-v and margin are computed per `mission_id`
  (`MissionAssessmentRequest.mission_id`, `core/mission_assessment.py:103`). A
  new mission id orphans the history the mission exists to show.
- `mission_detail` fails closed when more than one **active** mission claims a
  policy (`mission_control.py:2341-2352`), so the abandon must land first — an
  ordering hazard on an append-only log with no transaction.
- Abandonment is a **terminal mission** state (`vocab.MISSION_STATUS`), and
  raising a target is not abandoning a mission.

**Amendment A1 applied** — added to the rejected-alternatives table with this
evidence, because "declare a new Mission" is the first thing a reviewer will
propose and the draft did not pre-empt it.

### C2. Does "changes no RFC-006 contract" survive scrutiny? — **Yes, with one masked failure mode**

Verified: no field is added to `MissionDefinition`, `MissionAssessmentRequest`,
`MissionAssessment`, `MissionMilestone` or the registry's validation. Assessors
reach a target the same way they already reach `EntityProjection`.

**But** `MissionAssessmentRegistry.dispatch` wraps every provider call in
`except Exception` and returns "assessment provider failed safely"
(`core/mission_assessment.py:538-544`). A target-resolution failure inside an
assessor will therefore surface as a generic provider failure with no indication
that intent, rather than evidence, was the problem — a real information-honesty
cost (FR-008) that the draft did not name.

**Amendment A2 applied** — recorded in §4.1 and as watch item **W6**. Not
fixed here: fixing it means changing a frozen RFC-006 contract.

### C3. Is household scoping specifiable as drafted? — **No. The draft was wrong**

The draft required a target's household to agree with "the mission's household
scope". **A `Mission` has no household.** `core/entities.py:56-69` carries
`id`, `name`, the target fields, `assessment_policy_id`, `assumption_set_id`,
`status`, provenance and history — and no party reference. `declare_mission()`
takes no household argument.

Worse, the render path is household-blind in both directions:

```python
def _household_scope(console):      # mission_control.py:185-191
    ...  return Subject("party", households[-1].id) if households else None

def _active_missions(console):      # mission_control.py:194-198
    return [m for m in console.entities.missions.values() if m.status == "active"]
```

Every active Mission in the log is assessed against **the most recently declared
active household**. In a two-household log this is already wrong, and it is not
a defect this RFC created or may fix.

The correction has architectural weight rather than being a wording fix:

1. The target's own `household_id` is **authoritative**; there is nothing on the
   mission to agree with.
2. Household equality is therefore enforced between **target and session**, and
   the draft's three-way equality is replaced by a two-way one plus an explicit
   statement of what cannot be checked.
3. A useful consequence: a target can *give* a mission a household. **First
   target binds** — once a household holds an active target against a mission,
   a target from any other household against that mission is refused. Household
   scoping becomes derivable from canonical state without changing the frozen
   `Mission` contract.

**Amendment A3 applied** — §2.2, §3.3 and §3.4 rewritten; the first-target-binds
rule added; **GD-10** added; **W7** records that mission-level household scoping
remains absent platform-wide.

### C4. Are four dimensions justified? — **No. Two are**

The draft declared `TARGET_DIMENSION = {currency, duration_months, ratio,
count}` while asserting that "no fifth value is added speculatively". Two of the
four have no consumer: the locked missions need `currency` (FI, Mortgage) and
`duration_months` (Resilience) only; Pension declares no target value at all.

Reserving values "because they are likely" is precisely the reasoning RFC-015
refused for extra event kinds, and a `ClosedVocabulary` is extended by a
governed Core change (`core/vocab.py:58-62`) — which is the correct cost for
adding a dimension, not a reason to pre-empt it.

**Amendment A4 applied** — reduced to `{currency, duration_months}`, with the
extension path stated.

### C5. Are `none` and `derived` genuinely different horizons? — **Yes, and there is a consumer**

`InstrumentApplicability` (`core/mission_assessment.py:123-143`) requires each
instrument to be `applicable`, `not_applicable` or `unavailable`, and the
registry rejects an `applicable` instrument that is absent (`:697-703`). A
steady-state mission with no date must declare ETA `not_applicable`; a mission
whose date is computed from evidence must not. Collapsing the two would make an
assessor guess which.

**Amendment A5 applied** — §6 now cites the consumer rather than asserting the
distinction.

### C6. Is `basis` free text safe in an append-only log? — **Bounded, and the cost must be stated**

`basis` is the only operator-authored prose in a target payload. The event log is
append-only and hash-chained; a household that records "saving for IVF" cannot
retract it. A redaction precedent exists (`core.evidence.redacted`,
`core/acquisition.py:356`) and this RFC deliberately does **not** extend it —
extending a redaction mechanism to a new entity is its own decision.

**Amendment A6 applied** — §9 now states the irreversibility, keeps `basis`
optional and length-bounded, and records that redaction is not extended.

### C7. Is `status: "withdrawn"` on the closure payload right? — **No**

`grammar.close()` validates `status` against a vocabulary only when one is
supplied, and `close_party` deliberately writes no status because "unlike
Mission, Party has no distinct terminal sub-states to record"
(`core/entities.py:93-96`). A Mission Target has exactly one terminal state.
Writing an unvalidated `"withdrawn"` string would put an ungoverned value in the
append-only log — the exact thing `grammar.relate()` refuses by design
(`grammar.py:75-78`) — and inventing a third vocabulary to govern one value is
worse.

**Amendment A7 applied** — withdrawal is generic closure with a reason and no
`status` extra.

### C8. Does this RFC deliver "canonical strategic intent" on its own? — **No, and the boundary needs a ruling**

Targets are declarable only against Missions, and no Mission declaration path
exists (§1.3). The four *definitions* are locked, but the four *Mission
entities* are per-household instances and exist today only in synthetic demo
data. Whether Phase 3 instantiates Missions from locked definitions, or whether
that is a separate boundary, is a genuine scoping question this RFC must not
answer for itself.

**Amendment A8 applied** — **GD-11** added; **W4** strengthened from a note into
a stated limitation in §16.

---

## Part 3 — Amendments applied before commit

| # | Amendment | Where |
|---|---|---|
| **A1** | "Revise by declaring a new Mission and abandoning the old" added to rejected alternatives, with the orphaned-history and ordering evidence | §13 |
| **A2** | The registry's blanket `except Exception` masks target-resolution failures | §4.1, W6 |
| **A3** | **Household scoping corrected** — a Mission has no household; target household is authoritative; first-target-binds; what cannot be checked is stated | §2.2, §3.3, §3.4, GD-10, W7 |
| **A4** | `TARGET_DIMENSION` reduced to `{currency, duration_months}` | §5.3 |
| **A5** | `none` vs `derived` horizon justified by `InstrumentApplicability` | §6 |
| **A6** | `basis` irreversibility stated; redaction explicitly not extended | §9, W5 |
| **A7** | Withdrawal is generic closure, no `status` extra | §3.2, §7 |
| **A8** | Mission-instantiation boundary raised as a Governor decision | GD-11, §16 |

---

## Part 4 — Residuals: what this review did **not** fix

| # | Residual | Why it stands |
|---|---|---|
| **R1** | A duplicate-target conflict makes a mission unassessable rather than picking one | Accepted cost of FR-009. Choosing arbitrarily would make an arbitrary decision about what a household is trying to achieve |
| **R2** | This architecture cannot, by itself, make a deployed instance render four live missions | Missions do not exist in a deployed log (§1.3). Named in §16 and W4; not solvable inside this boundary |
| **R3** | Nothing structurally compels a provider to consult its target (W1) | Fixing it changes a frozen RFC-006 contract; per-domain tests are the available defence |
| **R4** | The RFC number is unresolved | By design (§0). EECOM has no authority to amend a recorded Governor ruling |
| **R5** | Mission Control assesses every active Mission against the last-declared household (C3) | Pre-existing, platform-wide, and outside this burn's scope (FR-004). Recorded as W7 so it is not mistaken for something this RFC introduced |

---

## Part 5 — Flight Rule compliance

| Rule | Assessment |
|---|---|
| **FR-004** Burn discipline | Scope exclusions declared in §12 and restated in the architecture report; no production source touched |
| **FR-006** Secure by design | §9 answers every checklist question, including `N/A` answers |
| **FR-007** Deterministic validation | As-of resolution required to be equal under two distinct frozen clocks (T1-C) |
| **FR-008** Honest information | An undescribed metric refuses rather than assumes a unit; retrospective declaration is disclosed; §16 states what the RFC does not fix |
| **FR-009** Fail closed | Every gate refuses: unknown metric, dimension mismatch, cross-household, cycle, duplicate, prohibited event kind |
| **FR-011** Platform before domain | Core carries no domain vocabulary; the descriptor provider is domain-owned; Phase 1 proven against a mock domain only |
| **FR-012** Evidence before AI | No model on any target write path; `basis` is stored and never interpreted |
| **FR-013** Architecture before code | Documentation exclusively; no source, test, fixture, template or configuration changed |
| **FR-014** Review artefact continuity | This document is the durable self-review artefact; every finding carries an assertion, a reference and a disposition |
| **FR-015** Burn classification | Declared Architecture Burn; performed as one. No reclassification claimed |

---

## Part 6 — Verdict

**The architecture is internally consistent and implementable after the eight
amendments, and it is not approvable without rulings GD-1 through GD-11.**

The single most important finding is **A3**: the draft specified a
household-scoping rule that the `Mission` contract cannot satisfy. Had it
reached implementation unamended, BOOSTER would have had to invent the missing
household binding — which is exactly the failure FR-013 exists to prevent.
