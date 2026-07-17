# Spec 000 — Foundry Core Domain Model

Status: **Adopted** (Revision 2 — adds the Metric Provider contract)
Layer: **Product domain, above the substrate** (see `docs/architecture.md`)
Depends on: `foundry.eventlog`, `foundry.canon`, `foundry.kernel`, `foundry.models`
Does not modify: `src/foundry/eventlog.py`, `src/foundry/canon.py`, `src/foundry/kernel.py`
Depended on by: `001-finance-domain-model.md` (adopted, Amendment 3)

This document was originally proposed to extract the concepts in
`001-finance-domain-model.md` that are demonstrably domain-agnostic —
Party, Mission, Employer, the Decision lifecycle, the evidence/tagging
mechanism, the shared event grammar, the Flight Deck contract — into a
shared specification every domain depends on, instead of each domain
re-declaring them. It was adopted, and `001` was amended (Amendment 3)
to depend on it rather than duplicate it.

**Revision 2** resolves the one gap identified at adoption time:
neither this document nor `001` defined how Mission status (§8) or a
Flight Deck tile (§14) actually retrieves a metric "from whichever
domain owns it." §13, the Metric Provider contract, is that definition.
It also resolves the smaller open question left in the original
proposal — whether Claim tags and subject links are indexed once,
centrally, or once per domain (§11.1).

---

## 1. Purpose

Foundry's substrate (`eventlog.py`, `canon.py`, `kernel.py`) is
domain-agnostic by construction — it knows nothing about money, career,
or health. The Finance Domain (001) is the first *product* layer built
on that substrate, and in building it, a second layer emerged without
being asked for: a set of entities and mechanisms — a person or group
who can hold things, an organisation they're affiliated with, a named
objective, a way to record and learn from a decision, a way to
distinguish a relationship from a classification, a way to retrieve a
deterministic figure without knowing which domain computed it, a way to
display a scoped, evidence-backed summary — that have nothing to do
with finance specifically and that any future domain (career, health,
household, education, knowledge) will need in an equivalent form.

This document is that second layer, made explicit.

## 2. Scope

### In scope

- The shared five-verb event grammar every domain spec follows.
- Party, Employer, and Mission as domain-agnostic entities.
- The relationship-link vs. classification-tag distinction, and the
  relationship vocabularies that are not tied to any one domain's
  subject matter.
- Scope attribution and drill-down resolution as a general pattern.
- The evidence model: how any domain represents interpreted knowledge
  without inventing a parallel claim system, and the one shared index
  that makes it queryable (§11.1).
- The Decision → Execution → Outcome → Review → Learning lifecycle.
- The Metric Provider contract: how Core retrieves a deterministic
  figure from whichever domain owns it, without importing that
  domain's calculation code (§13).
- The Flight Deck output contract's general shape: per-tile fields,
  scope parameterisation, the Mission-first organising principle, and
  the 5–7 top-page tile cap.

### Explicitly out of scope

- Anything with financial, monetary, or accounting meaning. All of
  this remains in Finance (§16).
- Anything career-, health-, education-, or knowledge-domain-specific.
- Redesigning any extracted concept beyond what's required to resolve
  the dispatch gap this revision closes.
- A concrete Metric Provider implementation — no Python interface,
  base class, or plugin mechanism is prescribed (§13.4).

## 3. Relationship to domain specifications

This document defines entities and mechanisms; it does not define a
domain. A domain specification (Finance, and eventually Career, Health,
etc.) **depends on** this document — by consuming what's defined here,
adding its own domain-specific entities and vocabulary extensions, and
never redefining anything this document already defines.

Concretely: a domain spec

- may declare its own entity types, event kinds (`<domain>.<type>.*`),
  and controlled vocabularies for concepts specific to it;
- may **extend** a vocabulary defined here additively;
- must **not** re-declare Party, Employer, or Mission as its own
  entity type, and must not append events under a domain-prefixed
  shadow of `core.party.*`/`core.employer.*`/`core.mission.*` (§4);
