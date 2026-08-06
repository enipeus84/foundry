# RFC-015 — Capture Target Registry

**Status:** **ARCHITECTURE FROZEN — 2026-08-05** at the Governor freeze gate
(HEAD `0ad18b3`). Approved GO WITH AMENDMENT at architecture review; the
amendment is applied. Freeze record:
[`RFC-015-architecture-freeze-record.md`](../reviews/RFC-015-architecture-freeze-record.md).
The approved [Phase 2A Diagnostic Event Amendment](../reviews/RFC-015-phase-2a-diagnostic-event-amendment.md)
adds the programme's second and final authorised event kind; no further
canonical event kinds are authorised without Governor approval.
Phase 0 has shipped; Phase 1 is open for implementation.
**Title:** Capture Target Registry *(amended by the Governor from "Capture
Target Registration": the architecture concerns the derived registry,
discovery, compatibility, lifecycle and retirement of capture targets;
registration is a workflow within that boundary, not the boundary itself)*
**Depends on:** RFC-011 (acquisition), RFC-012 (Operations), RFC-013 (capture
contracts; number contested and expressly **not** renumbered during this burn)
**Supersedes in part:** the provisional "Asset Registry & Provenance" boundary
recorded in RFC-012 §2.8

---

## 0. Naming and governance check *(Check 0 — performed before drafting)*

RFC-012 §2.8 registered two provisional working boundaries:

```text
RFC-013  Asset Registry & Provenance       PROVISIONAL working boundary
RFC-014  Governed Corrections              PROVISIONAL working boundary
```

Both are still recorded as provisional in `docs/rfcs/index.md`. Two facts
constrain the number this mission may take:

1. **RFC-013's number is already contested.** The number was consumed by
   *Operations Capture Contracts*, whose implementation report opens by
   stating that "RFC-number and architecture reconciliation remain a Governor
   decision before merge; this report claims neither a resolved RFC number nor
   architectural approval." The provisional *Asset Registry & Provenance*
   boundary was displaced without a recorded decision. That is the governance
   debt RFC-013 left behind, and this RFC does not resolve it — only the
   Governor can.
2. **RFC-014 is live.** *Governed Corrections* is an unstarted but reserved
   boundary with a specific, distinct subject (who may correct a confirmed
   value, and how restatement renders). Taking 014 for capture-target
   registration would repeat exactly the overwrite that produced the RFC-013
   debt.

**Recommendation: this mission is RFC-015 — Capture Target Registry.**
Taking the next free number costs nothing and leaves both contested boundaries
intact for the Governor to settle independently.

> **Governor ruling (approved).** RFC-015 is the correct programme number.
> RFC-014 remains reserved for Governed Corrections. The displacement of the
> provisional RFC-013 boundary is recorded governance debt and must not be
> repeated by overwriting RFC-014. **Capture Contracts is not retrospectively
> renumbered during this burn.**

### Does this belong with "Asset Registry & Provenance"? — *No*

RFC-012 §2.8 explicitly required its successor to challenge whether registry
curation, asset detail, provenance investigation and timeline browsing belong
in one RFC, warning that "the same rhythm test that split RFC-012 from them may
well split them from each other." Applying that test:

| Rhythm | Surface | User mode |
|---|---|---|
| **Occasional curation** | Capture-target registration and retirement | "What may Foundry record against?" |
| **Rare investigation** | Asset detail, provenance timeline, audit | "Why does Foundry believe this?" |

These are different rhythms, different users' mental modes, and — decisively —
different *dependency directions*. Registration is a **precondition** of the
weekly loop: without it RFC-013's contracts are inert, which is the defect this
mission exists to fix. Provenance investigation is a **consequence** of the
weekly loop having run. Shipping them together would block a load-bearing fix
behind an investigative surface nobody needs until history exists.

**The provisional "Asset Registry & Provenance" boundary should therefore be
decomposed, not inherited:**

```text
RFC-015  Capture Target Registry                  this document
RFC-016  Asset Detail & Provenance Investigation  successor; not proposed here
```

> **Amendment to G3 — Governor ruling GD-1, 2026-08-06.** The successor's
> **number** is reassigned: *Asset Detail & Provenance Investigation* is now
> **RFC-017**, and RFC-016 is *Mission Target Framework*
> ([`RFC-016-mission-target-framework.md`](RFC-016-mission-target-framework.md) §0).
> The decomposition itself, the boundary's subject and its successor status are
> unchanged; only the number moves, and it moves by recorded decision rather
> than by silent consumption — which is precisely the distinction §0's first
> paragraph draws about the RFC-013 debt. The block above is retained as the
> original record.

The title is **Capture Target Registry**, *not* "Capture Targets, Asset
Registration & Provenance". Two exclusions, for two different reasons:

- **"Provenance" is excluded** because registration provenance is an
  **attribute of the declaration** (§8) and is fully in scope, whereas
  provenance *investigation* is a **surface** and is not. Naming it in the
  title would re-import the boundary this section just split.
