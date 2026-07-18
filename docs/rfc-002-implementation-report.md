# RFC-002 Finance Domain — Implementation Report (Part 1)

Branch: `rfc-002-finance-domain`
Spec: `docs/specifications/001-finance-domain-model.md` (Amendment 4), depends on `000-core-domain-model.md` Revision 2 (adopted as RFC-001, `v1.2-core`)
Status: **for review** — stops before Financial Projections and Scenarios, as instructed. Includes the fixes from an adversarial second pass (§3a below).

## 1. What this delivers

- `src/foundry/finance/vocab.py` — Finance's nine controlled vocabularies (001 §6), plus the two additive extensions to Core's vocabularies (`party_relationship` gains `tax_resident_in`, `structural_relationship` gains `fulfils`), registered at import time the same way `foundry.core.vocab`'s own docstring prescribes for a dependent domain.
- `src/foundry/finance/entities.py` — eleven of 001 §7's thirteen entities (Account, Asset, Obligation, Transaction, Valuation, Position, Recurring Series, Tax Jurisdiction Configuration, Exchange Rate, Tax Position, Capital Gain Event), each with `declare`/`update`/`close` writes built on `foundry.core.grammar`'s generic verbs, and `FinanceEntityProjection` — a fold over `finance.*` events only, a sibling to `foundry.core.entities.EntityProjection`, never a modification of it.
- `src/foundry/finance/metrics.py` — `FinanceMetricProvider`, registering the first five Facts: `finance.net_worth`, `finance.liquidity_runway`, `finance.cash_flow`, `finance.asset_allocation`, `finance.employer_concentration`. Implements the `MetricProvider` protocol structurally; nothing in `foundry.core` imports it.
- `src/foundry/finance/fixtures.py` — `build_parker_brads_household()`, a synthetic four-person household (Chris, Fiona, Hamish, Harriet) with joint and sole accounts, a co-owned home, a foreign-currency holiday let, a mortgage, two investment positions (one deliberately concentrated in Chris's own employer, per 001 §21's worked example), and six months of categorised transactions.
- `examples/finance_demo.py` — runs the fixture, registers the provider, and composes real Flight Deck tiles through `foundry.core.flight_deck.compose_flight_deck`.
- 81 new tests across five files (`test_finance_vocab.py`, `test_finance_entities.py`, `test_finance_metrics.py`, `test_finance_household.py`, `test_finance_flight_deck.py`), including the regression tests added during the adversarial pass. Full suite: **172 passed, 2 skipped** (the two skips are pre-existing `fastapi`-gated web tests, unrelated to this change).
- Two pre-existing Core tests updated (see §5) — both were explicit canaries whose own docstrings said they'd need revisiting once a real domain existed.

Zero changes to `eventlog.py`, `canon.py`, `kernel.py`, or any file under `src/foundry/core/`. Every new mutation is `EventLog.append` under `finance.*`; every new read is a projection over that same log.

## 2. What was deferred, and why

Per your instruction to stop before projections or scenarios:

- **Assumption Set and Scenario (001 §7 entities) are not implemented.** Both exist in the spec solely to serve §16's Financial Projection model (Baseline, Scenario Projection, Projection Series). An Assumption Set with no projection engine to consume it, or a Scenario with nowhere to compute a delta against Baseline, would be dead structure — implementing the data shape without the mechanism it exists for seemed worse than deferring both together.
- **§16 Financial Projection model** (Baseline/Scenario Projection, Projection Series, the `horizon`/`assumption_set_id`/`scenario_id` fields on `MetricRequest`) — not touched. All five registered metrics operate on `as_of` only.
- **§18 Pension model's projected-value output** — out of scope for the same reason (it's explicitly "a Financial Projection output, never stored").
- **§19 Tax model beyond the entities themselves** — Tax Jurisdiction Configuration and Tax Position are implemented as declarable, readable entities with the `estimation_basis`-is-never-optional discipline enforced at write time. No tax *calculation* logic exists — nothing computes a liability from a jurisdiction's rules, matching "no tax engine beyond the specification" and 001 §2's own scope note ("full tax law for any jurisdiction... out of scope").
- **§20 AI-assisted financial analysis** — not touched. Nothing here calls a `ModelAdapter`; both `entities.py` and `metrics.py` are checked by an AST-based test (mirroring `test_core_metrics.py`'s own) asserting neither imports `foundry.models`.
- **§21 Decision lifecycle's financial content** — Core's Decision/Execution/Outcome/Review machinery is already exercised by Core's own test suite and needs nothing from Finance to work; I didn't add a Finance-specific worked example of it, since it wasn't asked for and the fixture already demonstrates the two things that were: live entities and live metrics.

## 3. Judgment calls made (none pinned by the spec's text)

The spec is deliberately silent on exact formulas in several places ("V1 candidate KPI," "provisional... not permanent product logic" — echoing how `mission_evaluation.py`'s RAG banding is documented in RFC-001). Where I had to pick something concrete to make code runnable, I picked the simplest defensible option and documented it in the module docstring at the point of decision, rather than in a design doc separate from the code:

| Decision | Where | Choice made |
|---|---|---|
| Which `ownership_relationship` values count as "holds economic value" for net worth | `vocab.VALUE_OWNERSHIP_RELATIONS` | `owner`, `co_owner`, `beneficial_owner`. `custodian`/`beneficiary` excluded (stewardship/future entitlement, not present value). `owes` handled separately as `vocab.LIABILITY_RELATIONS`. |
| Account "value" | `metrics._account_value` | Transaction ledger sum + market value of Positions held within it. Position currency assumed equal to its Account's (documented limitation — see §4). |
| Asset/Obligation "value" | `metrics._account_value` siblings | Latest Valuation by `as_of`; Obligation falls back to its own declared `amount` if no Valuation exists. |
| Ownership link's `share` field | `entities.link_ownership` | 001 §8 requires an optional `share` on ownership links, but `grammar.relate()`'s payload shape is fixed to `{entity_id, relation, target}`. Bypassed it via a direct `EventLog.append`, the same sanctioned pattern `evidence.derive_claim_directly()` already uses when a generic helper's shape doesn't fit. |
| "Essential + committed monthly outflow" (liquidity runway) | `metrics.ESSENTIAL_COMMITTED_CATEGORIES` | Fixed category set: housing, transport, groceries, childcare, education, healthcare, tax_payment. Excludes discretionary and all three contribution categories (those are savings, not committed outflow). |
| Cross-currency conversion failure mode | `metrics._convert` | An item whose currency has no applicable Exchange Rate is excluded from the total and named in `limitations`, rather than failing the whole request `unsupported`. Chosen so one missing rate doesn't blank out an otherwise-computable net worth; documented as a limitation, not silently absorbed. |
| `unavailable` vs `unsupported` | throughout `metrics.py` | `unsupported` for request shapes that can never be honoured (wrong scope kind, missing required `parameters`, invalid vocabulary value). `unavailable` for "the shape is fine, there's just no data yet" (a child with no accounts, a person with no declared employer). Distinguishing these was requested by 000 §13.3's own status semantics but left to implementation for each domain. |
| Household total's target currency for a person-scoped request | `metrics._target_currency` | The reporting currency of the first household the person belongs to, defaulting to GBP if none. 001 §9 only defines `reporting_currency` on the Household Party. |
| Flow attribution for a person scope | `metrics._flow_weight` | A joint account's transactions are attributed to each co-owner by their ownership `share` (001 §9's individual-attribution rule applied to flows), so per-member `finance.cash_flow` and liquidity-runway denominators sum to the household's. A household scope counts each account's flows once, at full value. |
| Refunds in essential categories | `metrics._average_essential_outflow` | Net, not absolute: a refund reduces the burn it refunds. Zero or negative net burn → `unavailable`, never an infinite or negative runway. |

## 3a. Adversarial review findings (second pass)

A deliberately adversarial re-review against `000`/`001`/`architecture.md` and the Core implementation found six material defects in the first pass, all fixed, each with a regression test:

1. **Historical requests leaked future data.** `_account_value` summed *all* transactions regardless of `as_of`; `_asset_value`/`_obligation_value` picked the latest valuation even if dated after `as_of`; Positions valued after `as_of` counted. Fixed: every dated observation (transaction `ts`, Valuation `as_of`, Position `valuation_date`, Exchange Rate `as_of` — the last was already correct) is filtered to the request's `as_of`, with excluded items named in `limitations`. Undated entity *state* (status, ownership links, revised attributes) remains current-projection state — documented in `metrics.py`'s docstring and §4 below.
2. **Projection-shaped requests were silently answered with Baseline numbers.** A `MetricRequest` carrying `horizon`, `assumption_set_id`, or `scenario_id` — none of which Part 1 can honour — computed a plain current value as if nothing had been asked. That misrepresents the request (000 §13.4: reject unsupportable shapes *before* calculating). Fixed: all three now return `status: unsupported`, as does a `requested_calculation_version` other than the current one.
3. **Per-member cash flows double-counted joint accounts.** `finance.cash_flow` (and the liquidity-runway denominator) counted a joint account's transactions at 100% for each co-owner, so Chris + Fiona exceeded the household total — violating 001 §9's reconciliation criterion for flows. Fixed via share-weighted flow attribution (`_flow_weight`); reconciliation now holds and is tested.
4. **The correction path bypassed vocabulary validation.** `correct_transaction()` accepted any `transaction_category`, letting an ungoverned value reach the append-only log through the one write path that skipped the check `declare_transaction()` enforces. Fixed and tested (nothing is written on rejection).
5. **Refunds inflated the liquidity burn.** `abs(t.amount)` counted a grocery refund as additional grocery *spending*. Fixed: net outflow; zero/negative net burn is `unavailable`.
6. **The projection silently dropped `name`.** `FinanceEntityProjection` folded Account/Asset without their declared `name`, holding less than the log — invisible to the replay-parity tests because both replays dropped it equally. Fixed and tested.

Smaller hardening from the same pass: `link_ownership()` now rejects non-ownable entity types (`position`, `transaction`, …) and out-of-range `share` values at write time; an ownership link improperly targeting the household Party is proven inert (001 §9) by a test rather than left as a docstring-only placeholder; provider-level `unsupported` results carry the provider's real `calculation_version` (per `foundry.core.metrics.unsupported`'s own docstring) instead of the registry-level empty string; available results carry `confidence_or_quality: "derived"` (Finance's `tax_estimation_basis` sense — deterministic, no judgement) instead of `None`; an empty account is a real £0 anchored to its declaration event, distinct from an unvalued asset, which is excluded *and named* in `limitations`.

## 4. Known limitations

- **`as_of` reconstructs dated observations, not undated entity state.** Transactions, Valuations, Position valuation dates, and Exchange Rates are all filtered to `as_of` (§3a, finding 1). But an entity's *current* status, ownership links, and revised attributes come from the current projection — a query predating an account's closure still sees it closed, and `employed_by` history is not `as_of`-resolved (the most recent link wins, per 000 §8's stated Employer limitation). True point-in-time entity state means replaying a truncated log — deferred alongside the projection engine, where "state at time T" becomes a first-class need.
- **Position currency is assumed equal to its Account's currency.** A Position's own `currency` field is stored and could differ, but `_account_value` doesn't convert it separately. Not exercised by the fixture (all positions are GBP, matching their GBP account); would need a fix before a real foreign-currency brokerage holding is modelled.
- **Co-owner shares must individually be in (0, 100] (now enforced at write time) but are not validated to sum to 100%.** 001 §8 says declared shares "must sum to 100% when present." Nothing rejects a *set* of links that doesn't — that's a cross-event invariant, and `link_ownership()` validates single events only, consistent with the codebase's validate-at-write-time discipline. `_shares()` degrades gracefully for omitted shares, but 70%+70% across two co-owners will over-attribute, silently.
- **Unvested equity is not modelled.** A Position is a held holding; there is no grant/vesting concept, so `finance.employer_concentration` measures vested exposure only. Unvested RSUs — often the *larger* employer exposure — would need their own entity before the concentration number can claim to be the whole picture.
- **`finance.cash_flow` and `finance.asset_allocation` require `request.parameters`**, which `foundry.core.flight_deck.compose_tile()` never populates (it only ever sends `metric_id`/`scope`/`as_of`). Both metrics work correctly when dispatched directly through a `MetricRegistry` (as the tests do), but neither can appear as a Flight Deck tile without a Core-side change to forward `parameters` — out of scope here since it touches `foundry.core.flight_deck`, not Finance. `finance.net_worth` and `finance.liquidity_runway` — the two 001 §23 names explicitly — have no such restriction and are the ones `examples/finance_demo.py` puts on tiles.
- **`finance.employer_concentration`'s household-scope union is per-account, not per-position.** If two household members co-own an account and have *different* current employers, a Position issued by either counts toward the numerator (correct), but the metric doesn't separately break down "whose" concentration it is at household scope — only at person scope. The fixture only exercises the person-scope case (Chris).

## 5. Two pre-existing Core tests updated

Both `tests/test_core_flight_deck.py::test_core_module_imports_no_finance_package` and `tests/test_core_grammar_vocab.py::test_extending_a_core_vocabulary_shape_does_not_remove_base_values` failed once this branch existed — not because Core broke, but because both tests' own docstrings say they were written as canaries for a state ("no real domain exists yet") that RFC-002 necessarily ends. Specifically:

- The flight-deck test asserted `foundry.finance` never appears in `sys.modules` process-wide — true only while Finance didn't exist, and inherently fragile to pytest's single-process test collection once it legitimately does. Replaced the process-global check with the same static AST inspection `test_core_metrics.py` already uses for "no model adapter import": no `foundry.core.*` module's own source names `foundry.finance`. That's the invariant 001/000 actually require; the old test conflated it with a test-ordering artifact.
- The vocab test asserted the real shared `PARTY_RELATIONSHIP` singleton never contains `tax_resident_in` — but `foundry.finance.vocab` legitimately extends it with exactly that value at import time, by design (the "register on import" pattern `vocab.py`'s own docstring prescribes for a dependent domain). Changed the test to extend a synthetic value no real domain will ever claim, so it still proves what it always meant to prove (a copy's `.extend()` never leaks into the shared global) without depending on whether Finance has been imported yet in the same process.

No production code changed in either fix — both are entirely within `tests/`, and neither weakens what's being checked.

## 6. Acceptance criteria coverage (001 §24)

| # | Criterion | Status |
|---|---|---|
| 1 | Uses core event namespaces only | ✅ `test_no_duplicated_core_event_kind_anywhere` |
| 2 | Shared entities/indexes not duplicated | ✅ `FinanceEntityProjection` folds only `finance.*`; ownership/tags read via Core |
| 3 | Additive relationship extensions only | ✅ `tax_resident_in`, `fulfils` — tested |
| 4 | Flight Deck tiles conform to core contract | ✅ `finance.net_worth`/`finance.liquidity_runway` via `compose_tile` unmodified |
| 5 | Finance registers, Core never imports | ✅ AST-checked both directions |
| 6–10 | Substrate compliance (one log, append-only, rebuild parity, deterministic facts, model-failure containment) | ✅ replay-parity tests; no `foundry.models` import |
| 11–13 | No double-counting, reconciliation, household never an ownership target | ✅ `test_net_worth_joint_asset_counted_once...`, `test_household_net_worth_equals_sum_of_member_attributions` |
| 14–16 | Financial Projections | **deferred** (§2) |
| 17 | No pre-created transactions | ✅ `test_recurring_series_never_pre_creates_a_transaction` |
| 18 | Allocation/concentration derivable from Position + core Employer, no string matching | ✅ `test_employer_concentration_uses_core_employer_no_string_matching` |
| 19 | Exposed pension assumptions | **deferred** (§2) |
| 20–21 | Tax: historical jurisdiction, visible uncertainty | ✅ entity-level only; no calculation exists to have an uncertainty about beyond the entity itself |
| 22–23 | Decision lifecycle traceability, citable learning | not exercised by Finance-specific code (Core's own suite covers the mechanism; no Finance content was asked for here) |
| 24–25 | Ownership historical, zero new core dependencies | ✅ |

## 7. Suggested next steps (not started)

1. Assumption Set + Scenario entities, then §16's Financial Projection engine (Baseline/Scenario Projection Series, the `horizon` field on requests).
2. Extend `foundry.core.flight_deck.compose_tile()` to forward `MetricRequest.parameters`, so `finance.cash_flow`/`finance.asset_allocation` can appear as tiles too — a Core change, needs its own review.
3. Co-owner share-sum validation, either at `link_ownership()` write time (requires reading existing links first) or as a `FinanceEntityProjection` consistency check.
4. Position-currency conversion in `_account_value`, once a fixture actually needs a foreign-currency brokerage holding.