- may link its own resources as valid subjects for scope attribution
  (§10) and as valid `concerns` targets in the Decision lifecycle
  (§12), without this document needing to know those resource types
  exist;
- must **register**, not calculate ad hoc, any deterministic figure it
  wants Core (Mission status, the Flight Deck) to retrieve — via the
  Metric Provider contract (§13), not a direct function call Core
  imports.

## 4. Terminology

- **projection** (unqualified) — the architectural term: a
  deterministic, model-free materialised view computed by folding the
  event log (`Canon`, each domain's own entity-state projection, and
  the Core Evidence Index, §11.1).
- **relationship link** — an event asserting that two addressable
  entities are related. `target` is always another entity's id.
- **typed tag** — an event asserting a controlled-vocabulary
  classification of one entity. There is no second entity on the other
  end, only a vocabulary value.
- **metric** — a named, deterministically computable figure owned by
  exactly one domain, retrieved through the Metric Provider contract
  (§13), never computed by Core itself and never by a model.
- **domain** — a product layer above the substrate (Finance; in future,
  Career, Health, Household, Education, Knowledge) that declares its
  own entities and event kinds and depends on this document for the
  entities and mechanisms that aren't its own to define.

## 5. Design principles

Every domain inherits the five constitutional invariants from
`docs/architecture.md` directly (append-only log; entity mutations are
events; deterministic replay; model identity is provenance; model
failure never corrupts the substrate). This document adds:

1. **No domain requires a substrate change.** Everything here — shared
   entities, the tagging mechanism, the Decision lifecycle, the Core
   Evidence Index, the Metric Registry — reuses `EventLog.append`,
   `kernel.link()`, and `Canon`'s existing fold behaviour unmodified.
   `canon.py` continues to see only
   `claim.derived/updated/superseded/linked`, plus `claim.tagged`,
   which it silently ignores the same way it already ignores `ingest`
   events. The Metric Registry (§13.5) is operational wiring, not
   event-sourced state, and touches nothing.
2. **A relationship link's `relation` is always drawn from a
   controlled relationship vocabulary; a classification is always a
   typed tag, never a relationship.** A property of the event grammar
   itself (§6), binding every domain equally.
3. **A shared entity has exactly one canonical event stream.** Party,
   Employer, and Mission are declared and mutated via `core.<type>.*`
   events (§6). A domain that needs to attach domain-specific
   attributes to one of these entities appends to that *same* stream —
   it does not maintain a parallel, domain-prefixed shadow history.
4. **Controlled vocabularies are additive and centrally owned, but
   extensible.** A vocabulary defined here (§7) may be extended with
   new values by a dependent domain spec; it may never be redefined or
   have an existing value repurposed.
5. **No component may claim more precision than it has.** Any domain
   producing an estimate under uncertainty must say so structurally.
   Extended by this revision: **a metric provider must never invent a
   value, and Core must never ask an AI model to calculate one** —
   `unsupported`/`unavailable` is always the honest alternative (§13.3).
6. **The Flight Deck's organising principle is Mission status, not raw
   reporting**, across every domain that contributes to it. Extended by
   this revision: **the domain calculates a metric; Core evaluates
   mission status against it; AI may explain the result but cannot
   determine it** (§8, §13.6).

## 6. Shared event grammar

Every domain's events are appended to the **same `EventLog` instance**.
Entities defined by this document use an unprefixed `core.` kind;
domain-specific entities use that domain's own prefix. `Claim`
mutations remain entirely unprefixed (`claim.*`).

| Verb | Payload shape | Meaning |
|---|---|---|
| `<prefix>.<type>.declared` | `{..attributes}` | A new entity is asserted to exist. |
| `<prefix>.<type>.updated` | `{entity_id, ..revised attributes, reason}` | An attribute is revised, with a reason. |
| `<prefix>.<type>.closed` | `{entity_id, reason}` | The entity reaches a terminal lifecycle state. |
| `<prefix>.<type>.linked` | `{entity_id, relation, target: <entity id>}` | A relationship to another addressable entity (§9). `relation` from a controlled relationship vocabulary. |
| `<prefix>.<type>.tagged` | `{entity_id, tag_type, value, reason?}` | A classification of this entity (§11). `tag_type` and `value` from controlled vocabularies. |

