# RFC-010 — Mission Console UX Framework (architecture only)

**Approved — architecture frozen. Ready for review.** Architecture-only burn:
this PR contains documentation exclusively — no production source, tests, CSS,
templates or runtime configuration are changed.

The Governor approved RFC-010 on **2026-07-31**. All seven Governor amendments
are complete, **no open architecture questions remain**, and the contracts in
this RFC are frozen: **implementation must not change a frozen contract without
a new Governor decision.**

## What this is

Foundry's four Finance missions all render through one generic route and one
shared renderer with no mission-name branching — a property worth protecting.
But the page's *information architecture* was never designed as a whole: it
accumulated across RFC-005, RFC-006, RFC-008 and RFC-009. The result is a
financial report rather than an operational console, with equally weighted
cards, trajectory reduced to a status word, premature detail, and two competing
"next actions" in the analysis rail.

RFC-010 defines the universal Mission Console: five ordered regions through
which every mission — Finance today, Career, Health, Household or Learning
later — answers the same four questions in the same order.

## The console

| Region | Question |
|---|---|
| Mission Hero | Where am I? Where am I going? |
| Flight Analysis | Am I on course? |
| Essential Mission Telemetry | What else must I know to read that? |
| Next Burn | What should I do next? |
| Progressive Disclosure | Show me the working |

Key decisions: the hero becomes fixed slots rather than a second telemetry
grid; Flight Analysis composes current position, destination, trajectory and
margin into **one dominant Trajectory Panel** rather than four equal cards;
essential telemetry is capped at six with an omit-when-empty rule so no
decorative cell can exist; exactly one Next Burn is dominant, with six defined
states including "no burn required" and "suppressed by another mission"; and
supporting material moves behind native `<details>` disclosure that works
without JavaScript.

## Three additive contract amendments

Each is additive with an inert default, so all four shipped missions replay and
render unchanged:

1. **`TELEMETRY_REGION` gains `essential`** — the primary telemetry
   classification. `hero` is deprecated.
2. **Trajectory gains `movement`** (`advancing` / `holding` / `receding` /
   `unknown`) — closes RFC-008's deferred G5 delta-v debt without widening the
   schedule-specific `DeltaV.direction`.
3. **`InstrumentApplicability` gains `margin`** — so a genuinely binary mission
   can declare margin inapplicable instead of rendering a misleading
   "unavailable".

Two existing domain-neutrality defects are also addressed: `MissionMargin`'s
`pace_percent` and `schedule_buffer_days` are schedule vocabulary that neither
Financial Resilience nor Pension Independence can use, and are deprecated in
favour of a domain-neutral value/unit/format.

## Deterministic testing — the PR #23 lesson, encoded

RFC-009's route goldens seeded fixtures from `time.time()`, so calendar
projections moved and `main` broke the next morning. RFC-010 makes explicit
deterministic clocks a mandatory requirement (DET-1 … DET-6), including two
additions that would have caught it before merge: a test rendering the same
console under two distinct frozen clocks and asserting hash equality, and a
guard test that fails if any fixture builds demo data without an explicit
`as_of`.

## Reference mission

**Pension Independence**, with **Financial Resilience mandated as the second
migration**. Pension is the stated failure case and exercises every region;
Resilience is the framework's absence-path validator (trajectory unavailable,
ETA and Δv not applicable) and the console is not proven until it renders
honestly with no empty cells.

## Adversarial self-review

A self-review against ten challenges is included and produced **six amendments
to the RFC before commit** — most consequentially the discovery that Mission
Margin is not universal for binary missions (amendment A3, now the third
contract amendment) and that the draft's disclosure safety rule was
unenforceable judgement rather than a testable contract rule (A5). The review
also records what it did *not* fix: `TELEMETRY_FORMAT` remains Finance-leaning,
`movement` yields nothing for two of four current missions, and Region 3
interrupts the four-question flow by mandate.

## Documentation governance

`PROJECT_STATUS.md` was materially stale — it still described RFC-008 as
unimplemented and the version as `1.5.1`. It is corrected here so
`PROJECT_STATUS.md`, `docs/rfcs/index.md` and `docs/architecture.md` no longer
contradict one another. `docs/architecture.md` is **not** modified: RFC-010
changes no invariant, and observation 3 already records the completion/
trajectory principle this console must obey.

## Explicit non-goals

No financial calculation, Finance metric, completion semantic, mission policy,
event-sourcing, authentication or navigation change. No frontend framework. No
mission-specific renderer branch. No implementation, no page migration, no test
or CSS modification in this PR.

## Governor review outcome

**GO WITH MINOR AMENDMENTS** (2026-07-31). Seven amendments applied in
`ce7cc17`, none redesigning a concept or adding scope: the seam is renamed the
**Mission Console Model**; Mission Margin is confirmed as the architectural
concept with an optional domain-specific label (Runway, Income Gap, LTV Buffer,
Recovery Reserve); a hero five-second success criterion is added as an
architecture principle with structural proxies as its testable form; the
Mission Console Model is made the explicit owner of ordering, grouping,
visibility, disclosure placement and card priority, with the renderer owning
presentation only; **Mission Console is declared a platform capability rather
than a Finance one**, so all future domains render through it unless an RFC
approves an exception; disclosure ownership is split between Core (ordering,
slot identity, behaviour) and providers (titles, content, telemetry); and the
Governor visual review becomes an explicit mandatory gate between the reference
mission and the remaining migrations.

## Closeout rulings

All previously open questions are ruled and closed:

- **Q1** — the legacy scalar adapter and the RFC-005 `phase`/`phases` aliases
  are **retired during the RFC-010 implementation Burn**; Decision 15 items 5
  and 6 become mandatory.
- **Q2** — `MissionMargin`'s deprecated `pace_percent` and
  `schedule_buffer_days` are **retained for one compatibility release**, then
  removed as an explicit breaking change.
- **Q3** — **Core owns disclosure ordering, slot identity, stable IDs and
  behaviour; providers own titles, content and telemetry.**
- **Region ordering accepted for V1** — Essential Telemetry and Next Burn are
  not reordered in this burn.

The three additive contract amendments are approved:
`TELEMETRY_REGION` gains `essential` (consumed via
`TelemetryItem.display_region`), `MissionTrajectoryView.movement` with the new
`TRAJECTORY_MOVEMENT` vocabulary, and `InstrumentApplicability.margin`. The
RFC records a transcription discrepancy in the closeout brief, which listed the
first as `InstrumentApplicability.essential`; the accurate identifiers are
frozen in the RFC.

## Review path

Architecture Gate → Security Gate → merge. Fifteen required decisions each
carry an explicit recommendation; no unresolved question remains.

**Do not merge yet.** Ready for review, pending the remaining gates.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