- **"Registration" is excluded** *(Governor amendment)* because registration
  is one **workflow** (§7) inside a larger architecture that also owns the
  derived registry (§2), discovery and compatibility (§6), lifecycle and
  retirement (§9). Naming the boundary after one of its workflows would
  understate it — and would invite a later RFC to claim the registry itself as
  unclaimed territory.

**Governor rulings (all three settled):** (G1) RFC-015 ratified for this
mission; (G2) the RFC-013 number remains a separate, open Governor decision and
is **not** resolved here; (G3) the decomposition of the "Asset Registry &
Provenance" boundary is accepted.

---

## 1. Problem statement

Operations correctly discovers three capture contracts. Selecting any of them
produces:

> No compatible manual telemetry stream is registered.

The cause is not a bug in RFC-013. It is a **missing layer**, and the evidence
is unambiguous.

**`core.telemetry_stream.declared` has no production writer.** The only call
site of `TelemetryStreamRegistry.declare()` in the entire repository is
`src/foundry/core/acquisition.py:215` — the method itself. Every *caller* lives
in `tests/`:

```text
tests/test_rfc_011_acquisition.py:58
tests/test_rfc_011_web.py:49
tests/test_rfc_012_operations_console.py:50
tests/test_rfc_012_operations_web.py:58
tests/test_rfc_013_capture_contracts.py:143, :231
```

There is no CLI command, no fixture, no seed, no migration and no Operations
route that declares a telemetry stream. RFC-011 built the stream *contract*,
RFC-012 built a *consumer* of it, and RFC-013 built *contracts compatible with
it* — but nothing has ever created one outside a test. A deployed instance
therefore has an empty `TelemetryStreamRegistry`, so
`_manual_streams()` (`src/foundry/operations_web.py:129`) returns `[]`, and
every contract reports zero eligible targets.

The architecture gap this RFC closes:

```text
Capture Contract          exists  (RFC-013)
        ↓
Compatible Capture Target MISSING ← this RFC
        ↓
Registered Telemetry Stream  contract exists, no writer
        ↓
Acquisition Draft         exists  (RFC-011)
```

**A second, independent defect** produces the misleading panel. In
`src/foundry/operations_web.py:344-346` the fallback is bound to the wrong
condition:

```python
if guided:
    body += "<section ...>Capture an update ... </section>"
else:
    body += "<section ...><h2>Capture is not configured</h2>..."
```

`guided` is the list of *legacy guided-workflow* streams. The `else` fires
whenever that list is empty — **regardless of whether `cards` (the registered
capture contracts) is non-empty**. Three contracts are registered and rendered
immediately above, and the page still claims Capture is not configured. This is
a false statement about system state, not a cosmetic issue, and §11 corrects it
independently of everything else in this RFC.

---

## 2. Domain concept: what is a capture target?

> **A capture target is the household-scoped, canonically-declared permission
> for one observable property of one existing domain entity to receive manual
> observations through Operations.**

It answers exactly one question: *which real account, pension or property may
receive this captured observation?*

A target binds:

| Facet | Source | Notes |
|---|---|---|
| Household | `TelemetryStream.household_id` ∧ `AssetRegistration.household_id` | must agree; fail-closed |
| Entity identifier | `TelemetryStream.subject_id` | canonical id, never a display name |
| Entity type | Finance projection (`account_type` / `asset_category`) | resolved at read time |
| Display name | Finance projection (`name`) | **presentation only** |
| Telemetry stream | `TelemetryStream.id` | the target's own identity |
| Observable property | `TelemetryStream.property` | the compatibility key |
| Allowed contracts | derived: `contract.accepts_stream(property)` | never enumerated on the target |
| Provenance | declaration event metadata | §8 |
| Lifecycle status | derived from stream retirement ∧ entity status | §9 |

### 2.1 Decision: a target is a **projection**, not a new aggregate

Four shapes were considered:

| Shape | Verdict |
|---|---|
| New `CaptureTarget` aggregate with its own event stream | **Rejected** — duplicates `TelemetryStream`, which already binds subject + property + household + unit |
| Mutable metadata on the Finance entity | **Rejected** — puts capture capability inside the domain, and Finance entities are append-only declarations with no capability slot |
| Side-table configuration | **Rejected** — mutable configuration outside the event log; explicitly forbidden by the mission constraints |
| **Projection over existing canonical declarations** | **Adopted** |

**A capture target is the join of an `AssetRegistration` and a
`TelemetryStream` with `channel == "manual"`, resolved against the domain
entity projection.** Nothing is stored that is not already canonical. Capability
is *derived from* canonical state, which is the discipline the mission brief
required and the same discipline `OperationsConsoleModel` already follows.

---

## 3. Source of truth

### 3.1 The canonical declarations

How does Foundry know that the Aviva pension exposes `pension_balance`?
Because **two canonical events say so**, and both already exist:

```text
core.asset_registry.declared     subject_id → domain, household_id, lifecycle
core.telemetry_stream.declared   stream_id  → subject_id, property, channel,
                                              household_id, unit_or_currency,
                                              refresh/confirmation policy
```