For `Claim`, the tagging verb is `claim.tagged` — unprefixed, since
classifying a claim is core-substrate-adjacent, not owned by any one
domain. `Canon._apply` requires no change: it already ignores event
kinds it doesn't explicitly fold. `claim.tagged` events, together with
the `concerns`-relation subset of `claim.linked` events (scope
attribution, §10), are folded into **one shared Core Evidence Index**
(§11.1) — not duplicated by each domain's own projection. Domains query
that index; they do not maintain a silent copy of it.

Where a domain needs to create a `Claim` whose provenance is not an
`ingest` event (a Decision Review, §12), it appends a `claim.derived`
event directly via `EventLog.append`, bypassing `kernel.derive()`
(gated to `ingest`-sourced events only). This is legitimate and
requires no kernel change: `kernel.ingest()` is itself nothing but a
thin wrapper over the same call.

## 7. Controlled vocabularies

Core-owned, additive, extensible by dependent domains, never redefined.

| Vocabulary | Core values | Extended by |
|---|---|---|
| `party_type` | `person`, `household` | — |
| `party_relationship` | `member_of`, `employed_by` | Finance adds `tax_resident_in` |
| `structural_relationship` | `concerns`, `informed_by`, `modelled_by`, `outcome_of`, `reviews`, `executes`, `revises` | Finance adds `fulfils` |
| `tag_type` | `insight_type`, `review_verdict` | — |
| `insight_type` | `observation`, `interpretation`, `vulnerability`, `opportunity`, `recommendation`, `warning`, `review` | — |
| `review_verdict` | `achieved`, `partially_achieved`, `not_achieved`, `inconclusive` | — |
| `mission_status` | `on_track`, `at_risk`, `off_track`, `achieved`, `abandoned` | — |
| `metric_status` | `available`, `unavailable`, `unsupported`, `stale`, `error` | — |

Vocabularies entirely about financial ownership or classification are
not extracted. They stay in Finance (§16).

## 8. Entities

| Entity | Represents | Lifecycle states |
|---|---|---|
| **Party** | A person, or a group of persons treated as a planning/aggregation scope. | active, closed |
| **Employer** | An organisation a Person is or was affiliated with. | active, defunct |
| **Mission** | A named objective with an optional target and date. | active, achieved, abandoned |

Common fields on every entity: `id`, `status`, `provenance`,
`asserted_by`, `history`, plus whatever domain-specific attributes a
dependent domain attaches via `core.<type>.updated` (§5, principle 3).

### Party

`party_type` (§7): `person` or `household`. A `Party` with
`party_type: person` and relationship `self` is the primary user. A
`Party` with `party_type: household` is a **group container**: it
aggregates and plans across its members, but holds nothing itself.

**Group pattern.** A group-type Party is never itself the holder of a
domain's resources. Members link via `member_of`. Any metric a domain
computes "for the group" should be a **union over what members hold**,
not a **sum per member**.

### Employer

Fields: `name`, `industry` (optional). A Person's affiliation history is
the ordered sequence of `employed_by` links over time; the most recent
is treated as current. **Stated limitation:** this document does not
represent employment gaps or concurrent multiple employers.

### Mission

Fields: `name`, `target_metric` (a metric identifier, §13.1 — e.g.
Finance's `finance.net_worth` or a future Career domain's
`career.time_to_promotion`), `target_value` or `target_range`,
`target_date` (where relevant), `tolerance`/RAG policy.

`mission_status` (§7) is **computed, never declared**, in three
strictly separated steps:

1. **The owning domain calculates the metric** — Core issues a
   `MetricRequest` (§13.2) through the Metric Registry (§13.5), scoped
   to the Mission's subject, with `horizon` through `target_date` when
   a forward view is needed.
2. **Core evaluates mission status** by comparing the returned
   `MetricResult` (§13.3) against the Mission's declared
   `target_value`/`target_range` and `tolerance`.
