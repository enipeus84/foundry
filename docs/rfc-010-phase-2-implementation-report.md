# RFC-010 Phase 2 Implementation Report

## Scope and Governor gate

The Governor approved the Pension Independence reference console and issued a
GO for Phase 2. This burn migrates Financial Resilience, Financial
Independence and Mortgage Freedom to the frozen Mission Console architecture,
retains Pension Independence as the reference implementation, and makes no
Finance policy or calculation changes. The implementation remains unmerged
pending SAFE and Governor review.

## Governor refinements

Shared telemetry grids now collapse to their actual item count, so disclosure
sections cannot manufacture empty decorative cells. Trajectory state is
presented consistently as a human-readable trajectory label, including
`NOMINAL TRAJECTORY`, without mission identity branching. Pension scenario
labels are now `EXPECTED PATH`, `CONSERVATIVE CASE` and `OPTIMISTIC CASE`.
Shared supporting text is slightly larger, while the approved hero trajectory
retains its size and visual priority.

## Shared architecture

Every assessment-backed Finance route now follows the same pipeline:
Mission Definition → Mission Provider → Mission Assessment → Mission Console
Model → presentation-only renderer. The pure model owns region order,
visibility, essential telemetry, supporting-instrument priority, disclosure
grouping and the primary recommendation. The renderer iterates the model's
declared region order verbatim and contains no mission-name, slug or policy-id
branch.

The universal order is Mission Hero, Flight Analysis, Essential Mission
Telemetry, Next Burn and Show Me The Working. Essential telemetry is omitted
only when the model supplies no meaningful items; it is never padded. Core
owns disclosure slots, stable IDs and native disclosure behaviour. Providers
own plain-text titles, telemetry and recommendation content.

## Financial Resilience migration

The resilience console is the mandatory absence-path implementation. It
states that observed trajectory history is unavailable, treats intercept and
recent movement as not applicable or unavailable, and does not draw a fake
trajectory. Runway is the Mission Margin. Emergency Reserve Gap and Deployable
Surplus are the two essential metrics; reserve requirements, stress analysis
and margin evidence remain under Show Me The Working. The provider emits one
clear primary burn without padding the analysis rail.

## Financial Independence migration

The existing accessible-investment bands, thresholds and destination policy
are unchanged. Net Cash Flow and Runway are essential when current evidence is
available. Accessible Assets and its band evidence remain in disclosure to
avoid repeating the hero's current position. Mission Margin is expressed as
Schedule Buffer through provider metadata; the shared renderer contains no
schedule logic. The provider retains one primary structured recommendation.

## Pension Independence refinements

Pension remains the approved reference console. Its projection scenarios use
plain financial narrative labels, disclosure grids collapse naturally, and
the shared typography and trajectory-state improvements apply without
mission-specific CSS. Current Pension, Required Retirement Wealth and Funding
Ratio remain the three essential metrics; Income Gap remains the Mission
Margin.

## Mortgage Freedom migration

Monthly Payment and Fixed-rate Protection are the two essential metrics.
Property acquisition facts, current equity, LTV, principal repaid, valuation
movement and secondary mortgage position evidence are grouped under Show Me
The Working. The hero and trajectory reuse the existing provider calculation;
no new payoff calculation is introduced. LTV Buffer is the Mission Margin. A
liquidity-floor precedence case is represented as one explicit suppressed
burn rather than an absent or competing recommendation.

## Compatibility retirement

The homepage legacy scalar Mission adapter is removed. The RFC-005
`MissionPhaseAssessment`, `MissionAssessment.phase`,
`MissionAssessment.phases` and `MissionAssessment.phase_thresholds`
compatibility paths are removed after provider migration and repository-search
proof of disuse. The deprecated `pace_percent` and
`schedule_buffer_days` Mission Margin numerics remain for the approved single
compatibility release.

## Accessibility and security

