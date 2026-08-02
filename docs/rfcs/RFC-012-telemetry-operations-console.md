# RFC-012 — Telemetry Operations Console

**Status: Approved — architecture frozen.** Approved by the Governor on
2026-08-02 (Revision 2, after the six required amendments A1–A6 were applied
and verified). **Architecture-freeze date: 2026-08-02. Implementation:
HOLD** until this architecture is merged and the G6 Release Closeout
condition is met.

**The contracts in this document are frozen. Implementation must not change
a frozen contract without a new Governor ruling.** Where implementation
discovers that a frozen contract cannot be built as specified, it stops and
returns to the Governor rather than adapting the contract in code (the
RFC-010 and RFC-011 freeze discipline, applied unchanged).

Architecture Burn output amended by a Governor Remediation Burn: this
document is documentation exclusively — no production source, tests,
templates, CSS or runtime configuration are changed by it (RFC-100 §3.1
rule 3).

```text
Mission Declaration (RFC-100 Amendment 1, Check 0)
Spacecraft:    Claude Code
Fuel:          Claude Opus
Effort Level:  MEDIUM
Mission Type:  Architecture Amendment Burn
Authority:     Governor
```

*Model statement (RFC-100 §12.0.2 — a burn states which model filled which
role, and does not justify it against the non-normative table): the original
RFC-012 Architecture Burn was authored under Claude Fable at HIGH effort;
this remediation burn was executed after the Flight Director set the session
model to `claude-opus-5`.*

Pre-flight dependency verified: **RFC-100 Amendment 1 — MERGED AND GREEN**
(PR #29 merged to `main` at `b12f315`; CI run `30758819646` passed on the
merge commit, 2026-08-02).

Date: 2026-08-02 (Revision 1 — original burn; Revision 2 — Governor
remediation, same date).

Author: EECOM (architecture Flight Controller role, Claude), commissioned by
the RFC-012 Architecture Burn brief and the RFC-012 Governor Remediation
brief.