3. **AI may explain the result but cannot determine it** — a
   model-generated narrative about *why* a Mission is off track is a
   `Claim` (§11), never an input to, or substitute for, the
   deterministic comparison itself.

Missions are the organising unit of the Flight Deck (§14).

## 9. Relationships

Relationship links use the `.linked` verb (§6), governed by exactly one
controlled vocabulary — never a bare string (design principle 2).

### Party relationships (core)

| Relation | Direction | Meaning |
|---|---|---|
| `member_of` | Person → household-type Party | Group membership. |
| `employed_by` | Person → Employer | Current or past affiliation. |

Finance additively extends this vocabulary with `tax_resident_in`.

### Structural relationships (core)

| Relation | Meaning |
|---|---|
| `concerns` | An Insight/Recommendation/Decision/Decision Outcome relates to a subject (§10). |
| `informed_by` | A Decision, or a domain's own assumption-holding entity, cites a Claim or a domain-specific quantifying model that shaped it. |
| `modelled_by` | A Decision cites whatever domain-specific mechanism quantified its expected outcome. |
| `outcome_of` | A Decision Outcome relates to its Decision. |
| `reviews` | A Decision Review Claim relates to the Decision it reflects on. |
| `executes` | A domain-specific entity mutation relates to the Decision it carries out. |
| `revises` | A newer Decision, or assumption-holding entity, relates to the one it supersedes-in-effect. |

Finance additively extends this vocabulary with `fulfils`.

Ownership relationships are **not** extracted — they describe
legal/financial ownership of a domain resource, which is Finance's
concept (§16).

## 10. Scope attribution & drill-down model

Any interpreted or recorded knowledge — an Insight, a Recommendation, a
Decision, a Decision Outcome — links to one or more **subjects** via
`concerns` (§9): a Party, an Employer, a Mission, or a domain-specific
resource that domain declares as a valid subject. A `MetricRequest`'s
`scope` (§13.2) uses this identical subject model.

- **For Claims**: `kernel.link(claim_id, "concerns", subject_id)`.
- **For domain entities**: `<prefix>.<type>.linked {relation:
  "concerns", target: subject_id}`.

**Drill-down resolution:**

- **Group view** — subject is a group-type Party, or resolves via a
  domain's own membership/ownership relations to a group member.
- **Individual view** — subject is a specific person-type Party, or a
  resource that person holds a relevant relation to.
- **Resource view** — subject is a specific domain resource, directly.

## 11. Evidence model

Interpreted knowledge is always a `Claim` in the existing `Canon`. **No
domain may introduce a parallel claim system** — this follows from
constitutional invariant 4 (model identity is provenance): a second,
differently-shaped record of interpreted knowledge would fracture
provenance into two systems.

Every Claim's current classification is a **typed tag** (§6), not a
relationship: `insight_type` (§7) — what kind of interpretation this
is; `review_verdict` (§7) — used specifically by Decision Review
Claims (§12). A Claim's current value for a given `tag_type` is the
value of its most recently applied tag; reclassification is a new tag
event, not an edit.

**Citation discipline:** confidence is stored and displayed, never
arithmetic. A `recommendation`-typed Claim never itself alters
canonical or projected state in any domain. Every Claim cited as
`informed_by` evidence remains traceable to its own source event(s)
via `why()`/`explain()`.

### 11.1 The Core Evidence Index

Claims, their tags, and their `concerns` links are Core concepts (§4),
so exactly **one** shared, Core-owned projection indexes them — not one
per domain. This resolves the open question left after the original
proposal, where each domain's own entity-state projection was assumed
to fold `claim.tagged` events into its own side-index.

**Why this doesn't touch `canon.py`.** The index is a *second*
projection, a sibling to `Canon`, not a modification of it — the same
relationship each domain's own entity-state projection already has to
`Canon`. It folds `claim.tagged` events and `concerns`-relation
`claim.linked` events into two lookups: `claim_id → current tags` and
`subject_id → concerning claim ids`. `Canon._apply` requires no change
— it already ignores event kinds and link relations it doesn't act on,
and the Core Evidence Index reads the same log independently, exactly
as any projection does. **What *would* violate the kernel
architecture** is storing this state *inside* `Claim` itself — adding a
`tags` field to the dataclass in `canon.py` — which is precisely what
this design avoids by keeping the index external and additive.