Show Me The Working uses native `details`/`summary`, is collapsed by default,
works without JavaScript, retains stable deep-link IDs and preserves print
behaviour. Provider titles remain plain text and are escaped. Authentication,
household scope selection, provider-envelope validation, fail-closed route
isolation and the existing trusted-HTML boundary are unchanged. No financial
state moves to client persistence, page metadata or logs, and collapsed
content is not treated as access control.

## Determinism and validation

The four Finance routes have pinned normalized SHA-256 goldens generated from
explicit assessment timestamps and deterministic stepped event clocks. Tests
guard against current-date dependencies, verify read-only rendering, exercise
the resilience absence path, and enforce the model/renderer boundary. Local
validation uses Python 3.13; the pull-request workflow runs the full suite on
Python 3.10, 3.11, 3.12 and 3.13.

Local Python 3.13 validation finishes with 605 passing tests after SAFE
remediation. The one pre-existing Starlette/httpx deprecation warning remains.
The security-documentation
inventory is complete, `git diff --check` is clean, and source/test compilation
succeeds. The repository validation harness passes its test, replay,
provenance and hash-chain checks, then returns its documented non-production
exit because no real-model API keys are present.

The Phase 1 count was 602 and the pre-remediation Phase 2 count was 593. That
temporary reduction was confined to deletion of legacy Mission Detail renderer
tests for the paths retired in this burn; their supported behaviour was
replaced by model, provider, route-order, absence-path, escaping,
accessibility, responsive and four-route golden coverage. SAFE remediation
adds twelve targeted tests, bringing the final count to 605.

The live preview review covers all four authenticated routes at a desktop
viewport and at 334 CSS pixels. Every page has five ordered regions, no empty
telemetry card, one primary burn, collapsed disclosures, stable IDs and no
horizontal overflow. The review found and removed an evidence-disclosure
auto-open heuristic and repaired a shared narrow analysis-grid overflow before
the final pass. Python 3.10–3.13 remain delegated to pull-request CI.

## SAFE remediation

`MissionAssessment.trajectory_movement` now carries the provider-owned value
movement classification through the Mission Console Model into the existing
renderer slot. Financial Independence classifies its observed accessible-asset
history as higher-is-better; Mortgage Freedom classifies its observed balance
history as lower-is-better. Their governed synthetic fixtures exercise
`advancing`. Financial Resilience and Pension Independence remain `unknown`
because their evidence contracts do not provide defensible observed history.
Tests also prove that a provider-declared `receding` value reaches the shared
renderer unchanged and that `unknown` is never converted into deterioration.
This closes RFC-008 G5 through the separately approved domain-neutral movement
axis; `DeltaV.direction` remains schedule-specific and unchanged.

DET-6 is enforced by an AST guard over every test module that imports the demo
builder directly or through the synthetic seed module. The guard rejects a
projection-relevant `build` call without an explicit, non-`None` `as_of`.
The Pension fixture and four synthetic-household fixture calls are pinned to a
fixed assessment clock; their event clocks are deterministic where route
rendering reads event timestamps. A calendar-boundary Pension test and the
existing dual-clock route-golden test prove stability without changing any
production clock default.

The unused `DisclosureSectionView.open_by_default` field and its renderer
branch are removed. Critical limitations continue to be hoisted into Next Burn
and disclosures remain natively collapsed. Milestone sorting now occurs in
the Mission Console Model; the SVG renderer consumes the supplied tuple
verbatim, with a deliberately non-sorted-order regression test. PR #25's
description states that it contains both implementation phases and that its
`phase-1` branch name is retained only for continuity.

## Known limitations

Financial Resilience still lacks honest historical trajectory evidence;
unavailability is now represented rather than disguised. Historical Finance
reconstruction, per-request replay cost, single-writer constraints and the
remaining Mission Margin numeric retirement are unchanged governed debt.
Children remains outside the fixed Finance mission hierarchy and outside this
burn.
