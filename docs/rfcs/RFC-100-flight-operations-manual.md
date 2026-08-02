# RFC-100 — Flight Operations Manual

**Status:** Revision 2 — Governor-approved and frozen; documentation
implementation in progress.
**Type:** Governance architecture. Documentation-only.
**Author:** EECOM (architecture Flight Controller role, Claude), commissioned by
CAPCOM on behalf of the Governor.
**Date:** Revision 1, 2026-08-01. Revision 2, 2026-08-01.
**Supersedes:** nothing. **Extends:**
[`../engineering/review-gates.md`](../engineering/review-gates.md).
**Self-review:** [`../reviews/RFC-100-architecture-self-review.md`](../reviews/RFC-100-architecture-self-review.md)
— ten challenges, **four amendments applied before commit** (A1 report-shape
provenance, A2 role occupancy, A3 FR-014 duty to seek, A4 Hotfix Burn), two
watch items; extended for Revision 2.

**Revision 2 — Governor amendments.** The Governor's first architecture review
returned **GO WITH AMENDMENTS**, accepting the constitutional model, the Mission
Control organisation and the Flight Rules, and directing five refinements. All
five are applied. Nothing was redesigned: no Flight Director responsibility,
lifecycle stage, burn classification, Governor authority, existing Flight Rule
or architectural decision is altered.