Every domain — including the Metric Provider dispatch layer (§13) and
the Flight Deck (§14) — reads this one index for "which Claims concern
this subject" and "what is this Claim's current `insight_type`,"
rather than scanning the log or maintaining a redundant per-domain
copy.

## 12. Decision lifecycle

Foundry's operating model —

    Observation → Understanding → Decision → Execution → Outcome
    → Reflection → Learning

— is realised with the mechanisms above, entirely domain-agnostically.
A domain supplies Observation and Understanding; everything from
Decision onward is defined here, once.

| Stage | Mechanism |
|---|---|
| Decision | `core.decision.declared` (below). |
| Execution | Domain-specific entity-mutation events, linked to the Decision via `executes` (§9). |
| Outcome | `core.decision_outcome.declared` (below). |
| Reflection | Decision Review — a `Claim` (below). |
| Learning | The Decision Review Claim, retrievable and citable like any other Claim. |

### Decision

`core.decision.declared`: `id`, `statement`, `rationale`,
`expected_outcome`, optionally `modelled_by` a domain-specific
quantifying mechanism, `informed_by` links to Claims, `concerns` links
to subjects (§10), `actor`, `ts`. No `.closed` state — a change of
course is a new Decision, linked `revises` to the one it
supersedes-in-effect.

### Execution

Not a new entity — it *is* whatever domain-specific events represent
the decision actually being carried out, each linked back via
`executes`.

### Decision Outcome

`core.decision_outcome.declared`, linked `outcome_of` its Decision and
`concerns` its subjects: `id`, `decision_id`, `observed_metric` (a
metric identifier, §13.1, resolved via the same Metric Registry any
other metric request uses), `observed_value`, `observed_at`,
`provenance`. A before/after comparison needs no new field: both values
are the same metric replayed at two points in the log's history.

### Decision Review

A **`Claim`**, created by appending `claim.derived` directly, with
`provenance` pointing at the Decision's and Decision Outcome's event
ids. Tagged `insight_type: review` and `review_verdict` (§7). Linked
`reviews` to its Decision and `concerns` to the same subjects.

### Learning

A Decision Review Claim, once created, is an ordinary Claim: retrievable
via `why()`, and eligible to be referenced by a later Decision's
`informed_by` link, or adopted into whatever domain-specific
configuration entity that domain uses to encode assumptions.

### Illustrative example (domain-neutral)

- **Decision** — `statement: "Accept the internal transfer offer"`,
  `expected_outcome: "Increase household income without a change of
  employer"`, `concerns` → a Person, their current Employer.
- **Execution** — whatever domain-specific event records the transfer
  taking effect, `executes` → the Decision.
- **Outcome** — `observed_metric: "career.household_income"`,
  `observed_value` at `observed_at`, `outcome_of` → the Decision.
- **Review** — a Claim: `statement: "Objective achieved; income rose as
  expected"`, tagged `insight_type: review`, `review_verdict: achieved`,
  `reviews` → the Decision.

(Finance's own PayPal RSU / concentration-risk example, in `001` §21,
is the financial instantiation of this identical pattern.)

## 13. Metric Provider contract

Resolves the dispatch gap identified when this document was adopted:
Mission status (§8) and Flight Deck tiles (§14) both need to retrieve a
deterministic figure "from whichever domain owns it," and nothing
before this revision defined how that dispatch happens. This is a
contract, not an implementation — no Python interface, base class, or
plugin mechanism is prescribed.

### 13.1 Metric identity

A metric identifier is a stable, globally unique, namespaced string:
`<domain>.<name>` — e.g. `finance.net_worth`,
`finance.liquidity_runway`, `finance.financial_independence_date`,
`career.optionality_score`, `health.resting_heart_rate`. The domain
prefix matches that domain's event-kind prefix (§6).

Metric identifiers are **append-only contracts**:

