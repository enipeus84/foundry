# RFC-009 Prep — Shared Mission Detail Refactor Implementation Report

Status: implementation complete on the RFC branch; no pull request opened.

## Scope

Refactored the existing authenticated Finance Mission Detail renderer into
three reusable server-rendered components without changing the Mission
Assessment contract, provider dispatch, route behaviour, calculations,
telemetry, recommendations, visual design, responsive CSS or interactions.

Pension Independence remains a planned definition. This change adds no
Pension provider, telemetry, calculation, forecast, recommendation or UI
special case.

## Repository and pre-flight

- Canonical repository: `/Users/chrisparker-brads/Projects/foundry`
- Refactor worktree:
  `/Users/chrisparker-brads/.codex/.chatgpt-projects/g-p-6a4d413c8dc081919f380f51b9bfba41/foundry-rfc009`
- Branch: `rfc-009-shared-mission-detail-refactor`
- Base: `origin/main` at `1448c58`
- Pre-flight result: **GO WITH WARNINGS**
- The canonical checkout was clean, but its local `main` was two commits
  behind `origin/main`. The worktree was therefore created directly from the
  current remote head.
- PR #20 had already moved the Mortgage Freedom schedule comparison into
  Flight Analysis. That merged layout is the baseline preserved here.
- GitHub had no open pull requests and no Pension branch. The only unmerged
  remote branch was the older RFC-005 Financial Independence branch.
- Two stale, prunable worktree registrations were identified and left
  untouched because cleanup is unrelated to this refactor.
- The normal macOS keep-awake process was started for the implementation run.

## Required implementation review

### Existing shared components

Before this change, the product already had more sharing than the brief's
examples imply:

- one generic authenticated `/missions/{slug}` route for every mission;
- one `MissionAssessmentRegistry` dispatch boundary;
- one domain-neutral `MissionAssessment` rendering path;
- shared page shell, navigation, footer and Earthrise assets;
- shared trajectory SVG, geometry and milestone rendering;
- shared value, date, month-delta and milestone-range formatting; and
- shared planned, not-configured, duplicate-mission, unavailable and not-found
  states.

There were no separate Financial Resilience and Mortgage Freedom page
implementations to merge.

### Duplicate or near-duplicate structure

The duplication risk was structural rather than two copies of code: one
approximately 400-line route mixed orchestration, presentation projection and
three large inline HTML regions. Every live mission depended on those regions
remaining aligned, but their boundaries were not reusable or independently
testable.

The stable regions were:

1. Mission Hero;
2. Flight Analysis; and
3. deeper telemetry, assumptions, limitations and provenance.

### Repeated formatting and transformation

The route already centralised:

- provider-declared current-value presentation;
- currency, percentage and month formatting;
- month-resolution Delta-v wording;
- milestone labels and completion;
- Mission Margin and confidence copy;
- recommendation availability and evidence detail;
- applicability-aware ETA, trajectory, forecast and Delta-v presentation; and
- telemetry value/status/reference formatting.

These transformations remain unchanged. Moving or redesigning them was not
required to establish the component boundary.

### Mission-specific code intentionally retained

The following remain owned by their Finance implementations:

- Financial Resilience evidence, stress telemetry, reserve policy, margin,
  confidence and recommendation;
- Financial Independence trajectory, forecast, milestones and scenario
  recommendation;
- Mortgage Freedom evidence, acquisition/current/equity telemetry ordering,
  schedule comparison and overpayment recommendation; and
- each mission definition, policy id, assessor and metric calculations.

No mission name, slug or policy-id branch was added to Mission Control.

### UI/domain coupling

Mission Control consumes only Core contracts. It formats provider-declared
values and uses the closed `InstrumentApplicability` states to omit, show or
explain instruments. It does not calculate mission status, margin, milestone
membership, ETA, Delta-v, confidence, forecasts or recommendations.

The remaining coupling is deliberate presentation coupling to
`MissionAssessment`: changes to that Core contract require corresponding
renderer review.

### Debt affecting another mission

The generic route already proves three live Finance providers: Financial
Resilience, Financial Independence and Mortgage Freedom. A further mission
does not require a copied page.

Remaining presentation debt:

- `mission_control.py` still contains the full page shell, CSS and
  presentation projection in one large module;
- some component inputs are trusted internal HTML fragments produced by the
  same renderer, so the component types remain private;
- route tests use HTML-region string boundaries because the product has no
  DOM snapshot or visual-regression harness; and
