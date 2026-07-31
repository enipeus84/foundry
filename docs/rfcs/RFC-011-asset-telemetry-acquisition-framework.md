# RFC-011 — Asset & Telemetry Acquisition Framework

**Status: Approved — architecture frozen.** Approved by the Governor on
2026-07-31 (Revision 2). Architecture-only: no production code, tests,
templates, connectors or runtime configuration are changed by this RFC.
Implementation proceeds as separate engineering Burns per the sequence
below.

**The contracts in this document are frozen. Implementation must not change
a frozen contract without a new Governor ruling.** Where implementation
discovers that a frozen contract cannot be built as specified, it stops and
returns to the Governor rather than adapting the contract in code (the
RFC-010 freeze discipline, applied unchanged).

Date: 2026-07-31 (Revision 1); Revision 2 and Governor approval same date.

Author: EECOM (architecture Flight Controller role, Claude), commissioned by
the RFC-011 Asset & Telemetry Acquisition Framework brief and the Revision 2
architecture refinement brief.

Base: `main` at `3375ed0` (RFC-010 Mission Console Phase 1 merged via PR #25).

## Governor Approval — Architecture Freeze

**Decision: GO — ARCHITECTURE APPROVED. Architecture-freeze date:
2026-07-31.** Revision 2 is the frozen architecture.

The five Revision 2 rulings are approved as recorded in this document's
rulings section:

1. **Identity Resolution is a permanent platform layer** (D13).
2. **Container/Holding is represented through the Core `contains`
   relationship** on the Asset Registry, with the derive-upward and
   reconciliation rules (D14).
3. **Refresh policy belongs to telemetry streams**; asset-level freshness is
   a derived, per-lens fold (D15).
4. **Temporal semantics are first-class contracts** — `valid_at`,
   `observed_at`, `received_at`, `recorded_at`, and the bitemporal read rule
   (D16).
5. **The Accessibility lifecycle is a platform capability** — Core
   vocabulary and lifecycle; domain profiles and transition events (D17).

**The standing open questions OQ1–OQ7 are resolved as Governor-approved on
their recorded recommendations** — see Open Questions, below, for each
ruling. No open architecture questions remain; questions arising after this
point are not open questions against RFC-011 and require a new Governor
ruling.

## Revision 2

The Governor's first architecture review assessed RFC-011 as architecturally
strong and withheld implementation authority pending five architectural
strengthenings. The core invariant — **channels multiply; the seam does not**
— is approved and is untouched by this revision. All five amendments refine
the platform *around* the seam; none alters the pipeline's gates, the
append-only philosophy, the confirmation gate, the no-AI-writes-to-canon
rule, provider plugin architecture, domain neutrality, or fail-closed
behaviour.

| # | Governor amendment | Ruling in this revision | Where applied |
|---|---|---|---|
| GA1 | Identity Resolution layer | **Adopted as a permanent platform layer** — an identity *service* consulted at proposal formation, not a pipeline *stage* between Evidence and Interpreter; the deviation from the briefed position is justified in the section | Identity Resolution Layer |
| GA2 | Asset hierarchy (Container → Holding) | **Adopted in Core** — a domain-neutral containment axis on the Asset Registry, with composition and reconciliation rules; domain entities unchanged | Asset Model § Containment |
| GA3 | Refresh behaviour belongs to streams | **Adopted fully** — refresh policy and update strategy are per-stream only; asset-level freshness becomes a derived, per-lens fold. The Revision 1 duplication on `AssetRegistration` is removed | Asset Model § Refresh policy |
| GA4 | Temporal contracts | **Adopted** — four first-class timestamps (`observed_at`, `received_at`, `recorded_at`, `valid_at`) and a bitemporal read rule | Temporal Contracts |
| GA5 | Accessibility lifecycle | **Elevated to a Core platform capability** — contract, condition vocabulary and lifecycle states are Core; profiles, evaluation and vesting entities remain domain-owned | Valuation Model § Capital Accessibility |

Each amendment section carries the Governor-required analysis: problem
statement, alternatives considered, recommended architecture, rejected
alternatives, compatibility impact, security impact, and future
extensibility. A consolidated change summary is in
[`../rfc-011-pr-description.md`](../rfc-011-pr-description.md).

---

## Context

RFC-010 answered: *how does Foundry present information?* The Mission Console
is a platform capability with a frozen five-region contract, a deterministic
Mission Console Model, and a renderer that owns presentation only.

RFC-011 answers the question upstream of everything RFC-010 renders:
**how does Foundry know what is true?**

Today, every figure the console shows descends from events that entered the
log by hand or from fixture data. There is no architecture for how a real
household's telemetry — balances, holdings, valuations, statements, vesting
notices, bills — is *acquired*: captured, validated, attributed to an owner,
valued, and committed to the canonical event streams the frozen pipeline
consumes. Each future channel (an API, a CSV import, an email extractor, Open
Banking) would otherwise invent its own path into the log, and the platform
would accrete acquisition the way it once accreted presentation — one
locally-sensible decision at a time, with no architecture to conform to.

The frozen pipeline this RFC feeds, and must not modify:

```text
Evidence  →  Canonical Events  →  Domain Projection  →  Metrics
         →  Mission Assessment  →  Mission Console
```

The layer this RFC adds, above it:

```text
Telemetry Acquisition  →  Evidence  →  (frozen pipeline unchanged)
```

## Frozen architecture this RFC integrates with

Nothing below is redesigned; every contract in this document composes with
these as they stand:

- **The substrate** (`docs/architecture.md`): append-only hash-chained event
  log; Canon as pure projection; deterministic replay; model identity is
  provenance; model failure never corrupts the substrate. Zero substrate
  change is an acceptance criterion of this RFC (AC-1).
- **Spec 000 — Core Domain Model, Revision 2**: shared five-verb event
  grammar; Party/Employer/Mission; typed tags vs relationship links; the Core
  Evidence Index; the Decision lifecycle; the Metric Provider contract,
  Metric Registry, `MetricRequest`/`MetricResult` and the `metric_status`
  vocabulary (including `stale`).
- **Spec 001 — Finance Domain Model, Amendment 4**: the thirteen finance
  entities (Account, Asset, Obligation, Transaction, Valuation, Position,
  Recurring Series, Assumption Set, Scenario, Tax Jurisdiction Configuration,
  Exchange Rate, Tax Position, Capital Gain Event); the
  `ownership_relationship` vocabulary; household union-not-sum aggregation;
  the rule that the Household Party is never an ownership target; the
  Recurring Series precedent that expectations never pre-create canonical
  events; `finance.transaction.corrected` as the correction discipline.
- **RFC-006 … RFC-009**: the Mission Assessment Framework's closed
  vocabularies, applicability, and evidence modules.
- **RFC-010**: the Mission Console contract. Acquisition changes nothing
  about assessment or rendering; it changes what upstream evidence exists for
  them to be honest about.
- **RFC-007 Revision 2**: `valuation_basis` already exists as an optional
  explicit field on property valuations, and a governed correction workflow
  is already recorded as deferred debt. RFC-011 generalises the former and
  inherits (does not solve) the latter.

## Problem Statement

Six structural absences, each of which becomes a defect the first time a real
channel is built without this architecture:

1. **No acquisition seam.** `kernel.ingest()` captures verbatim text and
   `ingestors.py` wraps a handful of file formats, but nothing defines how a
   *recurring, attributable, validated* stream of telemetry reaches the log.
   Every channel would define its own envelope, its own dedup, its own trust
   assumptions.
2. **Conclusions would be stored instead of evidence.** Without an
   architecture that insists on holdings × prices, the path of least
   resistance is "portfolio = £250,000" typed into a valuation event —
   unfalsifiable, unexplainable, and un-derivable.
3. **No staging boundary.** Anything that reaches the log's canonical
   `finance.*` streams is truth. AI-extracted or imported data that lands
   there directly makes a model, or a malformed CSV, an author of canonical
   financial state — violating the constitution's spirit while obeying its
   letter.
4. **Valuation is entangled with observation.** Gold's weight is a fact
   acquired once; its worth changes with every spot price. An architecture
   that acquires "the gold is worth £4,100" must re-acquire on every price
   move and can never explain itself.
5. **One value per asset.** Market value, what a mission may count, what is
   accessible before a date, book cost and liquidation value are different
   questions. The current Valuation entity can store any of them but nothing
   defines how they coexist, which are observed and which must be derived.
6. **No freshness or trust model.** `metric_status: stale` exists, but
   nothing declares how often each asset is *expected* to update, so
   staleness cannot be computed honestly; and nothing grades how much an
   observation should be trusted based on how it arrived.

## Governing Principles

Encoded as architectural requirements, testable wherever possible:

1. **Evidence first.** Foundry never stores a conclusion it could derive.
   Acquisition captures observations (units, weights, prices, statements,
   timestamps); valuation, accessibility and mission relevance are
   derivations with cited inputs. Where only a conclusion is obtainable (a
   director's estimate of private equity), it is stored *as* an estimate,
   with method, basis and confidence — never disguised as an observation.
2. **Verbatim before interpretation.** Raw source material is captured
   append-only *before* any parser or model touches it. Interpretation can
   fail, be wrong, or improve later; the source must survive all three.
3. **Acquisition is separate from valuation.** Acquiring what is held is one
   pipeline; pricing what is held is another. They meet only in derived
   lenses (below), never in a single stored figure.
4. **Nothing unconfirmed becomes canonical.** Between interpretation and the
   canonical domain streams stands a confirmation gate whose strictness is a
   declared property of the channel, not a per-import mood. Deterministic,
   authenticated channels may auto-commit; model-extracted content never
   does.
5. **Assets are first-class; telemetry belongs to assets.** Every telemetry
   stream is bound to a registered subject. Orphan telemetry — data with no
   declared asset to belong to — is a rejected registration, not a warehouse.
6. **Ownership is explicit and singular in scope.** Every asset has declared
   ownership from the existing `ownership_relationship` vocabulary. Household
   benefit is *derived* by aggregation over members — never declared, because
   the Household Party is never an ownership target (Spec 001 §9, upheld).
7. **Honesty about time and trust.** Every stream declares its expected
   cadence; staleness is computed, surfaced through the existing
   `metric_status`/confidence contracts, and never papered over. Every
   observation carries an evidence grade; derived values are capped by their
   weakest material input. Confidence is categorical and propagates by
   dominance — never arithmetic (Spec 000 §11 discipline, extended).
8. **Domain neutrality of the machinery.** The acquisition layer is platform
   capability, like the Metric Registry and the Mission Console (RFC-010
   principle 0). No Core acquisition contract names a financial concept. A
   future Health domain acquires observations through the identical
   machinery.
9. **Append-only philosophy preserved.** Proposals, confirmations,
   rejections and corrections are all events. Nothing in this architecture
   edits or deletes; a wrong confirmed observation is repaired by the
   correction discipline, visibly.
10. **Mission neutrality.** Acquisition knows nothing about missions.
    Missions consume acquisition's outputs through the existing Metric
    Provider contract, unchanged.

## Conceptual Architecture — the Platform Model

```text
        Acquisition Channel                    (manual, API, CSV, email, …)
                 ↓
        Acquisition Provider                   (plugin; one per channel kind)
                 ↓
        Telemetry Envelope ─────────────┐
                 ↓                      │ verbatim payload,
        EVIDENCE (append-only capture)  │ content-addressed
                 ↓                      ┘
        Interpreter                            (versioned; deterministic
                 ↓                              parser OR model extractor)
                 ↓ ←── Identity Resolution     (read-only identity service;
                 ↓      (Revision 2)            resolves external refs
                 ↓                              against the Identity Index)
        Observation Proposal                   (staged; an event, not truth;
                 ↓                              carries resolution outcomes)
        Confirmation Gate                      (policy declared per stream)
                 ↓
        CANONICAL DOMAIN EVENTS                (finance.* — existing grammar)
                 ↓
        Domain Projection → Valuation Lenses → Metrics
                 ↓
        Mission Assessment → Mission Console   (frozen, unchanged)
```

Seven platform contracts, each defined in this document (contracts 6 and 7
added by Revision 2; contract 5's accessibility half elevated to Core by
Revision 2):

| # | Contract | Kind | Analogue |
|---|---|---|---|
| 1 | **Asset Registry** (with containment axis) | Core projection over registration events | Core Evidence Index |
| 2 | **Telemetry Stream** (owns refresh behaviour) | Core entity (`core.telemetry_stream.*`) | Mission entity |
| 3 | **Acquisition Provider + Registry** | Operational plugin wiring | Metric Registry |
| 4 | **Interpreter + Observation Proposal** | Versioned contract + Core entity | `calculation_version` + Claim |
| 5 | **Valuation Lens + Capital Accessibility Lifecycle** | Core contract, domain-implemented profiles | Metric Provider |
| 6 | **Identity Resolution Service + Identity Index** *(Rev 2)* | Read-only Core service over an event-sourced index | Metric Registry dispatch + Core Evidence Index |
| 7 | **Temporal Contract** *(Rev 2)* | Cross-cutting field contract on envelopes and observations | `MetricRequest.as_of` discipline |

The load-bearing property: **channels multiply; the seam does not.** Adding
Open Banking, a pension API, or OCR is a new Acquisition Provider and
possibly a new Interpreter — no change to the evidence contract, the proposal
lifecycle, the confirmation gate, domain specs, mission logic, or the
console. That is the same property the Metric Registry gave metrics and the
Mission Console Model gave presentation.

## Identity Resolution Layer *(Revision 2, Amendment GA1)*

### Problem statement

Every artefact arriving through any channel names things symbolically: a
ticker ("PYPL"), a fund name ("Vanguard FTSE Global All Cap"), an account
number, a sender address, a property address. Nothing in Revision 1 defined
how those symbols are mapped to the household's registered subjects. Without
a defined layer, four failure modes are inevitable, and each has already
destroyed data quality in every aggregator that skipped this layer:

1. **Per-interpreter matching.** Each interpreter invents its own fuzzy
   matching; "PYPL", "PayPal Inc", "PAYPAL HOLDINGS" resolve differently per
   channel, and fixes don't transfer.
2. **Duplicate entities.** An unrecognised symbol quietly becomes a new
   asset; the same broker account exists three times with three histories.
3. **Misattribution.** Telemetry lands on the wrong asset — worse than a
   gap, because it is confidently wrong and double-counts downstream.
4. **Semantic duplicates.** The same statement re-arrives with different
   bytes (a re-download, a reminder email) and content-hash dedup —
   correctly — does not catch it.

### Recommended architecture

**Identity Resolution becomes a permanent platform layer** with three parts,
all Core, all domain-neutral:

**1. External references are first-class.** Interpreters never emit a bare
string as an identity. Every draft observation names its subjects as typed
`ExternalRef`s:

```text
ExternalRef { namespace, value }     # ("ticker", "PYPL")
                                     # ("isin", "IE00BD3RYZ16")
                                     # ("uk_sort_account", "……")
                                     # ("email_sender", "statements@hl.co.uk")
                                     # ("stream_local", <provider's own id>)
```

The namespace *mechanism* is Core-owned; namespace *values* are contributed
additively by domains and channels (`ticker` and `isin` are Finance's
contributions, not Core vocabulary — the same ownership split as every other
extensible vocabulary, so Core never names a domain concept). An
interpreter's job ends at transcribing the refs the artefact actually
asserts — it never resolves them.

**2. The Identity Index** is an event-sourced Core projection folding alias
assertions:

```text
core.identity_alias.declared
    { id, namespace, value, subject_id, basis, asserted_by }
core.identity_alias.updated      # retirement / correction, with reason
```

`(namespace, value) → subject_id`, with full history. Alias knowledge is
evidence-first like everything else: an alias exists because a resolution
was *confirmed*, and every future occurrence of that symbol resolves
deterministically from then on. The index also serves reverse lookup — "which
symbols have ever meant this asset" — which is what makes "does this PDF
refer to an existing asset?" answerable.

**3. The Resolution Service** is a pure, read-only function consulted during
proposal formation. For each `ExternalRef` set it returns exactly one of:

| Outcome | Meaning | Effect on the proposal |
|---|---|---|
| `resolved` | Deterministic index hit (or exact registry match) | Proposal carries the subject id **and** the resolution basis |
| `ambiguous` | More than one candidate | Proposal blocked from auto-commit; candidates listed for the confirming human |
| `unresolved` | No match | Proposal offers **registration of a new subject** as an explicit, reviewable draft — never a silent entity creation |

The service **never mutates evidence, never appends any event, never creates
canonical state** — it reads the Identity Index and the Asset Registry, and
annotates proposals. Confirmation is what commits: confirming a proposal
whose resolution was fuzzy or human-chosen appends the domain events *and*
the corresponding `core.identity_alias.declared` event, so the same
resolution never needs judgement twice. The confirmation gate's hard floor
extends to identity: **a model-suggested or fuzzy match never auto-commits;
only a deterministic index/registry hit can**. Ambiguity fails closed.

Semantic duplicate detection lives here too: a proposal whose resolved
`(stream, subject, observation kind, valid_at, external document ref)`
matches an already-confirmed proposal is flagged `duplicate_of` with a
**rejection recommendation the reviewer confirms — never a silent discard**
(two genuinely identical same-day dividends are distinguishable by their
document refs; where they are not, the human rules). This catches
re-downloads that byte-level envelope dedup cannot.

### Position in the pipeline — justified deviation from the brief

The brief positions Identity Resolution **between Evidence and Interpreter**.
This revision positions it **between Interpreter and Proposal** (as a service
the proposal-formation step consults), because identity resolution consumes
*interpreted symbols*, which do not exist until the interpreter has run: one
cannot ask whether "PYPL" is PayPal Inc before anything has extracted
"PYPL" from the PDF's bytes. Placing the layer before interpretation would
force interpreters to do covert parsing before the parsing stage, or reduce
the layer to byte-level dedup the envelope already performs.

The Governor's *intent* — identity as a single platform service, never
per-interpreter, never mutating evidence, never writing canon — is fully
preserved; only the stage boundary moves to where the data it needs first
exists. The two capabilities the briefed position implies are both kept, in
their natural places: byte-identical dedup at capture (envelope
`payload_hash`, unchanged), semantic dedup at resolution (above).

### Alternatives considered and rejected

| Alternative | Why rejected |
|---|---|
| Resolution as a pipeline stage between Evidence and Interpreter (as briefed) | Needs interpreted symbols that don't yet exist at that stage; would smuggle parsing ahead of the parsing layer |
| Per-interpreter matching | N divergent implementations; fixes don't transfer; the exact defect the Metric Registry idiom exists to prevent |
| Resolution deferred entirely to the confirmation UI | Human re-judges the same symbol forever; auto-commit channels become impossible; resolutions are unauditable and unreusable |
| Automatic fuzzy/AI matcher writing aliases directly | A heuristic becomes an author of identity — identity corruption is the one error class that *multiplies* every future observation's error; violates the no-AI-authorship principle upstream of canon |
| Aliases as operational configuration (not events) | Identity knowledge is user state and must replay; config would be a second truth |

### Compatibility impact

Additive only. New entity kind `core.identity_alias.*` (ignored by Canon and
all existing projections, like every acquisition kind); one new field group
on proposals (resolution outcomes); no change to envelope, evidence,
confirmation gate, domain specs, or any frozen surface. Streams acquired
before any alias exists behave exactly as Revision 1: everything lands
`unresolved` and is resolved by humans, teaching the index as it goes.

### Security impact

- **Identity poisoning is the attack this layer exists to survive.** A
  hostile email asserting "ticker PYPL → attacker's asset" can *propose* an
  alias, never commit one: aliases enter only through confirmation, fuzzy
  matches never auto-commit, and ambiguity fails closed (R11).
- Misattribution — the silent-corruption failure mode — becomes structurally
  impossible for auto-commit channels: they commit only on deterministic
  index hits, which exist only because a human once confirmed them.
- The index is replayable audit history: "why does Foundry believe this
  symbol means this asset" is `why()` over alias events.

### Future extensibility

New channels bring new namespaces (`open_banking_account_id`,
`hmrc_reference`, an OCR'd IBAN) as vocabulary additions, not architecture.
A future Health or Career domain resolves its own symbols (a provider NHS
number namespace, an employer HR system id) through the identical service —
nothing in the layer names finance. Cross-household identity is out of scope
by construction: the index is household-scoped like every projection.

## Asset Model

### Assets are domain entities; the registry is platform metadata

Foundry already has the asset entities it needs — Spec 001's Account, Asset,
Obligation and Position — and Spec 000 §16 deliberately keeps financial
semantics out of Core. RFC-011 does not move them. What is missing is not an
entity but a *capability*: one place that knows, for every value-bearing
thing the household tracks, how its telemetry arrives, how often it should,
and what may be derived from it.

**The Asset Registry is a Core-owned projection** folding registration events
that bind an existing domain entity to its acquisition metadata:

```text
AssetRegistration (per registered subject)
    subject_id            # an existing domain entity id (finance.account, …)
    domain                # owning domain prefix ("finance")
    telemetry_streams     # ids of Telemetry Streams that measure it
    contained_in          # optional parent registration (Rev 2, below)
    accessibility_ref     # where its Capital Accessibility profile lives
    valuation_bases       # which stored bases exist / are expected
```

*(Revision 2: `update_strategy` and `refresh_policy` no longer appear here —
refresh behaviour belongs to Telemetry Streams, below. Revision 1 carried
them in both places; the duplication is removed in the stream's favour.)*

The registry holds **routing and expectation metadata only** — never value,
never ownership, never domain semantics. It is to assets what the Metric
Registry is to metrics: Core can ask "what streams feed this subject, and is
it fresh?" without importing Finance. Unlike the Metric Registry, it **is**
event-sourced — which assets a household registered is user state, not
operational wiring, so registrations are `core.telemetry_stream.*` and
registration-attribute events, replayable like everything else.

### Containment — Container → Holding *(Revision 2, Amendment GA2)*

**Problem statement.** Revision 1 treated every registered subject as a flat
peer, but real assets nest: a Hargreaves Lansdown ISA *contains* a Vanguard
fund holding and a cash balance; a broker account contains positions and
accrued interest. Flatness forces three bad outcomes: statements (which
arrive at container level) have no defined relationship to the holdings they
report on; container-level totals and holding-level values can both be
stored and silently double-count; and "value of the ISA" has no defined
derivation.

**Recommended architecture.** Containment becomes a **first-class,
domain-neutral axis of the Asset Registry** — a Core structural relationship,
not a new entity kind:

```text
core structural_relationship gains:  contains
    <container registration> .linked { relation: "contains",
                                       target: <holding subject_id> }
```

The registry is a forest: any registered subject may contain registered
subjects; depth is unbounded in the contract and expected to be shallow in
practice. Valuations attach to *any* node — Valuation is what attaches, not
a third hierarchy level. Composition rules, normative:

1. **Telemetry attaches where it is observed.** A statement's evidence binds
   to the container's stream; its proposals may concern the container, its
   holdings, or both — identity resolution maps line items to holdings.
2. **Derive upward, never store upward.** A container with registered
   holdings derives its value as the fold of its holdings' lenses. Storing a
   container-level valuation *alongside* holding-level evidence is the
   double-count hazard, so:
3. **Container-level totals become reconciliation evidence.** When holdings
   exist, a statement's "account total" line is not a value source — it is a
   check: fold-of-holdings versus asserted total, with divergence surfaced
   as an explicit reconciliation finding (Information Honesty applied to
   arithmetic). When no holdings are registered (an opaque pension fund),
   container-level valuations are the honest, legitimate value source —
   both modes are valid; mixing them for the same container is not.
4. **Ownership and accessibility declare at the container by default** and
   may be overridden per holding where reality differs (the whole ISA is
   Chris's; every holding inherits that unless declared otherwise).
5. **No double-count, structurally:** any lens folding a scope counts each
   registered subject exactly once — a holding's value or its container's
   asserted value, never both (AC-16).

**Alternatives rejected.**

| Alternative | Why rejected |
|---|---|
| Keep the registry flat; leave nesting to Finance's Account/Position | The composition and reconciliation *rules* would live nowhere; every domain re-invents them; statements have no defined target |
| A new Core "Container" entity kind | Spec 000 §16 keeps entity semantics in domains; a relation over existing registrations achieves the shape without a new entity or any Finance change |
| Fixed two-level taxonomy (Container/Holding as types) | RFC-008 G3's anti-archetype ruling applies: it's a relation, not a taxonomy; gold in a safe is a holding with no container, a fund-of-funds nests three deep |

**Compatibility impact.** Additive: one new core `structural_relationship`
value (`contains`); Spec 001's Account→Position relationship maps onto it
directly with no entity change; flat Revision 1 registrations remain valid
(containment optional). **Security impact.** Reconciliation findings turn a
tampered or fat-fingered statement total into a surfaced divergence instead
of a silent overwrite; containment carries no new write path. **Future
extensibility.** Employer plan → grants; property → secured mortgage
linkage view; any future domain's nesting (a training programme containing
sessions) — all the same relation.

### Asset categories without branching

Cash, savings, brokerage, public equities, restricted equities, RSUs, ESPP,
pensions, Junior SIPPs, JISAs, property, mortgages, precious metals, foreign
currency, debt, director equity — all are already expressible as Spec 001
entities plus vocabulary values (`account_type`, `asset_category`,
`liability_category`, `tax_wrapper`). RFC-011 adds **no category taxonomy of
its own** and no per-category code path. What differs between a pension and a
krugerrand is *data*: their streams, refresh policies, accessibility profiles
and valuation bases. The architecture forbids category branching the same way
RFC-010 forbids mission-name branching (AC-8).

Two genuinely new Finance entities are required (proposed as **Spec 001
Amendment 5**, additive):

| Entity | Represents | Why existing entities don't suffice |
|---|---|---|
| **Grant** | An award of restricted equity: issuer, instrument, total units, grant date, plan reference, and a declared vesting schedule of tranches | A Position holds what is owned *now*; a Grant holds a structured expectation with per-tranche conditions. Recurring Series is cadence-shaped, not tranche-shaped |
| **Vesting Event** | The observed fact that a tranche vested: date, units, price at vest, withholding | It is an observation, not a schedule entry — the evidence-first split below |

### Refresh behaviour belongs to streams *(Revision 2, Amendment GA3)*

**Problem statement.** Revision 1 declared refresh policy per stream but
*also* carried `refresh_policy`/`update_strategy` on `AssetRegistration` — a
latent contradiction. The Governor's gold example exposes it as more than
tidiness: one asset, three streams, three unrelatable behaviours —

| Stream (gold) | update_strategy | refresh_policy |
|---|---|---|
| Weight held | `manual` | `on_event` |
| Market price | `api` | `continuous` (or `daily`) |
| Purchase cost | `manual` | `static` |

No single asset-level cadence is honest about all three; any asset-level
value is a fabricated average of unlike things.

**Recommended architecture — adopted fully.** `refresh_policy` and
`update_strategy` are properties of the **Telemetry Stream only**, from
closed, Core-owned vocabularies:

```text
refresh_policy  ∈ { continuous, daily, weekly, monthly, quarterly,
                    annual, on_event, static }
update_strategy ∈ { manual, api, csv_import, statement, email,
                    open_banking*, ocr* }          (* reserved, future)
```

- `on_event` — updates only when something happens (a vesting notice, a
  property revaluation). Staleness is not computable from cadence; the
  stream is honest about that.
- `static` — declared unchanging (a purchase cost, a fixed-term bond's
  terms). A static stream is *never* stale; declaring it static is the
  honest alternative to inventing a cadence.

**Asset-level freshness is derived, per lens, never declared.** Each
Valuation Lens declares which streams are *material* to it; a lens result's
freshness is the **worst material stream's** freshness. Gold's market-value
lens is stale when the price stream breaches `daily` — even with the weight
captured yesterday; a book-value lens over the `static` cost stream is never
stale at all. Staleness then flows through the existing
`MetricResult.status: stale` and the confidence caps (Confidence Model),
unchanged. `last_captured_at` per stream is computed by the acquisition
projection; nothing stores freshness.

**Alternatives rejected:** keeping an asset-level policy as a "summary"
(dishonest average; contradicts per-stream reality); deriving asset
freshness as the *best* stream (optimistic — a fresh price does not
un-stale a decade-old weight); making freshness a stored registry field
(derived state stored = conclusion stored).

**Compatibility impact:** removes two fields from a Revision 1 sketch never
implemented; no shipped surface reads them. **Security impact:** none new;
per-stream cadence bounds unsolicited polling per channel. **Future
extensibility:** new channels add `update_strategy` values additively; a
future SLA-style policy (e.g. `business_daily`) is a vocabulary value, not a
structure change.

## Ownership Model

### What already exists, upheld

Spec 001 §8's `ownership_relationship` vocabulary — `owner`, `co_owner`,
`beneficial_owner`, `custodian`, `beneficiary`, `owes`, `guarantees`,
`secures`, `collateralises`, with optional `share` — already expresses legal
and beneficial ownership, and it stays exactly where Spec 000 §16 put it: in
Finance. RFC-011 adds no ownership vocabulary and relocates none.

### The three ownerships, resolved without new machinery

The brief asks for legal, beneficial (economic), and *mission* ownership.
The first two are stored relationships; the third is not ownership at all:

| Question | Mechanism | Stored? |
|---|---|---|
| Who holds legal title? | `owner` / `co_owner` / `custodian` links | Yes — events |
| Who economically benefits? | `beneficial_owner` / `beneficiary` links | Yes — events |
| Which mission does it serve? | **Mission relevance is derived** by each mission's valuation lens over accessibility and policy — plus, where a human wants to assert intent, the existing Core `concerns` link (asset → Mission) | Derived; intent optionally an event |

**The Household is never an owner — including economically.** The Governor's
director-equity example ("Legal owner: Fiona; Economic benefit: Household")
is expressed *without* a Household ownership link, which Spec 001 §9 forbids
and this RFC upholds: Fiona holds `owner` (and, if title and benefit ever
split, another person holds `beneficial_owner`); household benefit is what
the union-not-sum aggregation already derives from Fiona's `member_of` the
Household. Mission relevance ("Financial Independence") is the FI mission's
lens counting it — at whatever confidence-weighted, accessibility-gated value
that lens computes. Nothing new is stored; three different questions get
three different answers from mechanisms that already exist.

Trusts and companies (future owners) become `party_type` extensions —
additive vocabulary values on a Core-owned vocabulary, a future amendment
requiring no structural change: an ownership link's subject is any Party, and
the aggregation rule already unions over declared relationships.

### The children as the ownership model's proof

Hamish's and Harriet's accounts (JISA, Junior SIPP) are the sharpest test the
ownership model has: the child is `beneficial_owner`/`beneficiary`, a parent
is `custodian`, contributions may arrive from either parent, the assets are
absolutely inaccessible until statutory ages, and — decisively — **they count
£0 toward every parental mission** while remaining fully real, fully valued
assets of the household's members. An architecture that renders the
children's accounts honestly has proven ownership separation, accessibility
gating, and mission-value derivation in one bounded context. This is why
they are recommended as the reference implementation (below).

## Acquisition Model

### Channel taxonomy

One contract, many providers. Evaluated shape per channel:

| Channel | Provider behaviour | Interpreter | Default confirmation | Evidence grade |
|---|---|---|---|---|
| **Manual** | User enters structured values in a form | Identity (already structured) | Auto-commit (user *is* the confirmation) | `declared` |
| **Connected API** | Authenticated pull from custodian | Deterministic, versioned parser | Auto-commit permitted per stream | `authoritative` |
| **CSV / file import** | User supplies an export file | Deterministic, versioned parser | Review batch summary; per-row auto within a confirmed mapping | `authoritative` or `declared` per source |
| **Email** | Watched mailbox, allowlisted senders | Deterministic where format known; model extraction otherwise | **Always review** when model-extracted | `extracted` → `confirmed` |
| **PDF statement** | User supplies document | As email | As email | As email |
| **OCR** (future) | Image → text | Model-assisted | Always review | `extracted` → `confirmed` |
| **Open Banking / pension APIs / HMRC** (future) | Standardised authenticated pull | Deterministic | Auto-commit permitted | `authoritative` |

Future channels are *rows in this table*, not architecture changes. Their
implementations are explicitly out of scope (Scope Exclusions).

### The Acquisition Provider contract

Mirrors the Metric Provider contract deliberately, so the platform has one
plugin idiom, not two:

- **Declares** which `update_strategy` kind it implements and which stream
  ids it serves.
- **Registers** with an Acquisition Provider Registry — operational wiring,
  rebuilt at startup, no persistence, fail-closed: an unregistered stream
  acquires nothing; duplicate registration for a stream is rejected.
- **Produces only Telemetry Envelopes** (below). A provider has **no write
  path to canonical domain streams** — it cannot append `finance.*` events,
  structurally.
- **Never interprets.** Parsing and extraction belong to Interpreters, so a
  provider's transport concerns (auth, fetch, watch) never entangle with
  meaning.
- **Holds no secrets in the substrate.** Credentials, tokens and mailbox
  configuration live in operational configuration (the `ModelAdapter`
  precedent), never in any event.

### The Telemetry Envelope and the Evidence Vault

Every acquisition, from every channel, captures **one envelope per source
artefact** before interpretation:

```text
TelemetryEnvelope (payload of the evidence event)
    stream_id             # which Telemetry Stream produced it
    channel               # update_strategy kind
    source_identity       # "hl_api", "mailbox:statements", "user:chris"
    received_at           # when Foundry first possessed it (Temporal Contracts)
    payload_hash          # content address of the verbatim payload
    payload_ref           # where the verbatim payload resides (vault)
    payload_media_type    # text/csv, application/pdf, message/rfc822, …
    external_ref          # provider's own id for the artefact, if any
    evidence_grade        # closed vocabulary (Confidence Model)
```

**Decision required — the Evidence Vault.** Verbatim payloads (PDFs, emails,
CSVs) are bulky and sensitive, and the JSONL log is neither a blob store nor
redactable. Recommended architecture: the event log stores the envelope with
`payload_hash` (entering the hash chain, so the log *commits* to the exact
bytes); the bytes themselves live in a local, content-addressed **Evidence
Vault**, encrypted at rest. Properties:

- **Truth is undiminished** — the log remains the only truth about *what was
  acquired and when*; the vault holds bytes the log has already committed to.
  A vault blob that fails its hash is detected corruption, exactly like a
  broken chain link.
- **Honest redaction becomes possible** — a payload can be expunged (legal or
  privacy need) by removing the blob and appending a redaction event; the
  hash remains in the chain, so the *fact that evidence existed* is
  permanent, its content demonstrably absent rather than silently missing.
  This is the only redaction path this architecture permits, and it never
  touches the log itself.
- **Small structured payloads may inline** — a manual entry's values are the
  envelope's payload directly; the vault is for artefacts, not a mandatory
  hop.

The existing `ingest` event and `ingestors.py` become the degenerate manual/
file case of this contract: an envelope with inline text payload. Legacy
`ingest` events remain valid and unmigrated; new acquisition writes
envelopes. (Decision 3.)

### The Interpreter contract

An Interpreter turns one evidence artefact into **zero or more Proposed
Observations**. It is the only component that understands a payload's format.

- **Versioned like a calculation**: every proposal records
  `interpreter_id` + `interpreter_version` (the `calculation_version`
  discipline applied to parsing). Re-running a newer interpreter over old
  evidence yields *new* proposals superseding old ones — possible only
  because evidence is verbatim (Principle 2).
- **Two classes, one contract:** *deterministic* interpreters (CSV mappings,
  known statement formats, API JSON) and *model* interpreters (AI extraction
  from unstructured email/PDF). The class is declared, recorded on every
  proposal, and drives the confirmation gate and evidence grade. A model
  interpreter is a witness, not an author — constitutional invariant 4
  applied upstream of the Canon.
- **Model interpreters are sandboxed by construction:** schema-validated
  output only; no tool access; no ability to append any event; unparseable
  output yields zero proposals (invariant 5, upstream). Their input is
  hostile by default (Security).
- **Interpreters never price, never value, never convert currency.** They
  transcribe what the artefact asserts. A statement saying "holding: 400
  units of VWRL" proposes a holding observation — not a market value.

### The Observation Proposal lifecycle

A proposal is a first-class Core entity — **in the log, because a proposal is
a fact about what an interpreter asserted**, and model identity is
provenance:

```text
core.observation_proposal.declared
    { id, evidence_id, interpreter_id, interpreter_version,
      interpreter_class, stream_id, subject_id,
      draft_events: [ {kind, payload}, … ],   # the canonical events that
                                              # confirmation would append;
                                              # observations carry valid_at
                                              # (and observed_at where the
                                              # artefact distinguishes it)
      resolutions: [ {external_ref, outcome,  # Rev 2: identity resolution
                      subject_id?, basis,     # outcomes per ExternalRef
                      candidates?} … ],
      extraction_confidence, notes }

core.observation_proposal.updated
    { entity_id, resolution: confirmed | rejected | superseded,
      reason, resolved_by }
```

- **Draft events are inert.** The Canon and every domain projection ignore
  `core.observation_proposal.*` wholesale (the same way Canon already
  ignores `ingest`). A proposal carrying a draft `finance.valuation.declared`
  changes nothing until confirmation appends the *real* event.
- **Confirmation appends the canonical events**, each carrying `provenance`
  chaining `evidence_id → proposal_id → confirming actor`. Every canonical
  figure is thereafter explainable to the byte it came from: `why()` walks
  value → valuation lens inputs → canonical event → proposal → interpreter +
  version → evidence hash → source identity.
- **Rejection is permanent, visible history** — an interpreter that keeps
  proposing garbage is diagnosable from the log itself.
- **The Acquisition Inbox is a projection** folding unresolved proposals —
  the staging area the confirmation UX (a *future* RFC) will render. It is
  deletable and rebuildable like every projection. It is not a second truth:
  it is a view of resolution state already in the log.
- **Idempotency at the boundary:** a provider capturing an artefact whose
  `(stream_id, external_ref, payload_hash)` already exists appends nothing.
  Re-imports and overlapping statements deduplicate on content, before
  interpretation — the append-only log's necessary guard against
  channel-driven duplication.

### The Confirmation Gate

A closed vocabulary, declared **per stream** at registration, enforced by the
gate — not chosen per import:

```text
confirmation_policy ∈ { auto_commit, review_batch, review_each }
```

Hard floor, non-configurable: **a proposal from a model-class interpreter
never auto-commits**, regardless of stream policy. Auto-commit is available
only to deterministic interpreters over `authoritative` or `declared`
channels. This is the acquisition layer's equivalent of "AI may explain but
cannot determine" — AI may *propose*, but only deterministic code or a human
commits.

Wrong data that was legitimately confirmed is repaired by the existing
correction discipline (`.updated` with mandatory reason — the
`finance.transaction.corrected` pattern), not by deletion. The governed
correction *workflow* remains the deferred debt RFC-007 recorded; RFC-011
does not silently absorb it (Technical Debt).

### Email — the Governor's pipeline, corrected by one step

The brief asks whether **Email → AI Extraction → User Confirmation →
Evidence** is the correct architecture. It is correct about the gates and
wrong about the order: **evidence capture must precede extraction.**

```text
Email → EVIDENCE (verbatim envelope, vault)
      → AI Extraction (model interpreter, versioned)
      → Observation Proposal
      → User Confirmation
      → Canonical Events
```

Three reasons the inversion matters, each already a principle:

1. If extraction fails or is wrong, the source survives and can be
   re-interpreted — including by a better model years later (Principle 2).
2. The confirmation UI can show the human the *verbatim source* beside the
   proposal, which is the only confirmation worth the name.
3. An extraction no one confirmed still leaves an honest trace of what
   arrived — nothing silently discarded.

Bills, statements, investment confirmations, dividend notifications, mortgage
statements and utilities all fit this identical pipeline; a known-format
sender graduates from model interpretation to a deterministic interpreter
without any other change. Mailbox mechanics, sender verification
implementation, and the extraction models themselves are out of scope here
(Scope Exclusions) — this RFC fixes the pipeline they must flow through.

## Temporal Contracts *(Revision 2, Amendment GA4)*

**Problem statement.** Revision 1 carried one acquisition timestamp
(`retrieved_at`) and inherited the log's own event time, leaving the hard
temporal questions implicit: a statement produced on 1 July, reporting a
balance as at 30 June, arriving by email on 3 July, confirmed and appended
on 5 July, is *four different facts about time* — and a June net-worth
metric, a staleness check, an audit query and a replay each need a different
one. Implicit time is how systems drift into answering "what was true?"
with "when did we hear about it?".

**Recommended architecture.** Four timestamps become first-class
architectural concepts, each with one owner and one question it answers:

| Timestamp | Question answered | Owner / where it lives |
|---|---|---|
| **`valid_at`** | *When was this state true in the world?* (balance date, vest date, price date) | Required on every observation an interpreter transcribes; flows into canonical events |
| **`observed_at`** | *When did the source assert it observed/produced this?* (statement production date) | On observations where the artefact distinguishes it; defaults to `valid_at` when it does not |
| **`received_at`** | *When did Foundry first possess the artefact?* (email arrival, API pull, upload) | Telemetry Envelope — set by the Acquisition Provider, replacing Revision 1's `retrieved_at` (one name for push and pull alike) |
| **`recorded_at`** | *When did this enter the log?* | The log event's own timestamp — never set by a provider or interpreter, always by the substrate |

Why each must exist — the consumer that breaks without it:

- **Metrics need `valid_at`.** `MetricRequest.as_of` means "state of the
  world at T": the correct fold selects observations with `valid_at ≤ T`,
  not events that happened to be recorded by T. Without `valid_at`, a
  late-arriving June statement can never correct June.
- **Staleness needs `received_at`.** A stream's freshness against its
  `refresh_policy` is about acquisition cadence — a statement *about* June
  received in December is fresh telemetry about a stale period; conflating
  the two corrupts both signals.
- **Audit and dispute need `observed_at`.** "The custodian said X on date
  D" is the provenance fact a discrepancy investigation turns on; it is the
  source's claim, preserved verbatim like everything else the source
  asserts.
- **Replay and belief-history need `recorded_at`.** It is the substrate's
  own ordering and the only one of the four Foundry itself witnesses.

**The bitemporal read rule** (the contract consumers must honour): *"what
did Foundry believe on date D about the state of the world at time T?"* is
answered by folding events with `recorded_at ≤ D`, selecting observations
with `valid_at ≤ T`. Ordinary metrics are the special case D = now. This
makes honest restatement architectural: when a backfilled statement changes
June's derived net worth, "as believed then" and "as known now" are both
computable, distinguishable, and never conflated — Information Honesty
applied to time. No projection stores either view; both are folds.

**Alternatives rejected:** one timestamp (the status quo ante — cannot
distinguish correction from change); two (`valid`/`recorded`, dropping
source claims and arrival — loses staleness and audit); five-plus (full
bitemporal `valid_from/valid_to` intervals — interval validity is derivable
from successive point observations and would burden every interpreter for a
need no consumer yet has; recorded as future extensibility, additive if
ever needed).

**Compatibility impact:** additive fields; `retrieved_at` existed only in
Revision 1's unimplemented sketch. Existing `ingest` events, which carry
only the log timestamp, remain valid — for them all four collapse to
`recorded_at`, which is exactly the honest statement of what legacy capture
knew. **Security impact:** provider/interpreter-supplied times are claims,
not authority — `recorded_at` is substrate-set and non-spoofable, so a
hostile artefact can misdescribe the world but cannot rewrite when Foundry
learned things; DET discipline (explicit clocks) applies to all four in
fixtures. **Future extensibility:** validity intervals, timezone-sensitive
domains, and effective-dated reference data (a rate change announced 15 July
effective 1 August is simply `valid_at` in the future) all fit without new
concepts.

## Valuation Model

### Observed valuations and derived lenses — the split

Two kinds of "value", never conflated:

- **A Valuation event** (Spec 001 entity, existing) is an *observed
  assertion*: someone or something asserted a worth, on a basis, by a
  method, at a time. Stored, with provenance and confidence.
- **A Valuation Lens** is a *derivation*: a deterministic, versioned function
  computing a value from canonical evidence — holdings × cited price
  observations; property valuation minus mortgage balance; accessibility-
  gated sums. Never stored; recomputed on replay like every projection.

Evidence-first, applied: **anything derivable is a lens; only what must be
asserted is a Valuation event.** Gold: acquired weight (observation) ×
spot price (price observation, its own `daily` stream) = market value —
a lens, cited to both inputs. Director equity: no derivation exists, so a
Valuation event *is* the evidence — flagged as an estimate, never dressed as
an observation.

### Multiple simultaneous bases (Governor question 5)

`valuation_basis` — pioneered by RFC-007 Revision 2 — is promoted to a
Finance-owned closed vocabulary, and an asset may hold **concurrent
valuations on different bases** plus lens-derived values, simultaneously:

```text
valuation_basis ∈ { market, book, tax, liquidation, estimate }
```

| Value | Kind | Example |
|---|---|---|
| Book value | Stored basis | Cost basis already on Position |
| Market value | Lens (listed) or stored `market`/`estimate` (unlisted) | units × price; director estimate |
| Tax value | Stored basis or lens over Tax Position rules | probate/CGT figures |
| Liquidation value | Stored basis (asserted haircut) or lens (declared haircut policy) | forced-sale property |
| **Accessible value** | **Always a lens** — Capital Accessibility over market value | pension before 57 → £0 accessible |
| **Mission value** | **Always a lens** — mission policy over accessible value and confidence | below |

Mission Value and Accessible Value are **never stored** — storing them would
be storing conclusions (Principle 1), and they change whenever policy,
accessibility, or price changes.

### Capital Accessibility Lifecycle — a Core platform capability
*(Revision 2, Amendment GA5)*

**Problem statement.** Revision 1 made accessibility's *shape* Core but left
its centre of gravity in Finance, with vesting as the motivating case. The
Governor's list — RSUs, stock options, deferred bonuses, trusts, escrow,
inheritance, restricted grants — shows the pattern is not vesting, and not
even equity: it is **"a resource exists, but its availability is conditioned,
and the condition has a lifecycle."** Left Finance-oriented, each new
conditioned form would grow its own state handling, and a future domain
(a Career sabbatical entitlement accruing service time; a Health capacity
gated on recovery) would re-invent the wheel Core exists to own once.

**Recommended architecture — accessibility is a platform capability.** Core
owns three things; domains own two:

| Concern | Owner |
|---|---|
| The **profile contract** — components, portions, condition references | **Core** |
| The **condition vocabulary** — closed, Core-owned, additively extensible by domains (the `000` §7 governance rule) | **Core** |
| The **condition lifecycle** — the state machine every condition instance follows | **Core** |
| **Profiles** — which asset carries which conditions | **Domain** (data on domain entities) |
| **Evaluation** — what real-world event satisfies a condition | **Domain** (asserted by domain events) |

The profile contract:

```text
AccessibilityComponent
    portion               # fraction or absolute amount
    condition             # closed vocabulary, below
    earliest_at           # date the condition can lift, if datable
    condition_ref         # e.g. the Grant tranche, the trust deed,
                          #      the mortgage that secures
    note

accessibility_condition ∈ { none, age_gate, vesting, exit_event,
                            sale_required, notice_period, term_lock,
                            secured_against, action_required,
                            third_party_gate }
```

*(Revision 2 adds `action_required` — accessible only upon a deliberate,
usually costly act, the stock-option exercise shape — and
`third_party_gate` — release controlled by a party outside the household:
trustee discretion, escrow agent, probate. Both were unexpressible in
Revision 1.)*

The **condition lifecycle**, Core-owned and domain-neutral:

```text
pending  →  satisfied     (the gate lifted: vested, released, attained age)
         →  lapsed        (the opportunity expired: option unexercised,
                           offer withdrawn)
         →  revoked       (taken away: forfeiture, clawback, trust
                           revocation)
```

Transitions are never declared into Core directly — they are **asserted by
domain events** (a `finance.vesting_event.declared` satisfies its tranche's
condition; a grant revision revokes it; an option expiry lapses it), and the
Core contract defines only what states exist and what each means for the
derivation. All three terminal states are honest history: a lapsed option
and a revoked tranche are different facts and stay distinguishable forever.
**Terminal states never transition backwards**: a clawback arriving *after*
satisfaction is a **new condition instance** asserted by the domain event
that imposes it — restriction re-imposed is a new fact, not a rewound one,
which is the append-only philosophy applied to state machines.

The one derived function is unchanged from Revision 1 and stays
deterministic: `accessible_value(subject, as_of, horizon)` — the sum of
components whose conditions are `satisfied`, or datable and lifting within
the horizon, priced by the market lens, confidence-capped by its inputs.
The Governor's examples resolve as data, now including the new forms: cash
`none`; pension `age_gate(57)`; RSU tranches `vesting`; options `vesting`
then `action_required`; deferred bonus `term_lock`; trust distributions and
escrow `third_party_gate` (undatable unless the deed dates them);
inheritance `third_party_gate` (probate); director equity `exit_event`;
house `sale_required` + `secured_against`.

**Alternatives rejected:** leaving accessibility in Finance with a copyable
pattern (each domain re-implements a state machine; grades and horizons
drift); putting *profiles* in Core (Core would hold domain data — pension
ages are finance semantics); a per-form taxonomy (RSU-shaped,
option-shaped, trust-shaped — the RFC-008 G3 anti-archetype ruling again:
forms are condition *combinations*, not types).

**Compatibility impact.** Additive: two new vocabulary values, lifecycle
states formalising what Revision 1 implied. Vesting entities (Grant,
Vesting Event — Spec 001 Amendment 5) remain Finance-owned exactly as
proposed; what changes is that a Tranche's restriction is now *expressed as*
a Core condition instance rather than a Finance-private notion, so the
vesting architecture becomes the first *instantiation* of a platform
lifecycle rather than a special case. **Security impact:** none new — the
lifecycle adds no write path; transitions ride existing domain events
through the existing gate. **Future extensibility:** trusts and companies
as owners (TD3) plug in as `third_party_gate` issuers; a Career or Health
domain declares conditions with zero Core change beyond (at most) an
additive vocabulary value.

### Market value versus Mission value (the core concept)

**Mission value is not a property of an asset. It is a property of an
(asset, mission) pair, computed by the mission's declared policy.** The
platform form:

```text
mission_value(asset, mission, as_of) =
    policy_mission( accessible_value(asset, as_of, horizon_mission),
                    evidence_confidence(asset) )
```

- Financial Resilience counts cash at full weight (`none`, liquid) —
  £20,000 market, £20,000 mission.
- Financial Independence counts the pension at **£0** — not because it is
  worthless but because `age_gate(57)` exceeds the mission's horizon. Pension
  Independence, with a horizon beyond 57, counts it fully. Same asset, same
  evidence, two honest answers.
- RSUs contribute vested tranches now and scheduled tranches only insofar as
  the mission's policy admits scheduled-but-unvested value (a policy choice,
  visible as policy).
- Director equity contributes at whatever its confidence-capped, exit-gated
  accessible value is — typically £0 accessible with a visible "estimate,
  Provisional" market value, which is the honest rendering.

No new mission machinery is needed: a mission's provider requests parameterised
metrics (e.g. `finance.accessible_net_worth` with `horizon` and condition
parameters) through the **existing** `MetricRequest.parameters`/`horizon`
fields. Mission Assessment and the Console do not change (AC-12).

### Vesting architecture — Grant → Tranche → Vesting Event

The Recurring Series precedent (expectations never pre-create canonical
events), applied to restricted equity:

```text
Grant        (finance.grant.declared — Amendment 5)
   issuer_ref (Employer core id), instrument, total_units,
   granted_at, plan_ref,
   schedule: [ Tranche { tranche_id, units, expected_vest_at,
                         condition: time | performance } … ]
        ↓  schedule = declared expectation (metadata, like Recurring Series)
Vesting Event (finance.vesting_event.declared — Amendment 5)
   grant_id, tranche_id, vested_at, units, price_at_vest?,
   withheld_units?, provenance (→ the vesting notice evidence)
        ↓  observation; typically acquired via email/statement channel
Position      (existing) — vested units flow into the holding
        ↓
Market Value  (lens: units × price stream)
Accessible Value (lens: vested ∧ not window-locked)
Mission Value (lens: per-mission policy, above)
```

- **Unvested value is a projection, never canonical** — computed from the
  schedule, priced with visible assumptions, `Provisional` at best.
- **Cancellation / forfeiture** are `finance.grant.updated` schedule
  revisions with mandatory reason (`forfeited` is a future vocabulary value,
  reserved now). History preserved; nothing deleted.
- **Nothing couples to PayPal.** The issuer is an Employer reference —
  which also makes the existing employer-concentration metric structurally
  aware of *unvested* exposure, for free.
- One Grant, many tranches — not one asset per tranche; the Governor's
  requested shape, and the dedup-friendly one.
- *(Revision 2)* A tranche's restriction is a **Core accessibility condition
  instance** (`vesting`, lifecycle `pending → satisfied/lapsed/revoked`);
  the Vesting Event is the domain event that asserts the `satisfied`
  transition. Vesting is the first instantiation of the platform lifecycle,
  not a Finance-private mechanism.

### Director equity — the generic privately-held pattern

Not a new entity: an Asset (`asset_category: private_equity`) composed from
the contracts above — `manual` + `on_event`/`annual` streams; Valuation
events on `estimate` basis carrying a declared `valuation_method`
(finance-owned open-then-closed vocabulary: `funding_round`, `net_asset`,
`earnings_multiple`, `director_statement`, `third_party_appraisal`) with
supporting evidence attached (accounts, term sheets — via the vault);
accessibility `exit_event`, undatable; confidence capped at `Provisional` by
grade (below). A possible exit is a **Scenario** (Spec 001 §16), never a
canonical event until observed. Generic by construction: nothing names a
company.

## Confidence Model

One closed, Core-owned grading vocabulary at the evidence boundary:

```text
evidence_grade ∈ { authoritative,      # custodian API/statement, deterministic
                   declared,           # human manual entry
                   confirmed,          # model-extracted, human-confirmed
                   extracted,          # model-extracted, unconfirmed
                   assumed }           # explicit assumption (Assumption Set)
```

**Propagation is by dominance, never arithmetic** (Spec 000's "confidence is
stored and displayed, never arithmetic", made operational):

1. Every envelope carries a grade; every canonical event inherits the grade
   of the evidence chain that produced it.
2. Every lens result and `MetricResult` is **capped by the weakest material
   input** — a deterministic mapping, e.g. any material `extracted` input ⇒
   result no better than the existing framework's `Insufficient`; material
   `declared`/`confirmed`/`assumed` ⇒ no better than `Provisional`; material
   staleness (refresh policy breached) ⇒ capped and `status: stale`.
   "Material" is defined per lens as inputs whose absence changes the value —
   a declared, testable list, not a judgement call at runtime.
3. The cap flows through the **existing** fields —
   `MetricResult.confidence_or_quality` and RFC-006's `MissionConfidence`
   with its `confidence_basis` — so the Governor's chain (manual valuation →
   medium confidence → mission confidence) works today's contracts end to
   end, and RFC-010's safety rule (confidence caps render beside the burn,
   never disclosure-only) applies unchanged.
4. **No confidence arithmetic anywhere**: no multiplication, no averaging, no
   scores. Two `Provisional` inputs are `Provisional`, not "0.6".

The mapping table (grade × staleness → cap) is part of the Core contract,
versioned like a calculation, so a mission cannot quietly re-derive optimism.

## Reference Implementation — recommendation

**Recommended: the children's investment accounts (Hamish and Harriet — JISA
and Junior SIPP), acquired via manual + statement channels.** The Governor's
instinct is endorsed, for reasons that are architectural rather than
sentimental:

1. **Bounded**: two children × two accounts, one or two streams each, low
   event volume, no API dependency — the smallest real slice that is not a
   toy.
2. **Exercises the hard contracts, not the easy ones**: custodian vs
   beneficiary ownership; absolute `age_gate` accessibility with statutory
   dates; **mission value ≠ market value at its most extreme** (real assets,
   £0 toward every parental mission — while a future children's-provision
   mission would count them fully, proving mission-relative valuation);
   statement-based acquisition through the full evidence → proposal →
   confirmation pipeline; refresh honesty (`monthly`/`quarterly` statements
   going stale).
3. **Low blast radius**: no live mission's assessment depends on these
   assets, so the first pipeline shakeout cannot disturb RFC-005–009
   missions.
4. **A deliberate second validator** (the RFC-010 pattern of naming the
   absence-path exemplar): **PayPal RSUs** as the second implementation —
   the vesting architecture, `on_event` email-borne observations, and
   accessibility windows — the populated-path stress the children's accounts
   deliberately lack.

## Security

Acquisition is the largest new attack surface Foundry has added since
authentication. Assessed area by area:

- **Hostile input is the default.** Email and documents are untrusted
  content. Any instruction-like text inside acquired content is *data*: model
  interpreters are schema-constrained, tool-less, and their output is inert
  until human confirmation — a prompt-injected email can, at absolute worst,
  generate a visibly wrong proposal for a human to reject. No acquisition
  component follows links, fetches referenced resources, or executes any
  instruction found in a payload.
- **Providers cannot author truth.** Structural, not procedural: Acquisition
  Providers can append only envelopes; interpreters only proposals; only the
  confirmation gate appends canonical domain events. Compromising a channel
  yields quarantined, attributable evidence — never silent canonical state.
- **Credentials never enter the substrate.** API tokens, mailbox credentials
  and connection configuration are operational configuration (the
  `ModelAdapter` precedent). No event, envelope, proposal, or log line ever
  carries a secret; envelopes carry `source_identity` labels, not
  authentication material.
- **The vault bounds the sensitive-data blast radius.** Verbatim financial
  documents live encrypted at rest in the content-addressed vault, not
  inline in the log; the log holds hashes and structured envelopes. Honest
  redaction (blob removal + redaction event) exists for legal/privacy need
  without ever editing the log.
- **Allowlists fail closed.** Email streams bind to declared senders and
  artefact types; unlisted senders are not acquired. New-source onboarding
  is a registration event, a deliberate act, never inferred.
- **Idempotency prevents replay-flooding.** Content-hash dedup bounds what a
  compromised or misbehaving channel can append; a flood of duplicates
  appends nothing.
- **Scope discipline is unchanged.** Acquisition serves the existing
  single-household model; streams carry no cross-household reach.
  Authentication, sessions and the web surface are untouched (no new route
  is created by this RFC).
- **Provenance is the audit log.** Every canonical figure chains to
  interpreter identity + version and evidence hash; every rejection is
  permanent. "Which channel said this, when, through what code?" is a
  replayable query, not a forensic hunt.
- **Model failure containment extends upstream** (invariant 5): unparseable
  interpreter output yields zero proposals; a failed acquisition run leaves
  at most captured envelopes; partial interpretation never half-commits.
- ***(Rev 2)* Identity is poisoning-resistant by construction.** Aliases
  enter the Identity Index only through confirmed proposals; fuzzy and
  model-suggested matches never auto-commit; ambiguity and unknowns fail
  closed to human review. A hostile artefact can propose a wrong identity;
  it cannot teach one (R11).
- ***(Rev 2)* Time is claim versus witness.** `valid_at`/`observed_at`/
  `received_at` are source or channel claims, preserved as claims;
  `recorded_at` is set by the substrate alone, so no artefact can rewrite
  when Foundry learned something — the bitemporal audit trail is
  non-spoofable (R12).

## Architecture Decision Record

| # | Decision | Choice | Rejected alternative and why |
|---|---|---|---|
| D1 | Where does acquisition live? | Core platform capability (`core.*` namespaces, domain-neutral machinery) | Per-domain acquisition — would re-implement the seam per domain, the pre-Registry defect |
| D2 | Asset Registry | Core **event-sourced** projection of registration/stream metadata; entities stay domain-owned | Assets as Core entities — violates Spec 000 §16's frozen disposition; registry-as-wiring — connected accounts are user state, must replay |
| D3 | Evidence capture | Telemetry Envelope events + content-addressed Evidence Vault; legacy `ingest` = degenerate inline case, unmigrated | Blobs inline in JSONL — unredactable, unbounded log growth; blobs outside the chain — uncommitted evidence |
| D4 | Staging | Proposals are log events (`core.observation_proposal.*`), inert until confirmed; Inbox is a projection | Staging DB outside the log — a second truth, invisible to replay; direct-to-canonical — model becomes an author of truth |
| D5 | Confirmation | Closed `confirmation_policy` per stream; hard floor: model-class interpreters never auto-commit | Per-import human choice — unauditable; global single policy — makes APIs unusable or email unsafe |
| D6 | Valuation | Stored Valuation events on closed `valuation_basis`; Accessible and Mission value are lenses, never stored | Stored mission value — a stored conclusion, invalidated by every price/policy change |
| D7 | Mission value | Property of (asset, mission), computed via existing `MetricRequest` `parameters`/`horizon` | New mission-side contract — RFC-010/006 surfaces are frozen and need nothing new |
| D8 | Accessibility | Core contract shape (components + closed conditions + derivation); domain-owned profiles. **Rev 2 (GA5): elevated to a full Core lifecycle capability** — Core owns vocabulary and condition state machine; domains own profiles and transition-asserting events | Extending `liquidity_classification` — liquidity (speed) and permission (right) are different axes; per-form archetypes — RFC-008 G3 |
| D9 | Vesting | Grant (schedule as expectation) + observed Vesting Events + existing Position; Spec 001 Amendment 5 | Position-per-tranche — entity explosion, dedup hazard; schedule pre-creating events — violates the Recurring Series precedent |
| D10 | Confidence | Closed `evidence_grade` + dominance caps through existing confidence fields | Numeric propagation — forbidden arithmetic; per-domain grading — fragments one platform concept |
| D11 | Ownership | Unchanged, Finance-owned; mission relevance derived, household benefit derived | "Mission ownership" links or Household-as-owner — contradict frozen Spec 001 §9 and store conclusions |
| D12 | Provider wiring | Acquisition Provider Registry mirrors Metric Registry (explicit registration, fail-closed, no discovery) | Implicit discovery — the Metric Registry already rejected this idiom for good reasons |
| D13 *(Rev 2)* | Identity Resolution | Permanent platform layer: typed `ExternalRef`s, event-sourced Identity Index, read-only Resolution Service at proposal formation; aliases enter only via confirmation; ambiguity fails closed | Briefed Evidence→Interpreter stage position — needs symbols that don't yet exist there; per-interpreter matching; auto-writing fuzzy matchers; aliases as config |
| D14 *(Rev 2)* | Containment | Core `contains` structural relation over registrations; derive-upward-never-store-upward; container totals become reconciliation evidence when holdings exist | New Core Container entity — §16 disposition; fixed two-level taxonomy — anti-archetype ruling |
| D15 *(Rev 2)* | Refresh ownership | Per-stream only; lens freshness = worst material stream; registry fields removed | Asset-level cadence — a fabricated average; best-stream freshness — optimistic dishonesty |
| D16 *(Rev 2)* | Temporal semantics | Four first-class timestamps with single owners; bitemporal read rule (`recorded_at ≤ D`, `valid_at ≤ T`); `recorded_at` substrate-set | One or two timestamps — cannot distinguish correction from change; full validity intervals — derivable, no consumer yet |
| D17 *(Rev 2)* | Accessibility ownership | Platform capability: Core vocabulary + lifecycle (`pending → satisfied/lapsed/revoked`), domain profiles + transition events; adds `action_required`, `third_party_gate` | Finance-owned pattern-copying; profiles in Core (domain data in Core) |

## Governor Questions — recommendations

1. **Should Asset Registry become a Core capability?** **Yes** — as an
   event-sourced Core projection holding acquisition metadata and stream
   bindings only. Asset *entities and semantics* remain domain-owned; the
   frozen Spec 000 §16 disposition is untouched (D2).
2. **Should Valuation become a Core capability?** **Split.** The Valuation
   Lens *contract shape* and the Capital Accessibility contract are Core
   (like the Metric Provider contract — shape without semantics); valuation
   *calculations*, the Valuation entity, and `valuation_basis` remain
   Finance. Extract nothing further until a second domain demonstrably needs
   it — the extraction bar Spec 000 itself was held to.
3. **Should Ownership become Core?** **No.** `ownership_relationship` is
   inherently financial (frozen Spec 000 §16 ruling, reaffirmed). The
   domain-neutral parts of "who does this concern" already exist in Core
   (`concerns`, Party, scope attribution). Trusts/companies arrive later as
   additive `party_type` values, not as relocation.
4. **Should Acquisition Providers be plugins?** **Yes** — registered,
   fail-closed plugins behind a Core registry, exactly one idiom shared with
   Metric Providers (D12). Channels multiply; the seam does not.
5. **Should every asset support multiple simultaneous valuations?** **Yes**
   — concurrent stored bases (`market`, `book`, `tax`, `liquidation`,
   `estimate`) plus always-derived Accessible and Mission lenses. The two
   derived ones are never stored (D6).
6. **Should Mission Assessment ever read raw telemetry?** **Never.**
   Assessment reads canonical state through registered metrics, unchanged.
   Acquisition reality reaches missions only as metadata through existing
   fields: `status: stale`, capped `confidence_or_quality`,
   `confidence_basis`. Raw envelopes and proposals are structurally
   invisible to assessment (AC-12).
7. **How should confidence propagate?** Categorically, by weakest-material-
   input dominance, through a versioned Core mapping table into the existing
   `MetricResult`/`MissionConfidence` fields — no arithmetic anywhere
   (Confidence Model; D10).

### Revision 2 rulings (the five refinement questions)

1. **Does Identity Resolution become a permanent platform layer?** **Yes.**
   Identity is the one error class whose mistakes *multiply* — a wrong alias
   corrupts every future observation of that symbol — so it must be solved
   once, centrally, evidence-first, fail-closed. It enters as a read-only
   service plus an event-sourced Identity Index, positioned at proposal
   formation rather than the briefed pre-interpreter slot, because it
   consumes interpreted symbols that do not exist earlier (D13; deviation
   justified in the section).
2. **Should Container → Holding become part of Core?** **Yes** — as a
   containment *relation* on the Asset Registry with Core-owned composition
   and reconciliation rules, not as new Core entities. The rules (derive
   upward, never store upward; container totals as reconciliation evidence)
   are what prevent double-counting, and rules that live nowhere get
   re-invented wrongly per domain (D14).
3. **Should refresh policy move to telemetry streams?** **Yes, fully.** The
   Governor is right and Revision 1's registry duplication was a latent
   contradiction: gold's weight, price and cost cannot share a cadence.
   Refresh behaviour is per-stream; asset-level freshness is a derived,
   per-lens worst-material-stream fold (D15).
4. **Should temporal semantics become first-class contracts?** **Yes.**
   `valid_at`, `observed_at`, `received_at`, `recorded_at` — each has
   exactly one owner and one consumer that breaks without it, and the
   bitemporal read rule makes honest restatement ("as believed then" vs "as
   known now") architectural rather than accidental (D16).
5. **Is Accessibility a platform capability or a Finance concern?**
   **Platform.** The pattern — conditioned availability with a condition
   lifecycle — spans RSUs, options, deferred bonuses, trusts, escrow and
   inheritance today and non-financial domains tomorrow. Core owns the
   contract, the condition vocabulary and the
   `pending → satisfied/lapsed/revoked` lifecycle; domains own profiles and
   the events that assert transitions. Vesting remains Finance-owned but
   becomes the lifecycle's first instantiation (D17).

## Open Questions — ruled and closed

**All seven were approved by the Governor on 2026-07-31, each on its
recorded recommendation.** In particular: the Evidence Vault is adopted
(OQ1); redaction is Governor-gated per artefact in V1 (OQ2); Spec 001
Amendment 5 (Grant, Vesting Event, valuation vocabularies, accessibility
attributes) is approved and must land before the implementation Burns that
need it (OQ3); the Core vocabulary and relation additions are approved
(OQ4); the reference implementation is the children's accounts with PayPal
RSUs as second validator (OQ5); rejected proposals remain in the log (OQ6);
and market prices are ordinary telemetry streams on registrable instrument
subjects (OQ7).

| # | Question | Approved ruling (2026-07-31) |
|---|---|---|
| OQ1 | **Evidence Vault**: adopt the content-addressed vault with hash-committed payloads and the redaction-event mechanism? This nuances (without breaching) the append-only philosophy and is the only redaction path proposed | Adopt (D3) |
| OQ2 | **Retention stance**: is redaction Governor-gated per artefact, or policy-scheduled (e.g. raw bills after N years)? Blast-radius and privacy argue for a policy; append-only instinct argues for per-artefact deliberation | Governor-gated per artefact in V1; revisit with volume |
| OQ3 | **Spec 001 Amendment 5**: approve Grant + Vesting Event entities, `valuation_basis`/`valuation_method` vocabularies, accessibility profile attributes | Approve before any implementation Burn |
| OQ4 | **Core vocabulary additions**: `refresh_policy`, `update_strategy`, `evidence_grade`, `confirmation_policy`, `accessibility_condition` (incl. Rev 2's `action_required`, `third_party_gate`); structural relations `measures` (stream → subject) and `contains` (Rev 2); the `ExternalRef` namespace vocabulary (Rev 2); reserve `forfeited` | Approve |
| OQ5 | **Reference implementation**: children's accounts first, PayPal RSUs second? | Approve as recommended |
| OQ6 | **Proposal retention**: rejected proposals remain in the log forever (recommended — they are diagnostic history), or are they vault-side? | In the log; they are small and structured |
| OQ7 | **Price streams**: market prices as ordinary Telemetry Streams on their own subjects (an instrument registry entry) — accept that instruments become registrable subjects? | Yes; prices are telemetry like everything else |

## Risk Register

| # | Risk | Consequence | Control |
|---|---|---|---|
| R1 | Prompt injection via acquired content | Fabricated proposals | Model interpreters: schema-only output, no tools, no event append; hard no-auto-commit floor; verbatim source shown at confirmation |
| R2 | Credential leakage into the substrate | Irrevocable secret in an append-only log | Structural: envelopes carry labels not secrets; secrets live in operational config; reviewed as a named acceptance criterion (AC-6) |
| R3 | The Inbox becomes a shadow truth (perpetually unresolved proposals treated as data) | Two-truth drift | Proposals are structurally invisible to projections/metrics; staleness of *unresolved* proposals is surfaced, not consumed |
| R4 | Auto-commit corrupts canon via a bad deterministic parser | Wrong canonical state at scale | Interpreter versioning + supersession; per-stream policy can tighten; correction discipline; batch summaries on imports |
| R5 | Log/vault bloat from high-cadence channels | Operational degradation | Idempotent capture; envelope-not-blob in log; cadence declared per stream (no unsolicited polling faster than policy) |
| R6 | Confidence theatre — grades assigned optimistically | Dishonest mission confidence | Grades fixed by channel/interpreter class, not chosen per import; cap table versioned in Core |
| R7 | Acquisition scope creep into channel implementations during the architecture Burn | This RFC becomes an integration project | Scope Exclusions are explicit; channel implementations are separate RFCs |
| R8 | Vesting/accessibility policy quietly embeds mission policy into Finance code | Mission neutrality breached | Policies live with missions and are visible as parameters; lenses are mission-blind (AC-11) |
| R9 | The registry duplicates domain state (ownership, category) "for convenience" | Divergent copies | Registry schema is closed: routing + expectation metadata only (AC-4) |
| R10 | Correction workflow debt (RFC-007) is silently absorbed | Unowned governance gap | Named in Technical Debt; corrections use the existing event discipline until that RFC lands |
| R11 *(Rev 2)* | Identity poisoning — hostile content teaches a wrong alias | Every future observation of that symbol misattributed | Aliases only via confirmation; fuzzy/model matches never auto-commit; ambiguity fails closed; alias history replayable and correctable with reason |
| R12 *(Rev 2)* | Temporal misuse — a consumer folds by `recorded_at` where `valid_at` is meant | Backfill silently misdated; restatements conflated | The bitemporal read rule is the contract; AC-18 asserts it; `recorded_at` is substrate-set and non-spoofable |
| R13 *(Rev 2)* | Containment double-count — holding values and container totals both consumed | Inflated aggregates | Derive-upward rule; container totals demoted to reconciliation evidence when holdings exist; AC-16 |

## Acceptance Criteria

Blocking for any implementation Burn built on this architecture:

| # | Criterion |
|---|---|
| AC-1 | **Zero substrate change**: `eventlog.py`, `canon.py`, `kernel.py` unmodified; Canon and all existing projections ignore every new event kind |
| AC-2 | **Verbatim-first**: no interpreter runs except over a captured envelope; deleting all interpreters loses no acquired information (replay proves it) |
| AC-3 | **No unconfirmed canonical state**: no `finance.*` event exists whose provenance chains to an unresolved or rejected proposal; model-class proposals never auto-commit (structurally asserted, not policy-asserted) |
| AC-4 | **Registry is metadata-only**: no value, ownership or domain semantics in any Asset Registry projection field |
| AC-5 | **Idempotent capture**: re-acquiring an identical artefact appends zero events, for every channel |
| AC-6 | **No secrets in the substrate**: asserted by test over envelope/proposal schemas and by security review over provider implementations |
| AC-7 | **Full provenance chain**: for any canonical figure, `why()` reaches interpreter id + version and evidence `payload_hash` without gaps |
| AC-8 | **No category or channel branching** in Core acquisition code: no `account_type`, asset category, mission or domain term (the RFC-010 T16 discipline, applied upstream) |
| AC-9 | **Derived values never stored**: no event anywhere carries an accessible value or a mission value; both recompute on replay, byte-identically |
| AC-10 | **Confidence caps are deterministic**: same evidence grades + freshness ⇒ same caps, asserted across replay; no numeric confidence arithmetic exists |
| AC-11 | **Lenses are mission-blind**: accessibility and valuation lens code contains no mission reference; mission policy arrives only as request parameters |
| AC-12 | **Frozen surfaces untouched**: RFC-006/010 contracts and all four shipped missions' assessments replay and render unchanged when acquisition events are present in the log |
| AC-13 | **Deterministic testing**: DET-1…DET-6 (RFC-010) apply to every acquisition fixture; envelope `retrieved_at` uses explicit clocks |
| AC-14 | **Fail-closed registries**: unregistered stream acquires nothing; duplicate provider registration rejected; unknown interpreter version ⇒ proposal rejected, never guessed |
| AC-15 | **Vault integrity**: a vault blob failing its `payload_hash` is surfaced as corruption; a redacted blob renders as explicit, attributed absence — never as silently missing data |
| AC-16 *(Rev 2)* | **No containment double-count**: any lens fold counts each registered subject exactly once — a holding's value or its container's asserted value, never both; container totals with registered holdings surface only as reconciliation findings |
| AC-17 *(Rev 2)* | **Identity fails closed**: no canonical event's provenance chains to an `ambiguous` or `unresolved` resolution; no alias exists without a confirmation in its provenance; a fuzzy or model-suggested match never auto-commits (structurally asserted) |
| AC-18 *(Rev 2)* | **Temporal contract holds**: every canonical observation carries `valid_at`; `recorded_at` is substrate-set only; the bitemporal fold (`recorded_at ≤ D`, `valid_at ≤ T`) is deterministic across replay for any (D, T) |
| AC-19 *(Rev 2)* | **Freshness is derived per lens**: no stored asset-level refresh or staleness field exists anywhere; a lens result's freshness equals its worst material stream's, asserted deterministically |
| AC-20 *(Rev 2)* | **Accessibility lifecycle integrity**: condition state transitions occur only via domain events through the confirmation gate; `satisfied`, `lapsed` and `revoked` remain distinguishable in replay; no Core code evaluates a domain condition's semantics |

## Implementation Sequence

Gated like RFC-010's migration plan, with mock-first neutrality proof:

```text
Phase 0   Governor rulings OQ1–OQ7; freeze this contract
          — COMPLETE 2026-07-31 (Governor approval, above)
Phase 1   Core acquisition grammar: envelope events (temporal fields),
          proposal lifecycle, stream entity, registries, Identity Index +
          Resolution Service, containment relation — mock providers and
          mock domain ONLY (no Finance code); prove AC-1…AC-8, AC-13,
          AC-14, AC-16…AC-18
Phase 2   Evidence Vault + manual channel formalisation (existing ingest
          becomes the degenerate case); confirmation gate incl. identity
          floor
Phase 3   Valuation lenses + Capital Accessibility lifecycle + per-lens
          freshness + confidence caps over existing Finance entities;
          prove AC-9…AC-11, AC-19, AC-20
Phase 4   REFERENCE IMPLEMENTATION — children's accounts (manual +
          statement, deterministic interpreters, full pipeline incl.
          container→holding statements and identity resolution on real
          line items)
Phase 5   GOVERNOR REVIEW GATE — pipeline walkthrough on real children's
          statements; no further channel until passed
Phase 6   Spec 001 Amendment 5 entities (Grant, Vesting Event) +
          PayPal RSU vesting via the email/statement pipeline
          (deterministic first; model interpreter behind review_each)
Phase 7   Director equity pattern (estimate-basis valuations, exit_event
          accessibility)
Phase 8   CSV import channel; prove AC-5 at batch scale
Phase 9   Retire/absorb: ingestors.py becomes providers; prove AC-12
          across all four missions; SAFE + Governor review; merge
Phase 10  Confirm first post-merge main workflow passes (RFC-010 step-14
          discipline)
```

Each phase is a separate Burn candidate; Phases 1–3 are the platform, 4–8
are proof by real assets, and no phase implements an excluded channel.

## Technical Debt

Accepted, named, not hidden:

| # | Debt | Disposition |
|---|---|---|
| TD1 | **Governed correction workflow** (inherited from RFC-007) — confirming-then-correcting remains event-discipline-only, with no review UX | Successor RFC; acquisition raises its urgency because volume rises |
| TD2 | **Single-writer log assumption** meets multi-channel acquisition — providers must serialise appends | Acceptable at household scale; the roadmap's concurrency item now has a concrete driver |
| TD3 | **Trust/company ownership** — `party_type` extension deferred | Future amendment; structure already accommodates it |
| TD4 | **Performance-conditioned vesting** — Tranche `condition: performance` is representable but no evaluation architecture exists | Deliberate: evaluating performance conditions is a valuation-adjacent judgement, deferred until a real grant needs it |
| TD5 | **Instrument/price-stream registry** (OQ7) is minimal — one subject per priced instrument, no corporate-actions model | Sufficient for V1; a corporate-actions RFC is future work |
| TD6 | **Legacy `ingest` events** remain unmigrated alongside envelopes | Harmless duality, documented; migration is optional history-hygiene, never required |

## Future RFC Dependencies

| Future RFC | Depends on RFC-011 for |
|---|---|
| Acquisition Console / Inbox UX | Proposal lifecycle, confirmation gate, Inbox projection |
| Email channel implementation | Provider + interpreter contracts, allowlist registration, vault |
| Open Banking / pension APIs / HMRC | Provider contract, `authoritative` grade, auto-commit policy |
| OCR / document AI | Model-interpreter sandbox contract, review_each floor |
| Property Valuation Canon (RFC-007 successor) | `valuation_basis`/`valuation_method`, estimate discipline |
| Governed correction workflow (TD1) | Provenance chain as the correction's evidence trail |
| Children's-provision mission (candidate) | Mission-value lenses proving mission-relative valuation |
| Future domains (Health, Career) | The entire domain-neutral acquisition seam |

## Scope Exclusions

Unchanged from the brief, restated as binding: this RFC designs **no** Open
Banking implementation, no Plaid/TrueLayer evaluation, no bank or broker
integration, no OCR implementation, no email-parsing implementation, no UI,
no Mission Console change, no Mission Assessment change, and no
authentication change. Where this document names a channel, it defines only
the contract seam that channel must later fit.

## References

- [`../architecture.md`](../architecture.md) — constitutional invariants
- [`../specifications/000-core-domain-model.md`](../specifications/000-core-domain-model.md)
  — event grammar, Metric Provider contract, Evidence Index, §16 dispositions
- [`../specifications/001-finance-domain-model.md`](../specifications/001-finance-domain-model.md)
  — finance entities, ownership vocabulary, household aggregation
- [`RFC-010-mission-console-ux-framework.md`](RFC-010-mission-console-ux-framework.md)
  — platform-capability precedent, DET discipline, frozen console contract
- [`../rfc-006-mission-assessment-framework.md`](../rfc-006-mission-assessment-framework.md)
  — confidence vocabularies, removal discipline
- [`../rfc-007-mortgage-freedom-architecture.md`](../rfc-007-mortgage-freedom-architecture.md)
  — `valuation_basis` precedent, correction-workflow debt
- [`../security/threat-model.md`](../security/threat-model.md)
- [`index.md`](index.md) — RFC index