- A metric identifier's *meaning* must never be silently redefined. A
  domain that needs to change what a metric fundamentally measures
  declares a new identifier.
- A metric's *calculation method* may still evolve without a new
  identifier, via `calculation_version` (§13.3) — the same meaning,
  computed more accurately over time.
- Every `MetricResult` carries both `metric_id` and
  `calculation_version`, so a historic result remains interpretable
  after the owning domain's calculation logic moves on.

### 13.2 Metric request

A `MetricRequest` carries, at minimum:

| Field | Meaning |
|---|---|
| `metric_id` | Which metric (§13.1). |
| `scope` | A subject from the Core subject model (§10). |
| `as_of` | The point in time the value should reflect. |
| `horizon` *(optional)* | A forward-looking window (§13.6). |
| `assumption_set_id` *(optional)* | Which domain-specific assumption state to project under. |
| `scenario_id` *(optional)* | Which domain-specific hypothetical to project under; absent means Baseline. |
| `parameters` *(optional)* | A domain-defined bag for anything metric-specific the standard fields don't cover. |
| `requested_calculation_version` *(optional)* | Pin to a specific historical version; absent means current. |

`scope` reuses §10's subject model exactly — no second scope taxonomy
exists for metrics.

### 13.3 Metric result

A `MetricResult` carries, at minimum:

| Field | Meaning |
|---|---|
| `metric_id` | Echoes the request. |
| `value` | The computed figure, if any. |
| `unit_or_currency` | What `value` is denominated in. |
| `scope`, `as_of` | Echo the request. |
| `status` | `available` / `unavailable` / `unsupported` / `stale` / `error` (`metric_status`, §7). |
| `calculation_version` | Which version of the owning domain's calculation produced this. |
| `input_references` | Source event ids the calculation replayed. |
| `evidence_references` | Any Claims cited. |
| `assumption_references` | The specific assumption/configuration state used, where applicable. |
| `generated_at` | When this result was computed — distinct from `as_of`. |
| `confidence_or_quality` | A data-quality/estimation-basis assessment — never arithmetic (principle 5). |
| `limitations` | Structured or free-text caveats. |
| `projection_series_reference` *(optional)* | A pointer to a full dated series (§13.6). |
| `drill_down_target` *(optional)* | Where a consumer should link to next. |

**Status semantics:** `available` — a real, current value. `stale` — a
real value, computed from data older than expected freshness, still
returned and flagged. `unavailable` — supported in principle, but the
domain lacks sufficient data yet. `unsupported` — the provider cannot
honour this request shape, *or* the `metric_id` has no registered
provider at all (§13.5). `error` — an unexpected fault, distinct from
the deliberate, honest `unsupported`.

**`unavailable` and `unsupported` results must fail visibly. A
provider must never invent a value, and Core must never ask an AI model
to calculate one** — constitutional invariant 3 applied to every
metric.

### 13.4 Metric Provider

Each domain that owns metrics implements, conceptually, a Metric
Provider that:

- **Declares** which metric identifiers it owns.
- **Validates** an incoming request, rejecting unsupportable shapes as
  `unsupported` before attempting calculation.
- **Calculates** deterministically — no model call is ever part of a
  metric calculation itself.
- **Exposes** its current `calculation_version`, returning
  `unsupported` for a `requested_calculation_version` it can no longer
  reproduce.
- **Returns complete lineage** — every field in §13.3, every time.
- **Never writes a derived metric value into canonical observed
  state** unless the owning domain's own specification separately
  defines a genuine observation event for it.

No concrete interface is prescribed — that is an implementation
decision for whenever this contract is built.

### 13.5 Metric Registry

A lightweight, pure-routing contract between Core and every domain's
Metric Provider:

- Each `metric_id` maps to **exactly one** authoritative provider.
- **Duplicate ownership fails closed** — a second domain registering an
  already-owned `metric_id` is rejected at registration time.
- **Unknown `metric_id` fails closed** — returns `status: unsupported`,
  never an error indistinguishable from a bug, never a fabricated
  value.
- **Core dispatches every metric request through the registry.** Core
  code never imports or calls a domain's calculation function directly.
