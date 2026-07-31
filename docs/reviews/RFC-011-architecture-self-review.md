# RFC-011 — Architecture Self-Review (Revision 2)

Adversarial self-review performed by EECOM before commit, against the
Revision 2 draft of
[`../rfcs/RFC-011-asset-telemetry-acquisition-framework.md`](../rfcs/RFC-011-asset-telemetry-acquisition-framework.md)
at 2026-07-31, after applying the five Governor amendments (GA1–GA5).

**Outcome: three amendments made to the RFC as a result of this review**
(A1–A3 below). Five challenges produced no amendment and are recorded with
the reasoning that cleared them, including one accepted residual and two
watch items.

---

## Challenge 1 — Does the new Core surface stay domain-neutral?

**One leak found and fixed.**

Clean: the Identity Index, Resolution Service, containment relation,
temporal contract, condition lifecycle and per-stream refresh vocabularies
contain no domain concept, currency, or category branch.

**Leak found.** The `ExternalRef` section declared namespaces "a Core-owned,
additive vocabulary" while its examples — `ticker`, `isin`,
`uk_sort_account` — are Finance concepts. Core owning those *values* would
put domain nouns in a Core vocabulary, the exact defect RFC-010's
self-review A1 caught in disclosure slot names.

**Amendment A1.** The namespace *mechanism* is Core-owned; namespace
*values* are contributed additively by domains and channels — the same
ownership split every extensible vocabulary already follows. The RFC text
now states this explicitly.

---

## Challenge 2 — Is Identity Resolution over-engineered for one household?

**No amendment; defence recorded.**

The layer is one event kind, one projection (a two-column lookup with
history), and one pure function with three outcomes. That is less machinery
than a single per-interpreter fuzzy matcher would grow into, and the
alternative's failure mode — misattribution — is the only acquisition error
that *multiplies* (every future observation of a poisoned symbol lands
wrong). Scale is irrelevant to that argument: a household with one broker
account still receives "PYPL" in three spellings. The deviation from the
briefed pipeline position (service at proposal formation, not a stage
before interpretation) is justified in the RFC on data-dependency grounds:
identity consumes interpreted symbols, which do not exist pre-interpreter.

---

## Challenge 3 — Do container reconciliation rules contradict Evidence First?

**No — but only because of the capture/consumption split; reasoning
recorded.**

A custodian's "account total" line *is* evidence and is captured verbatim
like everything else (Principle 2 is untouched). What the containment rules
govern is *consumption*: when registered holdings exist, the total is
consumed as a reconciliation check rather than a value source, because
consuming both is the double-count hazard (AC-16, R13). Evidence First
governs what is stored; the composition rules govern what a lens may count.
No contradiction, and the distinction is now load-bearing enough that it is
stated in the containment section itself.

---

## Challenge 4 — Does semantic dedup silently destroy legitimate data?

**A real hazard was found and fixed.**

The draft said a semantic duplicate "defaults to rejection". Two genuinely
identical observations — two same-day, same-amount dividends — could then be
silently collapsed, which is data *loss* dressed as hygiene, and worse than
the duplication it prevents.

**Amendment A2.** A `duplicate_of` flag now carries a rejection
*recommendation that the reviewer confirms — never a silent discard* — and
the RFC notes that distinct external document refs are the usual
disambiguator, with the human ruling where they are absent. Auto-commit
streams are unaffected: their deterministic interpreters carry document refs
by construction.

---

## Challenge 5 — Is the accessibility lifecycle complete? (clawback)

**A gap was found and fixed.**

`pending → satisfied | lapsed | revoked` had no answer for a restriction
*re-imposed after* satisfaction — a clawback on vested equity, a trust
distribution recalled. Allowing a backwards transition
(`satisfied → revoked`) would rewrite history, violating the append-only
philosophy at the state-machine level.

**Amendment A3.** Terminal states never transition backwards: a clawback is
a **new condition instance** asserted by the domain event that imposes it.
Restriction re-imposed is a new fact, not a rewound one. The RFC states this
rule in the lifecycle section.

---

## Challenge 6 — Does the bitemporal rule burden every consumer?

**No amendment; one watch item.**

Ordinary consumers use the special case D = now, which is exactly what they
do today; only restatement views ("as believed then") need the full fold.
The genuine risk is a consumer folding by `recorded_at` where `valid_at` is
meant (R12), and the enforceable form is AC-18 plus the rule that
`recorded_at` is substrate-set only.

**Watch item W1.** No consumer-side contract yet *forces* correct timestamp
selection — AC-18 asserts the fold is available and deterministic, not that
every future metric uses the right one. The Metric Provider contract's
`as_of` semantics should be tightened to name `valid_at` explicitly when
Spec 000 is next amended for other reasons; not worth an amendment cycle on
its own.

---

## Challenge 7 — Was any frozen constraint weakened by Revision 2?

**No amendment; verified item by item.**

Append-only evidence — untouched (the vault decision is unchanged from
Revision 1 and remains OQ1). Immutable provenance — extended (resolution
basis and temporal claims add provenance, remove none). Confirmation gate —
strengthened (identity floor: fuzzy matches never auto-commit). No AI writes
to canon — extended upstream (no AI writes to the Identity Index either).
Mission Engine and Mission Console — no contract, field or behaviour
touched; acquisition remains structurally invisible to assessment (AC-12).
Provider plugin architecture — unchanged; identity is a service, not a
provider. Domain neutrality — Challenge 1. Fail-closed — extended to
identity (`ambiguous`/`unresolved` block auto-commit).

---

## Challenge 8 — Is "channels multiply; the seam does not" still true?

**Yes — and Revision 2 tightens it; residual recorded.**

Every amendment lands *inside* the seam: a new channel still touches only a
provider, possibly an interpreter, and vocabulary values (external-ref
namespaces, `update_strategy`). Identity, containment, time, refresh and
accessibility are seam-side, so channels inherit them rather than
implementing them — Revision 2 moved five concerns from "every channel's
problem" to "the seam's problem", which is the invariant's whole point.

**Residual, accepted.** The seam itself is now seven contracts. That is
irreducible given the Governor's five amendments — each answers a question
some channel would otherwise answer divergently — but seam growth is the
metric to watch: a Revision 3 that adds contracts without retiring
divergence risk should be challenged. Recorded as watch item W2.