- there is no governed loading state because the current application is
  synchronous server rendering.

Further extraction should wait for a second proven consumer or a dedicated
templating decision. Splitting domain-neutral presentation for its own sake
would increase movement without removing demonstrated duplication.

## Components extracted

- `_MissionHeroView` + `_render_mission_hero`
- `_FlightAnalysisView` + `_render_flight_analysis`
- `_MissionDataView` + `_render_mission_data`

The view inputs are frozen and component-specific. The route composes the
three regions in the unchanged order and appends the unchanged shared footer.

## Duplication removed

- The hero, Flight Analysis and deeper-data HTML are no longer embedded in
  the route orchestration block.
- Shared region order and accessibility landmarks now have one explicit,
  testable composition for all live Finance missions.
- No artificial abstraction was added around mission-specific telemetry or
  policy.

## Architecture before and after

Before:

```text
Mission Definition
        ↓
Mission Engine / Provider
        ↓
MissionAssessment
        ↓
authenticated generic route
        ↓
inline hero + analysis + telemetry/provenance HTML
```

After:

```text
Mission Definition
        ↓
Mission Engine / Provider
        ↓
MissionAssessment
        ↓
authenticated generic route
        ↓
Mission Hero ─ Flight Analysis ─ Mission Data/Provenance
```

The required Definition → Engine → Telemetry Projection → UI direction is
unchanged. The event log, Canon, Kernel, Finance providers and API contracts
are untouched.

## Behaviour and visual parity

- Baseline and refactored HTML were captured for Financial Resilience,
  Financial Independence and Mortgage Freedom.
- After excluding only the demo fixture's newly generated `DATA AS OF` minute,
  all three documents are byte-identical.
- No CSS, static asset, JavaScript, route, HTTP status, page hierarchy,
  typography, colour, spacing or responsive rule changed.
- Route-level regression coverage now pins one hero, one Flight Analysis
  region, one drill-down, one telemetry grid, unchanged region ordering and
  the existing accessibility relationships for every live Finance mission.
- A focused component regression pins HTML escaping of all textual Mission
  Hero inputs.

The live synthetic-data preview runs locally at
`http://127.0.0.1:8766/` and redirects into the authenticated app at port
8765. Agent-controlled visual inspection was unavailable because the in-app
browser's enterprise policy blocks localhost. No browser-policy workaround
was attempted.

## Security by Design checklist

### Security Considerations

- **Authentication:** unchanged. The existing session check still protects
  `/missions/{slug}` before any registry lookup or rendering. No public route
  was added.
- **Authorisation:** unchanged. The route still selects the server-side
  household scope and dispatches the matching active mission only. No
  household or object boundary moved.
- **Sensitive data and secrets:** unchanged. Mission values remain ephemeral
  rendered output from the existing read model. No value, credential, token
  or evidence was added to application logs, source control or snapshots.
- **Auditability:** unchanged. Mission rendering remains read-only and appends
  no event. Provider provenance/reference counts render exactly as before.

### Threat Assessment

- **Trust boundaries:** no dependency, connector, credential, input format,
  write path or outbound destination was added.
- **Threat model:** no documented threat or residual risk changes. Existing
  authentication, scope enforcement, provider validation and output escaping
  controls remain in place.
- **Failure and abuse:** planned, missing, duplicate, unavailable, malformed
  provider and hostile-text paths remain fail-closed. Existing evidence is
  preserved because the renderer still has no event-log write path.

### Validation

- **Evidence:** authenticated route tests, deterministic/read-only tests,
  malformed-provider isolation, applicability-state tests, hostile-text
  escaping, three-mission shared-structure coverage, normalized byte parity,
  full regression suite and security-document validation.
- **Deferred work:** the presentation debt above remains explicit. No security
  control is described as implemented by this refactor.

## Verification

- Mission Control focused suite: **82 passed**
- Full suite: **551 passed**, with the existing Starlette TestClient
  deprecation warning
- Security documentation validation: **COMPLETE**
- Repository structure/documentation validation: **COMPLETE**
- Deterministic replay and event-log hash chain: **OK**
- `git diff --check`: clean
- `validate.sh`: tests and mock-model architecture exercise completed; the
  script returned its documented non-zero result because no real-model API
  keys were present, so this is not represented as V1.0 real-model validation
- Normalized route HTML parity: byte-identical for all three live missions

## Review disposition

The branch is ready for the independent Architecture and Security gates. It
must not be described as approved until those read-only reviews complete.