- **Domains register their metric definitions explicitly** — no
  implicit discovery.
- **Registration order must not alter results** — ownership is by
  declared `metric_id`, never by registration order, because duplicate
  ownership is rejected outright rather than resolved by precedence.
- **The registry contains no business calculation logic** — routing
  only: `metric_id → provider`.

The registry is **operational wiring, not event-sourced data** — the
same category as `Kernel`'s constructor-injected `ModelAdapter`. It is
rebuilt fresh from each domain's explicit registration call every time
the system starts; it needs no persistence and introduces no new
source of truth about what's true, only about which domain to ask.

### 13.6 Projection contract

When a `MetricRequest` includes `horizon`, `assumption_set_id`, or
`scenario_id`, the `MetricResult` is **either** a point-in-time
projected value, **or** a reference to a dated Projection Series
(`projection_series_reference`) for a caller that wants the full
trajectory.

**Baseline and Scenario results must remain distinguishable and
comparable.** A `MetricResult`'s `scenario_id` (present or absent) is
always inspectable, so two results for the same
`metric_id`/`scope`/`horizon` — one Baseline, one Scenario — are the
same shape and directly diffable. This is the general form of
Finance's "Scenario Projection minus Baseline Projection" delta
(`001` §16), stated once so any domain's scenario mechanism works
identically.

## 14. Flight Deck output contract

The Flight Deck is the household's single output surface, assembling
Current State, Forecast, Interpretations, and Decisions from every
contributing domain into one provenanced, scope-aware view. It is a
**Core composition surface**: it composes tiles by dispatching
`MetricRequest`s through the Metric Registry (§13.5) and never imports
or calls a domain's calculation code directly.

**Scope.** Every request is parameterised by scope, resolved per §10.

**Each tile:**