Base: `main` at `b12f315` (RFC-100 Amendment 1 merged via PR #29; RFC-011
combined Phase 1–4 reference implementation merged via PR #27).

## Revision 2 — Governor Remediation

The Governor approved the architecture in substance and required six
amendments before freeze. All six are applied; none reopens the approved
boundary, operating loop or reference strategy.

| # | Governor amendment | Disposition | Where applied |
|---|---|---|---|
| A1 | Aggregation Neutrality | **Adopted** as a normative principle | §3.1 (new); §8 Q9; §9 R9; AC-11 |
| A2 | Remove operational dispositions from V1 | **Adopted** — `core.attention.disposed` withdrawn entirely; no defer, dismiss, acknowledgement or local suppression exists in V1 | §4.2 rule 3; §4.6; §5; §6.1; §7.6; §8 Q6–Q7; §9 R3; §11; §12; §13 (G4); AC-5 |
| A3 | Correct "nominal" semantics | **Adopted** — two distinct terminal states; a material unknown can never be described as nominal | §4.4 (new); §6.1; §7.1; §10; AC-9 |
| A4 | Attention vocabulary ownership | **Adopted** — attention kinds belong to the versioned RFC-012 Operations Console Model, not Core | §4.2; §4.3 (new); §5; §12; AC-6 |
| A5 | Define severity and ordering | **Adopted** — deterministic V1 ordering policy over authoritative platform facts only | §3.2; §4.2 rule 6; §4.5 (new); §9 R10; §12; AC-7 |
| A6 | Preserve successor boundary challenge | **Adopted** — RFC-013 and RFC-014 marked provisional working boundaries | §2.7; §2.8; §13 (G1) |

**The single largest change is A2.** Revision 1 proposed one new Core event
kind so that operator acknowledgements would survive replay. The Governor
rejected it for V1, and the rejection is architecturally cleaner than the
proposal: with no disposition mechanism at all, RFC-012 adds **nothing** to
any domain or Core contract. The console becomes a pure fold with no write
path of its own — which is what "strict consumer of RFC-011" should have
meant in the first place. The cost is accepted honestly in §9 R3.

---

## 1. Executive Assessment

The original brief proposed **RFC-012 — Household Telemetry Operations** and
asked, as a primary objective, whether that boundary was correct. It was not,
in three specific ways, and the Governor has approved the correction.

**The briefed scope was three products wearing one name.** The seven
candidate surfaces divide cleanly by operating rhythm:

| Rhythm | Surfaces | User mode |
|---|---|---|
| **Weekly operation** (minutes, exception-driven) | Attention queue, Manual Capture, Proposal Review, reconciliation findings | "What needs my attention today?" |
| **Occasional curation** (asset onboarding, stream and ownership changes) | Asset Registry | "Describe what exists" |
| **Rare investigation** (audit, dispute, provenance) | Asset Detail, Timeline | "Why does Foundry believe this?" |

One RFC covering all three would repeat the pre-RFC-010 defect this platform
has already paid to fix twice: surfaces accreting one locally-sensible
decision at a time, with no single contract any of them answers to. RFC-010
succeeded precisely because it refused that shape — one frozen console
contract, one deterministic model, one renderer.

**The approved boundary:** RFC-012 is the **Telemetry Operations Console** —
the exception-driven weekly operating surface only — consuming RFC-011
exactly as merged, adding no entities, no events, no channels and no new
write paths. Registry curation and provenance investigation become successor
RFCs; corrections remain the separately-governed debt RFC-007 named and
RFC-011 explicitly refused to absorb.

**What already exists matters more than the brief assumed.** RFC-011's merged
reference implementation already includes a minimal authenticated
`/acquisition/inbox` — evidence hash, four timestamps, identity state, grade,
CSRF-protected confirmation. RFC-012 is therefore not greenfield UX: it is
the governed replacement of a *reference* surface with an *operating*
surface, the exact relationship RFC-010's console bore to the pre-RFC-004
flight deck. The brief's "Proposal Inbox" question dissolves once this is
seen: the proposal *lifecycle* is RFC-011's frozen contract and stays there;
the *surface that renders it* was always future-RFC territory (RFC-011 names
"Acquisition Console / Inbox UX" as a dependent future RFC) and lands here.

**After A2, RFC-012's platform footprint is zero.** No new Core event, no new
Core vocabulary, no new Finance entity, no new domain event, no new
acquisition channel, no new write path. Every mutation the console can cause
travels through RFC-011's existing manual provider or its existing
confirmation gate. This is the strongest possible form of the "strict
consumer" relationship the Governor required, and it makes the freeze
decision correspondingly cheap to verify.

## 2. RFC Boundary Recommendation *(approved — recorded, not reopened)*

Answers to the original challenge questions, retained as the approved record:

**2.1 Is Household Telemetry Operations the correct boundary?** No — on name
and on scope. *Scope*: it bundled three operating rhythms (above). *Name*:
"Household" is not a product surface or an architectural concern — the
household dimension is already fully carried by the domain model (ownership
vocabulary, union-not-sum aggregation, Household-is-never-an-owner), all
frozen. Naming the RFC "Household" invites re-litigating settled ownership
semantics at the UX layer. The correct boundary is the **operating loop**;
the correct name is **Telemetry Operations Console**. Aggregation neutrality
(§3.1) is how the household dimension is honoured without owning it.

**2.2 Should Asset Registry and Telemetry Console be separate concerns?**
Yes. They differ in rhythm (weekly vs occasional), in mutation profile (the
console writes only through existing gates; registry curation appends
registration and stream metadata events), in failure cost (a confusing
console wastes minutes; a wrong registration corrupts routing for every
future observation), and in review needs (registry changes deserve the
deliberate ceremony the console must *not* have). Until the successor lands,
registration continues as it works today: programmatic, through RFC-011's
registration events — acceptable because registration is rare and the
operator is technical.

**2.3 Is Manual Capture a standalone capability?** No. Manual capture is a
*channel*, and channels are RFC-011's settled business (the manual provider
is merged and proven). What RFC-012 adds is the capture *action*: a form that
produces a manual envelope, reached from the attention queue ("this stream is
stale → capture now"). Capture is a verb inside the operations loop, not a
place, and certainly not an RFC.

**2.4 Should Proposal Inbox remain part of RFC-011?** Split verdict, and
cleanly: the proposal lifecycle, the Inbox *projection*, and the confirmation
gate are frozen RFC-011 contracts and do not move. The *presentation* moves
here. Per Governor ruling G2 the Phase-1 `/acquisition/inbox` **remains in
service until RFC-012 proves authenticated functional parity** — it is not
superseded on landing, only on proof.

**2.5 Are we attempting too many user problems in one burn?** Yes — seven
surfaces, three rhythms, plus an implicit fourth problem (delegated
maintenance / household roles) that is not a surface at all. The brief's own
principles argue for the cut: "operations are exception-driven" and
"progressive disclosure" describe *one* product — the console — not seven.

**2.6 Can the first implementation slice be significantly smaller?** Yes. The
proving slice is: **Attention Queue + Proposal Review + Manual Capture, over
the already-registered child accounts.** No registry UX, no Asset Detail, no
Timeline surface, no reconciliation workshop — findings appear *as attention
items*, which is all the weekly loop needs. This slice exercises the complete
operator workflow the brief requires with zero new platform machinery.

**2.7 Which user journeys belong in later RFCs?**

| Journey | Belongs to |
|---|---|
| Asset onboarding, stream/ownership/accessibility curation | RFC-013 *(provisional)* |
| Deep provenance investigation, per-asset timeline, audit browsing | RFC-013 *(provisional)* |
| Post-confirmation correction (the RFC-007 / RFC-011 TD1 debt) | RFC-014 *(provisional)* |
| Governed operational dispositions (defer / acknowledge), if real operating evidence ever demonstrates the need | Future RFC — see §12 |
| Delegated maintenance, roles, a second real operator | Future RFC, when a second operator actually exists |
| Every acquisition channel beyond manual (email, CSV, APIs, OCR) | RFC-011 Phases 6–8 and their own briefs, unchanged |

**2.8 Recommended decomposition — successors are provisional *(A6)*.**

```text
RFC-012  Telemetry Operations Console      (this document; weekly loop)
RFC-013  Asset Registry & Provenance       PROVISIONAL working boundary
RFC-014  Governed Corrections              PROVISIONAL working boundary
```

**RFC-013 and RFC-014 are registered as programme direction, not as approved
architecture.** Each must undergo its own architecture challenge before any
freeze, and RFC-012 pre-freezes neither. Specifically:

- **RFC-013 must independently challenge** whether registry curation, asset
  detail, provenance investigation and timeline browsing belong in one RFC
  at all. The grouping in this document is a convenience label for
  "everything the weekly loop deliberately excludes" — it is emphatically
  *not* a finding that those four share a boundary. The same rhythm test
  that split RFC-012 from them may well split them from each other.
- **RFC-014 must independently define** the governance, ceremony and audit
  semantics of correcting a confirmed value: who may correct, what review a
  correction requires, how restatement renders, and how the bitemporal
  contract ("as believed then" vs "as known now") surfaces to an operator.
  RFC-012 asserts only the boundary — that correction is out of its scope —
  and nothing about correction's design.

Ordering is deliberate: 012 first because the weekly loop is where the
product either earns its keep or dies of friction; 013 second because
curation is rare and has a programmatic workaround; 014 third but **before
any high-volume channel** (CSV, email), because correction volume scales with
acquisition volume and the debt's cost compounds exactly then.

## 3. Normative Principles

### 3.1 Aggregation Neutrality *(A1 — normative)*

> **The Telemetry Operations Console is ownership- and aggregation-neutral.**
> It surfaces operational work against canonical telemetry regardless of
> whether the affected subject is individually owned, jointly owned,
> beneficially owned, custodial, or included within a household aggregation.
>
> The same canonical assets and obligations may contribute to individual,
> household, accessibility and mission lenses **without changing the
> operational workflow and without duplicating value**.
>
> Household aggregation uses the frozen ownership and containment contracts
> and must prevent double counting. **Household is an aggregation scope, not
> an owner.**

**What this requires of the console — three obligations:**

1. **Workflow invariance.** An attention item's presentation, actions and
   ordering are identical whatever the ownership shape of its subject. There
   is no "joint asset" screen, no household-versus-individual mode, no
   ownership-conditional branching in console code. A stale price on a
   solely-owned JISA holding and a stale price on a jointly-owned property
   are the same kind of work.
2. **Attribution is displayed, never computed.** Where the console shows an
   attributable value it renders a lens result with that lens's declared
   scope, confidence and freshness. It performs no unioning, no share
   arithmetic, no netting and no household roll-up of its own.
3. **One subject, one item.** An asset that contributes to several scopes
   produces exactly **one** attention item, not one per scope. Duplicating
   operational work per lens would be the aggregation-layer equivalent of the
   double-count RFC-011 AC-16 forbids, and the queue's deduplication is by
   canonical subject, never by scope membership.

**The questions Foundry must be able to answer** — all of them through
existing domain lenses, none of them computed here:

- Chris's attributable net wealth;
- Fiona's attributable net wealth;
- combined household net wealth;
- household property equity;
- individual and household mission contribution.

**The joint-property case, which is the sharpest test:** the same canonical
house and the same canonical mortgage contribute **proportionately** to each
individual lens (by the declared ownership `share`) and **exactly once, at
full value,** to the household lens (union by entity id). One set of
canonical events, two honest attribution rules, no duplication, and — the
point of this principle — one attention item if that mortgage's balance
telemetry goes stale.

**RFC-012 neither calculates nor redefines any of these values.** It consumes
the existing ownership and aggregation model: Spec 001 §9's union-not-sum
rule and the Household-is-never-an-owner constraint, both frozen, both
already implemented in the Finance metrics layer (household union at full
value; per-person share attribution). Where a scope-specific lens a future
console view wants does not yet exist, it is supplied by the owning domain as
a domain change under that domain's governance — **never** by the renderer.
This is a named dependency, not an assumption: see §9 R9.

### 3.2 The console never computes

Restated as a principle because A5 depends on it: the console selects,
orders and renders folds the platform already defines. Any number the console
invented would be a number nothing can explain, and any severity it invented
would be a judgement with no provenance.

## 4. Product Architecture

### 4.1 One surface, one model, one renderer

The console follows RFC-010's proven shape, deliberately:

```text
Log (events)
  → RFC-011 projections (Asset Registry, Stream Registry, Proposal Inbox,
    valuation/accessibility/mission lenses, reconciliation findings,
    stream freshness)                                  [frozen, unchanged]
  → OPERATIONS CONSOLE MODEL   (new; deterministic fold, pure data,
                                no rendering concerns)
  → Renderer                   (presentation only; no computation)
```

The **Operations Console Model** is the RFC-012 contract to freeze: a
deterministic function from (projections, `as_of`) to a fully-resolved data
structure. Same log, same clock ⇒ byte-identical model. It computes nothing
RFC-011 does not already define — it *selects, classifies and orders*.

### 4.2 The Attention Queue is the product

The single home surface is the attention queue. Its item taxonomy is a
**closed vocabulary of the versioned Operations Console Model** — see §4.3
for its ownership status, which A4 makes explicit. Every kind is a
deterministic operational classification over an existing projection:

| Attention kind | Derived from (all existing, all RFC-011 or domain) |
|---|---|
| `proposal_pending` | Proposal Inbox projection: unresolved proposals |
| `identity_ambiguous` | Proposal resolution outcomes: `ambiguous` / `unresolved` |
| `telemetry_stale` | Per-stream freshness fold: `refresh_policy` vs latest `received_at` |
| `reconciliation_divergence` | Reconciliation finding: derived total vs supplied statement total |
| `valuation_expiring` | Refresh-policy breach on a stream carrying estimate-basis valuations (§4.5 limitation) |
| `unknown_material` | A lens reporting a `None` value with `Insufficient` confidence because a material input is unknown |

Rules, normative:

1. **The queue is a pure projection.** No attention item is stored; deleting
   every console artefact and replaying loses nothing (the RFC-010/011
   discipline).
2. **Every item carries its action.** An item is (fact, evidence link, one
   primary action): stale → Capture; pending → Review; divergence →
   Investigate; ambiguous → Resolve; unknown → Capture the missing fact. No
   item without an exit.
3. **An item persists until its underlying fact resolves.** *(A2.)* There is
   no defer, no dismiss, no acknowledgement, no snooze, no expiry and no
   browser-local suppression. The **only** thing that removes an item from
   the queue is the canonical or projected fact changing — through capture,
   confirmation, or a governed lens determination. An operator cannot make
   the queue quieter than the telemetry is.
4. **No channel, category, ownership or scope branching** (RFC-011 AC-8 and
   §3.1 applied to presentation): an item renders identically whether its
   stream is manual today or Open Banking in 2028, and whether its subject is
   solely or jointly owned. New channels change the console by zero lines.
5. **One canonical subject, one item** (§3.1 obligation 3): items deduplicate
   by subject and kind, never multiply by lens or scope.
6. **Ordering is deterministic and defined in §4.5** — never engagement
   heuristics, never invented financial severity.

### 4.3 Vocabulary ownership *(A4)*

**The attention kinds are not Core domain vocabulary and must not be
described as such.** They belong to the **versioned RFC-012 Operations
Console Model** — a presentation-layer classification, closed for V1,
extensible by a future revision of *this* RFC without touching any platform
contract.

The split, stated precisely:

| Concern | Owner |
|---|---|
| The *facts* — proposal state, resolution outcome, stream freshness, reconciliation difference, lens materiality | **RFC-011 and the relevant domain lenses** |
| The *operational classification* of those facts into attention kinds | **RFC-012 Operations Console Model** (versioned) |
| The *ordering* of classified items | **RFC-012 Operations Console Model** (§4.5, versioned) |
| The *rendering* | **RFC-012 renderer** |

Consequences that matter: no `core.*` namespace gains an attention term; no
Core vocabulary is added, extended or reserved by this RFC; a second console
(or a future domain's operating surface) is free to classify the same
underlying facts differently without contradicting a platform contract; and
changing the V1 taxonomy is an RFC-012 revision, not a Core amendment.

### 4.4 Terminal states — "complete" is not "nominal" *(A3)*

Revision 1 contained a genuine error: its walkthrough left a material unknown
outstanding while declaring the queue empty and the telemetry nominal. Those
are different claims and only one of them was true. The console must
distinguish them structurally, not merely in wording:

| State | Condition | Rendered as |
|---|---|---|
| **All actionable work completed** | No item the operator can act on remains, **but** one or more material unknowns are still unresolved | *"Four actions complete. One material value remains unavailable."* |
| **All telemetry nominal** | **Zero** attention items of **any** kind, material unknowns included | *"All telemetry nominal — N streams fresh as of T."* |

Normative rules:

1. **A materially unknown input is an active attention item.** It is not a
   footnote, not a badge on an otherwise-clean queue, and not suppressible.
2. **It remains active until one of exactly three things happens:** the
   missing fact is captured; an existing governed lens determines the input
   is no longer material; or an existing contract legitimately records that
   the value is not presently observable. All three are platform facts —
   none is an operator gesture, and the console can cause the first only
   through the existing capture path.
3. **"All telemetry nominal" is forbidden while any material unknown
   remains** — asserted as AC-9, not left to copywriting. The honest state is
   "actionable work complete, N unavailable".
4. **Neither terminal state shows an inventory.** An empty queue renders an
   affirmative fact, never a fallback list of all assets.

The distinction is the brief's Information Honesty principle applied to the
one screen the operator sees most: a system that says "nominal" while
something material is unknown has taught its operator to distrust the word on
the day it matters.

### 4.5 Severity and ordering *(A5 — deterministic and versioned)*

Revision 1 referred to a "severity class" without defining its source. The
ordering policy below is part of the versioned Operations Console Model and
is specified to the level tests can assert.

**The console must not derive severity from** asset category, provider,
account type, nominal or relative monetary value, mission name, UI
heuristics, or any engagement signal. Financial materiality is supplied by
the relevant lens or projection; the renderer never calculates it.

**V1 ordering — five ranked classes, then a stable tie-break.** Items sort
ascending by class, then by the class's declared within-class rule, then by
stable identifier:

| Class | Contains | Authoritative fact it reads | Within-class order |
|---|---|---|---|
| **1 — Blocked** | `identity_ambiguous` | Resolution outcome is `ambiguous` or `unresolved`; the confirmation gate **structurally refuses** such a proposal | Oldest proposal `received_at` first |
| **1 — Blocked** | `proposal_pending` | An unresolved proposal exists in the Inbox projection | Oldest proposal `received_at` first |
| **2 — Material unknown** | `unknown_material` | A lens returned a `None` value with `Insufficient` confidence — materiality already determined by the lens | Stable identifier |
| **3 — Reconciliation** | `reconciliation_divergence` | A reconciliation finding already produced by RFC-011 reports a non-zero difference between derived total and supplied total | Longest-standing divergence first, by the finding's `valid_at` |
| **4 — Freshness** | `telemetry_stale`, `valuation_expiring` | Refresh-policy breach: elapsed time since latest `received_at` exceeds the stream's declared cadence | **Breach duration descending** (longest overdue first) |
| **5 — Tie-break** | *(all)* | — | **Stable identifier ascending**, applied last and always |

Notes that keep this honest:

- **Class 1 groups identity blockage with pending confirmation** because both
  are the Governor's "confirmation or identity blockage" class. Within it,
  `identity_ambiguous` ranks ahead of `proposal_pending` on a verifiable
  platform fact rather than a judgement: the gate raises on an ambiguous
  identity, so that work is *blocked*, whereas a resolved pending proposal is
  merely *waiting*.
- **Breach duration is a fact, not a severity score.** It is
  `elapsed − declared_cadence` for streams with a datable cadence, computed
  from the stream's own `refresh_policy`. The console invents no thresholds.
- **`static` and `on_event` streams never generate freshness items,** by the
  frozen contract that they are never stale. This is the primary control on
  queue flooding (§9 R2).
- **V1 limitation, named rather than papered over:** because `on_event`
  streams cannot go stale by contract, an `on_event` estimate-basis valuation
  produces no automatic `valuation_expiring` item. V1 therefore raises that
  kind only for valuation streams with a datable cadence (e.g. `annual`,
  `quarterly`). Detecting a stale *undated* estimate requires a declared
  valuation horizon that no frozen contract currently carries; inventing one
  in the renderer is precisely what A5 forbids. Recorded as §9 R10 and as a
  candidate for RFC-013 or a domain amendment.
- **Ordering is total and reproducible:** with the stable-identifier
  tie-break applied last, the same model always yields the same sequence,
  which is what makes AC-7 testable.

### 4.6 The three in-scope actions

**Capture** (manual channel only): a structured form producing a manual
envelope through the **existing** provider — subject, observation kind,
value, `valid_at`, unit. It writes nothing canonical itself; it feeds the
existing pipeline, which for the manual channel commits per the stream's
frozen confirmation policy. Target friction: under one minute from queue item
to done, achieved by pre-binding the form to the item's stream.

**Review/Confirm**: the Phase-1 inbox's job, re-housed — verbatim evidence
beside proposal (already built under S3), all four timestamps, grade,
interpreter identity and version, resolution state, and the exact draft
events confirmation would append. Confirm and reject only. The gate's
contract is unchanged, including the model-interpreter hard floor and
`review_batch` semantics.

**Investigate (reconciliation)** *(A2-corrected)*: a divergence finding
presents derived fold versus asserted total with both provenance chains, and
offers exactly two paths — drill into the contributing evidence, or capture /
confirm new evidence that resolves the difference. **There is no
acknowledge-with-reason and no dismissal.** The console may *explain* a
divergence; only new telemetry can *resolve* it, and until it does the item
remains active. The console has no path that writes a value outside
capture-and-gate.

### 4.7 Navigation philosophy

- **Exception-first, inventory-never.** The home answers "what needs my
  attention today?"; there is no "browse all assets" surface in this RFC.
- **One home, actions as verbs.** Capture and Review are reached from items,
  not from a menu of places. Deep links exist; navigation trees do not.
- **Mission Console and Operations Console are peer surfaces** with disjoint
  jobs: missions answer "how is the household doing?"; operations answers
  "what does the operator do next?". Cross-linking is one-way and minimal in
  V1: an operations item may cite which missions its subject feeds (derived
  from existing metric wiring); the Mission Console is not touched.
- **Progressive disclosure is structural**: value → grade badge and freshness
  inline → provenance chain one interaction away → verbatim evidence one
  more. Nothing material is ever more than two steps from its evidence;
  nothing forensic is ever on the first screen.

## 5. Domain Model

**RFC-012 adds no entities, no domain events, no Core events, no Core
vocabulary, no Finance vocabulary, and changes no frozen contract.** After
amendment A2 this is now literally true with no exceptions, and it is the
document's strongest claim:

| Candidate addition | Disposition |
|---|---|
| `core.attention.disposed` (Revision 1) | **Withdrawn** — rejected by the Governor for V1 (G4). No replacement. See §12 |
| Attention-kind vocabulary | **Not a platform addition** — owned by the versioned Operations Console Model (§4.3, A4) |
| Ordering policy | **Not a platform addition** — owned by the versioned Operations Console Model (§4.5) |
| Anything else | None proposed |

The one new *contract* is the **Operations Console Model** itself (§4.1): a
deterministic fold, versioned like a calculation, frozen on approval, owning
the attention taxonomy and ordering policy and nothing else.

Everything the console renders is consumption: assets, streams, ownership,
containment, accessibility, lenses, grades, temporal contracts and
aggregation scopes are RFC-011 Revision 2 and Spec 001, byte-for-byte. Where
the console shows a value it shows the lens's output with the lens's
freshness and confidence cap; where a value is unknown it renders *unknown* —
never zero, never blank (already enforced at the lens layer since the B3
remediation, and now a rendering rule too).

## 6. User Workflows

### 6.1 The weekly loop *(A3-corrected)*

```text
Open console → Attention queue
  → for each actionable item: act (capture | confirm | resolve | investigate)
  → each action returns to the queue; the item clears only if the
    underlying fact resolved
  → terminal state, whichever is true:
       "All telemetry nominal"                    (zero items of any kind)
       "N actions complete; M material values remain unavailable"
                                                  (unknowns outstanding)
  → close
```

Budget: under ten minutes for a normal week. A week with two statements and
one stale price should be three items, not a dashboard tour.

Note what the loop deliberately cannot do: it cannot reach a quiet screen by
the operator's decision alone. Quiet is earned by telemetry, or it is
reported honestly as incomplete.

### 6.2 Capture workflow

Queue item ("Junior SIPP units: stale 12d") → capture form pre-bound to that
stream → enter value + `valid_at` → submit → envelope → committed per the
stream's frozen policy → item clears → provenance visible immediately.
Pre-binding from the queue is what makes capture lightweight *and* correctly
attributed: the operator never selects a subject from a global picker in the
weekly loop.

### 6.3 Review workflow

Item → evidence-beside-proposal view → confirm or reject (with reason).
Ambiguous identity renders the candidates; choosing one teaches the Identity
Index through the existing confirmed-resolution mechanism. The console adds
no identity machinery.

### 6.4 The correction boundary

A mistyped capture noticed **before** confirmation is reject-and-recapture —
in scope, already supported by the frozen lifecycle. A wrong **confirmed**
value is a governed correction: **out of scope**, deferred to the provisional
RFC-014, exactly as RFC-011 refused it (TD1). The console renders corrected
history whenever the discipline produces it, but authors no corrections in
V1.

### 6.5 Occasional-confirmer workflow (Fiona)

Opens the same console, sees the same queue, confirms items awaiting her
under her own authenticated identity — which the gate already records as the
confirming actor. Nothing else. No role system, no reduced "spouse view", no
second surface to maintain. Aggregation neutrality (§3.1) means she sees the
same workflow for jointly-owned subjects as for her own.

## 7. UX Philosophy

1. **The product is the absence of the product** — but only when absence is
   true. Success is the console saying "nothing needs you" *honestly*, and
   saying "some things are still unknown" just as readily (§4.4).
2. **Facts wear their provenance.** No figure renders without grade and
   freshness affordances; unknown renders as unknown; derived renders
   distinguishably from observed; a capped confidence renders beside the
   value, never in a tooltip (RFC-010's safety rule, applied here).
3. **Actions are ceremonies proportional to consequence.** Capture is one
   screen; confirmation shows verbatim evidence; correction demands a future
   RFC. The friction gradient *is* the governance model, made tangible.
4. **The console never computes** (§3.2).
5. **Delegation-ready, not delegation-featured**: every action attributes its
   actor; nothing assumes the actor is Chris; and that is the entire V1
   multi-user story.
6. **The operator cannot silence the instrument.** *(A2.)* There is no
   gesture in V1 that makes a true attention item go away. This is a
   deliberate constraint on the operator, accepted because the alternative —
   dismissal without a governed record — is the mechanism by which every
   monitoring product eventually starts lying.

## 8. Answers to the Required Questions

| # | Question | Recommendation |
|---|---|---|
| 1 | RFC boundary | RFC-012 = Telemetry Operations Console; RFC-013 and RFC-014 registered as **provisional** successors subject to their own architecture burns (§2, §2.8) |
| 2 | Product decomposition | One home (Attention Queue) + three actions (Capture, Review, Investigate); no other surfaces (§4) |
| 3 | Weekly workflow | Queue → act → honest terminal state; sub-ten-minute budget (§6.1) |
| 4 | Navigation philosophy | Exception-first, inventory-never, actions as verbs, peer to Mission Console (§4.7) |
| 5 | Asset modelling | Zero additions; consume RFC-011 Revision 2 as frozen (§5) |
| 6 | Editable vs append-only | Nothing is editable; every mutation travels an existing RFC-011 path; **no console-authored events of any kind in V1**; pre-confirmation fixes are reject-and-recapture (§5, §6.4) |
| 7 | Reconciliation | Findings surface as attention items with investigate / capture-new-evidence; **no acknowledgement, no dismissal**; the item persists until the difference resolves (§4.6) |
| 8 | Evidence presentation | Progressive disclosure, two-step maximum to evidence; grade and freshness inline always (§4.7, §7.2) |
| 9 | Household operating model | Aggregation Neutrality (§3.1): one workflow across all ownership shapes; household is an aggregation scope, never an owner, never an operator role |
| 10 | Delegated maintenance | Attribution now, roles later; a delegation RFC when a second real operator exists (§7.5) |
| 11 | Future acquisition channels | Console is channel-blind by acceptance criterion; new channels are new providers (RFC-011) and zero console change (§4.2 rule 4) |
| 12 | Integration with RFC-010 | None that touches it: peer surface, frozen console untouched, one-way informational links only (§4.7) |
| 13 | Relationship with RFC-011 | Strict consumer; reads projections, writes only via the existing provider and gate; Phase-1 inbox retained until parity is proven (G2) |
| 14 | Reference implementation | Children's accounts, retained — with a seeded exception set and an honest non-nominal ending (§10) |
| 15 | Governor visual gate | Mandatory, after the bounded reference implementation and before expansion (G5) |
| 16 | Correction workflows | Out of scope; provisional RFC-014; boundary at confirmation (§6.4) |
| 17 | Audit model | Inherited entire: everything is events; `why()` chains render on demand; **the console contributes no new audit surface and no new audit record**; Timeline as a surface is RFC-013's question to challenge |
| 18 | Never-think-twice information | Freshness, grade, unknown-vs-zero, observed-vs-derived, actionable-vs-nominal, what-needs-me-today, who-confirmed-what — all inline, all always, none configurable (§4.4, §7.2) |

## 9. Risks

| # | Risk | Consequence | Control |
|---|---|---|---|
| R1 | Console becomes a second truth (client state, cached queues, off-log suppression) | Two-truth drift, the platform's cardinal sin | Model is a pure fold; **no console-owned persistence of any kind in V1**; AC-3, AC-5 |
| R2 | Attention fatigue — mis-tuned staleness floods the queue | Operator stops trusting or opening the console | Thresholds derive only from each stream's declared `refresh_policy`, never invented by the console; `static`/`on_event` streams generate no freshness items by contract (§4.5) |
| R3 *(revised under A2)* | **No pressure valve** — with no defer or acknowledge, a long-lived unresolvable item (an estimate no one can refresh) sits in the queue indefinitely and trains the operator to ignore a non-empty queue | Slow erosion of the queue's signal value — the same end state dismissal would cause, reached by a different road | Accepted for V1 by Governor ruling G4. Bounded by three things: the reference slice is small; ordering (§4.5) sinks long-standing freshness items below actionable ones rather than surfacing them repeatedly; and the honest terminal state (§4.4) distinguishes "actionable work complete" from "nominal", so a persistent unknown does not read as a failure to act. **This risk is the explicit trigger for reconsidering governed dispositions in a future RFC (§12) — real operating evidence of it is the evidence the Governor asked for** |
| R4 | Scope re-accretion — registry curation "just a small form" creeps in | This RFC becomes the brief it corrected | Scope exclusions (§11) name it; provisional RFC-013 exists as the pressure valve |
| R5 | Collision with RFC-011's remaining phases over the inbox surface | Two RFCs building one surface | Governor ruling G2 records the split; the Phase-1 inbox is retained until parity is proven, so neither RFC is blocked on the other |
| R6 | Capture friction exceeds the weekly budget | Stale telemetry becomes chronic; the product fails at its point | Pre-bound capture from queue items; friction is a named acceptance criterion (AC-8 evidence, recorded in the implementation report) |
| R7 | Single-operator bus factor | Household knowledge concentrates in Chris | Accepted, documented, and already mitigated architecturally: everything is evidence-chained events a successor can replay; delegation RFC deferred until real |
| R8 | Peer-surface drift — the Operations Console evolves its own visual and interaction idiom | Two consoles, two languages, doubled maintenance | The renderer adopts RFC-010's presentation disciplines (information honesty, no decorative emptiness, DET fixtures) as binding, not inspirational |
| R9 *(new, A1)* | A scope-specific lens the console wants to display does not exist, and the pressure lands on the renderer to "just add it up" | Aggregation Neutrality breached; the console silently becomes a computation layer with no provenance | §3.1 obligation 2 is normative and AC-11 asserts it: a missing lens is a domain change under domain governance, or the view is not built. The console has no arithmetic path to fall back on |
| R10 *(new, A5)* | Undated estimate valuations (`on_event`) can never raise `valuation_expiring`, so a decade-old director estimate ages invisibly | A material staleness class the queue structurally cannot see | Named, not hidden (§4.5). The honest fix is a declared valuation horizon on the domain entity — a domain amendment for RFC-013 or a Spec 001 revision, never a renderer heuristic |

## 10. Reference Implementation *(amended)*

**Retain the children's accounts as the proving slice** — they are already
registered, already evidenced, already flowing through the merged pipeline,
and still carry zero adult-mission blast radius. The console slice runs on
top of live, proven canon rather than fresh fixtures. No new asset class and
no new acquisition channel is introduced.

**Use the smallest internally coherent fixture.** RFC-011's reference proved
the happy path; RFC-012's must prove the *exceptional* path, because
exceptions are the product. Four seeded exceptions:

- one stale stream;
- one pending proposal;
- one ambiguous identity;
- one materially unknown input.

**Reconciliation divergence is optional for the first visual proof** and is
included only if RFC-011 already produces the finding with no new platform
machinery. It does — the merged reconciliation fold compares a container's
derived total against a supplied statement total and reports the difference —
so a fifth seeded exception is *available* at no architectural cost, and its
inclusion is an implementation-burn judgement, not an architecture
requirement.

**The mandatory proof:**

```text
Open queue
→ review pending proposal (verbatim evidence beside it)
→ resolve ambiguous identity (teaching the Identity Index)
→ capture stale observation (pre-bound form)
→ observe canonical update
→ confirm child-policy valuation change
→ confirm adult missions remain unchanged
```

**The material unknown remains visible at the end unless it is resolved.**
The final state may say:

```text
Three actions complete.
One material value remains unavailable.
```

It may **not** say:

```text
All telemetry nominal.
```

That ending is the point of the amended reference, not a blemish on it: it
demonstrates the A3 distinction under the Governor's eye, on a real screen,
in the state the operator will actually meet most weeks. A walkthrough that
ended "nominal" would prove the console can render a clean screen while
proving nothing about whether it renders an honest one.

Mission Impact is proven at both extremes in the last two steps: the
child-policy lens shows the updated value, and the adult missions show £0
impact, unchanged — mission-relative valuation at its sharpest, which is why
the children remain the right subjects.

Per RFC-011 Phase 2's data rule: real child-account evidence lives only in
the vault; no raw data, identifiers or payloads enter the repository,
fixtures or logs. The seeded exception set uses the existing generic
child/custodian fixture idiom.

## 11. Scope Exclusions

Binding, restated per RFC-100 §3.1 rule 5. This RFC designs **no**: Open
Banking, Gmail/email ingestion, OCR, market/broker/pension APIs, PayPal RSU
support, precious-metal pricing, tax engines, bill management (the brief's
exclusions, all upheld); **and additionally no**: Asset Registry surface,
Asset Detail surface, Timeline surface, correction authoring, operational
dispositions of any kind (defer, dismiss, acknowledge, snooze), role or
permission system, Mission Console change, RFC-011 contract change, new
acquisition channel, new Finance entity or vocabulary, new Core event or
vocabulary, aggregation or attribution calculation, notification/push
machinery (the queue is a pull surface in V1), and no mobile-specific
surface. Where this document names an excluded thing, it defines only the
seam it must later fit.

## 12. Alternatives Considered

| Alternative | Why rejected |
|---|---|
| The briefed boundary — one RFC, seven surfaces | Three operating rhythms in one contract; the pre-RFC-010 accretion shape; violates the burn discipline RFC-100 codifies |
| **Governed operational dispositions (`core.attention.disposed`)** — Revision 1's proposal: acknowledge or defer an item with a mandatory reason, as a replayable Core event | **Rejected by the Governor for V1 (G4).** It added a Core event kind to a console RFC, and a suppression mechanism to a product whose entire value is refusing to suppress. V1 adopts the no-disposition fallback: items persist until the underlying fact resolves. **May be reconsidered in a future RFC once real operating evidence demonstrates the need** — the evidence being §9 R3 actually occurring, not anticipated |
| Browser-local dismissal (localStorage, session state) | Never considered viable: state the log cannot replay is the second truth R1 exists to prevent. Explicitly forbidden by AC-3 and AC-5 |
| Extend the Mission Console with an operations region | RFC-010 is frozen; and "how are we doing" and "what do I do next" are different user modes — coupling them makes both worse |
| Registry-first sequencing (curate, then operate) | Registration already works programmatically; curation is rare; the weekly loop is where value and product risk both live — prove it first |
| Keep the inbox surface inside RFC-011 and grow it | Surface accretion inside a platform RFC; the platform/surface split is the whole lesson of RFC-010 vs RFC-004 |
| Manual Capture as its own RFC | One form over an existing provider; an RFC would be ceremony with no contract to freeze |
| Include governed corrections here | Correction is governance-heavy and RFC-011 deliberately kept it a named debt; absorbing it silently is RFC-011's own R10 |
| Attention items as stored entities (an "inbox zero" task system) | Stored conclusions; a second truth the log cannot replay; the queue must be a fold |
| Attention kinds as Core vocabulary | Rejected under A4: they are operational classifications of a presentation layer, not platform semantics; Core gains nothing and would be constrained by a console's taxonomy |
| Severity from monetary value or asset category | Rejected under A5: invented financial judgement with no provenance; materiality belongs to lenses |
| Notification/push for exceptions | A pull surface honours "weekly operation should feel lightweight" and the roadmap's no-background-daemons philosophy; push can be a later additive channel |

## 13. Governor Rulings — recorded

The Governor Architecture Review returned **APPROVED WITH REQUIRED
AMENDMENTS**; architecture freeze and implementation both **HOLD**. The six
rulings are recorded exactly as decided:

| # | Ruling | Decision |
|---|---|---|
| G1 | Boundary | **APPROVED WITH CONDITIONS** |
| G2 | RFC-011 re-partition | **APPROVED WITH CONDITIONS** |
| G3 | RFC-011 Phase 5 gate | **MODIFIED — REMAINS SEPARATE** |
| G4 | `core.attention.disposed` | **REJECTED FOR RFC-012 V1** |
| G5 | Visual gate | **APPROVED** |
| G6 | Release Closeout | **MODIFIED** |

**G1 — Boundary. APPROVED WITH CONDITIONS.** RFC-012 is approved as the
Telemetry Operations Console. RFC-013 (Asset Registry & Provenance) and
RFC-014 (Governed Corrections) are registered as **provisional** successors,
each subject to its own architecture burn and its own boundary challenge
(§2.8). Aggregation Neutrality is added as a normative principle (§3.1).

**G2 — RFC-011 re-partition. APPROVED WITH CONDITIONS.** RFC-011 retains
ownership of provider contracts, the Evidence Vault, interpretation, identity
resolution, the proposal lifecycle, the Inbox projection, the confirmation
gate, and all acquisition channels and platform hardening. RFC-012 owns
operator-facing attention modelling, proposal-review presentation,
manual-capture interaction through the existing provider, and operating
navigation and workflow. **The Phase-1 `/acquisition/inbox` remains in
service until RFC-012 proves authenticated functional parity** (AC-10). **No
frozen RFC-011 contract is amended under the label of re-partitioning** —
this document amends none.

**G3 — RFC-011 Phase 5 gate. MODIFIED — REMAINS SEPARATE.** RFC-012 may
proceed because it adds no acquisition channel. The RFC-011 Phase 5 Governor
gate remains **independently open** and must be discharged before any future
RSU, CSV, email, OCR, Open Banking, broker, pension-provider or other
acquisition-channel burn. **RFC-012's visual gate (G5) does not satisfy the
RFC-011 platform gate**, and this document makes no such claim.

**G4 — `core.attention.disposed`. REJECTED FOR RFC-012 V1.** The
no-disposition fallback is adopted. V1 has no defer, no dismiss, no
acknowledgement event, no browser-local suppression and no console-owned
persistence; an attention item remains present until the underlying canonical
or projected fact is resolved. All contradictory design and acceptance
criteria are removed (§4.2 rule 3, §4.6, §5, §7.6, §9 R3, §12, AC-5).
Governed operational dispositions may be considered in a future RFC after
real operating evidence demonstrates the need.

**G5 — Visual gate. APPROVED.** A mandatory Governor visual and product gate
occurs **after the bounded reference implementation and before any
expansion**, using a live web-accessible preview wherever practical. The gate
assesses: queue hierarchy; action clarity; capture friction; evidence
proximity; freshness and grade visibility; observed-versus-derived
distinction; unknown-versus-zero honesty; actor attribution; Mission Console
separation; compatibility with individual and household lenses; and both
nominal and non-nominal terminal states (§4.4).

**G6 — Release Closeout. MODIFIED.** Before **architecture merge**: the
outstanding Release Closeout debt (RFC-005, RFC-010, RFC-011, RFC-100) must
be explicitly **scheduled**, with ownership and sequence recorded. Before
**RFC-012 implementation merge**: that debt must be **completed**. This
document does not assert that a documentation-only architecture merge is
automatically blocked — no governing RFC requires that, and FR-017 is
satisfied by recording the gap and its schedule.

## 14. Acceptance Criteria

Blocking for any implementation burn built on this architecture. Rewritten
under the remediation to align with the approved architecture; no criterion
requires disposition persistence or logged acknowledgement.

| # | Criterion |
|---|---|
| AC-1 | **No change to frozen contracts**: RFC-010 and RFC-011 contracts are untouched; all four shipped missions replay and render byte-identically with the console present |
| AC-2 | **Deterministic Operations Console Model**: same log + same clock ⇒ byte-identical model, asserted across replay, including classification and ordering |
| AC-3 | **No console-owned persistence**: deleting every console artefact and replaying loses no state; no client-side or server-side console store exists |
| AC-4 | **No new write path**: the only mutations are through RFC-011's existing manual provider (envelopes) and its existing confirmation gate; structurally asserted |
| AC-5 | **No dispositions in V1**: no defer, dismiss, acknowledgement, snooze, expiry or local suppression exists in any layer; an attention item clears only when its underlying canonical or projected fact resolves |
| AC-6 | **Attention kinds belong to the RFC-012 model**: no `core.*` attention vocabulary exists; the taxonomy and ordering policy are versioned properties of the Operations Console Model (asserted by test over Core sources, the RFC-011 B1 precedent) |
| AC-7 | **Deterministic ordering from authoritative facts only**: the §4.5 policy reproduces a total order; no ordering input derives from asset category, provider, account type, monetary value, mission name or any engagement signal |
| AC-8 | **Unknown never renders as zero, blank or nominal**: every rendered figure carries grade and freshness; observed and derived are visually distinct |
| AC-9 | **An unresolved material unknown prevents an "all nominal" state**: the model exposes the two terminal states of §4.4 distinctly, and "all telemetry nominal" is unreachable while any attention item of any kind remains |
| AC-10 | **Parity before retirement**: the existing `/acquisition/inbox` remains available until authenticated functional parity is demonstrated (evidence view, CSRF discipline, provenance redirect preserved or improved) |
| AC-11 | **Aggregation neutrality holds**: individual and household lenses remain compatible with no duplication; one canonical subject yields one attention item regardless of scope membership; no unioning, share arithmetic or netting exists in console code |
| AC-12 | **No implementation before freeze**: no console source, test, template, CSS or runtime configuration is written before this architecture is frozen and merged (FR-013) |
| AC-13 | **Deterministic fixtures**: DET-1…DET-6 apply to every console fixture; no wall-clock dependence anywhere in the model |

---

*References:*
[`RFC-011-asset-telemetry-acquisition-framework.md`](RFC-011-asset-telemetry-acquisition-framework.md) (Revision 2, frozen) ·
[`RFC-010-mission-console-ux-framework.md`](RFC-010-mission-console-ux-framework.md) (frozen) ·
[`RFC-100-flight-operations-manual.md`](RFC-100-flight-operations-manual.md) (incl. Amendment 1) ·
[`../specifications/001-finance-domain-model.md`](../specifications/001-finance-domain-model.md) (§8–§9, ownership and aggregation) ·
[`../rfc-011-phase-1-implementation-report.md`](../rfc-011-phase-1-implementation-report.md) ·
[`../rfc-011-phase-2-plan.md`](../rfc-011-phase-2-plan.md) ·
[`../rfc-011-technical-debt.md`](../rfc-011-technical-debt.md) (TD1) ·
[`index.md`](index.md)
