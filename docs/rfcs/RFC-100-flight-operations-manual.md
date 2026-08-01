# RFC-100 — Flight Operations Manual

**Status:** Proposed — awaiting Governor ratification.
**Type:** Governance architecture. Documentation-only.
**Author:** EECOM (architecture Flight Controller role, Claude), commissioned by
CAPCOM on behalf of the Governor.
**Date:** 2026-08-01.
**Supersedes:** nothing. **Extends:**
[`../engineering/review-gates.md`](../engineering/review-gates.md).
**Self-review:** [`../reviews/RFC-100-architecture-self-review.md`](../reviews/RFC-100-architecture-self-review.md)
— ten challenges, **four amendments applied before commit** (A1 report-shape
provenance, A2 role occupancy, A3 FR-014 duty to seek, A4 Hotfix Burn), two
watch items.

RFC-100 is the permanent operating manual for Project Foundry engineering. It
governs **how Foundry is engineered**, never **what Foundry does**. No product
architecture, domain model, mission, console, canon or acquisition contract is
created, amended or interpreted by this document.

Once ratified, an engineering brief may be reduced to:

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
- RFC-100 describes **how** any of them is designed, built, reviewed and
  merged.
- A product RFC may **not** redefine a Flight Rule, a role's authority, a burn
  classification, or a report verdict. Those are amended by revising RFC-100
  under Governor ruling.
- Where a product RFC states process (RFC-010's migration gate table, RFC-011's
  ten-phase sequence), that process is **burn-local sequencing** inside the
  RFC's own scope. It is subordinate to RFC-100 and may not weaken it.

### 1.4 Relationship to Governor authority

