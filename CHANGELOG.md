# Changelog

## [v1.3-finance-core] — 2026-07-18

RFC-002 Part 1: Foundry Finance Domain. The first real product domain
built on Core — it consumes Party, Employer, Mission, the event
grammar, the Evidence Index, the Decision lifecycle, and the Metric
Registry from `foundry.core` and duplicates none of them. Stops
deliberately before the Financial Projection model (001 §16).

### Added
- `foundry.finance`: eleven deterministic entities (Account, Asset,
  Obligation, Transaction, Valuation, Position, Recurring Series,
  Tax Jurisdiction Configuration, Exchange Rate, Tax Position,
  Capital Gain Event), each written through the shared five-verb
  grammar with vocabulary validation before anything reaches the
  append-only log, and folded by `FinanceEntityProjection` — a
  rebuildable sibling to `Canon` that folds only `finance.*` events.
- Nine Finance-owned controlled vocabularies, plus the two additive
  Core extensions (`party_relationship` gains `tax_resident_in`,
  `structural_relationship` gains `fulfils`).
- Ownership model (001 §8): `owner`/`co_owner`/`beneficial_owner`
  confer counted value, `custodian`/`beneficiary` deliberately don't,
  `owes` is the counted liability relation and `guarantees` (contingent)
  is not; optional `share` percentages, range-checked at write time.
- The first five registered metrics — `finance.net_worth`,
  `finance.liquidity_runway`, `finance.cash_flow`,
  `finance.asset_allocation`, `finance.employer_concentration` —
  dispatched exclusively through the Core Metric Registry.
  Household totals are union-by-entity-id and reconcile exactly with
  share-attributed individual values, for stocks and flows alike.
  Every dated observation respects `as_of`; cross-currency
  aggregation cites the specific Exchange Rate event used;
  projection-shaped requests (`horizon`/`assumption_set_id`/
  `scenario_id`) fail closed as `unsupported` rather than being
  silently answered with Baseline numbers.
- The synthetic Parker-Brads household fixture and
  `examples/finance_demo.py`, proving real Flight Deck tiles composed
  by Core from live Finance metrics with no import edge in either
  direction.
- 81 new tests (91 → 172 passing), including regressions from an
  adversarial review pass that caught six material defects before
  merge (as_of leakage, silent-Baseline scenario answers,
  joint-account flow double-counting, a correction-path vocabulary
  bypass, refund-inflated liquidity burn, projection name loss).
- GitHub Actions CI (`.github/workflows/test.yml`): the full suite on
  Python 3.10–3.13 — the repository's first CI, closing the gap of
  local-only validation on an unsupported interpreter.
- `docs/rfc-002-implementation-report.md`: judgment calls, adversarial
  findings, and residual limitations, recorded next to the code.

### Design notes
- Zero changes to `eventlog.py`, `canon.py`, `kernel.py`, or anything
  under `src/foundry/core/`. Two Core canary tests were updated to
  check their real invariant (static import inspection) now that a
  real domain exists — the exact eventuality their docstrings named.
- Deferred to Part 2: Assumption Set, Scenario, the Financial
  Projection engine, tax calculation beyond the declared entities,
  AI-assisted analysis, and any visual Flight Deck.

## [v1.2-core] — 2026-07-17

RFC-001: Foundry Core Domain. The first product layer above the V1.0
substrate — domain-agnostic by design, so Finance (RFC-002) and every
future domain (career, health, education, knowledge) depend on it
instead of each re-declaring the same entities and mechanisms.

### Added
- `foundry.core`: Party, Employer, Mission — three shared entities,
  each a projection over `core.*` events, in the same shape `Claim`
  already establishes.
- The shared five-verb event grammar (`declared`/`updated`/`closed`/
  `linked`/`tagged`), with relationship and classification values
  validated against controlled vocabularies *before* they reach the
  append-only log.
- Scope attribution and drill-down resolution, and the Core Evidence
  Index — one shared, queryable projection of Claim tags and subject
  links, replacing the per-domain duplication risk identified during
  the architecture phase.
- The full Decision → Execution → Outcome → Review → Learning
  lifecycle. A Decision Review is a `Claim`, not a new entity type — no
  second knowledge system.
- The Metric Provider contract: `MetricRequest`/`MetricResult`, the
  `MetricProvider` interface, and a `MetricRegistry` that dispatches by
  `metric_id` alone — Core never imports a domain's calculation code.
  Duplicate registration and unknown metrics both fail closed.
- Mission status evaluation, cleanly split three ways: the owning
  domain calculates the metric, Core evaluates status against the
  Mission's declared policy, and AI may explain the result but cannot
  determine it.
- Flight Deck composition (`compose_tile`/`compose_flight_deck`): a
  read-only Core composition surface proven, in tests, to assemble
  tiles from two independent mock domains with neither one's code
  appearing in the other's import graph.
- 57 new tests (34 → 91 total), including an adversarial-review pass
  covering replay determinism, provenance/lineage completeness,
  bypassable validation, and Finance independence.

### Design notes
- Zero changes to `eventlog.py`, `canon.py`, or `kernel.py`. Every new
  mutation is `EventLog.append` under `core.*`/`claim.*`; every new
  read is a projection sibling to `Canon`, never a modification of it.
- No Finance code, and no Flight Deck UI, is included in this release.

## [1.0.0] — 2026-07-11

Production-quality release of the V1.0 architecture.

### Added
- Packaging: `pyproject.toml`, pip-installable, `foundry` console entry
  point, optional extras for model SDKs. Core has zero dependencies.
- `foundry.errors`: minimal exception taxonomy (FoundryError,
  EventNotFoundError, IntegrityError).
- Structured logging (`foundry.*` loggers) at kernel, log and model
  layers.
- `validate.sh`: one-command venv + install + 34 tests + validation
  transcript.
- Deterministic-replay proof in the validation transcript (three
  independently computed Canons compared byte-for-byte).
- Docs: architecture overview, roadmap, contributing guide, MIT license.
- Test suite restructured: unit (eventlog, canon, kernel, models),
  integration, and regression oracles; 14 -> 34 tests.

### Changed
- `EventLog.append` is O(1): last hash cached, not rescanned per append.
- Kernel applies single events to the Canon incrementally;
  `Canon.rebuild()` retained as the correctness oracle, with a
  regression test asserting incremental == rebuilt.
- Anthropic/OpenAI adapters deduplicated behind `_RealAdapter`; adding
  a provider is ~15 lines.
- CLI data directory configurable via `FOUNDRY_DATA`.
- Repository moved to `src/` layout.

### Fixed
- Validation harness no longer crashes when extraction yields zero
  claims; exits with a clear diagnostic instead.

## [0.2.0] — V1.0 functional milestone
- Real document/conversation ingestors (markdown, ChatGPT export,
  Claude export); defensive claim parsing; `kernel.underived()`;
  real-model validation harness.

## [0.1.0] — Prototype Alpha
- Event log, Canon-as-projection, seven kernel operations, mock and
  real model adapters, CLI, 9 tests, acceptance demo.
