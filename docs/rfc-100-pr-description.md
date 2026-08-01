# RFC-100 — Flight Operations Manual (architecture only)

**Proposed — awaiting Governor ratification.** Architecture-only burn: this
branch contains documentation exclusively — no production source, tests,
templates, CSS or runtime configuration are changed.

## What this is

RFC-100 is the permanent operating manual for Project Foundry engineering. It
governs **how Foundry is engineered**, never **what Foundry does**.

Mission Control has been an evolving convention: every brief since RFC-009 has
had to restate its own pre-flight, its own review sequence, its own report shape
and its own escalation path. That worked, but it means engineering discipline
lives in prompts rather than in the repository, and it drifts silently. RFC-100
moves it into the repository as a governed subsystem.

After ratification, an engineering brief can be reduced to:

```text
Operate under RFC-100.
Mission: <engineering objective>
```

plus the two things that genuinely change per burn — the objective's scope and
its exclusions.

## Proven behaviour only

The governing constraint on this burn was *capture proven behaviour; do not
invent process.* Every Flight Rule cites the burn that produced it, and where
the manual goes beyond evidence it says so in place rather than blending in:

- **Guido** and **TELMU** are marked *(newly named)*. Both describe work with
  clear operating evidence — RFC canon and next-burn recommendation; post-merge
  verification and status coherence — that has never had a named owner.
  Ratification is **GD-1**.
- **FR-016** (Post-Merge Verification) and **FR-017** (Documentation Coherence)
  sit in a separate §5.1 marked *proposed*. Both generalise discipline RFC-010
  and RFC-011 already impose on themselves. Ratification is **GD-2**.
- **§11.3 and §11.4** (SAFE Report, SAFE Confirmation) are labelled *specified,
  not observed* — no SAFE artefact exists in the repository, only the
  remediation evidence written in response to findings (TD4).

## What it contains

| Section | Content |
|---|---|
| 1 | Purpose; relationship to RFCs and to Governor authority |
| 2 | Seven Flight Directors — authority, responsibilities, decision boundaries, required outputs, escalation — plus an authority matrix and a role-occupancy rule |
| 3 | Ten burn classifications with owners, outputs and exit gates; effort levels |
| 4 | The mission lifecycle, its rules, and mandatory internal gates |
| 5 | Flight Rules FR-001…FR-015, each with rule, rationale and evidence; FR-016/FR-017 proposed |
| 6 | Pre-flight — nine mandatory checks, GO / CONCERN / NO-GO |
| 7 | Checkpoints — testing, documentation, security, architecture, evidence |
| 8 | SAFE Review vs SAFE Confirmation; finding fields; disposition vocabulary |
| 9 | Governor authority, freeze, merge, rulings, debt rulings, reclassification, and the absence of implementation authority |
| 10 | Post-Flight |
| 11 | Six standard reports with required headings and verdicts |
| 12 | AI operating model, independence rule, effort guidance, handoffs |
| 13 | Nine operational precedents (P1–P9) |
| 14 | Governor decisions required (GD-1…GD-6) |
| 15–17 | Scope exclusions, technical debt, success criteria |

## The Flight Rules, reviewed

All fifteen briefed rules are retained and none is weakened. The changes are to
precision, not to discipline:

- **FR-008 Honest Information** absorbs the RFC-011 B3 remediation: a missing
  input is unknown, never zero; unknown propagates through every derived lens
  and caps confidence; a genuine observed zero remains a number.
- **FR-009 Fail Closed** absorbs B4: no optional dependency may silently turn a
  guard off — an unavailable dependency refuses the operation.
- **FR-011 Platform Before Domain** absorbs B1, including the testable form:
  neutrality asserted in prose is not neutrality; a regression test asserting
  Core contains no domain vocabulary is.
- **FR-014 Review Artefact Continuity** gains a **duty to seek** (self-review
  A3), closing the loophole where a burn could dismiss findings by asserting
  their text was insufficient.
- **FR-004 / FR-015** are separated cleanly: FR-004 governs scope within a burn,
  FR-015 governs the burn's classification. The draft blurred them.

## Adversarial self-review

[`docs/reviews/RFC-100-architecture-self-review.md`](reviews/RFC-100-architecture-self-review.md)
— ten challenges, **four amendments applied before commit**:

| # | Challenge | Amendment |
|---|---|---|
| A1 | §11 presented invented report shapes as observed practice | Explicit provenance note; SAFE report shapes labelled *specified, not observed* |
| A2 | The draft forbade CAPCOM acts the Governor routinely performs | New §2.9: separation is enforced on **acts, not occupants**; a brief is never an approval, a relay is never a ruling |
| A3 | FR-014 could be used to dismiss legitimate review | Duty to seek — search, record the search, request the text via CAPCOM |
| A4 | **PR #23 was unclassifiable** under the draft lifecycle | **Hotfix Burn** added, tightly constrained; recorded behaviour, not new process |

Two watch items recorded: §12's model table is operational guidance inside a
constitutional document (W1); pre-flight checks 6 and 7 are environment-specific
(W2). Four items are explicitly **not** fixed, including the overlap with
`review-gates.md` (TD1) and the still-open RFC-011 B2 reclassification (GD-6).

## Governor decisions required

**GD-1** ratify Guido and TELMU · **GD-2** ratify FR-016 and FR-017 ·
**GD-3** confirm RFC-100 binds product RFCs · **GD-4** confirm §12's model
assignment is a default, not a constraint · **GD-5** rule on RFC-100's amendment
procedure · **GD-6** rule separately on RFC-011's open B2 reclassification.

Each carries a recommendation in §14.

## Files

- `docs/rfcs/RFC-100-flight-operations-manual.md` — the manual
- `docs/reviews/RFC-100-architecture-self-review.md` — adversarial self-review,
  four amendments, two watch items
- `docs/rfc-100-pr-description.md` — this document
- `docs/rfcs/index.md` — index row and a governance note
- `docs/README.md` — engineering-process index entry

## Explicit non-goals

RFC-100 does not design, amend or interpret Foundry platform architecture, the
Finance domain, Mission Console, Mission Assessment, Asset & Telemetry
Acquisition, the Canon, the Design Constitution, the constitutional invariants
in `architecture.md`, or any specification. It introduces no production source,
tests, templates, CSS, fixtures or runtime configuration; modifies no existing
RFC; resolves no other RFC's open question; and creates no Governor authority.

`docs/engineering/review-gates.md` is **not** modified — RFC-100 cites it and it
remains canonical for gate mechanics. Folding the two together is recorded as
TD1 for a later Documentation Burn rather than done here, because editing it
would exceed this burn's declared scope (FR-004).

## Validation

Documentation-only. No test, build or runtime behaviour changes; the suite is
unaffected. Verification for this burn is: internal cross-reference integrity,
every Flight Rule traceable to a cited burn, and every claim about repository
state checked against the repository rather than recalled.

## Review path

Governor Review → ratification → merge. This is the first burn whose own
lifecycle is defined by the document under review; RFC-100 §4 does not bind
RFC-100 until it is ratified.

**Do not merge yet.** Ready for Governor review.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
