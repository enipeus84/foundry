# Spec 001 — Foundry Finance Domain Model

Status: **Draft v5 — for review** (Amendment 4)
Layer: **Product domain, above the substrate** (see `docs/architecture.md`)
Depends on: `foundry.eventlog`, `foundry.canon`, `foundry.kernel`, `foundry.models`,
**`000-core-domain-model.md`**
Does not modify: `src/foundry/eventlog.py`, `src/foundry/canon.py`, `src/foundry/kernel.py`

> **001-finance-domain-model.md depends on 000-core-domain-model.md and
> must not redefine shared core concepts.** Where this document once
> defined Party, Employer, Mission, the Decision lifecycle, the shared
> event grammar, the tag/link distinction, and the Flight Deck's general
> contract, it now references `000-core-domain-model.md` instead.
> Everything that remains defined *here* is genuinely financial: ledger
> entities, ownership of value-bearing resources, investments, pensions,
> tax, and forward-looking financial forecasting.

**Amendment 4** reflects `000-core-domain-model.md` Revision 2, which
added the Metric Provider contract (resolving how Mission status and
Flight Deck tiles retrieve a financial figure without Core importing
Finance's calculation code) and resolved the Core Evidence Index
question (one shared index for Claim tags and subject links, not a
per-domain copy). This amendment is reference-only: section numbers
that shifted in `000` are corrected, two statements that assumed the
now-superseded per-domain tag-index design are fixed, and Finance's
Facts are noted as exposed through the Metric Registry. No finance
concept, entity, or acceptance criterion changes in substance.

---

## 1. Purpose

The Finance Domain answers one question on an ongoing basis: **are we
still on glide path toward the household's declared objectives, and if
not, what should we do about it?** (Mission, and the Flight Deck's
Mission-first organisation, are core concepts — `000-core-domain-model.md`
§8, §14 — Finance's job is to supply the financial metrics, projections,
and tax reality that Mission status is measured against.)

Foundry's substrate demonstrates that durable, provenanced knowledge
can outlive any individual model. The Finance Domain applies that
substrate to a household's financial life: accounts, obligations,
investments, pensions, tax position, and the forward-looking
projections and financial interpretations built on top of them.

Financial understanding today is trapped inside whichever tool or model
produced it, with no durable record of *why* a number is believed,
*what raw evidence* supports it, *what was assumed* when a figure is a
forecast rather than a fact, or whether a past financial decision
actually worked. That last piece — the closed learning loop — is a
**core** concept (`000` §12); this document defines only its financial
instantiation (§21).

Four kinds of knowledge remain distinguishable, two defined here and
two defined in `000`:

- **Observations** *(here, §12)* — what was actually seen. Immutable,
  verbatim.
- **Facts** *(here, §13)* — what can be computed from observations with
  no judgement. Deterministic, reproducible, model-free, and exposed to
  Core as registered metrics (`000` §13).
- **Financial Projections** *(here, §16)* — Finance's own instantiation
  of the generic forward-looking mechanism a Mission's `target_metric`
  cites, now formalised by the Metric Provider contract (`000` §13.6).
- **Interpretations, Decisions, Execution, Outcome, and Review**
  *(mechanism defined in `000` §11, §12; Finance supplies only the
  financial content that flows through it)*.

## 2. Scope

### In scope

- Financial entities: accounts, assets, obligations, transactions,
  valuations, investment positions, recurring commitments, assumption
  sets, scenarios, tax jurisdiction configuration, exchange rates, tax
  positions, capital gain events.
- Ownership of those entities, and the finance-specific relationship
  vocabulary that describes it.
- Financial extensions to core relationship vocabularies
  (`tax_resident_in`, `fulfils` — `000` §7).
- Household financial aggregation (union-not-sum, share attribution,
  reconciliation) applied to the core Party/group pattern (`000` §8).
- Deterministic, model-free financial calculations, as an open,
  extensible set, registered as metrics for Core to retrieve (`000`
  §13).
- The Financial Projection contract: Baseline, Scenario, Projection
  Series, Assumption Set.
- Investment, pension, and V1 tax models.
- AI-assisted financial analysis, using the core insight-typing
  mechanism (`000` §11) unmodified.
- Finance's contribution to the shared Flight Deck: its candidate KPIs,
  populated through the core tile contract (`000` §14).

### Explicitly out of scope, and now defined elsewhere

The following are **no longer defined in this document** — they are
adopted from `000-core-domain-model.md` and must not be redeclared
here:

| Concept | Now defined in |
|---|---|
| Party (incl. `party_type`, group/`member_of` pattern) | `000` §8 |
| Employer | `000` §8 |
| Mission (incl. `mission_status`) | `000` §8 |
| Shared event grammar (`.declared/.updated/.closed/.linked/.tagged`) | `000` §6 |
| Relationship-link vs. typed-tag distinction | `000` §5, §6 |
| `party_relationship`, `structural_relationship` (base values) | `000` §7 |
| `tag_type`, `insight_type`, `review_verdict` | `000` §7 |
| Scope attribution & drill-down mechanism | `000` §10 |
| Evidence model (Claim reuse, citation discipline, the shared tag/link index) | `000` §11 |
| Decision, Execution, Decision Outcome, Decision Review, Learning | `000` §12 |
| Metric Provider contract, Metric Registry, `MetricRequest`/`MetricResult` | `000` §13 |
| Flight Deck general contract (tile fields, sections, scope model, Mission-first principle, 5–7 cap) | `000` §14 |

### Out of scope entirely (unchanged)

- Live bank/brokerage integrations, payment initiation, trade
  execution.
- Multi-user permissions.
- Automated investment or trading advice.
- Any mutable correction path.
- A second event log or storage primitive.
- Background daemons.
- Full tax law for any jurisdiction; actuarial-grade pension modelling.

## 3. Dependency & implementation order

This document depends on `000-core-domain-model.md` for every concept
listed in §2's table. It extends and consumes those concepts; it never
redefines them, and it never creates a parallel finance-specific copy
of a core object.

**Implementation order:**

1. **Core shared objects and conventions are implemented first** —
   the event grammar (`000` §6), Party/Employer/Mission (`000` §8), the
   relationship and tagging mechanisms (`000` §9–§11), the Decision
   lifecycle (`000` §12), and the Metric Registry (`000` §13), all
   under the `core.*` (and unprefixed `claim.*`) event namespaces.
2. **Finance then extends and consumes them** — declaring its own
   `finance.*` entities, additively extending `party_relationship` and
   `structural_relationship` (§6), registering its deterministic
   calculations as metrics (§13), and populating the Flight Deck's core
   tile contract with financial content (§23).
3. **No parallel finance-specific copies of core objects may be
   created.** There is no `finance.party.*`, `finance.employer.*`,
   `finance.mission.*`, `finance.decision.*`, or
   `finance.decision_outcome.*` event kind anywhere in this
   specification (§11), and no finance-local index of Claim tags or
   subject links duplicating the Core Evidence Index (`000` §11.1).
   Where Finance needs to attach a financial attribute to a core entity
   (the Household Party's `reporting_currency`, §9), it appends to that
   entity's *existing* `core.*` event stream, per `000` §5 principle 3
   — it does not open a second one.

## 4. Terminology

`000-core-domain-model.md` §4 defines *projection* (architectural),
*relationship link*, *typed tag*, *metric*, and *domain*. This document
adds only the one term that is genuinely Finance's own:

- **Financial Projection** (capitalised) — a forward-looking,
  time-indexed estimate of a financial metric under a stated set of
  assumptions (§16). It is Finance's specific answer to the generic
  projection contract a `MetricRequest` with a `horizon` triggers
  (`000` §13.6), not a redefinition of *projection* in the
  architectural sense.

## 5. Design principles

Finance inherits the five constitutional invariants (`docs/architecture.md`)
and the six cross-domain principles in `000` §5 (no substrate change;
relationship-vs-tag integrity; one canonical stream per shared entity;
additive vocabulary governance; no false precision, extended to metric
providers; Mission-first Flight Deck organisation, extended to the
domain-calculates/Core-evaluates/AI-may-only-explain division of
responsibility) without restatement here.

Two principles remain genuinely Finance's own:

1. **Hypothetical and forecast financial state never contaminate
   canonical financial state.** Neither a Scenario's adjustments nor
   any Financial Projection's output is ever expressed as an event
   against a real financial entity (§16).
2. **A financial estimate under uncertainty must say so structurally** —
   the specific instance of `000` §5's "no false precision" principle
   that governs Tax Position (§19): `estimation_basis` is never
   optional, and an unsupported calculation produces no `amount` rather
   than a guess. Finance's Metric Provider (§13) applies the identical
   discipline: an unsupported or unavailable financial metric returns
   `status: unsupported`/`unavailable`, never a fabricated `value`.

## 6. Controlled vocabularies

Finance-owned, additive, never redefined (governed by the same rule
`000` §5 states for core vocabularies):

| Vocabulary | V1 starting values |
|---|---|
| `account_type` | `checking`, `savings`, `credit_card`, `loan`, `mortgage`, `brokerage`, `pension`, `other` |
| `tax_wrapper` | `none`, `isa`, `pension_wrapper`, `gia_taxable`, `other` |
| `asset_category` | `property`, `vehicle`, `collectible`, `private_equity`, `cash_equivalent`, `other` |
| `liability_category` | `mortgage`, `personal_loan`, `credit_card_debt`, `informal_loan`, `other` |
| `transaction_category` | `income`, `housing`, `transport`, `groceries`, `childcare`, `education`, `healthcare`, `discretionary`, `savings_transfer`, `investment_contribution`, `pension_contribution`, `tax_payment`, `other` |
| `ownership_relationship` | `owner`, `co_owner`, `beneficial_owner`, `custodian`, `beneficiary`, `owes`, `guarantees`, `secures`, `collateralises` |
| `liquidity_classification` | `liquid`, `near_liquid`, `illiquid_short`, `illiquid_long` |
| `recurring_commitment_type` | `salary`, `pension_contribution`, `mortgage_payment`, `regular_expense`, `savings_contribution`, `investment_contribution`, `child_contribution` |
| `tax_estimation_basis` | `observed`, `estimated`, `derived`, `unsupported` |

**Extensions to core vocabularies** (`000` §7 — additive only, never
redefining a core value):

| Core vocabulary | Finance's additive value | Meaning |
|---|---|---|
| `party_relationship` | `tax_resident_in` | Person/Household → Tax Jurisdiction Configuration (§19). |
| `structural_relationship` | `fulfils` | A Transaction relates to the Recurring Series it satisfies (§15). |

`ownership_relationship` is **not** extracted to core — it describes
legal/financial ownership of a value-bearing resource, which is
inherently Finance's concept (`000` §16's disposition table).

## 7. Entities

| Entity | Represents | Lifecycle states |
|---|---|---|
| **Account** | A custodial financial container, including pensions. | active, closed |
| **Asset** | An item of value not held in a custodial account. | active, closed |
| **Obligation** | A liability not modelled as an Account. | active, settled, closed |
| **Transaction** | An atomic, dated flow of value. | active, corrected |
| **Valuation** | A point-in-time worth assertion. | active |
| **Position** | An investment holding within an Account (§17). | active, closed |
| **Recurring Series** | An expected future pattern of transactions (§15). | active, paused, ended |
| **Assumption Set** | A named, versioned set of forecasting assumptions (§16). | active, archived |
| **Scenario** | A named hypothetical variation from the Baseline (§16). | active, archived |
| **Tax Jurisdiction Configuration** | Declared tax-year and rule-reference data (§19). | active |
| **Exchange Rate** | A dated currency-pair rate observation (§22). | active |
| **Tax Position** | An estimated, observed, or derived tax liability (§19). | active, superseded, unsupported |
| **Capital Gain Event** | A realised gain or loss from a Position disposal (§19). | active |

Party, Employer, Mission, Decision, and Decision Outcome are **not**
listed here — they are core entities (`000` §8, §12) that Finance
consumes and, where relevant, links to or attaches financial attributes
onto. Decision Review is not an entity anywhere — it is a `Claim`
(`000` §12).

Common fields on every entity above: `id`, domain-specific attributes,
`provenance`, `asserted_by`, `status`, `history` — mirroring `Claim`,
as established in Amendment 1.

## 8. Ownership & relationship model

Ownership relationships use the `.linked` verb (`000` §6), governed by
Finance's own `ownership_relationship` vocabulary (§6) — never a bare
string, per `000` §5 principle 2.

| Relation | Direction | Meaning |
|---|---|---|
| `owner` | Person/Household → Account/Asset | Sole legal ownership. |
| `co_owner` | Person → Account/Asset | Shared legal ownership; see `share` below. |
| `beneficial_owner` | Person → Asset | Economic benefit without legal title. |
| `custodian` | Person → Account/Asset | Manages on behalf of another party. |
| `beneficiary` | Person → Account/Asset/Obligation | Entitled to a future benefit. |
| `owes` | Person → Obligation | Liable for a debt. |
| `guarantees` | Person → Obligation | Liable only on default by the primary obligor. |
| `secures` | Obligation → Asset | The obligation is secured against the asset (e.g. a mortgage against a property). |
| `collateralises` | Asset → Obligation | The inverse phrasing of `secures`; recorded once, never in both directions for the same pair. |

An ownership relation may carry an optional `share` (percentage);
co-owner shares default to an equal split when omitted and must sum to
100% when present (§9).

**Party and Employer relationships** (`member_of`, `employed_by`) are
core concepts, defined and governed entirely by `000` §9 — this
document adds nothing to them beyond the one case where a financial
resource references an Employer: a Position's `issuer` (§17) may
reference a declared Employer's core id, which is what makes
employer-concentration calculations (§13) precise rather than
string-matched.

Example: the mortgage on the family home is linked via
`finance.obligation.linked {relation: "secures", target:
<property_asset_id>}`, recorded once.

## 9. Household model

The Parker-Brads Household and its members (Chris, Fiona, Hamish,
Harriet) are declared per the core Party/group pattern
(`000` §8): a `Party` with `party_type: household`, with each member
linking via `core.party.linked {relation: "member_of", target:
<household_party_id>}`. This document adds nothing to that mechanism —
only the financial arithmetic that applies it.

The Household Party carries `reporting_currency` (§22, default GBP) —
declared via `core.party.updated {party_id: <household_id>,
reporting_currency: "GBP", reason: ...}`, per `000` §5 principle 3: this
attaches a financial attribute to the *existing* core Party event
stream, it does not open `finance.party.*`.

`000` §8 already establishes that a group-type Party must never itself
hold a domain's resources. Finance's specific instance of that rule:
**the Household Party must never be the target of an
`ownership_relationship` link.**

**Aggregation rule.** A metric's household total = the value of every
Account/Asset owned, in any ownership relation, by any Person
`member_of` the Household, **unioned by entity id** — not summed per
member (the general group pattern from `000` §8, applied to money).
Obligations are unioned the same way and subtracted.

**Individual attribution rule.** A Person's attributed value of a
jointly-held entity is its value × their `share` (equal split if
unspecified); a solely-held entity is attributed entirely to its one
owner.

**Reconciliation.** The sum of every household member's individually
attributed value for a metric equals the household's unioned total, by
construction, for any log state (§24, criterion 9).

## 10. Scope attribution

Every financial Insight, Recommendation, Scenario, Decision, and
Decision Outcome uses the scope-attribution mechanism defined in
`000` §10 (`concerns`, drill-down resolution) without modification.
Finance's contribution is only the set of valid financial subjects:
Account, Asset, and Obligation, alongside the core subjects (Party,
Employer, Mission) `000` §10 already names.

## 11. Event model

The event grammar itself — the five verbs, their payload shapes, and
the `claim.tagged`/direct-`claim.derived` mechanism — is defined once,
in `000` §6, and is not restated here.

**Namespace adoption.** Per the rename adopted in Amendment 3, the
following types use the `core.` prefix (or, for Claim operations,
remain unprefixed) and **no longer** appear under `finance.`:

| Was (Amendment 2) | Now |
|---|---|
| `finance.party.*` | `core.party.*` |
| `finance.employer.*` | `core.employer.*` |
| `finance.mission.*` | `core.mission.*` |
| `finance.decision.*` | `core.decision.*` |
| `finance.decision_outcome.*` | `core.decision_outcome.*` |

`finance.execution.*` and `finance.review.*` were requested at the same
time but never applied, because no such event kind exists in this
specification: **Execution** is the `executes` relationship applied to
Finance's own Transaction/Position mutation events, which correctly
carry the `finance.` prefix; **Review** is a `Claim`, created and
tagged entirely through the unprefixed `claim.*` vocabulary (see §25).

**Finance's own entity types**, retaining the `finance.` prefix:
`account`, `asset`, `obligation`, `transaction`, `valuation`,
`position`, `recurring_series`, `assumption_set`, `scenario`,
`tax_jurisdiction`, `exchange_rate`, `tax_position`,
`capital_gain_event`. Not every verb applies to every type —
`capital_gain_event` has no `.closed`; `exchange_rate` in V1 only uses
`.declared`.

`finance.observation.ingested` remains the existing `ingest` event.
`finance.transaction.corrected` remains `finance.transaction.updated`
with a mandatory `reason`.

## 12. Observation model

Unchanged. Verbatim `ingest` events; structured observations parsed
deterministically into `finance.*.declared` events; unstructured
observations handled by AI analysis using the core evidence model
(`000` §11).

## 13. Deterministic calculations (Facts)

Deterministic calculations are pure functions over Finance's own
entity-state projection (§14), with **no model call, at any stage**.
The set is open and extensible. Each is registered with the Metric
Registry (`000` §13.5) under a `finance.`-prefixed metric identifier
(`000` §13.1) so Core can retrieve it without importing this module.

- **Account balance**, **Net worth** (`finance.net_worth`), **Cash
  flow** (by `transaction_category`), **Ownership-attributed and
  household-unioned totals** (§9), **Asset allocation** (Position by
  `asset_category`), **Employer concentration** (Position `issuer`
  against a Person's core `employed_by` link), **Cross-currency
  aggregation** (citing Exchange Rate events, §22).
- **Liquidity Runway** (`finance.liquidity_runway`) — liquid +
  near-liquid assets (`liquidity_classification`) divided by average
  essential + committed monthly outflow, in months.

Every calculation is reproducible, traceable via `why()`/`explain()`,
and independent of any `Claim.confidence` or Tax Position value. Every
registered metric returns `status: unsupported`/`unavailable` rather
than a guess when it cannot be honoured (`000` §13.3) — the identical
discipline Tax Position (§19) already applies.

## 14. Architectural projection model

Finance's own entity-state projection replays only `finance.*` events
into current state for the thirteen entity types in §7. It has no
write path of its own, is deletable and rebuildable, and must be
byte-identical whether rebuilt from scratch or maintained incrementally
(§24, criterion 3) — mirroring `Canon`'s own regression oracle. It does
not fold `claim.tagged` events itself: a financial Claim's current
classification and scope attribution are queried through the shared
Core Evidence Index (`000` §11.1) instead, which is the resolved design
that replaced Amendment 2's assumption of a per-domain side-index. It
reads, but does not re-derive, `core.*` entity state — Party/Employer/
Mission/Decision/Decision Outcome remain the core projection's
responsibility (`000` §5, principle 3), never duplicated here.

## 15. Recurring financial commitments model

Unchanged. A Recurring Series describes an expected future pattern
(`recurring_commitment_type`, §6) and is read only by the Financial
Projection engine (§16) — it never pre-creates canonical
`finance.transaction.declared` events. An actual occurrence is recorded
separately, optionally cross-referenced via the `fulfils` extension to
`structural_relationship` (§6, §8).

## 16. Financial Projection model

Unchanged in substance. Assumption Set, Baseline Projection, Scenario,
Scenario Projection, and Projection Series are Finance's specific
answer to the generic projection contract a `MetricRequest` with a
`horizon` triggers (`000` §13.6). A Decision's `modelled_by` link
(`000` §12) may cite a Scenario when Finance has built one to quantify
the decision's expected outcome.

"If I do X at time T, what is the impact on Y over time?" is answered
exactly as established in Amendment 1: model X as a Scenario, compute
Scenario Projection minus Baseline Projection for metric Y across the
horizon — now expressible as two `MetricRequest`s differing only in
`scenario_id`, whose `MetricResult`s are guaranteed comparable (`000`
§13.6).

## 17. Investment model

Unchanged. A **Position** (instrument, account, quantity, unit price,
currency, cost basis, valuation date, market value, `issuer`) supports
allocation, unrealised gain, and realised gain (via linked Capital Gain
Events, §19). `issuer` may reference a declared Employer's core id
(§8) for precise concentration matching.

## 18. Pension model

Unchanged. An `Account` with `account_type: pension`, `tax_wrapper:
pension_wrapper`, employee and employer contributions as two separate
Recurring Series, an access age, and retirement assumptions as an
Assumption Set. Projected value is a Financial Projection output, never
stored, and must always expose the Assumption Set it used.

## 19. Tax model

Unchanged. **Tax Jurisdiction Configuration** (`id`, `code`,
`tax_year_start`, `tax_year_end`) is declared and revised via
`finance.tax_jurisdiction.declared/updated`, cited by tax year for
reproducibility. A Person or Household links to it via
`tax_resident_in` (§6's extension to `party_relationship`), supporting
relocation and multi-jurisdiction households historically.

**Tax Position** (`id`, subject, `tax_year`, `jurisdiction`,
`estimation_basis`, `amount`, `rule_set_reference`, `provenance`) fails
visibly — `estimation_basis: unsupported`, no `amount` — rather than
guessing, per design principle 2 (§5).

## 20. AI analysis model & insight types

Financial insights are `Claim`s, produced through the unmodified
`ModelAdapter.extract_claims` contract, classified using the core
tagging mechanism and `insight_type` vocabulary (`000` §6, §7, §11) —
`observation`, `interpretation`, `vulnerability`, `opportunity`,
`recommendation`, `warning`, `review`. This document defines no
finance-specific insight types and no finance-specific tagging
mechanism.

A `recommendation` remains a Claim a human evaluates — it never itself
becomes, triggers, or implies a Decision (§21).

## 21. Decision lifecycle — Finance's extensions

The Decision lifecycle mechanism — Decision, Execution, Decision
Outcome, Decision Review, Learning — is defined once, in `000` §12, and
is not restated here. Finance's role is to supply the financial content
that flows through it:

- **Decision** (`core.decision.declared`) — Finance-relevant decisions
  cite financial subjects via `concerns` (Account/Asset/Obligation,
  §10) and may cite a Scenario via `modelled_by` (§16) for a quantified
  expected outcome.
- **Execution** — Finance's own `finance.position.updated` and
  `finance.transaction.declared` events, linked `executes` to the
  Decision (`000` §9), are what carry a financial decision out.
- **Decision Outcome** (`core.decision_outcome.declared`) — its
  `observed_metric` is a registered Finance metric identifier (§13,
  `000` §13.1), typically one of Finance's own deterministic
  calculations.
- **Decision Review** — a `Claim`, tagged `insight_type: review` and
  `review_verdict` (§20), citing the Decision and Decision Outcome as
  provenance. No finance-specific review mechanism exists.
- **Learning** — a financial Decision Review Claim may later be adopted
  into a future Assumption Set (§16) exactly as `000` §12 describes for
  any domain's assumption-holding entity.

### Worked example (unchanged from Amendment 2, renamed events only)

- **Decision** — `core.decision.declared {statement: "Sell PayPal RSUs
  immediately", rationale: "Concentration risk from vested equity",
  expected_outcome: "Reduce concentration risk"}`, `concerns` → Chris
  (core Party), the PayPal Position.
- **Execution** — `finance.position.updated` (quantity reduced) +
  `finance.transaction.declared` (sale proceeds), both `executes` → the
  Decision.
- **Outcome** — `core.decision_outcome.declared {observed_metric:
  "finance.employer_concentration", observed_value: 0.17}`,
  `outcome_of` → the Decision. (The prior value, 0.24, is read by
  replaying the same calculation before the disposal.)
- **Review** — a Claim: `statement: "Objective achieved despite
  subsequent market movement"`, tagged `insight_type: review`,
  `review_verdict: achieved`, `reviews` → the Decision.

## 22. Multi-currency model

Unchanged. GBP household reporting currency (§9); Exchange Rate
observations; any cross-currency calculation must cite the specific
Exchange Rate event(s) used.

## 23. Flight Deck — Finance's contribution

The Flight Deck's general contract — per-tile fields, the four
sections, scope parameterisation, Mission-first organisation, the 5–7
top-page tile cap, and the dispatch-through-the-Metric-Registry rule —
is defined once, in `000` §14 (and §13 for dispatch), and is not
restated here. Finance is one contributing domain, not the Flight
Deck's owner.

**Finance's V1 candidate KPIs** remain product defaults, not
architecture, each populated through the core tile contract by
requesting a registered metric — no finance-specific field, no direct
call into this module's code:

| KPI | Composed from |
|---|---|
| Mission Status | Core mechanism (`000` §8): Core requests Finance's target metric via the Metric Registry (`000` §13) and evaluates status against the Mission's policy. |
| Net Worth | `finance.net_worth` (§13). |
| Financial Freedom Progress | A household-level Mission whose `target_metric` is `finance.net_worth` or a derived ratio — a `mission_status` special case (`000` §8), no finance-specific mechanism. |
| Liquidity Runway | `finance.liquidity_runway` (§13). |
| Strategic Vulnerability | Claims tagged `insight_type: vulnerability` (§20), scoped via `concerns` (§10) to a financial subject, retrieved through the Core Evidence Index (`000` §11.1). |
| Next Decision | Claims tagged `insight_type: recommendation`, retrieved the same way, or an outstanding Decision candidate. |
| Confidence | A rollup of per-metric freshness (`MetricResult.confidence_or_quality`, `000` §13.3), Financial Projection assumption currency, and Tax Position `estimation_basis` — a summary of fields the core tile contract already defines. |

Which indicators actually appear on the shared first page remains a
product decision outside this document's authority.

## 24. Acceptance criteria

**Dependency compliance:**

1. **Uses core event namespaces.** No `finance.party.*`,
   `finance.employer.*`, `finance.mission.*`, `finance.decision.*`, or
   `finance.decision_outcome.*` event exists anywhere in the log —
   these types appear only as `core.*` (or unprefixed `claim.*` for
   Decision Review).
2. **Shared entities and indexes are not duplicated.** Finance's own
   entity-state projection (§14) folds only `finance.*` events — it
   does not fold `claim.tagged` events itself, and does not
   independently re-derive Party, Employer, Mission, Decision, or
   Decision Outcome state from the log. Financial Claim classification
   and scope attribution are read from the shared Core Evidence Index
   (`000` §11.1).
3. **Finance-specific relationships extend core vocabularies cleanly.**
   `tax_resident_in` and `fulfils` appear only as additive entries
   alongside `000`'s `party_relationship`/`structural_relationship`
   values (§6) — no event anywhere redefines or repurposes a core
   relationship value.
4. **Flight Deck finance tiles conform to the core tile contract.**
   Every finance-sourced KPI populates exactly the field set `000` §14
   defines — no undocumented additional field, no missing required
   field.
5. **Finance registers, Core never imports.** Every metric listed in
   §13 is retrievable by Core through the Metric Registry (`000` §13.5)
   using only `metric_id`; no Core-level code path calls a Finance
   calculation function directly.

**Substrate compliance:**

6. One log. 7. Append-only. 8. **Rebuild parity** — Finance's own
   entity-state projection, for its thirteen entity types, is
   byte-identical whether rebuilt from scratch or maintained
   incrementally. 9. Deterministic facts. 10. Model-failure containment.

**Household and scope:**

11. No double-counting of joint ownership. 12. Household/individual
    reconciliation. 13. Household is never an ownership target.

**Financial Projections:**

14. Baseline reproducibility. 15. Transparent scenario deltas.
16. No forecast contamination.

**Recurring commitments:**

17. No pre-created transactions.

**Investments:**

18. Asset allocation and employer concentration are derivable from
    Position + the core Employer entity + core `employed_by` links
    alone — no string-matching fallback required.

**Pensions:**

19. Exposed assumptions.

**Tax:**

20. Historical jurisdiction. 21. Visible uncertainty — an unsupported
    Tax Position has no `amount`; an unsupported financial metric
    request returns `status: unsupported`, never a guessed `value`.

**Decision lifecycle (finance instance):**

22. **Full loop traceability, financially instantiated.** For any
    Decision concerning a financial subject, the chain Decision →
    Execution (`finance.position.*`/`finance.transaction.*`) →
    Decision Outcome → Decision Review is fully resolvable using only
    the relations `000` §9 and §12 define — no finance-specific
    linking convention exists or is needed.
23. **Learning is citable.** A financial Decision Review Claim can be
    referenced by a later Decision's `informed_by` link or adopted into
    a later Assumption Set, using the exact same citation mechanism as
    any other Claim.

**Ownership and history:**

24. Ownership is historical. 25. Zero new core dependencies.

## 25. Resolved questions from Amendment 3's instructions

Two of the seven namespace renames requested alongside Amendment 3 —
`finance.execution.* → core.execution.*` and `finance.review.* →
core.review.*` — were **not applied**, because no such event kind
exists in this specification to rename, and inventing one would
contradict `000` §12's explicit design: Execution is a relationship
(`executes`), not an entity; Decision Review is a `Claim`, not an
entity. This remains a resolved interpretation, unaffected by Amendment
4's reference-only changes.
