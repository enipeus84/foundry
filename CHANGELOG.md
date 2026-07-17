# Changelog

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
