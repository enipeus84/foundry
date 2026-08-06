# RFC-016 — Mission Target Framework: Architecture Report

Report shape per RFC-100 §11.1. Verdict vocabulary: `GO` · `CONCERN` · `NO-GO`.

Covers two burns against one architecture: the **Phase 1 Architecture Burn**
(drafting) and the **Phase 1A governance burn** (applying Governor rulings and
preparing for freeze).

## Mission Declaration *(as run)*

| Field | Phase 1 declared | Phase 1A declared | As run |
|---|---|---|---|
| **Spacecraft** | EECOM | EECOM | EECOM |
| **Fuel** | Claude Opus 5 | Claude Opus 5 | Claude Opus 5 |
| **Effort Level** | HEAVY | STANDARD | Phase 1 as **HIGH**; Phase 1A as **STANDARD** |
| **Mission Type** | Architecture Burn — Phase 1 | Governance burn — Phase 1A | Architecture Burn, then a documentation-only governance burn |
| **Authority** | Governor, via CAPCOM brief | Governor, via CAPCOM brief | unchanged |

The Phase 1 brief's effort level "HEAVY" has no entry in RFC-100 §3.2, whose
levels are HIGH / STANDARD / LOW. It was executed as **HIGH**, which is what
§3.2 and §12.3 prescribe for an Architecture Burn and for any burn touching a
Core seam. Phase 1A's declared **STANDARD** is a defined level and was executed
as declared. Both are disclosed rather than adopted silently (RFC-100 §6.0).

**Classification note (FR-015).** Phase 1A is briefed as a governance burn.
RFC-100 §3's nearest classification is **Documentation Burn** (EECOM,
documentation only, no contract change, exits to Governor Review), which is what
it was performed as. No burn reclassified itself; this is recorded so the gate
that applies is unambiguous.

---

## Pre-flight

| # | Check | Result | Evidence |
|---|---|---|---|
| 0 | Mission Declaration | **PASS with note** | Five fields present; effort level outside §3.2 vocabulary, recorded above |
| 1 | Repository | **PASS** | `~/Projects/foundry`, origin `enipeus84/foundry` (FR-001) |
| 2 | Branch | **PASS** | `rfc-016-mission-target-framework`, created for this burn (FR-002) |
| 3 | Ownership | **PASS** | Working tree clean at `023c917` before work began |
| 4 | CI | **PASS** | Latest `main` run `31094371157` — success, 2026-08-06 |
| 5 | Authentication | **PASS** | `gh auth status` authenticated as `enipeus84` |
| 6 | Python environment | **PASS** | `.venv` Python 3.13.14 (documentation-only burn; CONCERN threshold not reached) |
| 7 | Caffeinate | **CONCERN** | Not verified; a documentation burn with no long-running job |
| 8 | Worktrees | **PASS** | No stale worktree |
| 9 | RFC ownership | **PASS at Phase 1A** (was a raised NO-GO condition at Phase 1) | Governor ruling **GD-1**, 2026-08-06, settles the number |

**Phase 1 pre-flight verdict: CONCERN, proceeded.** Check 9 would have been a
NO-GO under a strict reading — the briefed RFC number was already assigned by
Governor ruling G3 to *Asset Detail & Provenance Investigation*. The burn
proceeded because stopping would have delivered nothing while the collision was
itself the first thing the Governor needed the analysis for, and because
RFC-100 §6.0 makes a briefed number a statement of fact rather than a ruling
EECOM could either rely on or overturn.

**Phase 1A pre-flight verdict: GO.** GD-1 resolved check 9. Branch, tree,
authentication and environment were re-verified; `main` CI remains green at run
`31094371157`.

---

## Architecture Summary

Foundry assesses four missions against a destination and has **no canonical
representation of what the household is trying to achieve**. RFC-016 defines
that representation.

A **Mission Target** is a household-scoped, immutable, typed, canonically
declared statement of where the household intends to arrive on one measured
dimension, and by when — held separately from the policy that judges progress
and the evidence that measures it. Revision is supersession, never mutation.
Attainment is an assessment outcome, never an event.

The problem is evidenced, not asserted:

- `declare_mission()` has **no production caller** — only `demo_data.py` and
  tests. The deployed Flight Deck therefore prints "Declare a Mission to give
  this Flight Deck something to steer by" (`mission_control.py:1186`) while the
  application exposes no route, form or command that declares one.
- All four assessors validate the declared target against a constant they
  already hold and return `unavailable` on mismatch. A household **cannot**
  declare an FI target other than £750,000, **cannot** want 24 months of
  resilience, and **cannot** declare a mortgage-freedom date at all — the target
  date must equal the contractual end date derived from evidence. The one place
  the real intent survives is the mission's **display name**.
- Revision is unrepresentable: `core.mission.updated` is folded by in-place
  assignment and written by nothing.

---

## Key Decisions

| # | Decision | Basis |
|---|---|---|
| 1 | A target is a **separately identified immutable declaration**, not a field on `Mission`, not a `MissionDefinition` attribute, not an `AssumptionSet` key | in-place folds destroy lineage; the `declare_assumption_set` precedent already governs this exact case |
| 2 | **Two canonical event kinds**, both instances of the existing five-verb grammar: `core.mission_target.declared`, `core.mission_target.closed`. `…updated` is **prohibited** and refused by the projection | RFC-015's "prove insufficiency, then ask for the minimum" discipline |
| 3 | **Typed quantities** — value + unit + closed `TARGET_DIMENSION`, validated against a domain-owned `MetricDescriptor` behind a narrow protocol | Core learns no domain unit; an undescribed metric refuses rather than assumes (FR-008, FR-011) |
| 4 | **Horizon kinds** `none` / `by_date` / `derived`, replacing four bespoke per-assessor conventions | the mapping is complete for the four locked missions; `InstrumentApplicability` is the consumer that needs the distinction |
| 5 | **As-of resolution by `effective_from`** — a historical assessment resolves the target in force at its `as_of` | otherwise raising a target silently rewrites last year's trajectory |
| 6 | **RFC-006 is untouched.** Assessors reach targets through a sibling projection, exactly as they already reach `EntityProjection` | avoids an FR-003 freeze breach for no capability gain |
| 7 | **Supersession and withdrawal ship in Phase 1**, before any real target is declared | append-only log; the same argument approved as RFC-015 ruling G6 |

---

## Contracts Frozen or Proposed

**Proposed, none frozen** (freeze is a Governor act):

- Events: `core.mission_target.declared`, `core.mission_target.closed`
- Vocabularies: `TARGET_DIMENSION` (closed), `TARGET_HORIZON_KIND` (closed)
- Shapes: `MissionTarget`, `TargetQuantity`, `MetricDescriptor`,
  `TargetMetricResolver` (Protocol), the target projection with
  `in_force(mission_id, as_of)`
- Twelve invariants (RFC §8) and eight Phase 1 acceptance criteria (§11.2)

**Explicitly unchanged:** `MissionDefinition`, `MissionAssessmentRequest`,
`MissionAssessment`, `MissionMilestone`, `MissionAssessmentRegistry`, and the
Trajectory / Margin / Confidence vocabularies.

---

## Scope Exclusions

Declared in RFC §12 and restated here (FR-004): all implementation; any route,
form, CLI or UI; migration of the four missions; the RFC-013/RFC-014/`statement_total`
questions; renaming `MissionMilestone.target_value`; multi-member authorisation;
new missions including Children; Assumption Set redesign.

**The index omission is closed.** Phase 1 deliberately left
[`docs/rfcs/index.md`](rfcs/index.md) unamended rather than assert an unsettled
number. With GD-1 ruled, Phase 1A added the RFC-016 row, the RFC-017 reservation
and the mission-instantiation note. The declared FR-017 coherence gap is
therefore closed rather than carried.

**Phase 1A exclusions.** No production code, no tests, no API, no projection, no
Mission Assessment change and no Mission Target implementation — as briefed.
`PROJECT_STATUS.md` and `CHANGELOG.md` were **not** edited: RFC-100 §2.7 makes
them TELMU's property, and no merged implementation exists to record. Their
staleness (the "Next Recommended RFC" section still names RFC-011 Phase 5) is
pre-existing, is not a contradiction created by this burn, and is flagged for
TELMU rather than corrected by EECOM acting outside its authority.

---

## Technical Debt

