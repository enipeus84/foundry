# RFC-017 — Value Provenance Framework: Architecture Self-Review

Adversarial review of [`../rfcs/RFC-017-value-provenance-framework.md`](../rfcs/RFC-017-value-provenance-framework.md),
performed by EECOM against its own draft before commit, per RFC-100 §2.4 and
precedent **P9** ("a self-review that produces no amendment and no recorded
residual has not been performed").

Every claim below is grounded in a cited repository line, not in the RFC's own
assertions.

**Outcome: ten amendments applied before commit; six residuals recorded and not
fixed.** Three amendments correct defects that would have reached
implementation as unresolvable ambiguities: **A4** (a unit rule that would have
refused every legitimate factor), **A5** (one field carrying two meanings) and
**A7** (an authorisation guarantee Core cannot enforce).

> **Subsequent rulings, 2026-08-06 — GO WITH RULINGS.** Residual **R1** ("the
> RFC number is unresolved") is **closed** by Governor ruling **GD-1**: the
> number is RFC-017 — *Value Provenance Framework* — and *Asset Detail &
> Provenance Investigation* is re-earmarked as an unnumbered future consumer
> boundary. Ruling **GD-10** confirmed the programme-number collision raised in
> challenge C11's neighbourhood and removed RFC-018/019/020 from reservation.
> GD-2 through GD-7 are approved as recommended; GD-8 and GD-9 are deferred as
> recommended.
>
> **No residual other than R1 is affected**, and no amendment is withdrawn. The
> review text below is retained **unchanged** as the evidence presented to the
> gate.

> **Governor freeze, 2026-08-06.** The architecture is **frozen** at head
> `b8cc0ed`, and **Phase 1 is GO** against acceptance criteria P1-A through
> P1-H. GD-8 and GD-9 remain explicitly deferred and confer no implementation
> authority. This review remains unchanged as the evidence presented to the
> gate. See the
> [`RFC-017 architecture freeze record`](RFC-017-architecture-freeze-record.md).
>
> Residuals **R2 through R6** survive the freeze as recorded: each is a stated
> limit of the frozen architecture, not an open question, and each has a watch
> item in RFC §15.

---

## Part 1 — Current-state analysis

### 1.1 What a value can be traced to today

| Mechanism | Location | What it answers |
|---|---|---|
| `kernel.why(claim_id)` | `kernel.py:200`, `canon.py:122-138` | full provenance for a **Claim** — source events, actor, evidence, revision history |
| `MetricResult.input_references` and siblings | `core/metrics.py:57-59` | which events were consulted for a **value** — as a flat, unordered bag |
| `"N INPUT EVENT(S)"` | `mission_control.py:1566`, `:2012` | a **count** |
| `Reconciliation.difference` | `core/acquisition.py:979-987` | derived vs supplied total for **one** container case |
| `limitations: tuple[str, ...]` | `core/metrics.py:62` | everything else, in English |

The Claim layer has a provenance contract. The value layer has a bag and a
count. That asymmetry is the RFC's premise, and it is verifiable rather than
rhetorical.

### 1.2 Where a decomposition is computed and discarded — verified line by line

| Site | Computed | Discarded at |
|---|---|---|
| `finance/metrics.py:528-550` `_store_total` | per-entity contribution at `:546` | `:550` returns `(total, refs, limitations)` |
| `finance/metrics.py:552-581` `_attributed_value` | per-entity share | `:581` |
| `finance/metrics.py:583-602` `_position_totals` | numerator vs total | `:602` |
| `finance/pension_metrics.py:102-184` `_pension_wealth` | per-account value **and** its ownership weight at `:156` | `:180` `tuple(sorted(set(refs)))` |
| `core/acquisition.py:1002-1015` `market_value` | a recursive tree | `:1007` flattens every level into one tuple |

`pension_metrics.py:153-160` is the sharpest case: the ownership `weight`
determines part of the answer and **never enters `refs` at all**. A household
is shown valuation events and an exchange rate as the support for a figure that
a co-ownership declaration halved.

### 1.3 Where an explanation exists but only as presentation

`mortgage_assessment.py:716-732` emits property-equity components as sibling
`TelemetryItem`s whose only statement of relationship is a `display_group`
string and an English `qualifier` (`core/mission_assessment.py:251-257`). The
authoring comment at `:716-717` states the intent exactly —

> "These observations explain current equity; they do not determine mission
> policy or correct one another."

— and there is no contract in which to say it.

`:816-824` then computes the residual and writes it into a `limitations`
sentence. The behaviour is right; the medium cannot be tested, filtered or
consumed.

### 1.4 Where the current contract makes honesty impossible

`pension_assessment.py:1184-1241` accumulates one `refs` list across employee,
employer and salary-sacrifice fields (`:1197`) and attaches it to all three
emitted metrics (`:1213`). The employee-contribution figure is therefore
supported, on the record, by employer evidence.

This is not a coding error that a careful author would avoid. `MetricResult`
has **one** reference bag per result and no per-component association, so there
is nowhere else for the references to go. The defect is in the contract.

### 1.5 Where an exclusion vanishes entirely

`pension_metrics.py:154-155`:

```python
weight = self._weight(links, attribute_to)
if weight <= 0:
    continue
```

Four sibling exclusion paths in the same function append a limitation (`:131`,
`:138`, `:149`, and the DB conflict at `:129`). This one appends nothing. An
account is considered, rejected, and leaves no trace anywhere in the system —
while `_available` (`metrics.py:644-651`) and `_result` report the resulting
partial sum with `status="available"`.

---

## Part 2 — Challenges, answered adversarially

### C1. Is "projection, not canonical state" right? — **Yes, but the draft under-argued it**

The strongest counter is the brief's own immutability principle: *historical
explanations must never be rewritten*. Stored explanations are literally
preserved across a calculation change; computed ones are not (RFC §3.4).

The counter fails, but not for the reason the draft gave. Storage does not
*solve* calculation drift — it **relocates** it. A stored explanation survives a
calculation change and then contradicts the value the current code produces from
the same log, and the platform holds two irreconcilable answers with no rule
that can choose correctly. A computed explanation fails in the honest direction:
reproducible, or refused.

Supporting evidence that this is the platform's existing position, not a new
one: [`../architecture.md`](../architecture.md) invariant 2 ("the Canon has no
write path of its own") and architecture observation 1 ("an assessment never
becomes canonical observed state merely by being shown").

**Amendment A1 applied** — §3.4 now states the relocation argument explicitly,
because a reviewer who raises the immutability principle deserves the answer in
the document rather than in a reviewer's head.

### C2. What is `completeness` for an `observed` node? — **The draft had no answer**

`EXPLANATION_COMPLETENESS` has three values — `complete`, `partial`,
`indivisible` — and none of them fits a terminal fact. Under the draft's
derivation rule an `observed` node has zero contributions, which computes to
`residual = quantity` and `partial`: a leaf would have reported that it failed
to explain itself.

**Amendment A2 applied** — `completeness` is `EXPLANATION_COMPLETENESS | None`,
and is `None` exactly when `kind = observed`. A fourth vocabulary value was
rejected: absence is the honest representation of "no claim is being made", and
adding `not_applicable` to a closed vocabulary to represent absence is what
`None` is for.

### C3. What is `completeness` when the value itself is unavailable? — **Also unanswered**

A `derived` node with `status = unavailable` carries `quantity = None`. The
residual arithmetic then subtracts from nothing.

**Amendment A8 applied** — `completeness` and `residual` are both `None`
whenever `quantity` is `None`. Reporting `partial` there would assert an
unexplained magnitude that does not exist, which is an FR-008 breach in the
direction least likely to be noticed.

### C4. Does the unit rule work? — **No. As drafted it refuses every legitimate factor**

The draft said: "a contribution whose `unit_or_currency` differs from its
parent's is refused". Applied to the RFC's own worked examples this refuses:

- the exchange rate (dimensionless) contributing to a GBP total
  (`aggregation.py:108-134`);
- the ownership weight (a fraction) contributing to a GBP pension value
  (`pension_metrics.py:156`);
- the unit price (per-share) contributing to a market value
  (`acquisition.py:996-1000`).

Every one is a `contextual` contributor, and `contextual` contributors are
never summed — so unit agreement has no arithmetic reason to bind them.

**Amendment A4 applied** — unit agreement binds `increases` and `decreases`
only. Contextual contributors carry any unit or none.

This also produced a property worth stating rather than discovering later: a
domain that mis-declares a ratio's numerator as `increases` (GBP into a
`ratio`-unit parent) is now refused structurally instead of producing a
nonsense residual. **Amendment A3 applied** — §6.3 records it, and records its
limit: the framework verifies internal consistency, never modelling
correctness.

### C5. Does `Contribution.quantity` mean one thing? — **No. It meant two**

For an additive contributor it meant "the share taken of the parent". For a
contextual contributor it meant "the factor's own magnitude" — a rate of 1.27,
a weight of 0.50. One field, two meanings, distinguished only by a sibling
enum. That is the ambiguity RFC §1.3 exists to remove, reintroduced in the
contract that removes it.

**Amendment A5 applied** — `quantity` is `float | None`: required for additive
roles, **absent** for contextual. A contextual contributor's magnitude is
obtained by expanding it, which is the mechanism the framework already has.
The worked examples in §7 were rewritten accordingly.

### C6. Can a domain lie about a contribution's size? — **Yes, and the draft could not detect it**

Nothing in the draft related `Contribution.quantity` to the contributor node's
own `quantity`. A domain could declare a £61,200 contribution from a node that
reports £122,400, and the parent's residual would balance while the tree
contradicted itself.

**Amendment A6 applied** — on expansion, an additive contributor's node
quantity must equal its declared contribution quantity, in the same unit and
within the same tolerance; disagreement makes the **parent** `unavailable`.
Stated with its limit: contributors that are not expanded are not verified, and
the framework does not claim they are.

### C7. Is the scope guarantee enforceable? — **No. The draft specified a rule Core cannot satisfy**

The draft asserted, as a Phase 1 criterion, that "recursive expansion never
surfaces a contributor outside the requesting scope". Core cannot check that.
`resolve_scope` (`core/scope.py:29-53`) explicitly accepts caller-resolved
resource ids and states in its own docstring that domain resource ownership is
"that domain's to resolve"; Core has no view of which accounts a person holds.

This is the same class of error RFC-016's self-review found in its own draft
(A3: a household-agreement rule that the `Mission` contract could not support),
and it is the class of error most likely to survive into implementation,
because it reads like a security guarantee.

**Amendment A7 applied** — the guarantee is split:

| Guarantee | Enforced by |
|---|---|
| **No scope substitution** — requesting `Subject`, `as_of` and `known_at` are carried down unchanged | **Core**, structurally (P1-F) |
| **Scope containment** — a contributor is one the requester could have read | **the domain explainer**, defended by per-domain tests |

§9, §11.1 P1-F, §16 and watch item **W8** all restate what Core does and does
not guarantee.

### C8. Is byte-identical reproduction actually specified? — **It was asserted, not specified**

§3.3 requires that the same query produce byte-identical provenance. Nothing in
the draft constrained the **order** of `contributions` or `exclusions`, so two
conforming implementations — or one implementation over a re-sorted collection —
could satisfy every stated rule and produce different bytes.

**Amendment A10 applied** — ordering is part of the contract: explainers emit a
deterministic order and the framework never reorders. Sorting by magnitude or
significance is presentation and belongs to a consumer.

### C9. Are four vocabularies justified, or is `EXCLUSION_REASON` avoidable? — **Justified, and the alternative is real**

The strongest simplification available: fold `Exclusion` into `Contribution` as
an additive role with no quantity. That deletes one shape **and** one
vocabulary, and completeness still works (any additive contribution with no
quantity forces `partial`).

It fails on one point, and it is the point of the framework: it deletes the
**reason**. `unobserved`, `out_of_period` and `incommensurable` are the three
distinctions the shipped code already makes and then loses to prose
(`metrics.py:504`, `:515`, `:544`; `pension_metrics.py:131-152`) — or, at
`pension_metrics.py:154-155`, loses entirely. A framework whose stated purpose
is honest partial explanation cannot discard the honest part to save a
dataclass.

**Amendment A9 applied** — recorded in §4.4 and as a rejected alternative in
§13, so the simplification is visibly considered rather than apparently missed.

### C10. Does the framework contain any finance assumption? — **No, and it is testable**

Checked against the RFC's own §2.3 list. The four vocabularies contain
`observed`, `derived`, `increases`, `decreases`, `contextual`, `complete`,
`partial`, `indivisible`, `unobserved`, `out_of_period`, `incommensurable` —
eleven values, none of which names money, time, ownership, liquidity or any
`finance.*` identifier. `value_id` is opaque and unparsed (§4.1); `label` is
carried and never interpreted (§4.2).

The test is the existing FR-011 regression pattern
(`test_core_acquisition_contract_contains_no_finance_event_vocabulary`), and
Phase 1 is proven against a mock domain only. **No amendment**; recorded as
evidence that the claim is checkable rather than aspirational.

### C11. Does this RFC own its number? — **No, and it must not assume it**

RFC-016 ruling **GD-1** (2026-08-06) reserved RFC-017 for *Asset Detail &
Provenance Investigation*, recorded in
[`../rfcs/RFC-016-mission-target-framework.md`](../rfcs/RFC-016-mission-target-framework.md)
§0, [`../rfcs/RFC-015-capture-target-registry.md`](../rfcs/RFC-015-capture-target-registry.md)
§0 and [`../rfcs/index.md`](../rfcs/index.md).

Unlike the RFC-016 collision, the subjects are adjacent: both contain the word
*provenance*. The rhythm test (RFC-012 §2.8) separates them — one is a rare
investigation **surface**, this is a **substrate** with no rhythm at all — but
that is analysis, not authority.

**No amendment; the position is the design.** §0 states the analysis, offers R1
and R2, adopts neither, and **withholds the [`index.md`](../rfcs/index.md) row**
until the Governor rules — exactly as RFC-016's Phase 1 burn withheld its own.
Recorded as residual **R1**.

---

## Part 3 — Amendments applied before commit

| # | Amendment | Where |
|---|---|---|
| **A1** | Canonical storage **relocates** calculation drift into a contradiction rather than solving it — the strongest counter-argument answered in the document | §3.4 |
| **A2** | `completeness` is `None` for an `observed` node; no fourth vocabulary value | §4.2, §4.5 |
| **A3** | Unit agreement structurally catches the commonest mis-modelling (a factor declared as a share), with its limit stated | §6.3 |
| **A4** | **Unit agreement binds additive roles only**; contextual contributors carry any unit — the draft refused every legitimate factor | §4.3, §6.3, §8 |
| **A5** | **`Contribution.quantity` carries one meaning**: required for additive roles, absent for contextual | §4.3, §7.1, §7.2 |
| **A6** | An expanded additive contributor must agree with its declared contribution; disagreement makes the parent `unavailable` | §5.1, §6.1, §8, §10 |
| **A7** | **Authorisation split**: Core guarantees no scope substitution; domain scope containment is a per-domain obligation Core cannot check | §9, §11.1 P1-F, §16, W8 |
| **A8** | `completeness` and `residual` are `None` when `quantity` is `None` | §4.5, §10 |
| **A9** | Folding `Exclusion` into `Contribution` considered and rejected, with the reason it fails | §4.4, §13 |
| **A10** | Deterministic ordering is part of the contract; the framework never reorders | §4.2, §8, §10 |

---

## Part 4 — Residuals: what this review did **not** fix

| # | Residual | Why it stands |
|---|---|---|
| **R1** | ~~The RFC number is unresolved (§0)~~ — **CLOSED 2026-08-06 by ruling GD-1** | Was: by design; EECOM has no authority to amend a recorded Governor ruling (RFC-100 §2.4). Ruled R1: RFC-017 is *Value Provenance Framework*; the investigation boundary is unnumbered |
| **R2** | Nothing compels any provider to publish a decomposition; a domain may keep discarding it and remain compliant (W1) | Compelling it changes a frozen RFC-001/RFC-006 contract. Per-domain tests are the available defence — the identical residual RFC-016 recorded |
| **R3** | Core cannot verify that an anchor genuinely supports a node's quantity (W9) | Verifying it means re-deriving the value, which is the boundary §6.1 exists to hold |
| **R4** | Cross-decomposition double counting is undetectable (W2) | Union rules are domain property (`aggregation.py:64-81`); adopting them would make Core an aggregation authority |
| **R5** | Historical explanation is reproducible only while its calculation version is still producible (W3) | Pre-existing and platform-wide; contained by refusing rather than re-deriving. Retention is a successor boundary |
| **R6** | `label` is presentation-adjacent data inside a contract that excludes presentation (§4.2) | A judgement call, defensible either way. Without it a consumer holds a `value_id → text` mapping table, which recreates §1.3's coupling one layer up. Bounded: optional, never parsed, never an identity, ignorable |

---

## Part 5 — Flight Rule compliance

| Rule | Assessment |
|---|---|
| **FR-004** Burn discipline | Scope exclusions declared in §12 and restated in the architecture report; no production source touched |
| **FR-006** Secure by design | §9 answers every checklist question, including the corrected authorisation split and the depth-bound abuse case |
| **FR-007** Deterministic validation | Bitemporal reproduction asserted under two distinct frozen clocks (P1-D); ordering determinism added by A10 |
| **FR-008** Honest information | Completeness is derived and cannot be self-declared; a zero-contribution node reports `partial`, not `complete`; an irreproducible historical explanation is `unavailable`, never re-derived; §16 states what the RFC does not fix |
| **FR-009** Fail closed | Every gate refuses: unknown `value_id`, unit mismatch, quantity present on a contextual role, cycle, repeated additive contributor, empty calculation version, expanded-contributor disagreement |
| **FR-011** Platform before domain | Eleven vocabulary values, none domain-shaped; `value_id` opaque; Phase 1 proven against a mock domain only (C10) |
| **FR-012** Evidence before AI | No model on any provenance path — enforced by absence, the `core/metrics.py:18-22` pattern; `label` is never interpreted |
| **FR-013** Architecture before code | Documentation exclusively; no source, test, fixture, template or configuration changed |
| **FR-014** Review artefact continuity | This document is the durable self-review artefact; every finding carries an assertion, a repository reference and a disposition |
| **FR-015** Burn classification | Declared Architecture Burn; performed as one. No reclassification claimed |
| **FR-017** Documentation coherence | Was deliberately incomplete at review time: [`../rfcs/index.md`](../rfcs/index.md) was not amended because the number was unruled, and the gap was declared rather than hidden. **Closed 2026-08-06** by the governance burn that applied GD-1 — index row added, and the reservation amendment recorded in RFC-015 and RFC-016 beside the retained originals |

---

## Part 6 — Verdict

**The architecture is internally consistent and implementable after the ten
amendments, and it is not approvable without a ruling on GD-1.**

The three findings that mattered are **A4**, **A5** and **A7**, and they share a
shape: each was a rule that read correctly and could not be satisfied. A4 would
have refused every legitimate contextual factor — including the ownership share
whose invisibility is one of the defects the RFC exists to fix. A5 would have
handed BOOSTER a field with two meanings and an enum to disambiguate them. A7
would have handed a reviewer a security guarantee Core cannot enforce, which is
worse than no guarantee at all.

The framework that survives is smaller than the one drafted: four vocabularies,
eleven values, five shapes, one seam, and one rule — **completeness is derived,
never declared** — that no participant can subvert.
