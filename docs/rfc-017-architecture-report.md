# RFC-017 — Value Provenance Framework: Architecture Report

Report shape per RFC-100 §11.1. Verdict vocabulary: `GO` · `CONCERN` · `NO-GO`.

Covers two burns against one architecture: the **RFC-017 Architecture Burn**
(drafting) and the **RFC-017 governance burn** (applying Governor rulings GD-1
through GD-10 and preparing for the freeze gate).

## Mission Declaration *(as run)*

| Field | Architecture burn declared | Governance burn declared | As run |
|---|---|---|---|
| **Spacecraft** | EECOM | EECOM | EECOM |
| **Fuel** | Claude | Claude | Claude |
| **Effort Level** | not stated in the brief | not stated | Architecture burn as **HIGH**; governance burn as **LOW** |
| **Mission Type** | Architecture Burn — "architecture-only burn" | applying Governor rulings | Architecture Burn, then a documentation-only governance burn |
| **Authority** | Governor, via engineering brief | Governor ruling, 2026-08-06 | unchanged |

**Classification of the second burn (FR-015).** The ruling briefed it as
"amend the RFC, report, self-review and governance record". RFC-100 §3's
nearest classification is **Documentation Burn** (EECOM, documentation only, no
contract change, exits to Governor Review), which is what it was performed as.
No burn reclassified itself; this is recorded so the applicable gate is
unambiguous.

**Effort level disclosure (RFC-100 §6.0).** The brief declared no effort level.
RFC-100 §3.2 and §12.3 prescribe **HIGH** for an Architecture Burn and for any
burn touching a Core seam; this burn proposes four new Core vocabularies and a
Core-owned resolver, so HIGH was executed. The omission is disclosed rather
than resolved silently.

**Classification (FR-015).** Declared and performed as an **Architecture
Burn**. The brief's constraints — "Do not implement code · Do not modify
schemas · Do not introduce events · Do not build UI" — match RFC-100 §3.1
rule 3 exactly. No burn reclassified itself.

---

## Pre-flight

| # | Check | Result | Evidence |
|---|---|---|---|
| 0 | Mission Declaration | **PASS with note** | Four of five fields present; effort level absent from the brief and disclosed above |
| 1 | Repository | **PASS** | working copy of `enipeus84/foundry` (FR-001) |
| 2 | Branch | **PASS** | `claude/rfc-017-value-provenance-5ixkye`, the designated branch (FR-002) |
| 3 | Ownership | **PASS** | working tree clean before work began |
| 4 | CI | **NOT VERIFIED** | no CI access from this session; documentation-only burn changing no source, so no CI-observable surface is touched |
| 5 | Authentication | **N/A** | no credentialed operation performed |
| 6 | Python environment | **N/A** | documentation-only burn; no test execution required by the change |
| 7 | Caffeinate | **N/A** | no long-running job |
| 8 | Worktrees | **PASS** | no stale worktree |
| 9 | **RFC ownership** | **PASS at the governance burn** (was a raised CONCERN at the architecture burn) | Governor ruling **GD-1**, 2026-08-06, settles the number: RFC-017 is *Value Provenance Framework* |

**Architecture burn pre-flight verdict: CONCERN, proceeded.**

Check 9 was the same condition RFC-016's Phase 1 burn met and recorded, and it
was handled the same way. The burn proceeded because stopping would have
delivered nothing while the collision is itself the first thing the Governor
needs analysis for, and because RFC-100 §6.0 makes a briefed number "a
statement of fact, not a grant of authority" — something EECOM may neither rely
on nor overturn. The analysis is RFC §0; the decision was **GD-1**.

**Governance burn pre-flight verdict: GO.** GD-1 resolved check 9. Branch and
tree were re-verified clean before work began.

---

## Architecture Summary

Foundry reports values and cannot decompose any of them. RFC-017 defines the
contract by which any value in any domain can be explained.

A **Value Provenance** is the deterministic, reproducible explanation of one
observable value: the contributions that produce it, each anchored in immutable
canonical facts, together with a **derived and unfalsifiable** statement of how
completely those contributions account for it.

The problem is evidenced, not asserted. Six defects, each with a file and line:

| # | Defect | Evidence |
|---|---|---|
| 1 | References are a flat bag; the rendered honesty signal is a **count** | `core/metrics.py:57-59`; `mission_control.py:1566`, `:2012` |
| 2 | The decomposition is computed and discarded — including the ownership share that determines part of the pension figure and **never enters the reference list** | `finance/metrics.py:546-550`; `finance/pension_metrics.py:153-180` |
| 3 | An explanation already exists, in **display strings** — the relationship between whole and parts survives only in a `display_group` and an English `qualifier` | `finance/mortgage_assessment.py:716-732` |
| 4 | Completeness is computed and then written into **prose** | `finance/mortgage_assessment.py:816-824` |
| 5 | Evidence is **over-attributed**: the employee-contribution figure is supported, on the record, by employer evidence | `finance/pension_assessment.py:1197`, `:1213` |
| 6 | Exclusions disappear and a partial sum reports `status="available"`; one exclusion path leaves **no trace at all** | `finance/metrics.py:540-549`, `:644-651`; `finance/pension_metrics.py:154-155` |

Defect 5 is not a coding error a careful author would avoid: `MetricResult` has
one reference bag per result and nowhere to put a per-component association.
The defect is in the contract, which is why the answer is a contract.

---

## Key Decisions

| # | Decision | Basis |
|---|---|---|
| 1 | **Provenance is a deterministic projection with zero canonical events, in every phase** | storing it puts a fold's output into its own input and creates a second truth that can contradict the first; and storage relocates calculation drift into a contradiction rather than solving it (RFC §3.2, §3.4) |
| 2 | **Completeness and residual are derived by the framework, never declared by a domain** | a self-reported honesty flag is the first thing to rot. No participant can claim to have explained what it has not (RFC §4.5) |
| 3 | **Three contribution roles** — `increases`, `decreases`, `contextual` — describing arithmetic relationships, never domain meanings | `contextual` is the only honest way to express that an ownership share or an exchange rate participated without carrying a share. Signed quantities were considered and rejected (RFC §13) |
| 4 | **Two node kinds** — `observed` / `derived` — answering only "does the explanation continue here?" | quality is already modelled by `EVIDENCE_GRADE` (`core/vocab.py:90-93`) and is not duplicated |
| 5 | **Bitemporal queries** (`as_of` + `known_at`), adopting RFC-011's existing mechanism (`core/acquisition.py:946-949`) | this is what makes "historical explanations are never rewritten" true, rather than aspirational |
| 6 | **Core routes and verifies; Core never calculates.** It may sum and compare within one unit and may never transform one | the `MetricRegistry` discipline (`core/metrics.py:103-105`) and the RFC-012 R9 mitigation: a missing explainer yields **no** provenance, never an invented one |
| 7 | **Bounded, lazy recursion; a cycle is a refusal, not a truncation** | `ValuationLenses.market_value` (`core/acquisition.py:1002-1015`) already recurses eagerly and flattens the structure at `:1007` — the defect, reproduced by the fix |

---

## Contracts Frozen or Proposed

**Proposed, none frozen** (freeze is a Governor act):

- **Vocabularies (all closed, all new):** `PROVENANCE_NODE_KIND` (2 values),
  `CONTRIBUTION_ROLE` (3), `EXPLANATION_COMPLETENESS` (3, derived),
  `EXCLUSION_REASON` (3) — eleven values in total
- **Shapes:** `ValueReference`, `ProvenanceNode`, `Contribution`, `Exclusion`,
  `ExplanationDescriptor`
- **Seams:** `ValueExplainer` (Protocol), `ProvenanceResolver`
- **Fifteen invariants** (RFC §8) and **eight Phase 1 acceptance criteria**
  (RFC §11.1)

**Reused rather than re-invented:** `Subject` (`core/scope.py:21`),
`METRIC_STATUS` (`core/vocab.py:124-127`), `EVIDENCE_GRADE`, the bitemporal
read shape, the registry/descriptor seam pattern.

**Explicitly unchanged:** `MetricRequest`, `MetricResult`, `MetricProvider`,
`MetricRegistry`, `MissionDefinition`, `MissionAssessmentRequest`,
`MissionAssessment`, `MissionMilestone`, `TelemetryItem`, `MissionTarget`,
`TargetQuantity`, and every existing vocabulary. **No event kind is added, in
any phase.**

