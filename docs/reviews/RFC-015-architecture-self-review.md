# RFC-015 — Architecture Self-Review

Adversarial review of [`RFC-015-capture-target-registration.md`](../rfcs/RFC-015-capture-target-registration.md),
performed against the mission's explicit review challenges. Every claim below
is grounded in a cited repository line, not in the RFC's own assertions.

---

## Part 1 — Current-state analysis

### 1.1 How Finance entities are represented today

| Entity | Writer | Type discriminator | Identity |
|---|---|---|---|
| Cash / pension accounts | `declare_account` — `src/foundry/finance/entities.py:294` | `account_type` ∈ `vocab.ACCOUNT_TYPE` (`src/foundry/finance/vocab.py:22-26`) | `grammar.new_id()` |
| Property | `declare_asset` — `src/foundry/finance/entities.py:321` | `asset_category` ∈ `vocab.ASSET_CATEGORY` (`:33-37`) | `grammar.new_id()` |
| Obligations | `declare_obligation` — `:345` | `liability_category` | `grammar.new_id()` |

Projection: `FinanceEntityProjection` (`src/foundry/finance/entities.py:687`),
exposing `.accounts` and `.assets` keyed by canonical id (`:701-702`).
Lifecycle: `close_account` / `close_asset` (`:315`, `:339`) emit
`finance.<type>.closed` via `grammar.close()`
(`src/foundry/core/grammar.py:44`), setting `status` off `"active"` (`:89`,
`:103`).

Identity is `uuid.uuid4()` (`src/foundry/eventlog.py:66`). `name` is an
optional display attribute only. **Nothing in the Finance model carries any
notion of capture capability** — which is why the RFC does not attempt to put
one there.

### 1.2 How telemetry streams are declared today

`TelemetryStream` (`src/foundry/core/acquisition.py:159-190`) already binds
`subject_id`, `property`, `channel`, `household_id`, `unit_or_currency` and the
refresh/confirmation policies. `TelemetryStreamRegistry`
(`:193-217`) rebuilds by folding `core.telemetry_stream.declared` and writes via
`declare()` (`:212`).

**`declare()` has no production caller.** Every caller is a test:

```text
tests/test_rfc_011_acquisition.py:58
tests/test_rfc_011_web.py:49
tests/test_rfc_012_operations_console.py:50
tests/test_rfc_012_operations_web.py:58
tests/test_rfc_013_capture_contracts.py:143, :231
```

No CLI command, no fixture (`src/foundry/finance/fixtures.py`), no demo seed
(`src/foundry/demo_data.py`) and no web route declares a stream.

### 1.3 Why the deployed contracts have no compatible targets

Direct causal chain, each link verified:

```text
no production caller of declare()          §1.2
  → deployed log has no core.telemetry_stream.declared events
  → TelemetryStreamRegistry.streams == {}      acquisition.py:201-210
  → _manual_streams() returns []               operations_web.py:129-135
  → eligible == []                             operations_web.py:293
  → "No compatible manual telemetry stream is registered."   :296
```

The separate stale-panel defect is at `src/foundry/operations_web.py:344-346`:
the `else` branch is bound to `if guided:`, so it fires whenever the legacy
guided-workflow list is empty **even though `cards` is non-empty and three
contracts were just rendered**. Two independent defects, one visible symptom
each.

### 1.4 Which existing canonical events can be reused

| Need | Existing event | Sufficient? |
|---|---|---|
| Entity → routing metadata | `core.asset_registry.declared` (`:272`) | yes |
| Stream declaration | `core.telemetry_stream.declared` (`:215`) | yes |
| Containment | `core.asset_registry.linked` (`:291`) | yes |
| Entity closure | `finance.account.closed` / `finance.asset.closed` | yes |
| Evidence, envelopes, proposals, confirmation | RFC-011, unchanged | yes |
| **Stream retirement** | — | **no** (§1.5) |

### 1.5 The one proven insufficiency

Retirement cannot be expressed. Four independent code facts, any one of which
is sufficient:

