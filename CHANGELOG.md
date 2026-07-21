# Changelog

## [v1.5.1-information-honesty] — 2026-07-20

RFC-004B: the Flight Deck's final presentation review. Three places
where the RFC-004 presentation could mislead (all documented in
docs/rfc-004-visual-review.md) now tell the truth. Presentation only;
no calculation, evaluation, registry, log, or security change, and
still zero JavaScript behind the unchanged CSP.

### Changed
- **Mission deviation gauge replaces the progress bar.** The old bar
  encoded value ÷ target — "higher is better" — and showed a full
  green bar for a Mortgage Freedom debt ratio *above* its target. The
  card now renders Core's actual policy (proximity to target): a track
  spanning ±3 tolerances (exactly the on_track / at_risk / off_track
  banding), the ±1-tolerance target band shaded at the centre, and a
  tick at the current value; the signed variance is spelled out in
  text ("+5.4% FROM TARGET", "−£119,240 FROM TARGET", "WITHIN RANGE").
  Handles higher-is-better, lower-is-better, and declared ranges
  identically; Missions with no numeric target or tolerance get no
  gauge at all — status only, nothing invented.
- **Flight Director is state-aware.** Under a WATCH or OFF COURSE
  Flight Plan it surfaces only a recommendation whose Claim concerns
  the deviating Mission ("Course correction for Retirement."); if none
  exists it says so explicitly — "No course correction on file for
  {mission}" plus an honest count of unrelated standing
  recommendations — rather than borrowing unrelated advice under a red
  banner. Nominal behaviour (latest standing recommendation, or the
  explicit no-intervention statement) is unchanged. The hero's
  corrections count now includes Mission-scoped recommendations.
- **Cash Flow card declares its period.** Relabelled Cash Flow with
  "SINCE FIRST OBSERVATION" on the opening telemetry instrument — the
  metric is net flow over all observed transactions, and the reader
  should never have to infer that. The drill-down continues to expose
  the complete raw result without claiming a separate period header.
- **Release metadata is aligned.** Runtime health, the Flight Deck
  footer, and package metadata now report version 1.5.1.
- Tests 265 → 272: gauge direction-honesty both ways, range and
  no-target Missions, deviation-relevant and honestly-absent Flight
  Director states, and the period label. Full suite passes.

### Deferred (documented, out of scope for RFC-004B)
- A "beyond scale" marker when the gauge tick clamps at ±3 tolerances.
- Multiple simultaneously deviating Missions: the Flight Director
  addresses the worst one only.
- RFC-004A's remaining cosmetic notes (mobile drawer scrim, 768px
  crumb breakpoint, lunar-surface wash, `input_references` disclosure).

## [v1.5.0-flight-deck] — 2026-07-20

RFC-004: the Flight Deck UI foundation — Mission Control's home page
restyled into the visual language of the Design Constitution.
Presentation only: no change to Core, Finance calculations, the Event
Log, Mission logic, or any schema; every number still arrives through
the Metric Registry and Flight Deck tile contract, every insight
through the Evidence Index, and rendering stays deterministic,
read-only, and zero-JavaScript behind the same fail-closed auth.

### Changed
- **Earthrise hero.** The home page opens with an Earthrise hero — an
  inline ~1 KB SVG rendition (no external asset, no CSP change, nothing
  to lazy-load) — overlaid with the three answers the page exists to
  give: FLIGHT PLAN (NOMINAL / WATCH / OFF COURSE — Core's RAG
  evaluation in NASA vocabulary, worst-of across active Missions), an
  evidence-backed "why" line naming the Mission and its numbers,
  STRATEGIC RISK (open vulnerability claims: LOW / WATCH), and the
  count of RECOMMENDED COURSE CORRECTIONS. Its sunrise tint progresses
  through the day driven by the data's own `as_of` clock, never the
  wall clock, preserving byte-identical renders.
- **Exactly four KPI cards** (RFC-004): Net Worth, Liquidity (cash
  available), Cash Flow, Runway. Employer concentration and debt ratio
  remain registry metrics with drill-down pages, one click deeper.
- **Apollo Mission cards** replace the mission-brief table: one card
  per active Mission with flight status, current-vs-target progress
  (real values, no context-free percentages), and a TELEMETRY
  drill-down affordance to the target metric's evidence page.
- **Flight Director** replaces NEXT DECISION: at most one
  evidence-backed recommendation (latest active recommendation Claim,
  with confidence, evidence count, and date); when nothing needs
  doing it says so explicitly — "Flight Plan remains nominal. No
  intervention required."
- **Recent Course Corrections**: the latest reviewed decisions
  (Decision Review claims, 000 §12) with their verdicts.
- **Hidden navigation**: a CSS-only drawer — hover or MENU to reveal
  on desktop, slide-over on mobile, `:focus-within` keeps it open for
  keyboard users; `prefers-reduced-motion` disables the slide.
- Accessibility: skip-to-content link, visible focus indicators,
  `aria-current` navigation state, AA-contrast palette, decorative
  SVG hidden from assistive tech.
- Tests 259 → 265: presentation assertions updated to the new layout
  (four cards, NOMINAL) plus new UI tests — the hero answers the three
  questions, mission cards show status/progress/drill-down, the
  Flight Director's explicit no-action state, course corrections
  surface review claims, hostile claim statements render escaped, and
  the page stays script-free. All architectural tests (registry-only
  access, determinism, read-only rendering, auth, import boundary)
  pass unchanged.