---

## Scope Exclusions

Declared in RFC §12 and restated here (FR-004): all implementation; all schema
changes; all event definitions; UI, Flight Deck, routes, forms and CLI; Mission
Assessment and any assessor change; capture, editing, correction and manual
attribution workflows; API endpoints and implementation classes; retrofitting
any shipped metric; caching and performance envelope; cross-decomposition
double-count detection; the RFC-013 numbering debt, RFC-014, and mission
instantiation; and any architecture for the consumer boundaries named in RFC
§0.4 and §6.4 — including the *Asset Detail & Provenance Investigation* surface
that GD-1 re-earmarked, which requires its own burn and its own boundary
challenge.

**The index omission is closed.** The architecture burn deliberately left
[`docs/rfcs/index.md`](rfcs/index.md) unamended rather than assert an unruled
number — the RFC-016 Phase 1 precedent — and declared the resulting FR-017
coherence gap rather than hiding it. With GD-1 ruled, the governance burn added
the RFC-017 row, rewrote the reservation note, and recorded the boundary's
re-earmarking in RFC-015 and RFC-016 beside their retained originals. The
declared gap is therefore **closed rather than carried**.

**Governance burn exclusions.** No production code, no tests, no contract
change and no architectural change of any kind. The rulings were applied as
recorded; nothing was reinterpreted. `PROJECT_STATUS.md` and `CHANGELOG.md`
were **not** edited: RFC-100 §2.7 makes them TELMU's property, and no merged
implementation exists to record.

---

## Technical Debt

Nine watch items, all named in RFC §15:

| # | Item |
|---|---|
| W1 | Nothing compels a provider to publish a decomposition |
| W2 | Cross-decomposition double counting is undetectable |
| W3 | Executable historical calculation versions are not retained |
| W4 | Recursive expansion multiplies an already-uncached per-request replay cost |
| W5 | Shipped over-attribution persists until a phase adopts provenance |
| W6 | The word *provenance* now has five meanings in the repository |
| W7 | The assessment registry's blanket `except Exception` masks failure origin |
| W8 | Core cannot verify domain scope containment during expansion |
| W9 | Core cannot verify that an anchor supports a node's quantity |

**W3, W4, W5 and W7 are pre-existing.** They are recorded so they are never
mistaken for something this RFC introduced, and none is fixed here.

---

## Risks

| Risk | Mitigation |
|---|---|
| The framework becomes a second calculation layer — the RFC-012 R9 failure mode | Core may sum and compare within one unit and may never transform one (RFC §6.1). A missing explainer yields no provenance, never an invented one. Asserted by P1-A and P1-B |
| A consumer surface is built before a **partial** explanation exists, and treats `partial` as an error | Proposed binding sequencing rule (RFC §11): Phase 3 — pension wealth, chosen *because* it is partial — ships before any consumer. The RFC-015 G6 precedent, on the same argument |
| Domains adopt the contract by wrapping today's flat reference bags, carrying today's over-attribution into the new shape | Phase 2 and Phase 3 acceptance must assert that the `pension_assessment.py:1213` over-attribution is **not** reproduced. Named as W5 rather than assumed away |
| Recursive expansion degrades an already-uncached replay path | Depth bound is mandatory, not advisory (RFC §5.1); it is also the denial-of-service mitigation in RFC §9 |
| A framework about honesty ships an authorisation guarantee it cannot enforce | Corrected before commit by self-review **A7**: Core guarantees no scope substitution; domain containment is a stated per-domain obligation (W8) |
| Freeze is granted while five Phase 1 blocking decisions are open | GD-2 through GD-6 are called out in RFC §14 and again below. A freeze leaving them open hands BOOSTER the storage model, the vocabularies, the honesty rule and Core's arithmetic bound to settle during implementation — the FR-013 failure |

---

## Self-Review Outcome

[`docs/reviews/RFC-017-architecture-self-review.md`](reviews/RFC-017-architecture-self-review.md)
— **ten amendments applied before commit, six residuals recorded.**

Three mattered, and they share a shape: each was a rule that read correctly and
could not be satisfied.