| # | Amendment | Applied |
|---|---|---|
| **1** | Three-layer structure — Constitution / Operations Manual / Engineering Standards & Templates, made explicit | New §1.5, with each major section tagged and per-layer change control; GD-5 applied in layer terms |
| **2** | Precedence — a normative section resolving RFC-100 against product RFCs | New §1.6 (P1–P8), normative; §1.3 now points to it rather than restating it |
| **3** | Flight Rule format — Identifier, Rule, Rationale, Provenance, Verification | §5 preamble defines the standard; all seventeen rules reformatted; **Verification is new to every rule** |
| **4** | Model guidance — the model table is recommended practice, not normative | New §12.0; §12.1 relabelled; §12.2 independence rule marked normative; GD-4 restated |
| **5** | Validation appendix — how Mission Control was validated | New [Appendix A](#appendix-a--how-mission-control-was-validated), evidencing RFC-009, RFC-010 and RFC-011 element by element, including what it does *not* cover |

The Revision 2 self-review produced **two further amendments before commit**:
precedence rule **P8**, because P2 as first drafted implied RFC-100 never
constrains product behaviour while four of its own rules do (A5); and the
**verification-mode table** in §5, because labelling every rule "verifiable"
without distinguishing test-verified from artefact-verified would have
overstated the audit the amendment was meant to create (A6).

RFC-100 is the permanent operating manual for Project Foundry engineering. It
governs **how Foundry is engineered**, never **what Foundry does**. No product
architecture, domain model, mission, console, canon or acquisition contract is
created, amended or interpreted by this document.

An engineering brief may be reduced to:

```text
Operate under RFC-100.
Mission: <engineering objective>
```

without losing engineering discipline. Everything a brief previously had to
restate — pre-flight, classification, checkpoints, review gates, report shape,
model selection — is defined here and inherited by reference.

---

## 1. Purpose

### 1.1 Mission of Flight Operations

Foundry is built as a long-lived platform rather than an accumulation of
features. Flight Operations exists to make that survivable: to ensure that a
change is understood before it is written, reviewed by someone who did not
write it, evidenced before it is believed, and merged only by the authority
that owns the platform.

The objective is not maximum process. It is maximum confidence that every
change remains secure by design, architecturally consistent, deterministic,
auditable, maintainable and honest about what it knows
([`../engineering/review-gates.md`](../engineering/review-gates.md)).

### 1.2 Engineering governance

Governance rests on one separation, already proven across RFC-002 through
RFC-011: **the party that implements never approves.** Implementation,
adversarial review and merge authority are three different roles, and a role
never occupies two of them on the same burn.

This manual codifies that separation into named Flight Directors, classified
burns, a formal lifecycle, permanent Flight Rules, and standard reports whose
verdicts are unambiguous.

### 1.3 Relationship to RFCs

An RFC is a governed unit of change to Foundry. RFC-100 is the governed unit of
change to *how RFCs are run*. Concretely:

- Product and platform RFCs (RFC-001…RFC-0nn) describe **what** Foundry is.
- RFC-100 governs the engineering governance of every future product RFC and
  describes **how** any of them is designed, built, reviewed and merged.
- Where a product RFC states process (RFC-010's migration gate table, RFC-011's
  ten-phase sequence), that process is **burn-local sequencing** inside the
  RFC's own scope.

The normative rule governing the boundary between the two is §1.6.

### 1.4 Relationship to Governor authority

RFC-100 does not create Governor authority; it records it. The Governor's
authority is prior to this document and is not delegated by it. RFC-100
constrains everyone *except* the Governor, and constrains the Governor only in
form: rulings must be recorded, attributable and durable
(§9, [FR-014](#fr-014--review-artefact-continuity)).

The Governor may override any clause of RFC-100 for a named burn by explicit
ruling. Such an override is a precedent and must be recorded (§13); it is not a
silent exception.

### 1.5 Document structure — three governance layers

*(Governor Amendment 1.)* RFC-100 is one document containing three layers that
change at different rates. The layer determines what it takes to amend a
section, and every section belongs to exactly one.

| Layer | Name | Sections | Changes | Amended by |
|---|---|---|---|---|
| **1** | **Constitution** | §1 Purpose and precedence · §2 Mission Control Organisation · §3 Burn Classification · §4 Mission Lifecycle · §5 Flight Rules | Rarely. Each change is a constitutional act | **Architecture Burn** revising RFC-100, with Governor approval and re-freeze |
| **2** | **Operations Manual** | §6 Pre-flight · §7 Checkpoints · §8 SAFE · §9 Governor · §10 Post-Flight | When a procedure is proven insufficient by a burn | **Documentation Burn** under Governor Review. May refine *how* a Layer 1 obligation is met; may never remove one |
| **3** | **Engineering Standards & Templates** | §11 Standard Reports · §12 AI Operating Model | Expected to evolve continuously | **Documentation Burn**, Governor notified. Records practice rather than constraining it |

**Supporting record** — §13 Operational Precedents, §14 Governor Rulings
Applied, §15 Scope Exclusions, §16 Technical Debt, §17 Success Criteria and
[Appendix A](#appendix-a--how-mission-control-was-validated). These are the
RFC's own record. Precedents (§13) are binding and are added by any burn that
produces one; the remainder are amended with the ratification they record.

**Layer discipline.** A lower layer may never weaken a higher one. If a
procedure in Layer 2 or a template in Layer 3 cannot be satisfied without
breaching Layer 1, the Layer 1 clause wins and the conflict is raised to the
Governor. Each major section below is tagged with its layer.

### 1.6 Precedence *(normative)*

*(Governor Amendment 2.)* Two governed bodies of architecture exist. This
section defines which governs what, and what happens when they meet.

| # | Rule |
|---|---|
| **P1** | **RFC-100 governs engineering governance** — roles, authority, burn classification, lifecycle, Flight Rules, review procedure, report form. Within that domain RFC-100 is authoritative over every other document, including this project's own conventions and any brief |
| **P2** | **Product RFCs govern product architecture** — domain models, contracts, vocabularies, seams, missions, console, canon, acquisition. Within that domain the product RFC is authoritative, and **RFC-100 has no opinion whatsoever** |
| **P3** | **A product RFC may not redefine** a Flight Rule, a role's authority, a burn classification, a lifecycle stage or a report verdict. Burn-local sequencing inside a product RFC (§1.3) is subordinate to RFC-100 and may not weaken it |
| **P4** | **RFC-100 may not redefine** a product contract, vocabulary or invariant, may not interpret one, and may not resolve another RFC's open question |
| **P5** | **The constitutional invariants in [`../architecture.md`](../architecture.md) are prior to both.** Neither RFC-100 nor any product RFC amends them; a change to an invariant is a new architecture, not a contribution (`CONTRIBUTING.md`) |
| **P6** | **Conflict requires a Governor ruling.** Where engineering governance and a product RFC genuinely conflict — where obeying one necessarily breaches the other — **no role resolves it locally.** Work stops on the conflicting point, the conflict is raised through CAPCOM with both clauses cited, and the Governor rules. The ruling is recorded as a precedent (§13) |
| **P7** | **Silence is not conflict.** Where RFC-100 is silent, the product RFC governs; where a product RFC is silent on process, RFC-100 governs. Neither silence authorises a role to invent a rule for the other's domain |
| **P8** | **Standing quality bars are the one place the boundary is shared.** Four Flight Rules — [FR-008](#fr-008--honest-information), [FR-009](#fr-009--fail-closed), [FR-011](#fr-011--platform-before-domain), [FR-012](#fr-012--evidence-before-ai) — constrain how software must behave, not only how work is conducted. They are **floors, not designs**: they say what any product architecture must not do, never what it must be. A product RFC may exceed them and may not lower them; it remains free to choose every contract, vocabulary and seam above them. A product RFC that believes a floor is wrong invokes P6 rather than deviating |

P6 exists because the alternative is an implementer deciding, mid-burn, which
governing document to disobey — and recording neither choice. P8 exists because
P2 as first drafted read as though RFC-100 never touched product behaviour,
which four of its own rules plainly do *(self-review A5)*.

---

## 2. Mission Control Organisation

**Layer 1 — Constitution** (§1.5).

Seven Flight Director roles. Each is a *role*, not a person and not a model —
roles are filled by whichever human or model is assigned (§12), and the
standards do not change with the occupant
(`review-gates.md`, "Models are Replaceable").

**Evidence status.** Seven roles — Governor, CAPCOM, EECOM, BOOSTER, SAFE,
**Guido** and **TELMU** — are documented here as permanent Flight Directors.
The Governor ratified Guido and TELMU under GD-1; their operating evidence is
recorded in the role descriptions and remains subject to ordinary post-flight
verification.

### 2.1 Governor

**Authority.** Total. The Governor is the platform owner and the only merge
authority.

| Aspect | Definition |
|---|---|
| **Authority** | Architecture approval and freeze; merge; governance rulings; technical-debt disposition; burn reclassification; Flight Rule amendment; override of any RFC-100 clause by recorded ruling |
| **Responsibilities** | Rule on open questions; approve or reject architecture; conduct visual and merge review; decide what is debt versus decision; authorise the next burn |
| **Decision boundaries** | **No implementation authority.** The Governor does not write code, tests, fixtures or documentation content, and does not resolve a finding by editing the work |
| **Required outputs** | Architecture Approval (with amendments), Governor Review report, Governor Merge Review, recorded rulings with dates |
| **Escalation** | Terminal. Nothing escalates past the Governor |

Proven: RFC-010 "GO WITH MINOR AMENDMENTS (2026-07-31)" with seven amendments;
RFC-011 Revision 2 five amendments plus OQ1–OQ7 rulings; the S6 encryption
deferral ruling; the Q1/Q2/Q3 closeout rulings; the B2 phase-reclassification
question referred to the Governor rather than resolved by the implementer.

### 2.2 CAPCOM

**Authority.** Sole channel between the Governor and the flight controllers.

| Aspect | Definition |
|---|---|
| **Authority** | Issue the burn brief; declare burn classification, effort level and scope boundary; relay Governor rulings; relay review findings |
| **Responsibilities** | Convert a Governor objective into an executable brief with explicit inclusions, exclusions, required outputs and success criteria; carry findings to the executing role with their supporting text intact |
| **Decision boundaries** | May not approve architecture, merge, or invent a ruling. **A CAPCOM relay is not itself evidence** — see [FR-014](#fr-014--review-artefact-continuity) |
| **Required outputs** | Burn brief; relayed rulings; relayed review artefacts |
| **Escalation** | To Governor |

Proven: the brief format itself; and the RFC-011 precedent where a CAPCOM brief
named findings S1 and S3–S7 without assertion, file or acceptance criterion,
and the burn correctly classified them "SAFE interpretation not supported"
rather than acting on an identifier alone.

### 2.3 Guido

**Authority.** Mission planning and RFC canon.

| Aspect | Definition |
|---|---|
| **Authority** | RFC numbering and sequencing; recommend the next burn; maintain the RFC index and specification canon; declare when an objective warrants an RFC versus a documentation burn |
| **Responsibilities** | Keep [`index.md`](index.md) truthful, including its own gaps; keep specification amendments tracked as proposals until ruled; maintain `roadmap.md` as the record of what is deliberately unbuilt |
| **Decision boundaries** | Recommends; never approves. Does not implement, review or merge |
| **Required outputs** | Updated RFC index row per burn; next-burn recommendation; specification amendment status |
| **Escalation** | To Governor via CAPCOM |

Evidence for the *work*: the RFC index self-documents its gaps; RFC-005's
missing CHANGELOG entry is tracked as [issue #13]; "Next Recommended RFC" is a
standing section of `PROJECT_STATUS.md`; Spec 001 Amendment 5 remained a
proposal until Governor ruling OQ3. Evidence for the *role*: none — the work
has been absorbed by the Governor and EECOM.

### 2.4 EECOM

**Authority.** Architecture.

| Aspect | Definition |
|---|---|
| **Authority** | Author architecture; define contracts, vocabularies and seams; declare scope exclusions; perform the adversarial architecture self-review |
| **Responsibilities** | Produce the RFC; challenge it adversarially before commit and amend it in response; state what the review did *not* fix; name technical debt rather than hide it; deviate from a brief only with recorded justification |
| **Decision boundaries** | **No implementation authority and no merge authority.** May not approve its own architecture. Once frozen, may not reinterpret a contract — only the Governor may |
| **Required outputs** | RFC document; Architecture Self-Review; Architecture Report; PR description; Governor questions |
| **Escalation** | To Governor via CAPCOM |

Proven: RFC-010 and RFC-011 are both authored "by EECOM (architecture Flight
Controller role, Claude)"; both self-reviews produced pre-commit amendments
(six for RFC-010, three for RFC-011) and both recorded accepted residuals and
watch items; RFC-011's GA1 records a justified deviation from the briefed
pipeline position on data-dependency grounds.

### 2.5 BOOSTER

**Authority.** Implementation.

| Aspect | Definition |
|---|---|
| **Authority** | Write production source, tests, fixtures and implementation reports within the frozen architecture and the declared burn scope |
| **Responsibilities** | Implement exactly the classified burn; produce deterministic validation evidence; run the live preview; keep the scope boundary explicit; remediate findings that carry actionable text |
| **Decision boundaries** | May not change a frozen contract ([FR-003](#fr-003--frozen-architecture)); may not reclassify its own burn ([FR-015](#fr-015--burn-classification)); may not approve or merge; may not act on a finding identifier that has no published text ([FR-014](#fr-014--review-artefact-continuity)) |
| **Required outputs** | Implementation Report; technical-debt register; validation evidence; live preview result; PR description |
| **Escalation** | To Governor via CAPCOM — including when the honest answer is "this cannot be repaired by a code change" |

Proven: RFC-011's PR description routes implementation "to BOOSTER per the
ten-phase sequence"; RFC-010 Phase 1 and Phase 2 and RFC-011 Phase 1 are
implementation burns with reports, debt registers and validation counts;
RFC-011's B2 finding was escalated rather than papered over — "No code change
can make that historical sequencing claim true."

### 2.6 SAFE

**Authority.** Adversarial review. Read-only.

| Aspect | Definition |
|---|---|
| **Authority** | Review implemented work against the frozen architecture, the Flight Rules and the security model; assign severity; block merge on Critical or High |
| **Responsibilities** | Produce durable, evidenced findings with identifier, assertion, file and acceptance criterion; distinguish fact from opinion; avoid speculative findings; confirm remediation independently |
| **Decision boundaries** | **Never edits code, implements fixes, commits, merges or modifies git state** (`review-gates.md`). Does not approve architecture and does not merge |
| **Required outputs** | SAFE Report (findings, severities, verdict); SAFE Confirmation (per-finding disposition, verdict) |
| **Escalation** | To Governor via CAPCOM |

Proven: SAFE review and remediation cycles on RFC-009 (PR #22), RFC-010 (PR
#25) and RFC-011 (PR #27); two sequential remediation burns on RFC-011 with
per-finding disposition recorded in the technical-debt register; the
`review-gates.md` severity model and its Critical/High block policy.

### 2.7 TELMU

**Authority.** Project telemetry and post-flight state.

| Aspect | Definition |
|---|---|
| **Authority** | Declare the repository's post-flight state; own `PROJECT_STATUS.md`, `CHANGELOG.md` and version bumps; verify CI after merge; verify cleanup |
| **Responsibilities** | Confirm the first post-merge `main` workflow passes before a burn is declared complete; keep status documents non-contradictory; record the mission archive |
| **Decision boundaries** | Reports state; does not implement features, review architecture or merge. May raise a NO-GO on repository state |
| **Required outputs** | Post-Flight Report; repository state; CI verification; next-burn recommendation handoff to Guido |
| **Escalation** | To Governor via CAPCOM |

Evidence for the *work*: PR #23's post-merge fixture failure, which produced
RFC-010's mandatory step 14 and RFC-011's Phase 10; RFC-010's correction of a
materially stale `PROJECT_STATUS.md`; the standing RFC-005 CHANGELOG/version
gap. Evidence for the *role*: none — the work has been performed
opportunistically by whichever burn noticed.

### 2.8 Authority matrix

| | Brief | Architecture | Freeze | Implement | Review | Remediate | Merge | Reclassify |
|---|---|---|---|---|---|---|---|---|
| **Governor** | — | approve | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ |
| **CAPCOM** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | relay only |
| **Guido** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | recommend |
| **EECOM** | ❌ | ✅ | ❌ | ❌ | self only | architecture only | ❌ | ❌ |
| **BOOSTER** | ❌ | ❌ | ❌ | ✅ | self only | ✅ | ❌ | ❌ |
| **SAFE** | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **TELMU** | ❌ | ❌ | ❌ | ❌ | state only | ❌ | ❌ | ❌ |

### 2.9 Role occupancy

A role is an **act**, not a person. One human or model may occupy several roles
across a project, and today several are occupied by the same parties. Separation
is therefore enforced on acts, not on headcount:

1. **No party performs two roles on the same artefact in the same burn.** The
   party that implemented does not review that implementation; the party that
   authored architecture does not approve it.
2. **The Governor may occupy CAPCOM.** Briefing and relaying are Governor-
   compatible acts. But an approval, freeze, ruling or merge is a **Governor
   act** and must be recorded as one (§9.4) — a brief is never an approval, and
   a relayed instruction is never a ruling.
3. **Where a role is unoccupied, its outputs are still required.** An
   unperformed Post-Flight is a missing report, not an absent obligation.

*(Amendment A2 from the self-review.)*

### 2.10 Escalation path

```text
EECOM / BOOSTER / SAFE / Guido / TELMU
                │
                ▼
             CAPCOM
                │
                ▼
             GOVERNOR   ← terminal
```

No role escalates laterally. No role bypasses CAPCOM to reach the Governor
inside a burn. A finding, a blocked decision and a scope conflict all take the
same path.

---

## 3. Burn Classification

**Layer 1 — Constitution** (§1.5).

A **burn** is one bounded, classified unit of engineering work with one owning
role, one declared scope and one required report. Every burn is classified in
its brief before work begins.

| Burn | Owner | Produces | Touches production code? | Gate to exit |
|---|---|---|---|---|
| **Architecture Burn** | EECOM | RFC + Architecture Self-Review + Architecture Report + PR description | **No** — documentation exclusively | Governor Architecture Approval |
| **Implementation Burn** | BOOSTER | Source, tests, Implementation Report, technical-debt register, validation evidence, live preview | Yes | SAFE Review |
| **SAFE Review** | SAFE | SAFE Report: findings with identifier, assertion, file, acceptance criterion, severity; verdict | No — read-only | Governor Review |
| **SAFE Confirmation** | SAFE | Per-finding disposition against the remediation evidence; verdict | No — read-only | Governor Merge Review |
| **Remediation Burn** | BOOSTER | Fixes bounded to published findings, regression tests, remediation evidence, debt disposition | Yes, bounded | SAFE Confirmation |
| **Governor Review** | Governor | Rulings, amendments, GO / GO WITH AMENDMENTS / NO-GO | No | Next lifecycle stage |
| **Documentation Burn** | EECOM or TELMU | Documentation only; no contract change | **No** | Governor Review |
| **Release Closeout** | TELMU | CHANGELOG entry, version bump, tag decision, index row | Version metadata only | Governor Merge Review |
| **Post-Flight** | TELMU | Post-Flight Report: merge confirmation, post-merge CI, cleanup, repository state, next-burn recommendation | No | Mission Complete |
| **Hotfix Burn** | BOOSTER | Minimal repair of a failing `main`, its regression test, and a Post-Flight | Yes, minimal | Governor Merge Review |

### 3.1 Classification rules

1. **One classification per burn.** A burn that finds itself doing two kinds of
   work has already failed [FR-004](#fr-004--burn-discipline).
2. **No burn may change its own classification.** Reclassification is a
   Governor decision ([FR-015](#fr-015--burn-classification)).
3. **An Architecture Burn changes no production source, tests, templates,
   CSS or runtime configuration.** RFC-010 and RFC-011 both state this
   explicitly in their PR descriptions; it is now a rule.
4. **A Remediation Burn is bounded by the published findings.** It may not
   carry opportunistic improvement, and it may not act on an identifier with
   no finding text.
5. **A burn's scope exclusions are declared in the brief and restated in the
   report.** Excluded work is scope discipline, not hidden debt (RFC-011
   Phase 1, "Non-debt boundaries").
6. **A Hotfix Burn is the only burn that may begin without a preceding
   Architecture Burn**, and only to restore a failing `main`. It is bounded to
   the failure and its regression test; it carries no feature work, no contract
   change and no refactor; it runs on a `hotfix/*` branch; and it still requires
   Governor Merge Review and Post-Flight. Anything larger is a Remediation Burn
   under the normal lifecycle. *(Amendment A4 from the self-review; precedent
   PR #23, `hotfix/deterministic-mission-control-fixture`.)*

### 3.2 Effort levels

| Level | Meaning | Typical burns |
|---|---|---|
| **HIGH** | Constitutional or platform-shaping. Full adversarial self-review; every Governor question surfaced explicitly | Architecture Burns; any burn touching a frozen contract, a Core seam or this manual |
| **STANDARD** | Bounded change within a frozen architecture | Implementation Burns; SAFE Reviews; Remediation Burns |
| **LOW** | Mechanical, verifiable, no judgement | Documentation Burns; Release Closeout; Post-Flight |

Effort level is declared by CAPCOM in the brief and is not self-adjusted.

---

## 4. Mission Lifecycle

**Layer 1 — Constitution** (§1.5).

```text
                     Idea
                       │
                       ▼
              ARCHITECTURE BURN                    (EECOM)
                       │
                       ▼
        GOVERNOR ARCHITECTURE APPROVAL             (Governor)
              — architecture frozen —
                       │
                       ▼
             IMPLEMENTATION BURN                   (BOOSTER)
                       │
                       ▼
                  SAFE REVIEW                      (SAFE)
                       │
                       ▼
                GOVERNOR REVIEW                    (Governor)
                       │
                       ▼
              REMEDIATION BURN  ◀──────┐           (BOOSTER)
                       │               │
                       ▼               │
              SAFE CONFIRMATION ───────┘           (SAFE)
                  │        findings remain
                  │ clean
                  ▼
           GOVERNOR MERGE REVIEW                   (Governor)
                       │
                       ▼
                    MERGE                          (Governor)
                       │
                       ▼
                  POST-FLIGHT                      (TELMU)
                       │
                       ▼
               MISSION COMPLETE
```

### 4.1 Lifecycle rules

- **No stage is skipped.** A stage may be *empty* — a SAFE Review with zero
  findings still produces a SAFE Report with a verdict — but it is never
  omitted.
- **Freeze is a hard boundary.** Nothing is implemented before Governor
  Architecture Approval ([FR-013](#fr-013--architecture-before-code)), and
  nothing frozen is changed after it without a new ruling
  ([FR-003](#fr-003--frozen-architecture)).
- **Remediation loops until SAFE Confirmation is clean.** RFC-011 required two
  sequential remediation burns; that is a normal outcome, not a failure.
- **A finding that cannot be repaired by a code change is escalated, not
  remediated.** RFC-011's B2 is the precedent.
- **Mission Complete requires the first post-merge `main` workflow to pass.**
  RFC-009 was declared complete before its post-merge run failed (PR #23);
  RFC-010 step 14 and RFC-011 Phase 10 encode the correction.
- **A multi-phase RFC re-enters the lifecycle per phase.** Each phase is a
  separate burn candidate with its own classification, review and gate
  (RFC-011's ten phases; RFC-010's two).

### 4.2 Gated sub-sequences

An RFC may declare a **mandatory internal gate** inside its implementation
sequence. Two exist:

- **Governor Visual Review** (RFC-010, amendment 7): after the reference
  mission is built and before any remaining migration. Live preview required
  ([FR-010](#fr-010--live-preview-first)).
- **Governor Phase Review** (RFC-011, Phase 5): after the reference
  implementation and before any further acquisition channel.

An internal gate binds exactly like a lifecycle stage. Passing it is a recorded
Governor ruling.

---

## 5. Flight Rules

**Layer 1 — Constitution** (§1.5).

Permanent. Numbered for citation. A Flight Rule is amended only by revising
RFC-100 as an Architecture Burn under Governor ruling.

**Standard format** *(Governor Amendment 3).* Every Flight Rule carries the same
five fields, in this order, so that rules are **auditable rather than
descriptive**:

| Field | Content |
|---|---|
| **Identifier** | `FR-0nn` plus a short name. Stable; cited from briefs, reports and findings |
| **Rule** | The normative statement. What must or must not happen |
| **Rationale** | Why the rule exists — the failure it prevents |
| **Provenance** | The observed precedent that produced it: the burn, finding or PR. A rule with no provenance is a proposal, not a rule |
| **Verification** | How compliance is checked on a given burn — the test, guard, artefact or pre-flight item a reviewer inspects. Where verification is by artefact rather than by test, the field says so |

A rule whose Verification field cannot be satisfied on a burn is a **finding**,
not a matter of judgement.

**Verification modes** *(self-review A6).* Verification is not uniformly strong,
and pretending otherwise would defeat the purpose of the field. Two modes exist:

| Mode | Meaning | Rules |
|---|---|---|
| **Test-verified** | An automated assertion fails if the rule is breached. A reviewer runs it | FR-007, FR-008, FR-009, FR-011 |
| **Artefact-verified** | A reviewer inspects a named artefact — pre-flight output, diff, report section, checklist, run identifier, ruling. Objective, but requires someone to look | FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-010, FR-012, FR-013, FR-014, FR-015, FR-016, FR-017 |

Artefact verification is **weaker** than test verification: it depends on a role
performing an inspection. Where a rule could plausibly be moved from artefact to
test — FR-012's "no model on a canon write path" is the strongest candidate —
doing so is an improvement a later burn should make. RFC-100 does not build such
tests; it is documentation (§15).

### FR-001 — Canonical Repository

**Rule.** `~/Projects/foundry` (remote `enipeus84/foundry`) is the sole
canonical working copy. No other checkout is authoritative. Any other directory
containing Foundry material — patch files, generated packages, briefs — is
scratch and is never implemented against.

**Rationale.** Two divergent copies produce work that cannot be merged and reviews
that describe code no one shipped.

**Provenance.** The deprecated `Documents/~:Projects:foundry` copy; the
`Downloads/foundry` brief-and-patch directory.

**Verification.** Pre-flight check 1. `git remote -v` names the canonical origin, and no burn artefact cites a path outside the canonical working copy.

### FR-002 — Branch Ownership

**Rule.** Every burn runs on its own branch, named for its RFC and phase. `main`
is never a working branch. One branch has one owning role at a time. A branch
name that no longer describes its contents is corrected in the PR description
rather than silently retained.

**Rationale.** Branch identity is the unit of review, and a misleading branch name
corrupts the audit trail.

**Provenance.** The full `rfc-0nn-*` branch history; PR #25's description
recording that it contains both implementation phases and that its `phase-1`
branch name is retained only for continuity.

**Verification.** Pre-flight checks 2 and 3. The report states the branch name; where a branch name no longer describes its contents, the PR description says so explicitly (precedent: PR #25).

### FR-003 — Frozen Architecture

**Rule.** On Governor Architecture Approval, the RFC's contracts are frozen.
**Implementation must not change a frozen contract without a new Governor
ruling.** Interpretation of a frozen contract is likewise a Governor act, not an
implementer's judgement.

**Rationale.** A contract that implementation may quietly reinterpret is not a
contract.

**Provenance.** Stated verbatim in both the RFC-010 and RFC-011 PR descriptions
and carried into `PROJECT_STATUS.md`.

**Verification.** Architecture checkpoint. Every frozen contract identifier named in the RFC is compared against the implementation; any divergence cites a dated Governor ruling or the burn is blocked.

### FR-004 — Burn Discipline

**Rule.** A burn does exactly its declared scope. Exclusions are stated in the
brief and restated in the report. Work that is out of scope is neither
performed nor recorded as deferred debt — absence by scope discipline is
declared as such.

**Rationale.** Unbounded burns cannot be reviewed, and undeclared exclusions later
read as undisclosed gaps.

**Provenance.** RFC-011 Phase 1's "Scope boundary" and "Non-debt boundaries"
sections, which enumerate every excluded channel and explicitly deny that their
absence is hidden implementation.

**Verification.** The brief's exclusions and the report's Scope Boundary enumerate the same set, and the diff contains nothing outside the declared scope.

### FR-005 — Merge Authority

**Rule.** The Governor is the only merge authority. Reviewers never merge,
never commit, never modify git state. An implementation PR is marked **"Do not
merge yet"** until Governor Merge Review.

**Rationale.** Merge is the moment a change becomes the platform's problem forever.

**Provenance.** `review-gates.md` ("Reviewers do not: edit code, implement fixes,
commit, merge, modify Git state"); RFC-010's PR description ends "**Do not merge
yet.**"

**Verification.** The merge is performed under a recorded Governor Merge Review, and no commit on the branch is authored by the role that reviewed it.

### FR-006 — Secure by Design

**Rule.** Every RFC and non-trivial PR answers the Security by Design checklist.
**`N/A` is an answer; silence is not.** An omitted or unanswered checklist is a
process failure that blocks approval. Critical or High security findings block
merge.

**Rationale.** Security added after the fact is not a property of the architecture.

**Provenance.** `CONTRIBUTING.md`; `review-gates.md` Security Gate; the RFC-011
Phase 1 security work (vault permissions, CSRF in body only, deterministic
secret detection, provenance chain).

**Verification.** `scripts/validate_security_docs.py` reports COMPLETE and the checklist carries an answer — including `N/A` — against every item.

### FR-007 — Deterministic Validation

**Rule.** Validation is deterministic or it is not validation. Fixtures use
explicit frozen clocks; no projection-relevant build occurs without an explicit
`as_of`; route goldens are hash-pinned and asserted equal under two distinct
frozen clocks; determinism is enforced by a guard test, not by convention.

**Rationale.** A suite that depends on wall-clock time passes on the day it is written
and fails the next morning.

**Provenance.** PR #23 (RFC-009's post-merge fixture failure); RFC-010's DET-1…
DET-6 and its AST guard over every test module importing the demo builder.

**Verification.** The determinism guards pass: golden-hash equality under two distinct frozen clocks, and the AST guard rejecting any projection-relevant build without an explicit `as_of`. The full suite passes on the CI Python matrix (3.10–3.13).

### FR-008 — Honest Information

**Rule.** Foundry never presents greater certainty than the underlying
calculation supports. A missing input is **unknown**, never zero. Unknown
propagates through every derived lens and caps confidence. A genuine observed
zero remains a number. Unavailability is represented, never disguised.

**Rationale.** A fabricated zero is indistinguishable from a real one at the point of
decision.

**Provenance.** `review-gates.md` "Honest Software"; RFC-011 finding B3, where
`ValuationLenses` returned `0.0` for a missing material observation and now
returns `None` with an `Insufficient` confidence cap; RFC-010's Financial
Resilience absence path, which states that trajectory history is unavailable
rather than drawing a fake trajectory.

**Verification.** A regression test asserts, for each derived value the burn touches, that a missing material input remains unknown rather than zero and caps confidence (precedent: `test_missing_material_market_evidence_remains_unknown_not_zero`).

### FR-009 — Fail Closed

**Rule.** When a guard's dependency is unavailable, the operation refuses — it
does not proceed with the guard disabled. Ambiguous identity, missing evidence,
corrupt evidence, unauthorised access, spoofed timestamps and cross-household
references all refuse. No optional dependency may silently turn a protection
off.

**Rationale.** A guard that degrades to permissive under failure is worse than no
guard, because it is trusted.

**Provenance.** RFC-011 finding B4 (`ResolutionService.semantic_duplicate()` now
raises when its inbox dependency is absent; `ManualInterpreter.interpret()`
refuses before creating a proposal); finding S3 (missing, corrupt or
unauthorised evidence is unavailable rather than rendered); the authentication
model's documented fail-closed behaviour.

**Verification.** A regression test asserts that each guard refuses when its dependency is unavailable (precedent: `test_identity_and_duplicate_protection_refuse_operation_when_inbox_is_unavailable`).

### FR-010 — Live Preview First

**Rule.** Any burn changing a rendered surface produces a **live preview**.
Screenshots are acceptable only when a live preview is genuinely unavailable,
and the unavailability is stated. Preview review covers a desktop viewport and a
narrow viewport, and its findings are recorded — including defects found and
repaired during the preview itself.

**Rationale.** Structural correctness in tests does not establish that a human can
read the page.

**Provenance.** RFC-010 migration step 6 ("Produce a live web preview; screenshots
only if a live preview is genuinely unavailable"); the Phase 2 preview at
desktop and 334 CSS pixels, which found and removed an evidence-disclosure
auto-open heuristic and repaired a shared narrow analysis-grid overflow.

**Verification.** The report records the preview, the viewports covered, and every defect the preview found and repaired. Where a live preview was unavailable, the report states why.

### FR-011 — Platform Before Domain

**Rule.** Platform layers are built and proven against **mock providers and a
mock domain only**. No domain vocabulary, event catalogue, prefix check or
category branch may live in Core. A domain is registered through a contract at
composition time, never hard-wired into the seam.

**Rationale.** A platform that knows one domain's nouns is that domain's code wearing
a platform's name.

**Provenance.** RFC-011 finding B1, where `core.acquisition` named a Finance event
catalogue and required a `finance.` prefix — a direct violation of AC-8 — and
the catalogue moved to `foundry.finance.acquisition.FinanceManualDraftContract`
behind a generic `DomainDraftContract` protocol, with a regression test
asserting Core's source contains no `finance.` vocabulary. Also RFC-011 Phase 1
("mock providers and mock domain ONLY (no Finance code)") and RFC-010 step 2.

**Verification.** A test asserts that the platform module's source contains no domain vocabulary (precedent: `test_core_acquisition_contract_contains_no_finance_event_vocabulary`), and platform phases are proven against mock providers only.

### FR-012 — Evidence Before AI

**Rule.** No model writes to canon. No model writes to the Identity Index. No
model-based detector stands between input and a security decision.
Interpretation is deterministic and versioned; a model interpreter, where one
exists at all, sits behind an explicit `review_each` confirmation policy. Fuzzy
or model-suggested matches never auto-commit.

**Rationale.** The platform's thesis is that memory belongs to the substrate, not the
model. A model that can write canon refutes it.

**Provenance.** RFC-011's frozen constraints ("no AI writing to canon", extended
in Revision 2 to the Identity Index); the deterministic `manual-json@1`
interpreter that records its identity and version and cannot append `finance.*`;
finding S1's remediation, which states "No detector uses a model."

**Verification.** No model invocation exists on any canon or Identity Index write path; interpreters record identity and version; any model interpreter is bound to `review_each`; and security detectors carry no model dependency.

### FR-013 — Architecture Before Code

**Rule.** Architecture is designed, adversarially self-reviewed, approved and
frozen before implementation begins. An Architecture Burn produces documentation
exclusively. Where implementation reveals an architectural defect, the defect
returns to the Governor; it is not resolved in the implementation.

**Rationale.** Architecture discovered during implementation is architecture chosen by
whoever typed fastest.

**Provenance.** RFC-010 and RFC-011 both approved and frozen as
documentation-only burns before any implementation existed; `PROJECT_STATUS.md`
recording "No RFC-010 source code, tests, CSS or framework changes exist in the
repository" at approval.

**Verification.** The Architecture Burn's diff contains documentation exclusively, and the recorded approval date precedes the first implementation commit.

### FR-014 — Review Artefact Continuity

**Rule.** A review finding exists only as a durable artefact containing an
**identifier, an assertion, a file or contract reference, and an acceptance
criterion**. A relayed identifier without finding text is **not actionable** and
must not authorise a change to a frozen architecture. Such an identifier is
recorded as *interpretation not supported* — evidence of a missing finding text,
never a claim that the system is defect-free — and can be reopened by supplying
the artefact. Review artefacts persist in the repository, not only in a review
channel.

**Duty to seek.** Before classifying an identifier as unsupported, the receiving
role must search for the artefact and record the search — the review channel,
the PR's review, inline and issue comments, and the repository — and must
request the missing text through CAPCOM. FR-014 protects against guessing at a
reviewer's meaning; it is never a route to dismissing review.
*(Amendment A3 from the self-review.)*

**Rationale.** Acting on a bare identifier means guessing what a reviewer meant and
changing frozen architecture on that guess.

**Provenance.** RFC-011 Phase 1, "Significant SAFE identifiers without published
finding text": the CAPCOM brief named S1 and S3–S7 with no assertion, file or
acceptance criterion; `gh api` returned `[]` for review, inline and issue
comments on the authoritative PR; no local SAFE artefact existed. S1 and S3–S6
were later actioned once finding text arrived, and S7 remains correctly
classified as not actionable.

**Verification.** Every actioned finding cites its identifier, assertion, reference and acceptance criterion. Every identifier classified unsupported records the search performed and the request made through CAPCOM.

### FR-015 — Burn Classification

**Rule.** Every burn is classified before it begins. **No burn may change its
own classification.** Reclassification — including discovering after the fact
that a burn spanned more phases than declared — is a Governor decision, and the
report states the true scope rather than the declared one.

**Rationale.** Classification determines which gates apply; self-reclassification
routes work around its own review.

**Provenance.** RFC-011 finding B2: commit `775812c` combined Phases 1–4 while the
branch and report claimed a Phase 1 slice. The implementation report stated "No
code change can make that historical sequencing claim true" and referred the
reclassification to the Governor, with no Phase 5 work authorised meanwhile.

**Verification.** The classification declared in the brief matches the scope stated in the report. Any divergence appears as a Governor reclassification decision, never as a restated scope.

### 5.1 Additional permanent Flight Rules *(GD-2 applied)*

These two rules describe behaviour the project has already been forced into but
which no existing rule stated before RFC-100. The Governor ratified both as
permanent Flight Rules under GD-2.

#### FR-016 — Post-Merge Verification

**Rule.** A burn is not complete until the **first post-merge `main` workflow
passes**. A failing post-merge run reopens the burn.

**Rationale.** Merge is not the last moment a change can fail.

**Provenance.** RFC-009 was declared complete before its post-merge `main` run
failed on a wall-clock-dependent fixture, repaired by PR #23. RFC-010 step 14
and RFC-011 Phase 10 already impose this on themselves; FR-016 generalises it.

**Verification.** The Post-Flight Report cites the post-merge `main` run identifier and its conclusion.

#### FR-017 — Documentation Coherence

**Rule.** `PROJECT_STATUS.md`, [`index.md`](index.md), `CHANGELOG.md` and
`architecture.md` may not contradict one another after a burn. A burn that
finds one materially stale corrects the project-state facts and says so, leaving
historical material unchanged. A version bump and CHANGELOG entry accompany
every merged implementation burn.

**Rationale.** Status documents are load-bearing for every subsequent decision; a
stale one silently misroutes the next burn.

**Provenance.** RFC-010 found `PROJECT_STATUS.md` materially stale (RFC-008
described as unimplemented, version as `1.5.1`) and corrected it. RFC-005
shipped with no CHANGELOG entry and no version bump — [issue #13], still open.

**Verification.** After the burn, `PROJECT_STATUS.md`, `index.md`, `CHANGELOG.md` and `architecture.md` contain no contradicting statement, and either a version bump and CHANGELOG entry exist or their absence is recorded as a named gap.

---

## 6. Pre-Flight

**Layer 2 — Operations Manual** (§1.5).

Mandatory before any burn begins. Every item is checked and reported; the burn
opens with an overall verdict.

| # | Check | Pass condition | Fails to |
|---|---|---|---|
| 1 | **Repository** | Working copy is the canonical repo with the expected `origin` (FR-001) | NO-GO |
| 2 | **Branch** | On a burn branch, not `main`; branch name matches the burn (FR-002) | NO-GO |
| 3 | **Ownership** | Working tree clean; branch tracks `origin`; no unowned in-flight work | NO-GO if dirty |
| 4 | **CI** | Latest `main` workflow is green | CONCERN, or NO-GO for an Implementation Burn |
| 5 | **Authentication** | `gh auth status` authenticated with the scopes the burn needs | NO-GO if the burn needs GitHub |
| 6 | **Python environment** | `.venv` interpreter ≥ 3.10, project installed with `[dev,web]` | NO-GO for an Implementation Burn; CONCERN for documentation-only |
| 7 | **Caffeinate** | A sleep inhibitor is active for long-running burns | CONCERN |
| 8 | **Worktrees** | `git worktree list` shows no stale or conflicting worktree | CONCERN |
| 9 | **RFC ownership** | The RFC exists, its status is known, and this burn's classification is authorised against it | NO-GO |

### 6.1 Verdicts

| Verdict | Meaning | Action |
|---|---|---|
| **GO** | Every check passes | Proceed |
| **CONCERN** | One or more non-blocking checks fail | Proceed, stating each concern and its effect on the burn's evidence |
| **NO-GO** | Any blocking check fails | Stop. Report to CAPCOM. Do not begin work |

A CONCERN is never silently upgraded to GO. Where a concern limits what the
burn can prove — a Python environment that cannot run the suite locally, for
example — the report says which evidence is delegated to CI instead.

---

## 7. Checkpoints

**Layer 2 — Operations Manual** (§1.5).

Checkpoints are the in-burn stops where a role verifies its own work before
handing off. They are self-checks, not review gates; passing them does not
substitute for SAFE.

| Checkpoint | Applies to | Verifies |
|---|---|---|
| **Testing** | Implementation, Remediation | Full suite passes; test count stated with its baseline and every decrease explained; every behavioural change has a test named for the architectural claim it defends; determinism guards pass (FR-007) |
| **Documentation** | All burns | Report written; technical debt named; scope exclusions restated; index and status documents coherent; no claim exceeds its evidence |
| **Security** | All burns | Security by Design checklist answered in full (FR-006); fail-closed paths exercised (FR-009); no secret, credential or live personal data in the repository, fixtures, logs or preview |
| **Architecture** | Architecture, Implementation | Domain neutrality holds (FR-011); no frozen contract changed (FR-003); seam boundaries tested, not asserted; deviations recorded with justification |
| **Evidence** | All burns | Every claim in the report is traceable to a file, a test name, a run identifier or a recorded ruling; absence of evidence is stated as absence, never as compliance |

### 7.1 Checkpoint reports

A checkpoint appears in the burn's report as a short, verifiable statement — not
a claim of diligence. The RFC-011 Phase 1 validation paragraph is the model:

> focused acquisition: 11 passed; focused web security: 13 passed; Core
> deterministic replay: 10 passed; focused Finance: 70 passed; full suite: 618
> passed … GitHub Actions `tests` run `30692011922` passed on Python 3.10,
> 3.11, 3.12 and 3.13.

Counts, identifiers and named runs. A checkpoint that cannot be stated that way
has not been performed.

---

## 8. SAFE

**Layer 2 — Operations Manual** (§1.5).

### 8.1 SAFE Review

The first adversarial pass over implemented work. Input: the implementation, the
frozen architecture, the Flight Rules and the security model. Output: a SAFE
Report.

Every finding carries:

| Field | Requirement |
|---|---|
| **Identifier** | Stable, referenced unchanged through remediation and confirmation |
| **Assertion** | What is wrong, stated as a fact about the code |
| **Reference** | The file, contract, acceptance criterion or Flight Rule violated |
| **Acceptance criterion** | What would make it closed |
| **Severity** | Critical / High / Medium / Low |

An identifier without the other four fields is not a finding
([FR-014](#fr-014--review-artefact-continuity)).

**Severity and merge policy** (`review-gates.md`): Critical and High **block**.
Medium is a real issue that may be deferred and **must be documented if
deferred**. Low may be deferred.

**Verdicts:** `APPROVE` · `APPROVE WITH CONDITIONS` · `BLOCK`.

### 8.2 SAFE Confirmation

The second pass, after remediation. **It is not a re-review.** Its scope is the
findings from the SAFE Review and nothing else; new observations are recorded
as new findings for a future burn, not folded into confirmation.

Each finding is dispositioned:

| Disposition | Meaning |
|---|---|
| **Closed** | Remediated; the acceptance criterion is met and a regression test asserts it |
| **Position supported, remediated** | The finding was correct; the fix is verified |
| **Position supported, not remediable in code** | Correct and unfixable by implementation — escalates to the Governor (RFC-011 B2) |
| **Interpretation not supported** | No published finding text; not actionable; reopenable on supply of the artefact (RFC-011 S7) |
| **Accepted debt** | Deferred with a named owner and a register entry |
| **Governor ruling applied** | Disposed by explicit Governor decision, not by implementation (RFC-011 S6) |

**Verdicts:** `CONFIRMED` · `CONFIRMED WITH RESIDUAL` · `NOT CONFIRMED`.

### 8.3 Difference between them

| | SAFE Review | SAFE Confirmation |
|---|---|---|
| **Scope** | The whole implementation | Only the prior findings |
| **Produces** | New findings | Dispositions |
| **May raise new findings** | Yes | Recorded, but never as confirmation blockers |
| **Precedes** | Governor Review | Governor Merge Review |
| **Blocks on** | Critical / High | Any finding not closed, escalated or ruled |

### 8.4 Evidence requirements

A SAFE Report and a SAFE Confirmation are both durable repository artefacts —
`docs/reviews/` — not review-channel comments. The RFC-011 precedent is
explicit: when `gh api` returned no review, inline or issue comments and no
local artefact existed, the findings were unactionable. Review evidence that
lives only in a channel does not survive the burn that produced it.

---

## 9. Governor

**Layer 2 — Operations Manual** (§1.5). Governor *authority* is Layer 1 and is stated in §2.1; this section is the procedure by which it is exercised.

### 9.1 Authority

The Governor owns the platform. Architecture approval, architecture freeze,
merge, governance rulings, technical-debt disposition and burn reclassification
are Governor acts and no one else's.

### 9.2 Architecture freeze

Approval freezes the RFC's contracts. From that moment: implementation may not
change a frozen contract; open questions are closed by ruling, not by
implementation choice; and amendments are numbered, dated and recorded in the
RFC itself.

RFC-010 froze on 2026-07-31 after seven amendments. RFC-011 Revision 2 froze on
2026-07-31 after five amendments and rulings on OQ1–OQ7. In both cases the RFC
text records the ruling and the date, not merely the outcome.

### 9.3 Merge authority

Merge is a distinct Governor act following SAFE Confirmation. An implementation
PR stays marked "Do not merge yet" until Governor Merge Review. No role, human
or model, merges on the Governor's behalf.

### 9.4 Governance rulings

Rulings resolve open questions, adopt or reject recommendations, and set
precedent. A ruling must be **recorded, dated and attributable** in the RFC or
its review artefact. Examples of ruled outcomes carried in the repository:
Q1/Q2/Q3 closeout on RFC-010; OQ1–OQ7 on RFC-011; the S6 ruling deferring
Evidence Vault encryption at rest to Phase 2.

### 9.5 Technical-debt rulings

The Governor decides what is debt and what is a decision. This distinction is
load-bearing: RFC-011's S6 was explicitly recorded as "Governor ruling — not
technical debt", removing an implementer-owned encryption-adapter item from the
Phase 1 register. Debt has an owner and a register entry; a decision has neither
and must not be carried as if it did.

### 9.6 Phase reclassification

Where a burn's true scope differs from its declared classification, only the
Governor may reclassify it, and only with the true scope stated. The
implementation states the discrepancy honestly and stops
([FR-015](#fr-015--burn-classification)); RFC-011 B2 is the operational
precedent. Governor reclassification of PR #27 as the combined Reference
Implementation Burn closed B2; it is no longer unresolved and no Phase 5 hold
remains under that ruling.

### 9.7 No implementation authority

The Governor does not write code, tests, fixtures or documentation content, and
does not close a finding by editing the work. This preserves the separation the
whole manual rests on: **the party that implements never approves.**

---

## 10. Post-Flight

**Layer 2 — Operations Manual** (§1.5).

Owned by TELMU. Every item is verified, not assumed.

| Step | Verification |
|---|---|
| **Merge** | The PR is merged by the Governor; the merge commit is identified |
| **CI verification** | The **first post-merge `main` workflow passes**. A failure reopens the burn (FR-016) |
| **Cleanup** | Burn branch disposition recorded; no stale worktree; no scratch artefact left in the repository |
| **Repository verification** | Working tree clean; `main` matches `origin/main`; `git diff --check` clean |
| **Documentation** | Index row updated; `PROJECT_STATUS.md` current; CHANGELOG entry and version bump present or their absence recorded as a gap (FR-017) |
| **Next burn recommendation** | Handed to Guido. **No next burn is implicit** — `PROJECT_STATUS.md` states plainly that Children, connectors and optimisation "still require a maintainer decision and none is authorised as an implicit next Burn" |
| **Mission archive** | Report, review artefacts, debt register and rulings are all in the repository at durable paths |

---

## 11. Standard Reports

**Layer 3 — Engineering Standards & Templates** (§1.5). Expected to evolve; a template may add headings but may never drop a verdict a Layer 1 or Layer 2 clause requires.

Every burn ends in exactly one report. Headings are required; a heading with
nothing to say says "None" rather than being omitted.

**Provenance of these shapes** *(Amendment A1 from the self-review).* §11.1 and
§11.2 are **observed**: they generalise the headings actually used by the
RFC-010 and RFC-011 architecture, PR and implementation reports. §11.5 and
§11.6 are **observed in substance** from recorded Governor rulings and
post-flight practice, though neither has previously been a titled document.
§11.3 and §11.4 are **specified, not observed**: no SAFE Report or SAFE
Confirmation artefact exists in the repository (TD4). Their required fields are
reconstructed from what the RFC-011 remediation actually needed in order to act
— identifier, assertion, reference, acceptance criterion, severity — and should
be reviewed against the first real SAFE artefact produced under RFC-100.

### 11.1 Architecture Report *(EECOM)*

`Pre-flight` · `Architecture Summary` · `Key Decisions` · `Contracts Frozen or
Proposed` · `Scope Exclusions` · `Technical Debt` · `Risks` · `Self-Review
Outcome` · `Governor Decisions Required` · `Files Changed` · `Validation` ·
`Repository State` · `Recommendation`

**Verdict:** `GO` · `CONCERN` · `NO-GO`.
**Evidence:** every contract change traceable to a decision; every deviation
from the brief justified.

### 11.2 Implementation Report *(BOOSTER)*

`Decision` · `Scope and Gate` · `Delivered Seam` · `Behaviour Intentionally
Preserved` · `Security Considerations` · `Determinism and Validation` ·
`Known Limitations` · `Technical Debt` · `Scope Boundary`

**Verdict:** `READY FOR SAFE REVIEW` · `READY FOR GOVERNOR REVIEW` · `BLOCKED`.
**Evidence:** test counts against a stated baseline, named CI run identifiers,
live preview result, `git diff --check`, security documentation status.

### 11.3 SAFE Report *(SAFE)*

`Scope Reviewed` · `Findings` (identifier, assertion, reference, acceptance
criterion, severity) · `Severity Summary` · `Merge Policy Assessment` ·
`Verdict`

**Verdict:** `APPROVE` · `APPROVE WITH CONDITIONS` · `BLOCK`.
**Evidence:** every finding references observable code. No speculative findings.

### 11.4 SAFE Confirmation *(SAFE)*

`Findings Under Confirmation` · `Per-Finding Disposition` · `Residual Items` ·
`New Observations (non-blocking)` · `Verdict`

**Verdict:** `CONFIRMED` · `CONFIRMED WITH RESIDUAL` · `NOT CONFIRMED`.

### 11.5 Governor Review *(Governor)*

`Scope Reviewed` · `Rulings` · `Amendments Required` · `Technical-Debt
Disposition` · `Classification Decision` · `Verdict` · `Authorised Next Step`

**Verdict:** `GO` · `GO WITH AMENDMENTS` · `NO-GO`.
Each ruling is dated and attributable.

### 11.6 Post-Flight Report *(TELMU)*

`Merge` · `Post-Merge CI` · `Cleanup` · `Repository State` · `Documentation
Coherence` · `Next Burn Recommendation` · `Mission Archive` · `Verdict`

**Verdict:** `MISSION COMPLETE` · `MISSION COMPLETE WITH FOLLOW-UP` ·
`BURN REOPENED`.

---

## 12. AI Operating Model

**Layer 3 — Engineering Standards & Templates** (§1.5). **Non-normative** — see §12.0.

### 12.0 Status of this section *(normative statement about a non-normative section)*

*(Governor Amendment 4.)*

**The model table in §12.1 records current recommended operating practice. It
is non-normative and replaceable.** It states which model has been found to
suit which role today, and nothing more.

Consequently:

1. **Model selection may evolve without a constitutional amendment.** Assigning
   a different model to any role — including a model from a different provider,
   or one that does not exist at the time of writing — requires no revision of
   RFC-100, no Governor ruling recorded against this document, and no re-freeze.
2. **No burn is out of compliance for using a different model.** A burn states
   which model filled which role; it does not justify the choice against this
   table.
3. **What *is* normative is §12.2** — the independence rule. It constrains
   *relationships between roles*, never the identity of the occupant, and it
   holds whatever models are in use.
4. **Review standards do not change with the model** (`review-gates.md`,
   "Models are Replaceable"). A weaker model does not earn a weaker review, and
   a stronger one does not excuse a gate.

This is the same principle the platform already applies to its own adapters:
implementation may come from any model, and the standards are held constant
against it. A constitution that named its models would contradict the thesis it
governs.

### 12.1 Current recommended practice *(non-normative)*

Models are assigned to roles. The assignment below records current recommended
practice; it is non-normative, replaceable guidance and never a mandatory model
selection or a constraint on the Governor (§12.0).

| Activity | Role | Primary model | Why |
|---|---|---|---|
| Large architecture | EECOM | **Claude Fable** | Sustained multi-thousand-line contract design with internal consistency |
| Architecture review | EECOM (self-review) | **Claude Opus** | Adversarial challenge against a draft the reviewer must be willing to amend |
| Implementation | BOOSTER | **GPT-5.6 (Codex)** | Long, bounded code and test production inside a frozen contract |
| Governor | Governor | **ChatGPT GPT-5.5 / 5.6** | Independent of both the architecture and the implementation lineage |
| SAFE | SAFE | **Claude Opus** | Adversarial security and architecture review, read-only |
| Validation | BOOSTER | **Codex** | Deterministic execution and evidence capture |

### 12.2 Independence rule *(normative)*

**The model that implements never reviews its own implementation, and the model
that authors architecture never approves it.** Where the same model family fills
two roles on one burn — Claude as both EECOM and SAFE — those roles operate on
different artefacts at different lifecycle stages, and the Governor, on a
different lineage entirely, remains the approving authority.

### 12.3 Effort level guidance

| Effort | Applies to | Expectation |
|---|---|---|
| **HIGH** | Architecture Burns; frozen-contract or Core-seam work; RFC-100 itself | Full adversarial self-review; every Governor question surfaced; deviations justified in writing |
| **STANDARD** | Implementation, SAFE Review, Remediation | Checkpoints performed and evidenced; no scope expansion |
| **LOW** | Documentation, Release Closeout, Post-Flight | Mechanical accuracy; verification over judgement |

### 12.4 Expected handoffs

```text
Governor ─brief─▶ CAPCOM ─brief─▶ EECOM   (architecture)
EECOM ─RFC + self-review─▶ Governor       (approval, freeze)
Governor ─frozen RFC─▶ CAPCOM ─▶ BOOSTER  (implementation)
BOOSTER ─implementation + report─▶ SAFE   (review)
SAFE ─findings artefact─▶ CAPCOM ─▶ BOOSTER (remediation)
BOOSTER ─remediation evidence─▶ SAFE      (confirmation)
SAFE ─confirmation─▶ Governor             (merge review)
Governor ─merge─▶ TELMU                   (post-flight)
TELMU ─state + recommendation─▶ Guido ─▶ Governor
```

Each handoff carries an artefact. A handoff without an artefact is a
[FR-014](#fr-014--review-artefact-continuity) failure.

---

## 13. Operational Precedents

**Supporting record** (§1.5). Binding until superseded by Governor ruling.

Lessons that changed how Foundry is engineered. Each is binding until a Governor
ruling supersedes it.

**P1 — Deterministic fixtures (RFC-009 → PR #23).** RFC-009's route goldens
seeded fixtures from `time.time()`; calendar projections moved and `main` broke
the next morning, after the burn had been declared complete. Produced
[FR-007](#fr-007--deterministic-validation), RFC-010's DET-1…DET-6 and its AST
guard, and the post-merge verification discipline now codified as FR-016.

**P2 — Governor visual gate (RFC-010, amendment 7).** Structural tests proved
region order and cardinality but could not establish readability. A mandatory
Governor visual review was inserted between the reference mission and all
remaining migrations. Produced [FR-010](#fr-010--live-preview-first) and §4.2.
The Phase 2 preview justified the gate by finding a disclosure auto-open
heuristic and a narrow-viewport overflow that the suite did not catch.

**P3 — Review Artefact Continuity (RFC-011, S1–S7).** A CAPCOM brief named
seven SAFE findings; the authoritative PR carried no review, inline or issue
comments, and no local artefact existed. The burn refused to act on bare
identifiers and classified them *interpretation not supported*. When finding
text later arrived, S1 and S3–S6 were remediated properly; S7 remains open and
reopenable. Produced [FR-014](#fr-014--review-artefact-continuity) and §8.4.

**P4 — Combined Reference Implementation Burn (RFC-011, B2; PR #27).** A
branch declared as a Phase 1 slice in fact contained Phases 1–4. Governor
reclassification of PR #27 closed B2 by recognising the branch as the combined
Reference Implementation Burn. The implementation stated plainly that no code
change could make the sequencing claim true. Produced
[FR-015](#fr-015--burn-classification) and §9.6.

**P5 — Governance versus implementation decisions (RFC-011, S6).** Evidence
Vault encryption at rest was deferred by Governor ruling and explicitly removed
from the implementer's technical-debt register — recorded as a decision, not as
debt. Produced §9.5. Misfiling a decision as debt manufactures a permanent
false obligation; misfiling debt as a decision hides one.

**P6 — Platform neutrality is testable (RFC-011, B1).** Core contained a Finance
event catalogue and a `finance.` prefix check. The fix moved the catalogue to a
Finance adapter behind a generic protocol and added a regression test asserting
Core's source contains no `finance.` vocabulary. Produced
[FR-011](#fr-011--platform-before-domain). Neutrality asserted in prose is not
neutrality; neutrality asserted by a test is.

**P7 — Unknown is not zero (RFC-011, B3).** A missing material observation
produced `0.0` and flowed into market, accessibility, mission and
reconciliation lenses as a real number. Produced
[FR-008](#fr-008--honest-information) in its current strict form: unknown
propagates and caps confidence at `Insufficient`; a genuine observed zero
remains a number.

**P8 — Guards may not degrade (RFC-011, B4).** Semantic-duplicate detection was
disabled rather than refused when its dependency was absent. Produced
[FR-009](#fr-009--fail-closed).

**P9 — Self-review must produce amendments (RFC-010, RFC-011).** Both
architecture self-reviews amended the RFC before commit — six amendments and
three respectively — and both recorded what they did *not* fix as accepted
residuals and watch items. A self-review that produces no amendment and no
recorded residual has not been performed.

---

## 14. Governor Rulings Applied

| # | Ruling | Application |
|---|---|---|
| **GD-1** | **Guido and TELMU are permanent Flight Directors.** | **Applied.** |
| **GD-2** | **FR-016 and FR-017 are permanent Flight Rules.** | **Applied.** |
| **GD-3** | **RFC-100 governs engineering governance for all future product RFCs.** | **Applied in §1.3 and §1.6.** |
| **GD-4** | **AI model guidance is recommended operating practice, non-normative and replaceable.** No model selection is mandatory. | **Applied in §12.0 and §12.1.** |
| **GD-5** | **The three governance layers are Constitution, Operations Manual, and Engineering Standards & Templates.** | **Applied in §1.5 and section layer tags.** |
| **GD-6** | **RFC-011 B2 is closed through Governor reclassification of PR #27 as the combined Reference Implementation Burn.** | **Applied in §9.6 and precedent P4.** |

---

## 15. Scope Exclusions

RFC-100 governs engineering only. It does **not** design, amend or interpret:

Foundry platform architecture · Finance domain architecture · Mission Console ·
Mission Assessment · Asset & Telemetry Acquisition · the Canon · the Design
Constitution · the constitutional invariants in `architecture.md` · any
specification.

RFC-100 also does not: introduce production source, tests, templates, CSS,
fixtures or runtime configuration; modify any existing RFC; resolve any open
question belonging to another RFC; or create Governor authority.

Where RFC-100 quotes another document, the quoted document remains canonical.

---

## 16. Technical Debt

| # | Debt | Disposition |
|---|---|---|
| **TD1** | **`review-gates.md` and RFC-100 overlap.** Severity definitions, reviewer prohibitions and the merge policy exist in both | Deliberate for this burn: RFC-100 cites rather than restates, and `review-gates.md` remains canonical for gate mechanics. A future Documentation Burn should fold it into RFC-100 §8 or reduce it to a pointer. Not done here — it would edit a document outside this burn's declared scope (FR-004) |
| **TD2** | **Two Flight Directors have no post-ratification operating history.** Guido and TELMU are named from documented work | Resolved by GD-1; later burns will provide operating evidence |
| **TD3** | **Gate coverage is unchanged.** Four of six planned review gates (Data Integrity, Performance, Product Design, Release) remain unbuilt. RFC-100 formalises the roles around the two that exist | Out of scope. RFC-100 does not create gates; a successor RFC should |
| **TD4** | **SAFE artefacts have no fixed home.** §8.4 requires durable artefacts but no SAFE Report currently exists in `docs/reviews/` — only self-reviews do | Recommended path `docs/reviews/RFC-0nn-safe-review.md`, established by the first SAFE Review run under RFC-100 |

---

## 17. Success Criteria

RFC-100 succeeds when a brief of the form

```text
Operate under RFC-100.
Mission: <engineering objective>
```

yields, without further instruction: a pre-flight with a verdict; a correctly
classified burn owned by one role; the checkpoints for that classification;
the report shape and verdict vocabulary for that classification; the Flight
Rules applied without restatement; every Governor question surfaced rather than
resolved locally; and no discipline weaker than RFC-010 or RFC-011 received.

It fails if any future brief needs to restate process to get the same result.

---

## Appendix A — How Mission Control was validated

*(Governor Amendment 5.)*

RFC-100 derives its authority from **observed engineering practice**, not from
design. This appendix is the audit trail for that claim: for each governing
element, the burn that exercised it, what was observed, and what the observation
produced. Every row is checkable against the repository.

A reader who doubts a clause in this manual should be able to find, here, the
burn that earned it.

### A.1 RFC-009 — Pension Independence Mission

*Merged [PR #22](https://github.com/enipeus84/foundry/pull/22), 2026-07-31;
hotfix [PR #23](https://github.com/enipeus84/foundry/pull/23).*

| Observed | Validated | Produced |
|---|---|---|
| A full architecture → implementation → SAFE review → remediation → merge cycle, with the SAFE remediation recorded in the PR description and the technical-debt register | The lifecycle (§4) as a sequence people actually follow | §4; the Remediation Burn classification (§3) |
| Remediation closed named findings without changing Pension policy — the implementation report states this explicitly | Remediation is **bounded by the findings** and does not carry opportunistic change | §3.1 rule 4 |
| Route goldens seeded fixtures from `time.time()`; calendar projections moved and `main` failed the morning after the burn was declared complete | That declared-complete is not the same as verified-complete, and that non-deterministic validation is not validation | [FR-007](#fr-007--deterministic-validation); FR-016; precedent P1 |
| The repair ran on `hotfix/deterministic-mission-control-fixture` — no RFC, no architecture, no freeze — and was correct | That a minimal repair path to a red `main` is legitimate and needs bounding, not prohibiting | Hotfix Burn (§3, §3.1 rule 6) — added by self-review A4 |

### A.2 RFC-010 — Mission Console UX Framework

*Architecture [PR #24](https://github.com/enipeus84/foundry/pull/24), frozen
2026-07-31; implementation [PR #25](https://github.com/enipeus84/foundry/pull/25).*

| Observed | Validated | Produced |
|---|---|---|
| An architecture-only burn: documentation exclusively, no source, tests, CSS, templates or runtime configuration | The Architecture Burn as a real classification with a hard boundary | §3; [FR-013](#fr-013--architecture-before-code) |
| Governor verdict **GO WITH MINOR AMENDMENTS**, seven amendments applied in `ce7cc17`, then freeze — with "implementation must not change a frozen contract without a new Governor decision" stated in the RFC itself | Governor Review as a distinct stage with its own verdict vocabulary, and freeze as an enforceable boundary | §9.2; [FR-003](#fr-003--frozen-architecture); §11.5 verdicts |
| Q1, Q2 and Q3 closed by dated ruling rather than by implementation choice | That open questions are Governor property, and that a ruling must be recorded to be a ruling | §9.4 |
| Amendment 7 inserted a **mandatory Governor visual review** between the reference mission and all remaining migrations | That structural tests establish correctness but not readability, and that a gate can live inside an RFC's own sequence | [FR-010](#fr-010--live-preview-first); §4.2; precedent P2 |
| The Phase 2 live preview at desktop and 334 CSS pixels found and removed a disclosure auto-open heuristic and repaired a narrow-viewport grid overflow the suite had not caught | That the visual gate pays for itself | [FR-010](#fr-010--live-preview-first) verification field |
| The self-review produced **six amendments before commit** and recorded three accepted residuals | The adversarial self-review as a productive obligation rather than a formality | §11.1; precedent P9 |
| The burn corrected a materially stale `PROJECT_STATUS.md` (RFC-008 shown unimplemented, version shown `1.5.1`), changing project-state facts only | That status documents decay silently and misroute the next burn | FR-017 |
| Phase 1 and Phase 2 ran as separately reported burns against one frozen architecture | Multi-phase re-entry into the lifecycle (§4.1) | §4.1 |

### A.3 RFC-011 — Asset & Telemetry Acquisition Framework

*Architecture [PR #26](https://github.com/enipeus84/foundry/pull/26), Revision 2
frozen 2026-07-31; implementation
[PR #27](https://github.com/enipeus84/foundry/pull/27), merged 2026-08-01.*

| Observed | Validated | Produced |
|---|---|---|
| Two sequential SAFE remediation burns, each with per-finding disposition recorded in both the implementation report and the technical-debt register | SAFE Confirmation as a distinct pass scoped to prior findings, with a disposition vocabulary rather than a re-review | §8.2, §8.3 |
| A CAPCOM brief named S1 and S3–S7 with no assertion, file or acceptance criterion; `gh api` returned `[]` for review, inline and issue comments; no local SAFE artefact existed | That a review identifier is not a finding, and that review evidence living only in a channel does not survive the burn | [FR-014](#fr-014--review-artefact-continuity); §8.1 finding fields; §8.4; precedent P3 |
| The burn classified those identifiers *interpretation not supported* — "evidence of absence of a finding text, not a claim that the system is defect-free" — and later remediated S1 and S3–S6 properly once text arrived | That refusing to guess is compatible with acting fully when evidence appears | §8.2 disposition vocabulary; FR-014's duty to seek (self-review A3) |
| Commit `775812c` combined frozen Phases 1–4 while the branch and report claimed a Phase 1 slice; the report stated "No code change can make that historical sequencing claim true", referred reclassification to the Governor, and held Phase 5 | Burn classification as a Governor property, and honest reporting as compatible with not self-correcting status | [FR-015](#fr-015--burn-classification); §9.6; precedent P4 |
| S6 — Evidence Vault encryption at rest — was deferred by Governor ruling and **explicitly removed from the implementer's debt register** as a decision rather than debt | The debt/decision distinction as a Governor act with real bookkeeping consequences | §9.5; precedent P5 |
| B1: `core.acquisition` named a Finance event catalogue and required a `finance.` prefix, violating AC-8. The fix moved it behind a `DomainDraftContract` protocol and added a test asserting Core's source contains no `finance.` vocabulary | That platform neutrality must be asserted by a test, not by prose | [FR-011](#fr-011--platform-before-domain); precedent P6 |
| B3: a missing material observation produced `0.0` and flowed through market, accessibility, mission and reconciliation lenses as a real number | That information honesty has a specific, testable failure mode | [FR-008](#fr-008--honest-information); precedent P7 |
| B4: semantic-duplicate detection **disabled itself** when its dependency was absent, rather than refusing | That a guard degrading to permissive is worse than no guard, because it is trusted | [FR-009](#fr-009--fail-closed); precedent P8 |
| The architecture froze with "no AI writing to canon", extended in Revision 2 to the Identity Index; S1's secret detection was remediated with the note "No detector uses a model" | Evidence-before-AI as an operating constraint, not an aspiration | [FR-012](#fr-012--evidence-before-ai) |
| Governance separation held throughout: EECOM authored and self-reviewed; the Governor approved, froze and ruled; BOOSTER implemented and remediated; SAFE reviewed and never edited | The core separation in §1.2 — the party that implements never approves | §1.2; §2; §2.9 |
| The PR description routed implementation "to BOOSTER per the ten-phase sequence", and each phase was declared a separate burn candidate | Named roles as the actual routing mechanism, and phase-level burn granularity | §2.5; §4.1 |

### A.4 What this validation does not cover

Stated so the appendix is not read as more than it is:

- **Guido and TELMU have not yet run as ratified roles.** Appendix A validates
  the work attributed to them; GD-1 is applied and later burns will provide
  operating evidence.
- **No SAFE Report or SAFE Confirmation artefact exists** in the repository —
  only remediation evidence written in response to findings. §11.3 and §11.4 are
  labelled *specified, not observed* for that reason (§11 provenance note, TD4).
- **Four of six planned review gates remain unbuilt** (TD3). RFC-100 formalises
  the roles around the two that exist and validates nothing about the others.
- **FR-016 and FR-017 are ratified rules without post-ratification operating
  history yet.** Both are observed in RFC-009, RFC-010 and RFC-011; later burns
  will provide standing-rule evidence.
- **One environment.** Every burn in this appendix ran on a single machine with
  a single maintainer. Pre-flight checks 6 and 7 are environment-specific
  (self-review W2).