`src/foundry/core/acquisition.py:159-217` defines `TelemetryStream` and its
replayable registry; `:220-274` defines `AssetRegistration` and `AssetRegistry`.
Both rebuild by folding the log. **Neither needs to change to represent a
target.**

### 3.2 Identity survives renaming

`TelemetryStream.subject_id` is a `uuid4` produced by `grammar.new_id()`
(`src/foundry/eventlog.py:66`). Display name lives in the Finance entity's
`name` attribute and is resolved at render time. Renaming "Cash ISA" to "Chris's
ISA" emits a `finance.account.updated` event and changes nothing about the
target. **No display name is ever an identity, a key, or a lookup term** —
which is also why §7's bootstrap resolves entities by canonical *criteria*
rather than by name matching.

### 3.3 Household scoping is fail-closed

A target is offered only when **all three** agree:

```text
stream.household_id == registration.household_id == authenticated household
```

The projection drops — never repairs — any stream whose registration is
missing, whose households disagree, or whose subject has no registration at
all. That closes the orphan-stream hole: a stream can name any `subject_id`
string, but a stream with no matching `AssetRegistration` is **not a target**.

> **Finding (carried to §10).** The web layer currently constructs
> `AssetRegistry(console.log, entity_exists=lambda _entity: True)` at
> `src/foundry/operations_web.py:60` and again in the capture POST path. The
> entity-existence check that `AssetRegistry.register()` performs at
> `src/foundry/core/acquisition.py:262` is therefore **disabled in production**.
> RFC-015 must supply a real `entity_exists` bound to the Finance projection
> before any registration path is exposed.

### 3.4 Duplicate registration

`TelemetryStreamRegistry.declare()` rejects only a duplicate stream **id**
(`:213-214`). Nothing prevents two streams sharing
`(household_id, subject_id, property)` — which would render two
indistinguishable options in the target chooser.

**Rule:** `(household_id, subject_id, property)` is unique among *active*
targets. Registration is refused at declaration time with an explicit error.
The projection additionally treats any surviving duplicate pair in the log as a
**conflict**: neither is offered, and the conflict is surfaced (§12). Silently
picking the lower id would make an arbitrary choice about which real account
receives a real balance.

---

## 4. Relationship to existing telemetry streams

**Default assumption upheld: reuse the existing telemetry-stream architecture.**
Registering a capture target *is* declaring a `core.telemetry_stream.declared`
event with `channel == "manual"`. No wrapper event, no Finance-specific stream
metadata, no parallel model.

### 4.1 The one place the existing model is genuinely insufficient

The mission requires targets to be **retired** — property sale, pension provider
transfer, account closure, stream-property correction. The current model cannot
express retirement, and this is demonstrable rather than asserted:

- `TelemetryStreamRegistry.rebuild()` uses
  `self.streams.setdefault(stream.id, stream)` (`:210`) — a stream, once
  declared, is permanent and immutable for all replay time.
- `declare()` raises on a duplicate id (`:213`), so a stream cannot be
  superseded by re-declaration.
- `TelemetryStream` has no `lifecycle_state`, `retired_at` or `supersedes`
  field (`:159-171`).
- `AssetRegistry.rebuild()` keeps only the **first** registration per subject
  (`:252-253`) and `register()` raises on duplicates (`:264`), so
  `lifecycle_state` is write-once and cannot be moved to `closed` either.

There is no combination of existing canonical events that retires a stream.

**Therefore RFC-015's authorised Core event set is:**

```text
core.telemetry_stream.retired
  payload: { stream_id, reason, retired_at, superseded_by? }

core.capture_target_bootstrap.diagnostic
  payload: defined by the approved Phase 2A Diagnostic Event Amendment
```

Domain-neutral, append-only, no mutation, symmetric with the existing
`core.evidence.redacted` precedent (`:356`). `rebuild()` folds it into a
`retired` set; retired streams are excluded from new-capture selection and
**retain full interpretability for historical proposals** (§9).

### 4.2 What does *not* need a new event

Entity closure already is canonical. `finance.account.closed` and
`finance.asset.closed` exist via `grammar.close()`
(`src/foundry/core/grammar.py:44`) and set `Account.status` / `Asset.status`.
**A target whose entity is closed is derived-inactive with no additional
event.** This is why the retirement event is scoped to the *stream* only: it
covers exactly the residual case where the entity survives but the stream
should not, and nothing more.

That is the complete new-event footprint: **one event, with proof of
insufficiency, and a documented case that needed none.**

---

## 5. Relationship to Finance entities

### 5.1 How a stream resolves to an entity

```text
TelemetryStream.subject_id
        → AssetRegistration (household + domain + lifecycle)
        → FinanceEntityProjection.accounts | .assets  (type, name, currency, status)
```

`FinanceEntityProjection` (`src/foundry/finance/entities.py:687`) exposes
`accounts` and `assets` dictionaries keyed by canonical id (`:701-702`).

### 5.2 Type compatibility

