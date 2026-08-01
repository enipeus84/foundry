# RFC-100 — Architecture Self-Review

Adversarial self-review performed by EECOM before commit, against
[`../rfcs/RFC-100-flight-operations-manual.md`](../rfcs/RFC-100-flight-operations-manual.md)
at 2026-08-01.

**Revision 1 outcome: four amendments** (A1–A4). Six challenges produced no
amendment and are recorded with the reasoning that cleared them, including one
accepted residual and two watch items.

**Revision 2 outcome: two further amendments** (A5–A6), after applying the five
Governor amendments. Four Revision 2 challenges produced no amendment. See
[Revision 2](#revision-2--review-of-the-governor-amendments) below.

---

# Revision 1

The governing constraint on this burn is unusual and worth naming: the brief
says *capture proven behaviour only; do not invent process.* A governance
document is the easiest place in the project to violate that, because invented
process reads exactly like real process. Four of the ten challenges below exist
solely to test that constraint.

---

## Challenge 1 — Does RFC-100 invent process, or record it?

**One material leak found and fixed; two disclosed rather than removed.**

Clean and traceable to evidence: the Flight Rules FR-001…FR-015 (each cites the
burn that produced it), the lifecycle, the burn classifications, the pre-flight
checks, SAFE Review versus Confirmation, the Governor's powers, the precedents,
and the model assignment.

**Leak found.** §11 specified required headings and verdict vocabularies for six
report types as though all six were observed practice. Two are not. **No SAFE
Report or SAFE Confirmation artefact exists anywhere in the repository** — only
the *remediation evidence* written in response to findings does (RFC-011's
implementation report and technical-debt register). Presenting an invented
report shape as recorded practice is precisely the failure mode the brief
prohibits, and it is the same defect class as RFC-010's A1 (Finance nouns
promoted into a Core-owned slot) and RFC-011's A1 (domain values presented as
Core vocabulary): something local being asserted at a higher level of authority
than its evidence supports.

**Amendment A1.** §11 gains an explicit provenance note. §11.1 and §11.2 are
marked **observed**; §11.5 and §11.6 **observed in substance**; §11.3 and §11.4
**specified, not observed**, with their required fields derived from what the
RFC-011 remediation actually needed in order to act, and flagged for review
against the first real SAFE artefact. TD4 already records the missing artefact
path; A1 stops the RFC from overstating its own basis.

**Disclosed, not removed.** Two further items are near the invention line and
are labelled in place rather than deleted: Guido and TELMU carry *(newly named)*
and GD-1; FR-016 and FR-017 sit in a separate §5.1 marked *proposed* with GD-2.
Both name work with clear evidence but no named owner. Deleting them would make
the manual tidier and the project no safer — the RFC-005 CHANGELOG gap and the
PR #23 post-merge failure are exactly what unowned work looks like.

---

## Challenge 2 — Is seven Flight Directors too much for one maintainer?

**No amendment on the count; one real defect found in how roles are separated.**

The count itself is defensible: five roles already operate, the two new ones
formalise work that is already happening, and a role costs nothing when it is
not invoked — a Documentation Burn touches CAPCOM, EECOM and the Governor and
never involves BOOSTER, SAFE or TELMU at all.

**Defect found.** The draft's role table said CAPCOM "may not approve
architecture" while the operating reality is that **the Governor and CAPCOM are
frequently the same party** — the briefs themselves are issued by the platform
owner. Read literally, the draft either forbade something that routinely happens
or forced a fiction of two separate people. Both readings damage the rule that
matters, which is not about headcount: *the party that implements never
approves.*

**Amendment A2.** New §2.9 *Role occupancy*. Separation is enforced on **acts,
not occupants**: no party performs two roles on the same artefact in the same
burn; the Governor may occupy CAPCOM, but approval, freeze, ruling and merge are
Governor acts that must be recorded as such — a brief is never an approval and a
relayed instruction is never a ruling; and an unoccupied role still owes its
outputs. The escalation path renumbers to §2.10.

---

## Challenge 3 — Does FR-014 give an implementer a way to refuse review?

**Real risk confirmed; amendment made.**

FR-014 is the rule most open to abuse in the manual. As drafted, a burn could
dismiss any inconvenient finding by asserting that its text was insufficient,
and the rule would appear to sanction it.