Seven watch items, all named in RFC §15: W1 (nothing compels a provider to
consult its target), W2 (`MissionMilestone.target_value` name collision), W3
(`core.mission.updated` foldable and unwritten), W4 (no Mission declaration
path), W5 (`basis` free text is irreversible), W6 (the registry's blanket
`except Exception` masks target-resolution failures), W7 (Mission Control
assesses every active Mission against the last-declared household).

**W7 is pre-existing and platform-wide.** It is recorded so that it is never
mistaken for something this RFC introduced, and it is not fixed here.

---

## Risks

| Risk | Mitigation |
|---|---|
| Phase 4 changes frozen assessor validation on four merged missions | each mission adopts behind its own governed amendment, reference mission first, then a mandatory Governor gate (GD-9) |
| A wrong target becomes permanent in an append-only log | supersession and withdrawal are Phase 1 deliverables, before any real declaration (GD-3) |
| "Target" now means three things in one repository | naming discipline is binding (RFC §0.5): *Mission Target* / `MissionTarget` / `core/mission_targets.py`, never the bare word |
| The framework lands and nothing visibly improves | stated plainly in RFC §16. **GD-11 ruled that mission instantiation is outside this boundary**, so this risk is now a *known, owned* gap: until a successor burn creates Missions, targets are declarable only against Missions that already exist — of which a deployed instance has none |
| Freeze is granted while four Phase 1 blocking decisions are open | GD-2, GD-3, GD-4 and GD-10 are called out in RFC §14.2 and again below. A freeze that leaves them open would hand BOOSTER an architecture it must invent inside — the FR-013 failure mode |

---

## Self-Review Outcome

[`docs/reviews/RFC-016-architecture-self-review.md`](reviews/RFC-016-architecture-self-review.md)
— **eight amendments applied before commit, five residuals recorded.**

The material one is **A3**: the draft required a target's household to agree
with "the mission's household scope". A `Mission` has no household
(`core/entities.py:56-69`), so the rule was unenforceable. It is replaced by a
two-way equality against the session plus a **first-target-binds** rule that
makes a mission's household derivable from canonical state — and by an explicit
statement of what still cannot be checked. Had that reached implementation
unamended, BOOSTER would have had to invent the missing binding, which is the
failure FR-013 exists to prevent.

Also amended: the strongest counter-proposal (revise by declaring a new Mission)
added to rejected alternatives with evidence; `TARGET_DIMENSION` cut from four
speculative values to the two the locked missions need; withdrawal changed to
generic closure with no ungoverned status string; the registry's exception
masking, the `basis` irreversibility and the horizon-kind justification all
added.

---

## Governor Decisions — ruled and open

**Ruled 2026-08-06 and applied by Phase 1A** (RFC §14.1):

| # | Ruling | Applied in |
|---|---|---|
| **GD-1** | RFC-016 confirmed for Mission Target Framework; *Asset Detail & Provenance Investigation* reassigned to **RFC-017**, amending RFC-015 G3 | RFC §0 ruling block, §0.3, header; RFC-015 §0 and §18; `index.md` |
| **GD-11** | RFC-016 governs targets attached to **existing** Missions and does **not** instantiate them | RFC §0.6, §11 Phase 3, §12, §16, W4; `index.md` |
| **W7** | Recorded as a watch item | RFC §15; RFC §14.1 |

**Open — eight** (RFC §14.2). Four are **Phase 1 blocking**:

| # | Decision | Blocks |
|---|---|---|
| **GD-2** | the two canonical event kinds and the `…updated` prohibition | **Phase 1** |
| **GD-3** | supersession and withdrawal ship before any real declaration | **Phase 1** |
| **GD-4** | the two closed vocabularies | **Phase 1** |
| **GD-10** | household scoping and first-target-binds | **Phase 1** |
| GD-5 | the RFC-006 boundary and W1 | Phase 4 |
| GD-6 | whether targets move policy bands | Phase 4 (FI) |
| GD-7 | the Mortgage Freedom contractual-ETA rule | Phase 4 (Mortgage) |
| GD-8 | assumption-implied versus declared destination | Phase 4 (FI) |
| GD-9 | adoption order and gate | Phase 4 |