Entity type comes from `Account.account_type` (`vocab.ACCOUNT_TYPE`:
`checking, savings, credit_card, loan, mortgage, brokerage, pension, jisa,
junior_sipp, other`) or `Asset.asset_category` (`property, vehicle,
collectible, private_equity, cash_equivalent, tracker_fund, other`) —
`src/foundry/finance/vocab.py:22-37`.

Type compatibility is enforced **at registration time, declaratively**, by a
property descriptor table owned by the domain, not by Operations:

| Observable property | Admissible entity types | Unit |
|---|---|---|
| `pension_balance` | `account_type == "pension"` | currency |
| `cash_balance` | `account_type ∈ {checking, savings}` | currency |
| `property_valuation` | `asset_category == "property"` | currency |

This prevents targeting an incompatible entity type without Operations ever
naming a pension. Once registered, the target carries only its property;
**discovery never re-consults entity type** (§6).

### 5.3 Domain neutrality *(review challenge)*

*Should capture-target registration be Finance-specific or domain-neutral?*

**Split by layer — the answer is both, and the seam already exists.**

- **The registry projection is domain-neutral.** It joins Core's
  `AssetRegistration` and `TelemetryStream` and knows nothing about pensions.
  It lives beside RFC-011's Core seam, which
  `src/foundry/core/acquisition.py:1-7` states "deliberately has no Finance
  imports."
- **The descriptor provider is domain-owned.** Display name, entity type and
  the §5.2 admissibility table are supplied by a Finance-side resolver behind a
  narrow protocol, exactly as `DomainDraftContract`
  (`src/foundry/core/acquisition.py:56-70`) already lets Finance own draft
  validation without Core importing Finance.

A second domain registers targets by supplying its own resolver. Neither Core
nor Operations changes.

---

## 6. Contract compatibility and target discovery

The resolution rule, declarative and complete:

```text
offer(contract, target) ⇔
      contract.accepts_stream(target.property)      RFC-013 metadata
  ∧   target.household_id == authenticated household
  ∧   target.stream.channel == "manual"
  ∧   target.is_active                              §9
  ∧   target.registration exists ∧ households agree §3.3
  ∧   target is not in a duplicate conflict          §3.4
```

`CaptureContract.accepts_stream()` already exists at
`src/foundry/capture_contracts.py:137-138`. **No `if contract.identifier == …`
appears anywhere.** Operations depends on contract metadata and target metadata
only, so a newly registered target appears with **no change to Operations
routing, renderer or contract code** — satisfying acceptance criterion 6.

### 6.1 Review challenge: is `cash_balance` the right stream property?

**Evidence of a real ambiguity.** The cash contract declares
`stream_properties=("cash_balance", "statement_total")`
(`src/foundry/capture_contracts.py:255`). But `statement_total` is *also*
matched by the legacy `_workflow()` mapping
(`src/foundry/operations_web.py:117`), which routes it to a **different**
canonical outcome. A single `statement_total` stream would therefore be
simultaneously:

- a Cash Balance Update target → `finance.account.reconciliation_observed`
  with `supplied_total`, record-only under the Path B boundary; **and**
- a guided "Update a balance" capture → a different event and payload.

One stream property with two canonical meanings is precisely the ambiguity a
declarative compatibility rule cannot resolve.

**Recommendation:** bootstrap cash targets on **`cash_balance` only**, and
recommend the Governor drop `statement_total` from
`cash-balance-update.stream_properties`. `statement_total` is the RFC-011
reconciliation lens's input, per RFC-013's own report; `cash_balance` is the
Path B record-only observation. Keeping them distinct preserves the Path B
boundary RFC-013 documented explicitly.

> **Governor ruling (approved — G4).** `statement_total` is to be removed from
> the Cash Balance contract's compatibility set; it must not retain two
> canonical meanings. The removal proceeds **through an explicit governed
> amendment** to the Capture Contracts work — **not** as a side effect of this
> architecture burn, and not in this branch. RFC-015 bootstraps cash targets on
> `cash_balance` only, which is correct both before and after that amendment
> lands.

---

## 7. Registration workflow

Three paths, one canonical outcome. All three converge on the same declaration
and the same validation; they differ only in who initiates and how the entity
is chosen.

### 7.1 Bootstrap registration — *resolve-then-declare*

For entities already in Canon. **Not versioned seed data** — see the review
challenge below.

```text
1. Fold the live log → FinanceEntityProjection + AssetRegistry
2. Select candidates by canonical criteria, never by name:
     account_type == "pension"                       → pension_balance
     account_type ∈ {checking, savings}              → cash_balance
     asset_category == "property"                    → property_valuation
3. Print resolved id, type, name, currency, household for operator review
4. Operator confirms explicitly (no --yes default)
5. Append core.asset_registry.declared (where absent)
   Append core.telemetry_stream.declared (channel="manual")
6. Idempotent: re-running declares nothing already declared
```

### 7.2 Review challenge: do bootstrap events belong in versioned seed data? — *No*

Two facts make versioned bootstrap events impossible, not merely undesirable:

1. **Canonical ids are random.** Entity ids come from `uuid.uuid4()`
   (`src/foundry/eventlog.py:66`). The deployed household's pension id was
   generated once, on the deployed instance, and cannot be reproduced by a file
   in the repository.
2. **The deployed log is not in the repository.** `.gitignore` excludes
   `foundry_data/`, `v1_data/` and `*_data/`; `render.yaml:28` supplies
   `FOUNDRY_DATA_PATH` as a deploy-time environment variable pointing at a
   persistent disk. The repository's only `.jsonl` (`v1_data/events.jsonl`) is
   a legacy V1 log containing solely `claim.derived` and `ingest` events — no
   `finance.*` entities at all.

Committing literal ids would either be fabricated or would leak real household
identifiers into version control. **Bootstrap is an operator-run,
operator-confirmed CLI operation against the live log.** What *is* versioned is
the deterministic *selection rule* and its tests — the criteria in §7.1 step 2,
exercised against the synthetic Parker-Brads and Morgan fixtures.

> **Consequence for the mission brief.** The brief asked to "confirm the actual
> canonical entity identifiers from the repository fixtures or event log."
> They are **not present in the repository** and cannot be. The Aviva pension,
> Cash ISA and primary residence exist only in the deployed log. The bootstrap
> plan is written to resolve them at run time and is validated against fixtures
> instead; §13 states this as an open dependency, not a completed confirmation.

### 7.3 Operator-led registration

An authenticated operator picks an existing entity from a household-scoped list
and enables a supported observation property. Both inputs are **closed sets
derived from canonical state** — never free text. The form submits an entity id
and a property, both re-validated server-side against §5.2 and §3.3. This
satisfies "no raw JSON for normal target registration" and "no automatic target
registration from untrusted form input": the form supplies a *selection*, and
the server independently re-derives whether that selection is admissible.

### 7.4 Technical registration

The existing authenticated technical disclosure, for unusual cases. Retained,
unchanged in privilege, and subject to the identical §3.3/§5.2 server-side
validation. It is not a bypass.

### 7.5 Review challenge: is stream registration itself a reviewed acquisition? — *No*

Tempting, and wrong. RFC-011's proposal/confirmation gate confirms
**observations about values**, and its interpreters produce **domain** drafts
validated by `DomainDraftContract`. A telemetry-stream declaration is a
`core.*` structural declaration with no value, no `valid_at` and no observation
kind. Routing it through a Finance interpreter would force Core's confirmation
gate to append Core events on a Finance draft contract — a category error that
weakens exactly the seam RFC-011 froze.

**Registration is curation, not acquisition.** Its governance is: operator
authentication, household scoping, closed-set inputs, declarative type
admissibility, an explicit two-step confirmation in the UI, and provenance
recorded on the declaration itself (§8). Nothing becomes captureable until that
canonical declaration exists — which is the brief's actual requirement, and it
is met without stretching the acquisition contract.

---

## 8. Provenance

Registration provenance and capture evidence are **different claims about
different things** and are deliberately kept apart:

| | Target registration provenance | Capture evidence |
|---|---|---|
| Claims | "this entity may receive this observation" | "this value was true at this time" |
| Recorded on | `core.telemetry_stream.declared` | RFC-011 evidence envelope |
| Lives for | the target's lifetime | one observation |
| Graded | no — it is an authority, not a measurement | yes — `declared`/`confirmed`/… |

A trustworthy registration records: **who or what** registered it (actor,
already carried by `EventLog.append`); **when** it became effective; **the
canonical entity** it resolves to (`subject_id`); **the observable property**;
**the registration authority** (`bootstrap` / `operator` / `technical`); **any
source reference**; and **whether it is operator-declared or system-derived**.

Actor and timestamp already exist on every event. The remaining facets are
additive payload keys on the existing declaration. `TelemetryStream.__post_init__`
validates a fixed field set and `rebuild()` selects
`{key: payload[key] for key in TelemetryStream.__dataclass_fields__}`
(`:207`) — **extra payload keys are ignored by construction**, so provenance
can be carried without altering the frozen dataclass or breaking replay of
existing events. Whether provenance becomes typed dataclass fields is a Phase 4
decision; it is not required for Phase 1 correctness.

---

## 9. Lifecycle and mutation

| Event in the world | Mechanism | New event? |
|---|---|---|
| Account closure | `finance.account.closed` → `status != "active"` → derived-inactive | no |
| Property sale | `finance.asset.closed` → derived-inactive | no |
| Pension provider transfer | retire old stream, declare new stream on the new entity, `superseded_by` links them | uses §4.1 |
| Entity replacement | new entity declared; new target registered; old retired | uses §4.1 |
| Stream-property correction | retire the wrong stream, declare the right one | uses §4.1 |
| Duplicate registration | refused at declaration; pre-existing pairs surface as conflict (§3.4) | no |
| Target retirement | `core.telemetry_stream.retired` | §4.1 |

**Active target predicate:**