- **A4** — the draft's unit rule ("a contribution whose unit differs from its
  parent's is refused") would have refused **every legitimate contextual
  factor**, including the ownership share whose invisibility is defect 2 above.
  Unit agreement now binds additive roles only.
- **A5** — `Contribution.quantity` meant "share of the parent" for additive
  roles and "the factor's own magnitude" for contextual ones. One field, two
  meanings, disambiguated by a sibling enum: the exact ambiguity the RFC exists
  to remove. It is now required for additive roles and absent for contextual.
- **A7** — the draft asserted, as a Phase 1 criterion, that expansion never
  surfaces a contributor outside the requesting scope. **Core cannot check
  that**: `resolve_scope` (`core/scope.py:29-53`) takes no view on domain
  ownership by design. This is the same class of error RFC-016's self-review
  caught in its own draft (A3), and it is the class most likely to survive into
  implementation because it reads like a security guarantee.

Also amended: canonical storage shown to relocate rather than solve calculation
drift (A1); `completeness = None` for terminal and unvalued nodes (A2, A8);
expanded-contributor agreement verification (A6); folding `Exclusion` into
`Contribution` considered and rejected with its reason (A9); deterministic
ordering made part of the contract (A10).

---

## Governor Decisions — ruled 2026-08-06

**Verdict: GO WITH RULINGS. All ten decisions are disposed; none remains open.**

| # | Decision | Ruling | Applied in |
|---|---|---|---|
| **GD-1** | The RFC number | **R1 approved.** RFC-017 is *Value Provenance Framework*; *Asset Detail & Provenance Investigation* becomes an **unnumbered future consumer boundary** | RFC §0 ruling block, header, §6.4, §12, §16; RFC-016 §0/§14.1/header; RFC-015 §0/§18; `index.md` |
| **GD-2** | Deterministic projection, zero canonical events, every phase | **Approved as recommended** | RFC §3, §8 |
| **GD-3** | Four closed vocabularies, eleven values | **Approved as recommended**; extension is a governed Core change | RFC §4 |
| **GD-4** | Completeness derived, never declared | **Approved as recommended** | RFC §4.5 |
| **GD-5** | Core's arithmetic bound | **Approved as recommended** | RFC §6.1, §6.3 |
| **GD-6** | Bounded, lazy recursion with cycle refusal | **Approved as recommended** | RFC §5 |
| **GD-7** | Partial explanation before any consumer surface | **Approved as recommended** | RFC §11 |
| **GD-8** | Whether an assessor must consult provenance (W1) | **Deferred as recommended.** Authorises no assessor change and no RFC-006 amendment | RFC §14, W1 |
| **GD-9** | Whether `MetricResult`'s reference bag is superseded | **Deferred as recommended.** Phase 5 remains unauthorised | RFC §11, §14 |
| **GD-10** | The programme sequence | **Collision confirmed.** RFC-018/019/020 are **not reserved numbers**; Mission Target capture is RFC-016 adoption unless a future burn proves a new boundary; mission assessment belongs to RFC-006; Flight Deck intelligence is unnumbered | RFC §0.4 ruling block, §6.4, §12; `index.md` |

### How the boundary re-earmarking was recorded — the auditability requirement

The ruling required the reservation change to be "explicit and auditable". Four
documents carry it, and in every case the **original wording is retained
verbatim** with a dated amendment recorded beside it (RFC-100 §9.2):

| Document | Change | Original retained? |
|---|---|---|
| `docs/rfcs/RFC-016-mission-target-framework.md` | header note; §0 amendment block after the retained "Ruled: R1" block; §14.1 GD-1 row extended | **yes** — the RFC-016 ruling text is untouched |
| `docs/rfcs/RFC-015-capture-target-registry.md` | §0 **second** amendment block to G3, below the first; §18 G3 row records both amendments in sequence | **yes** — both the original block and the first amendment are untouched |
| `docs/rfcs/index.md` | RFC-017 row added; reservation note rewritten with a three-move amendment history; GD-10 table added | n/a — an index, not a ruling record |
| `docs/rfcs/RFC-017-value-provenance-framework.md` | §0 and §0.4 ruling blocks; §0.1–§0.3 retained as the analysis that produced the ruling | **yes** |