**EECOM raises this for the freeze gate, and does not resolve it.** A freeze
that leaves GD-2, GD-3, GD-4 and GD-10 open would authorise BOOSTER to begin
without a settled event set, vocabulary, sequencing rule or scoping rule — which
is architecture chosen during implementation, the failure FR-013 exists to
prevent. The cleanest disposition is to rule the four alongside the freeze; each
carries an EECOM recommendation in RFC §14.2 and none requires new analysis.

---

## Files Changed

| File | Change | Burn |
|---|---|---|
| `docs/rfcs/RFC-016-mission-target-framework.md` | new — the architecture; GD-1, GD-11 and W7 applied | 1, 1A |
| `docs/reviews/RFC-016-architecture-self-review.md` | new — adversarial self-review | 1 |
| `docs/rfc-016-architecture-report.md` | new — this report | 1, 1A |
| `docs/rfcs/index.md` | RFC-016 row; RFC-017 reservation; mission-instantiation note; G3 renumbering recorded | 1A |
| `docs/rfcs/RFC-015-capture-target-registry.md` | §0 and §18 amendment note recording the G3 renumbering — **original text retained** | 1A |

**No production source, test, fixture, template, CSS or runtime configuration is
touched** (FR-013, RFC-100 §3.1 rule 3). Documentation exclusively.

**On editing a frozen RFC.** RFC-015 is frozen, and the change to it is an
*amendment note*, not a revision: the original G3 record is retained verbatim
and a dated superseding ruling is recorded beside it. RFC-100 §9.2 prescribes
exactly this — "amendments are numbered, dated and recorded in the RFC itself".
No RFC-015 contract, invariant, phase, acceptance criterion or event kind is
altered.

---

## Validation

- `git diff --stat main...HEAD` contains only the five documents above.
- `git diff --check` clean; working tree clean after commit.
- `tests/test_docs_governance.py` — **4 passed**, confirming every relative
  Markdown link in the new and amended documents resolves.
- Every repository claim in the RFC and the self-review cites a file and line,
  and each was read during this burn — `core/entities.py`, `core/grammar.py`,
  `core/vocab.py`, `core/metrics.py`, `core/scope.py`,
  `core/mission_assessment.py`, `core/capture_targets.py`,
  `finance/mission_assessment.py`, `finance/resilience_assessment.py`,
  `finance/pension_assessment.py`, `finance/mortgage_assessment.py`,
  `finance/missions.py`, `finance/runtime_bootstrap.py`, `mission_control.py`,
  `operations_web.py`, `web.py`, `demo_data.py`.
- Writer analysis for `declare_mission`, `core.mission.updated`,
  `achieve_mission` and every `router.post` was performed by exhaustive grep
  over `src`, `tests`, `scripts` and `examples`.
- **Full test suite not run** — no source changed, so there is nothing either
  burn could have broken. The docs-governance guard above is the relevant one
  and it passes.

---

## Repository State

| | |
|---|---|
| Branch | `rfc-016-mission-target-framework` (created from `main` at `023c917`) |
| Implementation files changed | **none** |
| Committed | yes — architecture package and governance updates |
| Pushed | yes |
| PR | opened; marked **do not merge yet** pending Governor freeze (FR-005) |

---

## Recommendation

**Verdict: GO — the architecture package is complete and ready for the Governor
freeze gate.**

GD-1, GD-11 and W7 are applied; the governance artefacts are coherent; the
architecture is internally consistent after eight self-review amendments; and it
is precise enough that Phase 1 requires no architectural invention — what a
target is, which events exist, what is prohibited, how conflicts resolve, how
as-of resolution works, what fails closed and what "done" means are all decided
in the document.

**Requested next step:** Governor freeze gate on the architecture PR, ruling
**GD-2, GD-3, GD-4 and GD-10 alongside the freeze**. Each has a stated EECOM
recommendation and needs no further analysis. Freezing without them would leave
BOOSTER to settle the event set, the vocabularies, the sequencing rule and the
scoping rule during implementation.

**Do not brief BOOSTER.** No implementation is authorised until the architecture
receives a formal GO and is frozen. On freeze, the freeze record is the
Governor's artefact to issue — this burn does not write one, because a freeze
record written by the party seeking the freeze is not evidence (RFC-100 §1.2).