```text
target.is_active ⇔
      stream_id ∉ retired
  ∧   registration.lifecycle_state == "active"
  ∧   entity.status == "active"
```

### 9.1 Operational suppression; history remains interpretable

Retirement removes a target from new-capture selection **and current
operational action generation**. A retired target raises no Update Now, overdue,
missing-update, reminder, queue or degraded-operational-status obligation. It
does not alter, hide or invalidate anything already captured:

- `TelemetryStreamRegistry.streams` keeps the retired stream, so historical
  envelopes and proposals still resolve their stream and render their labels.
- Confirmed proposals and canonical Finance observations are untouched —
  append-only, and retirement writes nothing to them.
- A retired target renders in historical views with its retirement plainly
  stated, never blank and never silently dropped.
- Evidence, provenance and replay remain available and deterministic; retirement
  changes only the current operational interpretation of the same history.

This satisfies acceptance criterion 7: a retired target disappears from
new-capture selection without invalidating history.

---

## 10. Security boundaries

Preserved without weakening: RFC-011 acquisition and its confirmation gate;
RFC-012 Operations; RFC-013 contracts; append-only storage; household scoping;
authentication; body-only signed CSRF; SAFE-012-01.

Registration-specific controls:

| Control | Rule |
|---|---|
| Authentication | registration requires the authenticated operator; no preview bypass |
| CSRF | body-only signed token with its **own purpose** string, distinct from `rfc012-capture` and `rfc013-capture` |
| Household | server re-derives the household; a submitted household is never trusted |
| Input domain | entity id and property are validated against closed, canonically-derived sets |
| Entity existence | **must be fixed** — `entity_exists=lambda _entity: True` at `src/foundry/operations_web.py:60` disables the check at `src/foundry/core/acquisition.py:262`; bind it to the Finance projection |
| Cross-household | stream, registration and session households must be equal; any mismatch drops the target |
| Retirement | authenticated, reason required, no cross-household retirement |
| Write path | registration appends `core.*` declarations only; it never writes `finance.*` and never bypasses acquisition |

No dynamic plug-in loading is introduced: the descriptor provider is an
explicitly composed object at the composition root, resolved the same way
`_contracts()` resolves an injected registry
(`src/foundry/operations_web.py:73-76`).

---

## 11. Correcting the stale empty state

Independent of the registry, and shippable first. The current binding is wrong
(`src/foundry/operations_web.py:344-346`); the corrected condition is:

```text
contracts ∧ (targets ∨ guided)   → render normally
contracts ∧ ¬targets ∧ ¬guided   → target-specific empty state
¬contracts ∧ ¬guided             → "Capture is not configured"
```

"Capture is not configured" appears **only when neither capture contracts nor
guided workflows are available** — exactly as the brief requires. When
contracts exist but targets do not, the page says so honestly and
contract-specifically:

> **No Cash Balance targets are registered.**
> Register the account you want to record against, then return here.

