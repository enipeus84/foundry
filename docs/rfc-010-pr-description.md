# RFC-010 — Mission Console UX Framework (architecture only)

**Draft. Architecture-only burn — no implementation.** This PR contains
documentation exclusively: no production source, tests, CSS, templates or
runtime configuration are changed.

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

## Review path

Governor architecture review → Architecture Gate → Security Gate. Fifteen
required decisions each carry an explicit recommendation; three unresolved
questions carry recommendations pending ruling, of which Q1 (whether to retire
the legacy scalar adapter and RFC-005 phase aliases in the same Burn) most
affects scope.

**Do not merge.** This PR is a draft and must remain so until Governor
architecture review completes.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