**The boundary has now moved twice, and both moves are on the record.** G3
earmarked it RFC-016; RFC-016's GD-1 moved it to RFC-017; RFC-017's GD-1 moved
it off numbering. `index.md` states that history in one place so a reader never
has to reconstruct it.

### Two artefacts deliberately **not** amended

| Artefact | Why |
|---|---|
| [`docs/reviews/RFC-016-architecture-freeze-record.md`](reviews/RFC-016-architecture-freeze-record.md) | A **Governor artefact** recording the result of a gate held on 2026-08-06. Its statement that "RFC-017 remains reserved for Asset Detail & Provenance Investigation" was true at that gate. Editing it would rewrite a historical record rather than amend a live one |
| [`docs/rfc-016-architecture-report.md`](rfc-016-architecture-report.md) and RFC-016's self-review | Completed burn artefacts. Both describe what a past burn did and are accurate as of their dates |

This is stated rather than left implicit, so a reader who greps for `RFC-017`
and finds the older wording in those three files knows it is retained history,
not an unpropagated amendment.

---

## Files Changed

| File | Change | Burn |
|---|---|---|
| `docs/rfcs/RFC-017-value-provenance-framework.md` | new — the architecture; GD-1 through GD-10 applied | architecture, governance |
| `docs/reviews/RFC-017-architecture-self-review.md` | new — adversarial self-review; subsequent-rulings block added, R1 closed, FR-017 row updated | architecture, governance |
| `docs/rfc-017-architecture-report.md` | new — this report | architecture, governance |
| `docs/rfcs/index.md` | RFC-017 row; reservation note rewritten with its amendment history; GD-10 programme-number table | governance |
| `docs/rfcs/RFC-016-mission-target-framework.md` | header note, §0 amendment block, §14.1 GD-1 row — **original text retained** | governance |
| `docs/rfcs/RFC-015-capture-target-registry.md` | §0 second amendment block, §18 G3 row — **original text and first amendment both retained** | governance |

**No production source, test, fixture, template, CSS or runtime configuration
is touched** (FR-013, RFC-100 §3.1 rule 3). Documentation exclusively.

**On editing two frozen RFCs.** RFC-015 and RFC-016 are both frozen, and the
changes to them are **amendment notes, not revisions**: no contract, invariant,
phase, acceptance criterion, event kind or other ruling in either document is
altered, and every original wording is retained verbatim. RFC-100 §9.2
prescribes exactly this, and it is the same mechanism RFC-016's own Phase 1A
burn used on RFC-015.

---

## Validation

- `git diff --stat main...HEAD` contains only the three new documents above.
- `tests/test_docs_governance.py` — relative-Markdown-link resolution passes
  for the new documents.
- Every repository claim in the RFC and the self-review cites a file and line,
  and each was read during this burn: `eventlog.py`, `canon.py`, `kernel.py`,
  `core/metrics.py`, `core/vocab.py`, `core/scope.py`, `core/grammar.py`,
  `core/evidence.py`, `core/acquisition.py`, `core/mission_assessment.py`,
  `finance/metrics.py`, `finance/pension_metrics.py`, `finance/aggregation.py`,
  `finance/pension_evidence.py`, `finance/mortgage_evidence.py`,
  `finance/pension_assessment.py`, `finance/mortgage_assessment.py`,
  `mission_control.py`, `docs/architecture.md`.
- The claim that the ownership `weight` never enters the pension reference list
  (defect 2) was verified by reading `pension_metrics.py:153-160` in full, not
  by grep.
- The claim that four exclusion paths append a limitation and one does not
  (defect 6) was verified against `pension_metrics.py:129-155`.
- **Full test suite not run** — no source changed, so there is nothing either
  burn could have broken.

**Governance burn validation.** Every relative Markdown link in the six changed
documents resolves (`tests/test_docs_governance.py` link rule, executed
directly); every Markdown table in `index.md` has a consistent cell count; and
an exhaustive grep for `RFC-017` across `docs/` confirms that the only
occurrences of the superseded reservation wording are in the three historical
artefacts named above as deliberately unamended.

---

## Repository State

