# RFC-100 — Flight Operations Manual (architecture only, Revision 2)

**Revision 2 — Governor amendments applied. Awaiting Governor final architecture
review and freeze.** Architecture-only burn: this branch contains documentation
exclusively — no production source, tests, templates, CSS or runtime
configuration are changed.

The Governor's first architecture review returned **GO WITH AMENDMENTS**,
accepting the constitutional model, the Mission Control organisation and the
Flight Rules, and directing five refinements. All five are applied. Nothing was
redesigned: no Flight Director responsibility, lifecycle stage, burn
classification, Governor authority, existing Flight Rule or architectural
decision is altered.

## Revision 2 — amendment summary

| # | Amendment | What changed |
|---|---|---|
| **1** | **Three-layer structure** | New §1.5 makes the layers explicit — **Layer 1 Constitution** (§1–§5: purpose, precedence, roles, classification, lifecycle, Flight Rules), **Layer 2 Operations Manual** (§6–§10: pre-flight, checkpoints, SAFE, Governor procedure, post-flight), **Layer 3 Engineering Templates** (§11–§12: reports, model guidance) — each with its own change control, plus a supporting record (§13–§17, Appendix A). Every major section is tagged, and a layer-discipline clause forbids a lower layer weakening a higher one |
| **2** | **Precedence** | New normative §1.6, rules **P1–P8**: RFC-100 governs engineering governance; product RFCs govern product architecture; neither redefines the other's domain; the constitutional invariants in `architecture.md` are prior to both; **genuine conflict stops work and requires a Governor ruling** (P6); silence is not conflict (P7); and four Flight Rules are shared-boundary floors (P8, from self-review A5) |
| **3** | **Flight Rule format** | Every rule now carries **Identifier · Rule · Rationale · Provenance · Verification** in that order. **Verification is new to all seventeen rules** — the test, guard, artefact or pre-flight item a reviewer inspects. A §5 preamble defines the standard and a verification-mode table (self-review A6) separates the four test-verified rules from the thirteen artefact-verified ones |
| **4** | **Model guidance** | New §12.0 states that the model table **records current recommended operating practice and is not normative**: model selection may evolve without constitutional amendment, no burn is out of compliance for using a different model, and review standards do not change with the model. §12.1 is relabelled *(non-normative)*; the independence rule becomes §12.2 *(normative)* |
| **5** | **Validation appendix** | New **Appendix A — How Mission Control was validated**: RFC-009, RFC-010 and RFC-011 element by element, each row separating *observed* from *validated* from *produced*, every fact checkable against the repository. **A.4 states what the appendix does not cover** — Guido and TELMU unproven, no SAFE artefact exists, four gates unbuilt, FR-016/FR-017 lessons rather than operating rules, one environment |

**Governor decisions:** all six retained. **GD-4** and **GD-5** are restated in
the vocabulary the amendments created — same questions, same recommendations —
because Amendment 4 supersedes "a default" with the sharper non-normative
framing and Amendment 1 supersedes section-number amendment procedure with the
three layers. GD-1, GD-2, GD-3 and GD-6 are untouched.

**Revision 2 self-review** produced two further amendments before commit: **A5**
precedence rule P8, because P2 as first drafted implied RFC-100 never constrains
product behaviour while FR-008, FR-009, FR-011 and FR-012 plainly do; and **A6**
the verification-mode table, because labelling all seventeen rules "verifiable"
without distinguishing test-verified from artefact-verified would have created
the appearance of an audit rather than an audit.

**Preservation audit.** Every removed line was checked: only §1.3's duplicated
bullet (now normative P3), §5's old preamble, §12's preamble and subsection
numbering, and the GD-4/GD-5 restatements. **All fifteen Flight Rule statements
are verbatim**; §2, §3 and §4 change only by their layer tag.

---

## Revision 1

The material below describes the manual as first submitted. The Governor
accepted it in principle; Revision 2 refines it and supersedes nothing here
except where the amendment summary above says so.

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
| 1 | Purpose; relationship to RFCs and to Governor authority; the three governance layers (§1.5); precedence, normative (§1.6) |
| 2 | Seven Flight Directors — authority, responsibilities, decision boundaries, required outputs, escalation — plus an authority matrix and a role-occupancy rule |
| 3 | Ten burn classifications with owners, outputs and exit gates; effort levels |
| 4 | The mission lifecycle, its rules, and mandatory internal gates |
| 5 | Flight Rules FR-001…FR-015, each with identifier, rule, rationale, provenance and verification; FR-016/FR-017 proposed |
| 6 | Pre-flight — nine mandatory checks, GO / CONCERN / NO-GO |
| 7 | Checkpoints — testing, documentation, security, architecture, evidence |
| 8 | SAFE Review vs SAFE Confirmation; finding fields; disposition vocabulary |
| 9 | Governor authority, freeze, merge, rulings, debt rulings, reclassification, and the absence of implementation authority |
| 10 | Post-Flight |
| 11 | Six standard reports with required headings and verdicts |
| 12 | AI operating model — §12.0 non-normative status, current practice, independence rule (normative), effort guidance, handoffs |
| 13 | Nine operational precedents (P1–P9) |
| 14 | Governor decisions required (GD-1…GD-6) |
| 15–17 | Scope exclusions, technical debt, success criteria |
| Appendix A | How Mission Control was validated — RFC-009, RFC-010, RFC-011, and the limits of that validation |

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
— Revision 1: ten challenges, **four amendments applied before commit**:

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
unaffected.

Verification performed on both revisions: internal cross-reference integrity
(every `§n.n` reference resolves to a heading, every anchor link resolves, every
relative file link exists); every Flight Rule traceable to a cited burn; every
claim about repository state checked against the repository rather than
recalled.

Revision 2 adds: all seventeen rules confirmed to carry the five standard fields
in order; a line-by-line audit of every removed line against Revision 1,
confirming no Flight Rule statement, lifecycle stage, burn classification or
role definition was altered; and every Appendix A fact checked against the
repository — PR numbers, dates, commits `775812c` and `ce7cc17`, the empty
`gh api` comment result, the named regression tests, and the B1–B4 / S1–S7
dispositions.

Revision 2 adds six further challenges scoped to the Governor amendments, two of
which produced amendments (A5, A6) and one of which — R6 — is a line-by-line
audit that nothing the brief said to preserve was altered.

## Review path

**Governor Final Architecture Review → Architecture Freeze → BOOSTER
Documentation Burn → SAFE Review → Governor Merge → Guido Post-Flight.**

This is the first burn whose own lifecycle is defined by the document under
review; RFC-100 §4 does not bind RFC-100 until it is frozen.

**Do not merge yet.** No PR is open. Ready for Governor final architecture
review.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