- References one or more metric identifiers (§13.1).
- Requests their `MetricResult`s through the Metric Registry.
- Applies its own declared display and RAG policy (typically mirroring
  a linked Mission's tolerance policy, §8, but not required to).
- Links to a domain-owned drill-down page.
- Preserves every relevant `MetricResult` field, in particular the
  full calculation and evidence references — Core neither strips nor
  summarises lineage on the way to render.

Populated this way, every tile carries: current value, trajectory
(`projection_series_reference`, when present), variance from target
(against a linked Mission), RAG status/`mission_status`, data
confidence/freshness, strategic vulnerability (a linked Claim tagged
`insight_type: vulnerability`, via the Core Evidence Index, §11.1),
next decision (a linked Claim tagged `insight_type: recommendation`),
drill-down target, and calculation/evidence references — all sourced
from the `MetricResult`/`Claim` contracts already defined, not a
separate Flight-Deck-specific shape.

**Sections**, kept visually and structurally distinct: Current State,
Forecast, Interpretations (Claims grouped by `insight_type`, via the
Core Evidence Index), Decisions.

**Mission-first organisation.** The first page's top-level tiles are
organised around active Mission status (§8), not a flat metric list.
Metrics without a linked Mission remain available through drill-down.

**Top-page constraint:** 5–7 high-level indicator tiles. Which
indicators appear, and which domain each draws from, is a product
decision outside this document's authority.

**Core is capable of composing tiles from multiple domains without
importing domain calculation code directly** — a direct consequence of
dispatching exclusively through the Metric Registry (§15, criteria 9
and 15).

The Flight Deck is a **consumer**, never a producer: rendering it must
never append an event, in any domain's event stream.

## 15. Acceptance criteria

**Foundational:**

1. **Zero substrate change.** No entity, mechanism, or relation in this
   document requires modifying `eventlog.py`, `canon.py`, or
   `kernel.py`.
2. **Single canonical stream per shared entity.** All mutations to
   Party/Employer/Mission use `core.<type>.*`.
3. **No domain redefines a core vocabulary value.**
4. **A second domain requires no change to this document.**
5. **Tag/link integrity holds across domains.** In no domain's event
   stream does a `.linked` event's `relation` hold a classification
   value, or a `.tagged` event's `value` hold another entity's id.
6. **A Decision lifecycle instance is fully traceable** for any domain,
   using only the relations defined in §9 and §12.
7. **Learning is citable without a second knowledge system.**
8. **The Flight Deck can compose tiles from more than one domain**
   without this document's contract changing.

**Metric Provider contract:**

9. **No direct import.** A Finance metric can be requested by Core
   through the Metric Registry without Core's dispatch code importing
   or referencing any Finance-specific calculation function.
10. **Unknown metrics fail closed.** A `MetricRequest` for an
    unregistered `metric_id` returns `status: unsupported` — never an
    error indistinguishable from a bug, never a fabricated value.
11. **Duplicate registration fails closed.** Two providers registering
    the same `metric_id` results in the second being rejected at
    registration time, never silently overriding the first.
12. **Scope routes correctly.** A `MetricRequest` scoped to a household
    Party and one scoped to a person Party both dispatch through the
    identical registry mechanism to the owning domain's own
    household-aggregation and individual-attribution calculations, with
    no special-casing in Core.
13. **Lineage survives dispatch.** Every `MetricResult` field —
    input, evidence, and assumption references in particular — is
    identical whether inspected at the provider or after Core's
    dispatch.
14. **Mission status is reproducible.** The same `MetricResult` and the
    same declared target/tolerance policy always yield the same
    `mission_status`.
15. **Cross-domain composition.** The Flight Deck can compose a page
    from two independently registered mock domain providers, neither of
    which references the other's code.
16. **Baseline/Scenario distinguishability.** A Baseline and a Scenario
    `MetricRequest` for the same `metric_id`/`scope`/`horizon` return
    `MetricResult`s distinguishable by `scenario_id` and directly
    comparable.
17. **No AI-calculated metrics.** No `metric_id` is ever registered to,
    or calculated by, a `ModelAdapter`; every `MetricResult` with
    `status: available` was produced by deterministic domain code.
18. **One evidence index.** Claim tags and subject-attribution links for
    any Claim are queryable through exactly one Core Evidence Index
    (§11.1) — no domain maintains an independent copy.

## 16. What moves, what stays, and why

| Concept | Disposition | Why |
|---|---|---|
| Shared event grammar | **Core** | Not financial; every domain needs the identical convention. |
| Party, Employer, Mission | **Core** | Not financial concepts; Finance's household aggregation *arithmetic* stays in Finance. |
| `party_relationship`, `structural_relationship` (base values) | **Core**, Finance extends with `tax_resident_in`, `fulfils` | Generic relations; Finance's additions are financial. |
| Tagging mechanism, `tag_type`, `insight_type`, `review_verdict` | **Core** | Classifying a Claim is core-substrate-adjacent. |
| Decision, Decision Outcome, Decision Review, Learning | **Core** | The learning loop is domain-agnostic by design. |
| Core Evidence Index | **Core** (new, Revision 2) | Claims and tags are Core concepts; one shared index avoids per-domain duplication. |
| Metric Provider contract, Metric Registry, `MetricRequest`/`MetricResult` | **Core** (new, Revision 2) | Cross-domain dispatch is inherently Core infrastructure — the same reasoning as the event grammar itself. |
| Flight Deck contract shape | **Core** | The Flight Deck is the household's surface, not any one domain's. |
| `ownership_relationship`, financial entities, Recurring Series, Assumption Set, Scenario, Financial Projection, tax concepts | **Finance** | Inherently financial. |
| Household aggregation arithmetic | **Finance** | The *pattern* (group container, union-not-sum) is Core (§8); the money-specific arithmetic stays. |
| Finance's 7 candidate Flight Deck KPIs | **Finance** | Product defaults; the contract they plug into is Core. |

## 17. Adoption status

`001-finance-domain-model.md` Amendment 3 adopted this document for
everything in §16's "Core" rows as of the original proposal. This
revision adds the Metric Provider contract and the Core Evidence
Index's resolved design; `001` requires only concise reference
amendments to reflect them — no new duplication, no redesign of
anything already adopted. See `001`'s own changelog for exactly what
was touched.