| | |
|---|---|
| Branch | `claude/rfc-017-value-provenance-5ixkye` |
| Implementation files changed | **none** |
| Committed | yes — architecture package, then the governance amendments |
| Pushed | yes |
| PR | [#45](https://github.com/enipeus84/foundry/pull/45); architecture frozen at `b8cc0ed`. Merge remains a Governor act (FR-005) |

---

## Recommendation

**Verdict: GO — rulings applied; the package went to the freeze gate and was
frozen. See the freeze result below.**

The framework is smaller than the problem it addresses, which was the
Governor's stated guidance: four vocabularies, eleven values, five shapes, one
seam, zero events, and one rule — **completeness is derived, never declared** —
that no participant can subvert. It is precise enough that Phase 1 requires no
architectural invention: what a provenance record is, what is stored (nothing),
what is verified, what is refused, how recursion terminates, what Core may and
may not compute, and what "done" means are all decided in the document.

### Freeze blockers at the gate — **none**

| Condition for freeze | State |
|---|---|
| RFC number settled and the reservation change recorded | **PASS** — GD-1; four documents amended, originals retained |
| Programme-number collisions resolved | **PASS** — GD-10; no number is reserved beyond RFC-014 |
| Canonical event contract settled | **PASS** — GD-2; zero events, in every phase |
| Vocabularies settled | **PASS** — GD-3; four closed vocabularies, eleven values |
| Honesty rule settled | **PASS** — GD-4; completeness is derived, never declared |
| Core's computational bound settled | **PASS** — GD-5 |
| Recursion and termination settled | **PASS** — GD-6 |
| Sequencing settled | **PASS** — GD-7 |
| Open implementation-critical decisions | **PASS** — none remain. GD-8 and GD-9 are deferred to future governed decisions and authorise nothing now |
| Documentation coherence (FR-017) | **PASS** — the declared index gap is closed |

**Nothing blocks the freeze gate.** Phase 1 requires no architectural
invention: what a provenance record is, what is stored (nothing), what is
verified, what is refused, how recursion terminates, what Core may and may not
compute, and what "done" means are all decided in the document and all now
ruled.

**Two items were raised at the gate, and both are now ruled:**

1. **Freeze scope — ruled: Phase 1 only.** RFC §11 now carries an Authority
   column recording it. Phases 2 and 3 remain architecturally described and
   unauthorised; Phase 4 and later retain their stated gates.
2. **§6.4 device — ruled: not a blocker, and not to be done.** The contract is
   already normative in the RFC, and documentation churn solely to restate it
   is not authorised. The item is closed, not carried as debt.

---

## Governor freeze result — 2026-08-06

**GO — RFC-017 is FROZEN at head `b8cc0ed9c63b10d2fbc03ec9440c154826c7efd6`.**

The Governor accepted the amended architecture, settled GD-1 through GD-7 as
recorded, kept GD-8 and GD-9 explicitly deferred with **no implementation
authority conferred**, and confirmed that GD-10 resolves programme numbering
**without reserving successor RFC numbers**. The formal record is
[`reviews/RFC-017-architecture-freeze-record.md`](reviews/RFC-017-architecture-freeze-record.md),
held separately from this report and from the RFC and self-review at the
Governor's direction, so the decision is never mistaken for self-certification
(RFC-100 §1.2, §9.4).

**Phase 1 is authorised** — the Core Value Provenance Framework, against
acceptance criteria P1-A through P1-H, proven against a mock domain only. The
freeze record enumerates the nine frozen invariants that Phase 1 must preserve;
a change to any of them is a change to frozen architecture (FR-003) and a
Governor decision, not an implementation choice.

**Nothing else is authorised**: no Phase 2 or 3 explainer, no consumer or
surface, no assessor change, no `MetricResult` change, no retrofit of a shipped
metric, and no canonical event in this or any later phase.

**Next burn.** Phase 1 is an **Implementation Burn owned by BOOSTER**
(RFC-100 §3), requiring its own brief and its own pre-flight. EECOM has **no
implementation authority** (§2.4) and this burn does not begin it. Under §2.9
rule 1 the separation is on acts within a burn, so the role may be occupied by
the same party on a later, separately classified burn — but it is a different
burn, and it is not self-authorising.
