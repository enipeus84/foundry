# RFC-100 — Architecture Self-Review

Adversarial self-review performed by EECOM before commit, against the draft of
[`../rfcs/RFC-100-flight-operations-manual.md`](../rfcs/RFC-100-flight-operations-manual.md)
at 2026-08-01.

**Outcome: four amendments made to the RFC as a result of this review** (A1–A4
below). Six challenges produced no amendment and are recorded with the reasoning
that cleared them, including one accepted residual and two watch items.

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

**W2.** Pre-flight checks 6 and 7 are environment-specific; move to an appendix
if a second engineering environment appears.