| Fact | Line |
|---|---|
| `rebuild()` uses `setdefault` — a declared stream is permanent | `src/foundry/core/acquisition.py:210` |
| `declare()` raises on duplicate id — no supersession | `:213-214` |
| `TelemetryStream` has no lifecycle field | `:159-171` |
| `AssetRegistry` keeps only the first registration and `register()` raises on duplicates — `lifecycle_state` is write-once | `:252-253`, `:264-265` |

Exactly one new event is therefore justified: `core.telemetry_stream.retired`.

---

## Part 2 — Proposed event flow

```text
  Existing canonical Finance entity
  finance.account.declared / finance.asset.declared
  (uuid identity; account_type or asset_category; name is display only)
                    │
                    ▼
  Capture-target registration                        [RFC-015]
  bootstrap CLI · operator-led form · technical path
  household re-derived server-side; entity type checked declaratively
                    │
                    ▼
  Canonical declarations                             [existing Core events]
  core.asset_registry.declared     subject → domain, household, lifecycle
  core.telemetry_stream.declared   stream  → subject, property, manual,
                                             household, unit, + provenance keys
                    │
                    ▼
  Capture registry projection                        [RFC-015, derived]
  join(AssetRegistration, TelemetryStream) ⋈ FinanceEntityProjection
  fail-closed: households must agree; orphans dropped;
  duplicates → conflict; retired/closed → inactive
                    │
                    ▼
  Operations target discovery                        [RFC-012 surface]
  targets for authenticated household only
                    │
                    ▼
  RFC-013 contract
  offer ⇔ contract.accepts_stream(target.property) ∧ target.is_active
                    │
                    ▼
  RFC-011 acquisition proposal                       [unchanged]
  ManualAcquisitionProvider → evidence envelope → FinanceManualInterpreter
  → inert pending proposal
                    │
                    ▼
  Confirmation                                       [unchanged]
  CSRF-protected inbox gate — the only route to canon
                    │
                    ▼
  Canonical Finance observation
  finance.valuation.declared / finance.account.reconciliation_observed
```

Retirement path, orthogonal and non-destructive:

```text
core.telemetry_stream.retired  →  target.is_active = false
                               →  absent from new-capture selection
                               →  historical envelopes, proposals and
                                  canonical observations unchanged
```

---

## Part 3 — The mission's review challenges, answered adversarially

### C1. Does this belong with *Asset Registry & Provenance*? — **No**

RFC-012 §2.8 required this challenge and predicted its outcome. Registration is
**occasional curation** and is a *precondition* of the weekly loop; asset
detail and provenance timelines are **rare investigation** and a *consequence*
of it. Bundling them would block a load-bearing fix behind an investigative
surface with no history to investigate yet.

*Steelman:* both are "things the weekly loop excludes", and one RFC would
settle the whole successor space at once. *Rebuttal:* "what RFC-012 excluded"
is a label, not a boundary — RFC-012 §2.8 says so in terms. Shared exclusion is
not shared rhythm.

### C2. Is a new event type really needed? — **Yes, exactly one, and no more**

The default was reuse, and reuse wins everywhere except retirement, where §1.5
gives four independent proofs of insufficiency. Note the discipline actually
held: entity-closure-driven retirement was **found to need no event**, because
`finance.*.closed` already exists. The footprint is one event.

*Steelman:* skip the event; treat entity closure as the only retirement.
*Rebuttal:* that cannot express a pension provider transfer or a
stream-property correction, where the entity survives but the stream must not —
and in an append-only log with `setdefault`, an uncorrectable wrong stream is
permanent.

### C3. Is stream registration itself a reviewed acquisition? — **No**

RFC-011 confirms observations *about values*; drafts are validated by
`DomainDraftContract` (`src/foundry/core/acquisition.py:56-70`). A stream
declaration is a `core.*` structural fact with no value, no `valid_at` and no
observation kind. Routing it through a Finance interpreter would force the
confirmation gate to append Core events under a Finance draft contract.