RFC-100 does not create Governor authority; it records it. The Governor's
authority is prior to this document and is not delegated by it. RFC-100
constrains everyone *except* the Governor, and constrains the Governor only in
form: rulings must be recorded, attributable and durable
(§9, [FR-014](#fr-014--review-artefact-continuity)).

The Governor may override any clause of RFC-100 for a named burn by explicit
ruling. Such an override is a precedent and must be recorded (§13); it is not a
silent exception.

---

## 2. Mission Control Organisation

Seven Flight Director roles. Each is a *role*, not a person and not a model —
roles are filled by whichever human or model is assigned (§12), and the
standards do not change with the occupant
(`review-gates.md`, "Models are Replaceable").

**Evidence status.** Five roles — Governor, CAPCOM, EECOM, BOOSTER, SAFE — have
operating evidence in the repository and are documented here as proven
behaviour. Two roles — **Guido** and **TELMU** — name work that demonstrably
happens but has never had a named owner. They are marked *(newly named)* and
require Governor ratification (§14, GD-1).

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

### 2.3 Guido *(newly named — requires ratification, GD-1)*

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

### 2.7 TELMU *(newly named — requires ratification, GD-1)*

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

Permanent. Numbered for citation. Each rule states the rule, why it exists, and
the operating evidence that produced it. A Flight Rule is amended only by
revising RFC-100 under Governor ruling.

### FR-001 — Canonical Repository

**Rule.** `~/Projects/foundry` (remote `enipeus84/foundry`) is the sole
canonical working copy. No other checkout is authoritative. Any other directory
containing Foundry material — patch files, generated packages, briefs — is
scratch and is never implemented against.

**Why.** Two divergent copies produce work that cannot be merged and reviews
that describe code no one shipped.

**Evidence.** The deprecated `Documents/~:Projects:foundry` copy; the
`Downloads/foundry` brief-and-patch directory.

### FR-002 — Branch Ownership

**Rule.** Every burn runs on its own branch, named for its RFC and phase. `main`
is never a working branch. One branch has one owning role at a time. A branch
name that no longer describes its contents is corrected in the PR description
rather than silently retained.

**Why.** Branch identity is the unit of review, and a misleading branch name
corrupts the audit trail.

**Evidence.** The full `rfc-0nn-*` branch history; PR #25's description
recording that it contains both implementation phases and that its `phase-1`
branch name is retained only for continuity.

### FR-003 — Frozen Architecture

**Rule.** On Governor Architecture Approval, the RFC's contracts are frozen.
**Implementation must not change a frozen contract without a new Governor
ruling.** Interpretation of a frozen contract is likewise a Governor act, not an
implementer's judgement.

**Why.** A contract that implementation may quietly reinterpret is not a
contract.

**Evidence.** Stated verbatim in both the RFC-010 and RFC-011 PR descriptions
and carried into `PROJECT_STATUS.md`.

### FR-004 — Burn Discipline

**Rule.** A burn does exactly its declared scope. Exclusions are stated in the
brief and restated in the report. Work that is out of scope is neither
performed nor recorded as deferred debt — absence by scope discipline is
declared as such.

**Why.** Unbounded burns cannot be reviewed, and undeclared exclusions later
read as undisclosed gaps.

**Evidence.** RFC-011 Phase 1's "Scope boundary" and "Non-debt boundaries"
sections, which enumerate every excluded channel and explicitly deny that their
absence is hidden implementation.

### FR-005 — Merge Authority

**Rule.** The Governor is the only merge authority. Reviewers never merge,
never commit, never modify git state. An implementation PR is marked **"Do not
merge yet"** until Governor Merge Review.

**Why.** Merge is the moment a change becomes the platform's problem forever.

**Evidence.** `review-gates.md` ("Reviewers do not: edit code, implement fixes,
commit, merge, modify Git state"); RFC-010's PR description ends "**Do not merge
yet.**"

### FR-006 — Secure by Design

**Rule.** Every RFC and non-trivial PR answers the Security by Design checklist.
**`N/A` is an answer; silence is not.** An omitted or unanswered checklist is a
process failure that blocks approval. Critical or High security findings block
merge.

**Why.** Security added after the fact is not a property of the architecture.

**Evidence.** `CONTRIBUTING.md`; `review-gates.md` Security Gate; the RFC-011
Phase 1 security work (vault permissions, CSRF in body only, deterministic
secret detection, provenance chain).

### FR-007 — Deterministic Validation

**Rule.** Validation is deterministic or it is not validation. Fixtures use
explicit frozen clocks; no projection-relevant build occurs without an explicit
`as_of`; route goldens are hash-pinned and asserted equal under two distinct
frozen clocks; determinism is enforced by a guard test, not by convention.

**Why.** A suite that depends on wall-clock time passes on the day it is written
and fails the next morning.

**Evidence.** PR #23 (RFC-009's post-merge fixture failure); RFC-010's DET-1…
DET-6 and its AST guard over every test module importing the demo builder.

### FR-008 — Honest Information

**Rule.** Foundry never presents greater certainty than the underlying
calculation supports. A missing input is **unknown**, never zero. Unknown
propagates through every derived lens and caps confidence. A genuine observed
zero remains a number. Unavailability is represented, never disguised.

**Why.** A fabricated zero is indistinguishable from a real one at the point of
decision.

**Evidence.** `review-gates.md` "Honest Software"; RFC-011 finding B3, where
`ValuationLenses` returned `0.0` for a missing material observation and now
returns `None` with an `Insufficient` confidence cap; RFC-010's Financial
Resilience absence path, which states that trajectory history is unavailable
rather than drawing a fake trajectory.

### FR-009 — Fail Closed

**Rule.** When a guard's dependency is unavailable, the operation refuses — it
does not proceed with the guard disabled. Ambiguous identity, missing evidence,
corrupt evidence, unauthorised access, spoofed timestamps and cross-household
references all refuse. No optional dependency may silently turn a protection
off.

**Why.** A guard that degrades to permissive under failure is worse than no
guard, because it is trusted.

**Evidence.** RFC-011 finding B4 (`ResolutionService.semantic_duplicate()` now
raises when its inbox dependency is absent; `ManualInterpreter.interpret()`
refuses before creating a proposal); finding S3 (missing, corrupt or
unauthorised evidence is unavailable rather than rendered); the authentication
model's documented fail-closed behaviour.

### FR-010 — Live Preview First

**Rule.** Any burn changing a rendered surface produces a **live preview**.
Screenshots are acceptable only when a live preview is genuinely unavailable,
and the unavailability is stated. Preview review covers a desktop viewport and a
narrow viewport, and its findings are recorded — including defects found and
repaired during the preview itself.

**Why.** Structural correctness in tests does not establish that a human can
read the page.

**Evidence.** RFC-010 migration step 6 ("Produce a live web preview; screenshots
only if a live preview is genuinely unavailable"); the Phase 2 preview at
desktop and 334 CSS pixels, which found and removed an evidence-disclosure
auto-open heuristic and repaired a shared narrow analysis-grid overflow.

### FR-011 — Platform Before Domain

**Rule.** Platform layers are built and proven against **mock providers and a
mock domain only**. No domain vocabulary, event catalogue, prefix check or
category branch may live in Core. A domain is registered through a contract at
composition time, never hard-wired into the seam.

**Why.** A platform that knows one domain's nouns is that domain's code wearing
a platform's name.

**Evidence.** RFC-011 finding B1, where `core.acquisition` named a Finance event
catalogue and required a `finance.` prefix — a direct violation of AC-8 — and
the catalogue moved to `foundry.finance.acquisition.FinanceManualDraftContract`
behind a generic `DomainDraftContract` protocol, with a regression test
asserting Core's source contains no `finance.` vocabulary. Also RFC-011 Phase 1
("mock providers and mock domain ONLY (no Finance code)") and RFC-010 step 2.

### FR-012 — Evidence Before AI

**Rule.** No model writes to canon. No model writes to the Identity Index. No
model-based detector stands between input and a security decision.
Interpretation is deterministic and versioned; a model interpreter, where one
exists at all, sits behind an explicit `review_each` confirmation policy. Fuzzy
or model-suggested matches never auto-commit.

**Why.** The platform's thesis is that memory belongs to the substrate, not the
model. A model that can write canon refutes it.

**Evidence.** RFC-011's frozen constraints ("no AI writing to canon", extended
in Revision 2 to the Identity Index); the deterministic `manual-json@1`
interpreter that records its identity and version and cannot append `finance.*`;
finding S1's remediation, which states "No detector uses a model."

### FR-013 — Architecture Before Code

**Rule.** Architecture is designed, adversarially self-reviewed, approved and
frozen before implementation begins. An Architecture Burn produces documentation
exclusively. Where implementation reveals an architectural defect, the defect
returns to the Governor; it is not resolved in the implementation.

**Why.** Architecture discovered during implementation is architecture chosen by
whoever typed fastest.

**Evidence.** RFC-010 and RFC-011 both approved and frozen as
documentation-only burns before any implementation existed; `PROJECT_STATUS.md`
recording "No RFC-010 source code, tests, CSS or framework changes exist in the
repository" at approval.

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

**Why.** Acting on a bare identifier means guessing what a reviewer meant and
changing frozen architecture on that guess.

**Evidence.** RFC-011 Phase 1, "Significant SAFE identifiers without published
finding text": the CAPCOM brief named S1 and S3–S7 with no assertion, file or
acceptance criterion; `gh api` returned `[]` for review, inline and issue
comments on the authoritative PR; no local SAFE artefact existed. S1 and S3–S6
were later actioned once finding text arrived, and S7 remains correctly
classified as not actionable.

### FR-015 — Burn Classification

**Rule.** Every burn is classified before it begins. **No burn may change its
own classification.** Reclassification — including discovering after the fact
that a burn spanned more phases than declared — is a Governor decision, and the
report states the true scope rather than the declared one.

**Why.** Classification determines which gates apply; self-reclassification
routes work around its own review.

**Evidence.** RFC-011 finding B2: commit `775812c` combined Phases 1–4 while the
branch and report claimed a Phase 1 slice. The implementation report stated "No
code change can make that historical sequencing claim true" and referred the
reclassification to the Governor, with no Phase 5 work authorised meanwhile.

### 5.1 Proposed additions *(require ratification — GD-2)*

These two rules describe behaviour the project has already been forced into but
which no existing rule states. They are presented separately because RFC-100
captures proven behaviour and these have not previously been written down.

#### FR-016 — Post-Merge Verification *(proposed)*

**Rule.** A burn is not complete until the **first post-merge `main` workflow
passes**. A failing post-merge run reopens the burn.

**Why.** Merge is not the last moment a change can fail.

**Evidence.** RFC-009 was declared complete before its post-merge `main` run
failed on a wall-clock-dependent fixture, repaired by PR #23. RFC-010 step 14
and RFC-011 Phase 10 already impose this on themselves; FR-016 generalises it.

#### FR-017 — Documentation Coherence *(proposed)*

**Rule.** `PROJECT_STATUS.md`, [`index.md`](index.md), `CHANGELOG.md` and
`architecture.md` may not contradict one another after a burn. A burn that
finds one materially stale corrects the project-state facts and says so, leaving
historical material unchanged. A version bump and CHANGELOG entry accompany
every merged implementation burn.

**Why.** Status documents are load-bearing for every subsequent decision; a
stale one silently misroutes the next burn.

**Evidence.** RFC-010 found `PROJECT_STATUS.md` materially stale (RFC-008
described as unimplemented, version as `1.5.1`) and corrected it. RFC-005
shipped with no CHANGELOG entry and no version bump — [issue #13], still open.

---

## 6. Pre-Flight

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
([FR-015](#fr-015--burn-classification)); RFC-011 B2 is the precedent, including
its explicit hold: "no Phase 5 work is authorized meanwhile."

### 9.7 No implementation authority

The Governor does not write code, tests, fixtures or documentation content, and
does not close a finding by editing the work. This preserves the separation the
whole manual rests on: **the party that implements never approves.**

---

## 10. Post-Flight

Owned by TELMU. Every item is verified, not assumed.

| Step | Verification |
|---|---|
| **Merge** | The PR is merged by the Governor; the merge commit is identified |
| **CI verification** | The **first post-merge `main` workflow passes**. A failure reopens the burn (FR-016 proposed) |
| **Cleanup** | Burn branch disposition recorded; no stale worktree; no scratch artefact left in the repository |
| **Repository verification** | Working tree clean; `main` matches `origin/main`; `git diff --check` clean |
| **Documentation** | Index row updated; `PROJECT_STATUS.md` current; CHANGELOG entry and version bump present or their absence recorded as a gap (FR-017 proposed) |
| **Next burn recommendation** | Handed to Guido. **No next burn is implicit** — `PROJECT_STATUS.md` states plainly that Children, connectors and optimisation "still require a maintainer decision and none is authorised as an implicit next Burn" |
| **Mission archive** | Report, review artefacts, debt register and rulings are all in the repository at durable paths |

---

## 11. Standard Reports

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

Models are assigned to roles. **Review standards do not change with the model**
(`review-gates.md`, "Models are Replaceable"). The assignment below records
current practice; it is a default, not a constraint on the Governor.

| Activity | Role | Primary model | Why |
|---|---|---|---|
| Large architecture | EECOM | **Claude Fable** | Sustained multi-thousand-line contract design with internal consistency |
| Architecture review | EECOM (self-review) | **Claude Opus** | Adversarial challenge against a draft the reviewer must be willing to amend |
| Implementation | BOOSTER | **GPT-5.6 (Codex)** | Long, bounded code and test production inside a frozen contract |
| Governor | Governor | **ChatGPT GPT-5.5 / 5.6** | Independent of both the architecture and the implementation lineage |
| SAFE | SAFE | **Claude Opus** | Adversarial security and architecture review, read-only |
| Validation | BOOSTER | **Codex** | Deterministic execution and evidence capture |

### 12.1 Independence rule

**The model that implements never reviews its own implementation, and the model
that authors architecture never approves it.** Where the same model family fills
two roles on one burn — Claude as both EECOM and SAFE — those roles operate on
different artefacts at different lifecycle stages, and the Governor, on a
different lineage entirely, remains the approving authority.

### 12.2 Effort level guidance

| Effort | Applies to | Expectation |
|---|---|---|
| **HIGH** | Architecture Burns; frozen-contract or Core-seam work; RFC-100 itself | Full adversarial self-review; every Governor question surfaced; deviations justified in writing |
| **STANDARD** | Implementation, SAFE Review, Remediation | Checkpoints performed and evidenced; no scope expansion |
| **LOW** | Documentation, Release Closeout, Post-Flight | Mechanical accuracy; verification over judgement |

### 12.3 Expected handoffs

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

Lessons that changed how Foundry is engineered. Each is binding until a Governor
ruling supersedes it.

**P1 — Deterministic fixtures (RFC-009 → PR #23).** RFC-009's route goldens
seeded fixtures from `time.time()`; calendar projections moved and `main` broke
the next morning, after the burn had been declared complete. Produced
[FR-007](#fr-007--deterministic-validation), RFC-010's DET-1…DET-6 and its AST
guard, and the post-merge verification discipline now proposed as FR-016.

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

**P4 — Combined implementation burn (RFC-011, B2).** A branch declared as a
Phase 1 slice in fact contained Phases 1–4. The implementation stated plainly
that no code change could make the sequencing claim true, referred
reclassification to the Governor, and held Phase 5. Produced
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

## 14. Governor Decisions Required

| # | Decision | Recommendation |
|---|---|---|
| **GD-1** | **Ratify Guido and TELMU as Flight Directors.** Both name work with clear operating evidence but no named owner: RFC canon and next-burn recommendation (Guido); post-merge verification, project telemetry and status coherence (TELMU) | **Ratify.** The alternative is that this work continues to be absorbed opportunistically by whichever burn notices, which is how PR #23 and the RFC-005 CHANGELOG gap happened |
| **GD-2** | **Ratify or reject FR-016 (Post-Merge Verification) and FR-017 (Documentation Coherence)** as permanent Flight Rules. Both generalise discipline that RFC-010 and RFC-011 already impose on themselves | **Ratify both.** They add no new obligation the last two RFCs did not already carry; they make it non-optional for the next one |
| **GD-3** | **Confirm that RFC-100 binds product RFCs (§1.3)** — that a product RFC may not redefine a Flight Rule, role authority, burn classification or report verdict | **Confirm.** Without it, process drifts back into individual briefs, which is the condition RFC-100 exists to end |
| **GD-4** | **Confirm the model assignment in §12 is a default, not a constraint** — the Governor may reassign any role to any model for any burn without amending RFC-100 | **Confirm.** "Models are Replaceable" is an existing principle; §12 records practice, and freezing it would contradict that principle |
| **GD-5** | **Rule on RFC-100's amendment procedure.** Recommended: Flight Rules, role authority, burn classification and lifecycle change only by a revision of RFC-100 approved as an Architecture Burn; §12 and §13 may be extended by a Documentation Burn under Governor Review | **Adopt as recommended.** Precedents accumulate faster than constitutional clauses should |
| **GD-6** | **Rule on the open RFC-011 B2 reclassification**, which RFC-100 §9.6 documents as precedent but does not resolve. It remains open and blocks Phase 5 | **Rule separately from RFC-100.** This RFC records the precedent; it does not and should not decide the live case |

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
| **TD2** | **Two Flight Directors have no operating history.** Guido and TELMU are named from unattributed work | Resolved by GD-1, then proven by use. Marked *(newly named)* until a burn has run under each |
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