The per-contract message at `src/foundry/operations_web.py:296` ("No compatible
manual telemetry stream is registered") is likewise replaced with target
language and a route to registration.

---

## 12. UI state model

| # | State | Condition | Presentation |
|---|---|---|---|
| 1 | Contracts and targets available | both non-empty | contract chooser → contract form with target select |
| 2 | Contracts available, no compatible target | contracts ∧ ¬targets | "No *{contract}* targets are registered" + register action; **never** "Capture is not configured" |
| 3 | No contracts available | ¬contracts ∧ ¬guided | "Capture is not configured" — the only place it appears |
| 4 | Target retired | stream retired or entity closed | absent from selection; visible in history with retirement stated |
| 5 | Target inaccessible to household | household mismatch | absent entirely; **not** rendered as denied — presence is not disclosed |
| 6 | Registration pending review | declaration not yet appended | "Not yet captureable" — never offered as a target |
| 7 | Duplicate conflict | two active streams share (household, subject, property) | neither offered; conflict surfaced for operator resolution |

State 5 is deliberately silent: rendering "you cannot access this" would
disclose the existence of another household's entity.

---

## 13. Bootstrap plan for the existing household

**Not executed during this mission.** The prerequisite is Phase 1.

| Target | Selection criterion | Property | Evidence policy |
|---|---|---|---|
| Aviva pension | `account_type == "pension"` | `pension_balance` | RECOMMENDED |
| Cash ISA / cash accounts | `account_type ∈ {checking, savings}` | `cash_balance` | OPTIONAL |
| Primary residence | `asset_category == "property"` | `property_valuation` | REQUIRED |

Stream defaults: `channel="manual"`, `unit_or_currency` from the entity's own
currency, `refresh_policy` and `confirmation_policy` from RFC-011's existing
vocabularies, `source_identity` naming the registering operator.

**Open dependency (§7.2):** the actual canonical identifiers are not in the
repository and cannot be confirmed from it. The Cash ISA in particular carries
`tax_wrapper == "isa"` on a `brokerage` account in the fixtures, which is *not*
in the `cash_balance` admissible set of §5.2 — so whether the deployed "Cash
ISA" is a `savings` account or a `brokerage` account **materially changes
whether it is a valid cash target**.

> **Governor ruling (G7).** The deployed Cash ISA **must not be assumed
> eligible from its display name.** Phase 2 resolves its canonical entity type
> at runtime against the live log and **fails closed**: if the resolved
> `account_type` is not in the `cash_balance` admissible set of §5.2, the
> bootstrap declares nothing for it and reports why. An account is never
> promoted to a target because its name contains "Cash" or "ISA".

---

## 14. Implementation phases

The brief's suggested sequence is **challenged on one point** and otherwise
adopted.

| Phase | Content | Rationale |
|---|---|---|
| **0** | Empty-state correction (§11) | One-line condition fix removing a false claim about system state. Depends on nothing. Should not wait for the registry. |
| **1** | Target projection, **retirement event**, fail-closed rules, real `entity_exists` | see below |
| **2** | Bootstrap CLI (resolve-then-declare) + deployed-log identifier confirmation | needs Phase 1 |
| **3** | Retired capture-target telemetry suppression | keeps terminal targets auditable while removing only current operational obligations |
| **4** | Retired pending-proposal lifecycle; provenance typing, duplicate/conflict UX and lifecycle hardening | completes M1 without changing target retirement semantics |

**The challenge: retirement must move from Phase 4 into Phase 1.** The brief
placed lifecycle in "provenance and lifecycle hardening". Repository evidence
says that ordering is unsafe. The log is append-only and
`TelemetryStreamRegistry.rebuild()` uses `setdefault` (`:210`), so a stream
declared in Phase 2 is **permanent and irretractable** until the retirement
event exists. Bootstrapping real household targets before retirement is
implementable would create production state that cannot be corrected — a sold
property would remain captureable, with no mechanism to stop it, until Phase 4
shipped. Retirement is not hardening; it is a precondition for declaring
anything real.

> **Governor ruling (approved).** The delivery sequence is approved as
> Phase 0 → 1 → 2 → 3 → 4 above. **Retirement must precede bootstrap**, because
> declared streams would otherwise be permanently selectable in the append-only
> model.

### 14.2 Phase 4 lifecycle item — M1

**M1 — retired pending-proposal disposition.** Retirement rejects matching
pending proposals through the existing `core.observation_proposal.updated`
lifecycle event. The transition is household- and stream-scoped, append-only,
deterministic under replay and idempotent on repeated retirement. Historical
proposals, evidence and provenance remain available; confirmed, rejected and
superseded proposals are unchanged. No event kind or payload is added.

### 14.0 Phase 0 — shipped, and what it deliberately did *not* do

Phase 0 shipped at commit `0ad18b3`, touching only
`src/foundry/operations_web.py` and `tests/test_rfc_013_capture_contracts.py`.
It corrected the §11 empty-state conditions and added one test per condition.

**Phase 0 is not evidence that the registry exists.** Two clarifications
recorded at the freeze gate so that Phase 1 does not inherit a false premise:

- The `compatible_targets` list introduced in `capture_form` is a **rendering
  predicate only** — manual streams for the household whose property some
  contract accepts. It is **not** the registry projection of §2/§6: it performs
  no asset-registration join, applies no lifecycle or retirement filter, and
  detects no duplicate conflict. **Phase 1 replaces it with the real
  projection**; it must not be extended in place.
- The per-contract message at `src/foundry/operations_web.py:296` ("No
  compatible manual telemetry stream is registered") is **still stream
  language** and was intentionally left for Phase 1, because the target-language
  replacement §11 specifies needs a registration route that does not yet exist.
  This is UI state 2 of §12 and is carried as a Phase 1 deliverable.

### 14.1 Phase 1 acceptance criteria *(Governor ruling 7 — binding)*

Phase 1 does not pass until **all** of the following hold. The first is an
explicit **implementation blocker**:

| # | Criterion |
|---|---|
| **P1-A** | **`entity_exists` is bound to the real Finance entity projection at the composition root.** The production stubs `entity_exists=lambda _entity: True` at `src/foundry/operations_web.py:60` and in the capture POST path are removed, restoring the check at `src/foundry/core/acquisition.py:262`. A test asserts that registering an unknown `subject_id` is refused. **No registration path may be exposed while the stub remains.** |
| P1-B | The registry projection resolves targets by the §6 rule, with household equality enforced across stream, registration and session. |
| P1-C | `core.telemetry_stream.retired` is implemented and folded by `rebuild()`; retired streams leave selection and remain resolvable for history. |
| P1-D | `(household_id, subject_id, property)` uniqueness is enforced at declaration; pre-existing duplicates surface as a conflict (§3.4) rather than an arbitrary pick. |
| P1-E | Orphan streams, cross-household streams and closed entities are excluded — each with its own test. |
| P1-F | `compatible_targets` in `capture_form` is replaced by the registry projection, and the per-contract message at `src/foundry/operations_web.py:296` is restated in target language (§14.0, §12 state 2). |

---

## 15. Key invariants

1. No display name is ever an identity.
2. A target exists only where a stream **and** a registration **and** a
   domain entity agree on household.
3. Capability is derived from canonical state; no mutable side-table.
4. Operations names no domain type, no contract identifier and no entity.
5. The two authorised canonical events are `core.telemetry_stream.retired` and
   `core.capture_target_bootstrap.diagnostic`; any further event requires
   Governor approval.
6. Registration writes `core.*` declarations only; never `finance.*`.
7. Retirement removes a target from current selection and operational action
   generation while preserving history, evidence, provenance and deterministic
   replay.
8. `(household_id, subject_id, property)` is unique among active targets.
9. Every gate fails closed; ambiguity is refused, never resolved by guess.

---

## 16. Testing strategy

- **Projection:** household isolation; orphan stream excluded; household
  mismatch excluded; closed entity excluded; retired stream excluded;
  duplicate pair yields conflict, not an arbitrary pick.
- **Discovery:** each contract offers exactly its compatible targets; a
  **fourth** injected contract with a **newly registered** target renders with
  no change to Operations code (acceptance criteria 6).
- **Retirement:** retired target absent from selection; its historical
  proposals still resolve and render (acceptance criterion 7).
- **Registration:** cross-household refused; incompatible entity type refused;
  free-text subject refused; unauthenticated refused; CSRF purpose isolation;
  duplicate refused.
- **Empty state:** the three §11 conditions asserted independently —
  specifically that contracts-without-targets does **not** emit "Capture is not
  configured".
- **Bootstrap:** deterministic selection against both synthetic fixtures;
  idempotent re-run appends nothing.
- **Regression:** the existing 661-test suite, unmodified.

---

## 17. Rejected alternatives

| Alternative | Why rejected |
|---|---|
| New `CaptureTarget` aggregate + event stream | duplicates `TelemetryStream`; adds canonical surface with no capability the join lacks |
| Capture capability as Finance entity metadata | puts acquisition concerns inside the domain; Finance entities have no capability slot |
| Mutable registry table outside the log | forbidden by mission constraints; destroys replay provenance |
| Registration as a reviewed RFC-011 acquisition | category error — Core structural declaration through a Finance draft contract (§7.5) |
| Versioned bootstrap seed events with literal ids | ids are `uuid4` and the deployed log is not in the repository (§7.2) |
| Inferring targets from Finance entities with no declaration | capability without provenance; every account silently captureable |
| Contract-side enumeration of eligible entities | reintroduces `if contract.identifier == …`; the brief forbids it |
| Retirement by re-declaring a stream | `declare()` raises on duplicate id; `rebuild()` uses `setdefault` (§4.1) |
| Retiring via `AssetRegistration.lifecycle_state` | write-once; `register()` raises and `rebuild()` keeps only the first (§4.1) |
| Keeping `statement_total` on the cash contract | one property, two canonical meanings (§6.1) |

---

## 18. Governor decision register

Governor review returned **GO WITH AMENDMENT**. All seven decisions are
settled; the amendment is the title (§0), applied throughout.

| # | Decision | Ruling |
|---|---|---|
| G1 | RFC number for this mission | **Approved — RFC-015.** RFC-014 remains reserved for Governed Corrections |
| G2 | The RFC-013 number and the displaced *Asset Registry & Provenance* boundary | **Deferred by ruling.** Recorded governance debt; Capture Contracts is **not** retrospectively renumbered during this burn |
| G3 | Decomposition into RFC-015 (registry) + a successor (provenance investigation) | **Accepted.** **Amended 2026-08-06 by ruling GD-1:** the successor is **RFC-017**, not RFC-016; RFC-016 is *Mission Target Framework*. Decomposition and boundary unchanged (§0) |
| G4 | `statement_total` on `cash-balance-update` | **Approved for removal** — via an **explicit governed amendment**, not as a side effect of this burn. It must not retain two canonical meanings (§6.1) |
| G5 | New event `core.telemetry_stream.retired` | **Approved.** Entity closure and stream retirement remain **separate canonical facts** (§4.1, §4.2) |
| G8 | New event `core.capture_target_bootstrap.diagnostic` | **Approved by narrow Phase 2A amendment.** It records bootstrap diagnostics without changing target eligibility or projection ownership. |
| G6 | Retirement moved from Phase 4 into Phase 1 | **Approved.** Retirement must precede bootstrap (§14) |
| G7 | Deployed Cash ISA eligibility | **Ruled:** must **not** be assumed eligible from its display name. Resolve the canonical entity type at runtime and **fail closed** (§13) |
| — | Title | **Amended:** *Capture Target Registry*, not *Capture Target Registration* (§0) |
| — | Runtime bootstrap | **Approved.** No repository seed events containing invented or environment-specific entity identifiers (§7.2) |
| — | `entity_exists` production stub | **Ruled:** an implementation blocker and explicit Phase 1 acceptance criterion — **P1-A** (§14.1) |

**Architecture approved; not frozen.** The freeze gate is separate and has not
been requested.