The RFC-011 precedent it comes from was handled honestly — the burn ran `gh api`
against the PR's review, inline and issue comments, found `[]` on all three,
searched locally, and stated explicitly that this was "evidence of absence of a
finding text, not a claim that the system is defect-free." But the rule as
written recorded the *conclusion* of that behaviour without requiring the
*behaviour*. A weaker occupant could reach the same conclusion without doing any
of the work.

**Amendment A3.** FR-014 gains a **duty to seek**: before classifying an
identifier as unsupported, the receiving role must search for the artefact —
review channel, PR review/inline/issue comments, repository — record the search,
and request the missing text through CAPCOM. The rule protects against guessing
at a reviewer's meaning; it is never a route to dismissing review.

I note that this makes FR-014 the only Flight Rule imposing an obligation on the
role the rule protects. That asymmetry is intentional: a rule that can be
invoked unilaterally needs a cost.

---

## Challenge 4 — Does the lifecycle cover every burn that has actually happened?

**One uncovered case found; amendment made.**

I replayed the last five merged PRs against §4. PRs #24, #25, #26 and #27 all
route cleanly. **PR #23 does not.** It was a hotfix: `main` was red after
RFC-009's declared-complete burn, and the repair went straight to a
`hotfix/deterministic-mission-control-fixture` branch with no preceding
architecture, no RFC and no freeze. Under the draft lifecycle that merge was
unclassifiable — which would mean the manual's first act was to render an
already-shipped, correct piece of engineering illegitimate.

**Amendment A4.** A **Hotfix Burn** classification is added to §3 with §3.1
rule 6 constraining it tightly: the only burn that may begin without a preceding
Architecture Burn, and only to restore a failing `main`; bounded to the failure
and its regression test; no feature work, no contract change, no refactor;
`hotfix/*` branch; still requires Governor Merge Review and Post-Flight.
Anything larger is a Remediation Burn under the normal lifecycle.

This is recorded behaviour, not new process — PR #23 already did all of it.

---

## Challenge 5 — Does FR-015 conflict with honest reporting?

**No amendment; defence recorded.**

The apparent conflict: FR-015 forbids self-reclassification, while FR-008 and
the Evidence checkpoint demand that a report state what is true. If a burn
discovers it has done four phases' work, must it report a false Phase 1?