## [v1.4.1-demo-mode] — 2026-07-19

RFC-003.2 + RFC-003.3: deployable synthetic demo mode. A deployed
instance can now show a fully populated Mission Control before any
personal data exists — an env-gated, disposable evaluation dataset,
not persistence and not onboarding.

### Added
- `foundry.demo_data`: the synthetic Morgan household — ~24 months of
  unevenly spaced history (salary rise, annual bonuses, tax refund,
  unexpected repair, holidays, joint ownership, shared mortgage paying
  down, house appreciation, vehicle depreciation, a USD asset with
  Exchange Rate events, market decline and recovery) plus one complete
  Mission → Decision → Execution → Outcome → Review → Learning
  lifecycle, written entirely through Core's and Finance's public
  write APIs. All five KPI cards render AVAILABLE; the mission
  evaluates GREEN. Every seeded log permanently carries an in-band
  marker Claim (actor `synthetic_demo`, statement beginning
  "SYNTHETIC DEMO DATA") so the file itself can never be mistaken for
  a real household.
- `FOUNDRY_DEMO_DATA=true` (exactly that string — no truthy
  lookalikes) seeds `FOUNDRY_DATA_PATH` at startup if, and only if,
  the file is missing or zero-byte. Seeding is atomic (same-directory
  temp build, hash-chain verification, `os.replace`), serialized
  across concurrent starts by an O_EXCL lock file, startup-only (no
  HTTP route), and evidence-preserving: existing content of any kind
  — real events, malformed bytes, whitespace — is never parsed to
  decide emptiness, never modified, never "repaired". Unwritable or
  directory paths fail startup closed.
- `examples/seed_synthetic_household.py`: thin CLI wrapper over the
  same builder. `render.yaml` gains dashboard-controlled
  `FOUNDRY_DEMO_DATA`/`FOUNDRY_DATA_PATH` (off by default); README
  documents the settings and Render's ephemeral-filesystem behaviour.
- 50 new tests (209 → 259, zero skips): dataset realism and lineage,
  replay determinism, all-KPIs-available, and the demo-mode safety
  matrix — strict opt-in, crash-mid-seed atomicity, a two-process
  concurrency race, evidence preservation, fail-closed paths, no
  public trigger, git hygiene.

### Fixed (found by the RFC-003.3A adversarial review)
- A crash mid-seed left a valid-looking half dataset that every later
  start then accepted and skipped — seeding now publishes atomically
  or not at all.
- Two simultaneous starts (multi-worker uvicorn) interleaved two
  datasets into one file and corrupted the hash chain — now
  serialized by the lock, proven with racing OS processes.
- The emptiness check json-parsed unknown existing data (malformed
  logs crashed startup; whitespace-only files would have been
  appended into) — emptiness is now decided by file size alone.
- Seeded/skipped audit lines were invisible under uvicorn's default
  logging — the composition root now attaches one scoped stderr
  handler when nothing else has configured logging.

## [v1.4-mission-control] — 2026-07-18

RFC-003: Mission Control v0.1 — the first real product surface. A
read-only, server-rendered, zero-JavaScript console over Core's
contracts: Finance calculates, Core evaluates, Mission Control
composes (enforced by an AST import-boundary test).

### Added
- `foundry.mission_control`: opening screen (Mission Status banner,
  five live KPI cards, Mission Brief, System Health footer with live
  hash-chain and replay-parity checks), per-metric drill-down with
  household/member attribution and the full raw MetricResult, and a
  collapsed left nav with placeholder pages. Dark-first, typography
  over chrome, no new dependencies.
- Two new deterministic Finance metrics so every KPI card is
  registry-backed: `finance.debt_ratio`, `finance.cash_available`
  (7 registered in total).
- `web.py` as the composition root (FOUNDRY_DATA_PATH event log,
  provider registration, router mount) plus public-internet security
  headers: strict CSP, X-Frame-Options DENY, nosniff, no-referrer,
  no-store on authenticated pages.
- `examples/seed_mission_control.py`: fixture + Mission +
  recommendation Claim — the console renders only real replayed state.
- 37 new tests (172 → 209, zero skips), including the five RFC-required
  proofs: Core-only imports, registry-only dispatch (observed by a
  spy), graceful missing metrics, authentication on every surface, and
  byte-identical deterministic rendering. CI now installs [dev,web] so
  the web suites run on Python 3.10–3.13.

### Fixed (found by the adversarial review pass)
- ZeroDivisionError when a zero exchange rate in the log matched as an
  inverse pair: skipped at read time with a named limitation, and
  rejected at write time.
- The mission banner conflated "NOT EVALUABLE" with "NO ACTIVE
  MISSION" — two different facts, now displayed distinctly.
- Footer honesty: KERNEL carries the event count; CORE reports what
  Core actually holds (parties/missions).

### Design notes
- Rendering is deterministic because `as_of` is the latest event's
  timestamp, never the wall clock; rendering any page appends nothing
  to the log (tested byte-for-byte).
- Deferred to RFC-004+: projections, scenarios, charts, the four
  placeholder surfaces, and `compose_tile` parameters forwarding.

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
