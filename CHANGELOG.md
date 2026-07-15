# Changelog

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