No, and the RFC-011 B2 precedent already demonstrates the resolution. The burn
**reported the true scope** ("the evidence is a combined Phase 1–4
implementation"), **refused to restate it as compliant** ("No code change can
make that historical sequencing claim true"), **referred the reclassification to
the Governor**, and **held Phase 5**. Reporting truth and changing status are
different acts; FR-015 forbids only the second. §9.6 carries this explicitly. No
change needed.

---

## Challenge 6 — Are the effort levels evidence-based?

**No amendment; accepted residual.**

HIGH is evidenced — it is declared in the briefs and its practice is visible in
RFC-010's and RFC-011's self-reviews. **STANDARD and LOW are names I chose.** No
burn has ever been labelled either.

I considered dropping §3.2 and §12.2 to a single sentence ("HIGH means full
adversarial self-review"). I did not, for one reason: with only HIGH defined,
every burn either claims HIGH or is unlabelled, and an unlabelled burn has no
stated expectation at all — which is the condition that let a Phase 1 slice grow
into four phases. Two additional labels with explicit expectations is a smaller
invention than an undefined default.

**Recorded as an accepted residual, not a defect.** If the Governor prefers, the
levels reduce to HIGH / not-HIGH without touching any other section.

---

## Challenge 7 — Does RFC-100 constrain the Governor illegitimately?

**No amendment; defence recorded.**

A manual written by EECOM that binds the Governor would invert the authority it
claims to record. §1.4 handles this: RFC-100 does not create Governor authority,
which is prior to the document and not delegated by it; it constrains everyone
*except* the Governor, and constrains the Governor only in **form** — rulings
must be recorded, attributable and durable. §9.7's "no implementation authority"
is not a limit imposed on the Governor either; it is the same separation that
protects the Governor's approvals from being self-approvals.

The override clause is the proof: the Governor may set aside any RFC-100 clause
for a named burn. The single requirement is that the override is recorded rather
than silent — which is a requirement on the *record*, not on the decision.

---

## Challenge 8 — Will §12 age badly the moment a model is renamed?

**No amendment; watch item W1.**

Naming six specific model versions in a constitutional document guarantees
staleness. Two mitigations are already present: `review-gates.md`'s existing
"Models are Replaceable" principle is cited in §12's opening, and GD-4 asks the
Governor to confirm that the assignment is a **default the Governor may
reassign without amending RFC-100**. GD-5 additionally routes §12 changes
through a Documentation Burn rather than a full revision.

**W1.** If GD-4 is confirmed, §12's table is operational guidance embedded in a
constitutional document. A later revision should consider moving it to a
separate, faster-moving operations note that RFC-100 references. Not done here:
splitting it now would create a second process document, which is the condition
RFC-100 exists to end.

---

## Challenge 9 — Is the pre-flight over-fitted to one machine?

**No amendment; watch item W2.**

Two of the nine pre-flight checks are environment-specific: **caffeinate** is
macOS-only, and **`.venv` ≥ 3.10** encodes this project's current local Python
arrangement. A constitutional document containing `caffeinate` is a slightly
uncomfortable object.

They stay, because both are proven pre-flight practice on the machine every burn
has actually run on, and because the brief names them explicitly. Both are also
correctly graded — caffeinate fails to CONCERN, never NO-GO.

**W2.** If Foundry is ever engineered from a second environment, checks 6 and 7
move to an environment appendix and §6 retains only their intent ("a supported
interpreter for the burn's validation" / "uninterrupted execution for
long-running burns").

---

## Challenge 10 — Does RFC-100 shorten briefs without losing discipline?

**No amendment; tested against a real brief.**

I tested the claim by reducing this burn's own CAPCOM brief. Its ~1,400 words
carry six kinds of content:

| Brief content | Under RFC-100 |
|---|---|
| Spacecraft, fuel, effort level, authority | §12 (model assignment), §3.2 (effort), §2 (authority) — **inherited** |
| Burn type ("Architecture Burn") | §3 classification — **inherited**, one word in the brief |
| Architecture inputs (which RFCs are authoritative) | **Still required** — objective-specific |
| Expected sections | **Still required** — objective-specific |
| Explicit exclusions | §3.1 rule 5 requires them; their *content* — **still required** |
| Required output shape ("RFC-100 ARCHITECTURE REPORT" + headings) | §11.1 — **inherited** |
| Pre-flight, checkpoints, Governor questions, GO/CONCERN/NO-GO | §6, §7, §11.1, §14 — **inherited** |

Roughly half the brief is now inheritable, and the half that remains is the half
that *should* be written each time: what the objective is, what it may not
touch, and what it must produce. The success criterion in §17 is met in
substance, though not in the literal two-line form — a brief will always need
its scope and exclusions. §17 is worded accordingly ("without further
instruction", not "without further content").

---

## What this review did not fix

- **TD1 — overlap with `review-gates.md`.** Severity definitions, reviewer
  prohibitions and merge policy now exist in two documents. RFC-100 cites rather
  than restates, and `review-gates.md` remains canonical for gate mechanics, but
  the duplication is real. Folding it in would edit a document outside this
  burn's declared scope (FR-004), so it is left for a Documentation Burn.
- **TD3 — four planned review gates remain unbuilt.** RFC-100 formalises the
  roles around the two gates that exist and does not create the other four.
- **GD-6 — RFC-011's B2 reclassification is still open** and still blocks
  Phase 5. RFC-100 records it as precedent (§9.6, P4) and deliberately does not
  resolve the live case.
- **No role has ever run as Guido or TELMU.** Ratification (GD-1) is a decision;
  proving them is a later burn's job.

## Watch items

**W1.** §12's model table is operational guidance inside a constitutional
document; consider extraction on a later revision if GD-4 is confirmed.
*Substantially addressed in Revision 2 by Governor Amendment 4 and §1.5: the
table is now explicitly Layer 3 and non-normative. It remains physically inside
the document, so the watch item is narrowed rather than closed.*

**W2.** Pre-flight checks 6 and 7 are environment-specific; move to an appendix
if a second engineering environment appears. *Open; now also recorded in
Appendix A.4.*

---

# Revision 2 — review of the Governor amendments

Performed at 2026-08-01, against the amended document, after applying Governor
Amendments 1–5. Scope is the amendments and their interaction with the frozen-in-
principle material — **not** a re-review of Revision 1, whose material the
Governor accepted.

**Outcome: two amendments (A5, A6).** Four challenges produced no amendment.

The specific risk in an amendment burn is different from a design burn: the
failure mode is not a bad idea, it is **drift** — refinements that quietly alter
something the brief said to preserve, or that read as refinement while removing
discipline. Challenge R6 exists solely to test for that.

---

## Challenge R1 — Does the three-layer split create a route to weaken Layer 1?

**No amendment; defence recorded.**

The obvious attack on Amendment 1 is that it manufactures a cheap path: move an
inconvenient obligation into Layer 2 or 3, then amend it away with a
Documentation Burn instead of a constitutional act.

Three properties close it. The layer assignment is itself Layer 1 material
(§1.5 sits inside §1, which the table lists as Constitution), so reassigning a
section is a constitutional act, not a documentation one. The **layer discipline
clause** states that a lower layer may never weaken a higher one and that the
Layer 1 clause wins any conflict. And Layer 2 is scoped to *how* a Layer 1
obligation is met, explicitly "may never remove one."

I checked the assignment for a smuggled obligation and found none: every
blocking rule — the Flight Rules, merge authority, the lifecycle, the
classifications — is Layer 1. Layer 2 holds procedure for exercising them and
Layer 3 holds forms. §9 is the one that needed care, and it is annotated in
place: Governor *authority* is Layer 1 (§2.1); §9 is the *procedure* by which it
is exercised.

---

## Challenge R2 — Does §1.6 P2 contradict the Flight Rules?

**Contradiction confirmed; amendment made.**

P2 as first drafted said that within product architecture the product RFC is
authoritative and "RFC-100 has no opinion whatsoever." That is a clean line, and
it is false about RFC-100's own contents.

**FR-008** requires that a missing input be represented as unknown rather than
zero. **FR-009** requires that guards refuse rather than degrade. **FR-011**
forbids domain vocabulary in a platform module. **FR-012** forbids a model on a
canon write path. Every one of those constrains **how the software behaves**,
not merely how work is conducted. A product RFC proposing a permissive-on-
failure guard would breach FR-009 while remaining, under a literal reading of
P2, entirely within its own authority.

Left unfixed, this is the worst kind of governance defect: the precedence
section — the part written specifically to remove ambiguity — would itself be
the ambiguity, and the four rules with the strongest provenance in the whole
manual (all four came from real RFC-011 findings) would be the ones a product
RFC could argue away.

**Amendment A5.** §1.6 gains **P8**: those four rules are **floors, not
designs**. They state what any product architecture must not do, never what it
must be; a product RFC may exceed them and may not lower them, and remains free
to choose every contract, vocabulary and seam above them. A product RFC that
believes a floor is wrong invokes P6 rather than deviating. The rationale under
the table names the defect rather than hiding the repair.

This preserves the brief's instruction not to alter existing Flight Rules — none
is altered. What changes is that the new precedence section stops
misdescribing them.

---

## Challenge R3 — Is every Verification field actually verification?

**Overstatement found; amendment made.**

Amendment 3's stated objective is to make Flight Rules "auditable rather than
descriptive." I wrote seventeen Verification fields and then audited them
against that objective rather than against my own intent.

Four are genuinely test-verified — FR-007, FR-008, FR-009 and FR-011 each name
an assertion that fails when the rule is breached, three of them citing tests
that already exist in the repository. The other thirteen are **artefact
inspection**: read the pre-flight output, the diff, a report section, a
checklist, a run identifier, a ruling. Those are objective and checkable, but
they depend on a role actually looking, which is a materially weaker guarantee.

Presenting all seventeen in an identical bold **Verification.** field implies a
uniform standard of proof that does not exist — the same defect class as
Revision 1's A1, where invented report shapes sat beside observed ones with no
visible distinction. An amendment intended to create an audit would instead have
created the appearance of one.

**Amendment A6.** The §5 preamble gains a **verification-mode table** splitting
the rules into test-verified and artefact-verified, stating plainly that
artefact verification is weaker, and naming FR-012 as the strongest candidate
for promotion to a test. RFC-100 does not build that test — it is documentation
(§15) — but the gap is now visible rather than smoothed over.

---

## Challenge R4 — Does Appendix A claim more than the record supports?

**No amendment; every row checked.**

Appendix A is the section most able to launder assertion into authority, since
its whole function is to say "this was validated." I checked each row against
the repository rather than against memory: PR numbers, merge and freeze dates,
commit `775812c`, commit `ce7cc17`, the `gh api` empty-comment result, the 334
CSS-pixel preview, the B1–B4 and S1–S7 dispositions, the two named regression
tests. Each is traceable.

Two properties keep it honest. Every row separates *observed* from *produced*,
so a reader can reject the inference while keeping the fact. And **A.4** states
what the appendix does not cover — Guido and TELMU are unvalidated, no SAFE
artefact exists, four gates are unbuilt, FR-016 and FR-017 are lessons rather
than operating rules, and every burn ran in one environment with one maintainer.

A validation appendix without A.4 would be the strongest argument in the
document for exactly the things it has the least evidence for. That asymmetry is
worth stating explicitly, so it is.

---

## Challenge R5 — Does making §12 non-normative weaken the independence rule?

**No amendment; the risk was live and is closed by construction.**

Amendment 4 declares the model table non-normative. §12 also contained the
independence rule — the model that implements never reviews its own
implementation, the model that authors architecture never approves it. Declaring
the whole section non-normative would have made the project's central separation
advisory, by accident, in the act of making model choice flexible.

The applied amendment separates them: §12.0 marks the *table* non-normative and
states explicitly that "what *is* normative is §12.2"; §12.2 carries
*(normative)* in its heading; and the underlying separation is stated
independently in §1.2 and enforced through §2.9's occupancy rules, so it does
not depend on §12 at all. Independence constrains relationships between roles,
never the identity of the occupant — which is precisely why it survives any
model change.

---

## Challenge R6 — Did the amendments alter anything the brief said to preserve?

**No amendment; audit recorded.**

The brief preserved six things. I diffed each against Revision 1:

| Preserved | Result |
|---|---|
| Flight Director responsibilities | Unchanged. §2.1–§2.10 are untouched except for the Layer 1 tag on §2 |
| Mission lifecycle | Unchanged. §4 and its diagram are byte-identical except for the layer tag |
| Burn classifications | Unchanged. Ten classifications, same owners, outputs and gates |
| Governor authority | Unchanged. §9's substance is identical; the layer tag records that §9 is *procedure* while the *authority* in §2.1 is Layer 1 |
| Existing Flight Rules | **All fifteen rule statements are verbatim.** Only the field labels changed (`Why` → `Rationale`, `Evidence` → `Provenance`) and the new Verification field was added. No rule was weakened, merged or dropped |
| Existing architecture | Unchanged. No decision reversed |

Two edits deserve to be called out rather than buried, because both *removed*
text:

1. **§1.3 lost a bullet.** The "a product RFC may not redefine a Flight Rule…"
   bullet moved into §1.6 as **P3**, verbatim in substance and now normative
   rather than explanatory. This is duplication removal, not a reduction — the
   rule is stronger where it now sits.
2. **GD-4 and GD-5 were restated.** The brief says to retain all six decisions
   and change none "unless required by the amendments." Both were required:
   GD-4 asked the Governor to confirm the model table is "a default", which
   Amendment 4 supersedes with the sharper non-normative framing; GD-5 described
   amendment procedure by section number, which Amendment 1 supersedes with the
   three layers. **Both decisions are the same decisions** — the same question,
   the same recommendation — expressed in the vocabulary the amendments created.
   GD-1, GD-2, GD-3 and GD-6 are untouched.

---

## What Revision 2 did not fix

- **TD1, TD3, GD-6 and the unproven Guido/TELMU roles** are unchanged from
  Revision 1 and remain open.
- **FR-012 remains artefact-verified.** A test asserting that no model
  invocation exists on a canon or Identity Index write path is buildable and
  would be a genuine strengthening. It is implementation and therefore outside
  an architecture burn (§15).
- **Appendix A validates one environment.** No amount of documentation changes
  that; only a second environment would.
- **§11.3 and §11.4 remain specified, not observed.** The first SAFE Review run
  under RFC-100 should be compared against them, as the §11 provenance note
  already directs.