*Steelman:* registration is governance-bearing, so it deserves the review gate.
*Rebuttal:* it deserves *a* gate, not *that* gate. §7.3/§10 supply
authentication, closed-set inputs, declarative admissibility, explicit
confirmation and recorded provenance — governance without category error.

### C4. Do bootstrap events belong in versioned seed data? — **No, and they cannot**

Ids are `uuid.uuid4()` (`src/foundry/eventlog.py:66`); the deployed log lives on
a Render disk via `FOUNDRY_DATA_PATH` (`render.yaml:28`) and `.gitignore`
excludes `foundry_data/`, `v1_data/`, `*_data/`. The repository's only
`.jsonl` is a legacy V1 log of `claim.derived` and `ingest` events with no
`finance.*` entities. Versioned literal ids would be fabricated or would leak
real household identifiers. What is versioned is the **selection rule** and its
fixture tests.

### C5. Is `cash_balance` the correct stream property? — **Yes; `statement_total` should be dropped**

`cash-balance-update` declares both (`src/foundry/capture_contracts.py:255`),
but `statement_total` is also claimed by the legacy `_workflow()` mapping
(`src/foundry/operations_web.py:117`) with a **different** canonical outcome.
One property, two meanings, and a declarative compatibility rule cannot choose.
`statement_total` is the RFC-011 reconciliation lens's input; `cash_balance` is
the Path B record-only observation RFC-013 documented. Recommended to the
Governor as G4 — **a recommendation against RFC-013's shipped metadata**, not a
change applied here.

### C6. Finance-specific or domain-neutral? — **Split by layer**

Projection domain-neutral (Core, no Finance imports — the constraint
`src/foundry/core/acquisition.py:1-7` already states); descriptor provider
domain-owned behind a narrow protocol, mirroring the existing
`DomainDraftContract` seam. A second domain supplies a resolver; Core and
Operations do not change.

---

## Part 4 — Findings against the RFC itself

| # | Finding | Disposition |
|---|---|---|
| S1 | `entity_exists=lambda _entity: True` at `src/foundry/operations_web.py:60` and in the capture POST path **disables** the existence check at `src/foundry/core/acquisition.py:262` in production | Must be fixed in Phase 1 before any registration path is exposed. Recorded in §10. Pre-existing defect, not introduced here. |
| S2 | Brief sequenced retirement into Phase 4; append-only `setdefault` makes Phase 2 declarations irretractable until it ships | RFC challenges the sequence and moves retirement to Phase 1 (§14, G6) |
| S3 | Deployed Cash ISA's `account_type` is unknown; if it is `brokerage` (as in the fixtures, where the ISA is a brokerage account with `tax_wrapper="isa"`) it is **not** admissible for `cash_balance` under §5.2 | Recorded as an open dependency (§13, G7), not guessed |
| S4 | Nothing prevents two streams sharing `(household, subject, property)`; `declare()` checks only stream id (`:213`) | Uniqueness rule + conflict state (§3.4, UI state 7) |
| S5 | The RFC adds a canonical event, which any freeze must justify | Four independent proofs of insufficiency (§1.5); footprint held to one |

**No finding blocks Governor review.** S1 and S3 are prerequisites for
*implementation* phases, both explicitly recorded.

---

## Part 5 — Acceptance criteria traceability

| # | Criterion | Where met |
|---|---|---|
| 1 | Entities registerable through canonical, provenance-bearing state | §3.1, §8 |
| 2 | Operations discovers targets dynamically | §6 |
| 3 | Compatibility derives from declared properties + contract metadata | §6 |
| 4 | Household and entity identity fail-closed | §3.3, §15 |
| 5 | No registration bypasses acquisition or canonical governance | §7.5, §10 |
| 6 | New target appears with no Operations routing or contract change | §6, §16 |
| 7 | Retired target leaves selection without invalidating history | §9.1 |
| 8 | Initial targets bootstrappable without hard-coded UI logic | §7.1, §13 |
| 9 | "Capture is not configured" corrected | §11, §12 |
| 10 | No new canonical events without proof | §4.1, §1.5 |

---

**Status: ready for Governor review. Architecture is not frozen.**
