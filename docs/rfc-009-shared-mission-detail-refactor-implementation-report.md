# RFC-009 Prep — Shared Mission Detail Refactor Implementation Report

Status: implementation complete on the RFC branch; PR #21 is open for
independent Architecture and Security review.

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
- At the original refactor pre-flight, GitHub had no open pull requests or
  Pension implementation branch. The current repository now has PR #21 for
  this shared-component prerequisite and PR #22 containing the approved
  RFC-009 Pension Independence architecture.
- PR #21 must pass the independent Architecture and Security gates and merge
  before the RFC-009 implementation burn begins on PR #22's branch.
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

## Canonical Mission Detail component inventory

| Component name | Classification | Purpose | Current consumers |
|---|---|---|---|
| `_render` | Shared Mission Control shell | Composes the authenticated page shell, navigation, metadata, responsive CSS and local interaction script around page content. | Flight Deck home, metric drill-down, every Mission Detail state and placeholder pages. |
| `_MissionHeroView` / `_render_mission_hero` | Shared Mission Detail | Renders mission identity, destination copy, current milestone, trajectory/ETA instruments, Mission Margin, Earthrise treatment and accessible trajectory summary. | Financial Resilience, Financial Independence and Mortgage Freedom through the generic live mission route. |
| `_FlightAnalysisView` / `_render_flight_analysis` | Shared Mission Detail | Renders the shared analysis heading, optional reference schedule, Delta-v instrument, milestone completion, Next Burn and optional estimated Delta-v. | Financial Resilience, Financial Independence and Mortgage Freedom; applicability controls which instruments are present, and Mortgage Freedom currently supplies the reference schedule. |
| `_MissionDataView` / `_render_mission_data` | Shared Mission Detail | Renders the disclosure containing primary telemetry, recommendation evidence, assumptions, limitations and provenance counts. | Financial Resilience, Financial Independence and Mortgage Freedom. |
| `_mission_trajectory_svg` | Shared Mission Detail instrument | Renders provider-declared trajectory, forecast, sensitivity and milestone presentation, or the declared unavailable/not-applicable state. | All three live mission assessments; Financial Independence and Mortgage Freedom currently render SVG trajectories, while Financial Resilience declares trajectory unavailable. |
| `_format_value`, `_month_year`, `_format_month_delta`, `_milestone_range_text` | Shared presentation helpers | Preserve canonical value, date, month-resolution Delta-v and milestone-bound wording. | Mission Hero, Flight Analysis, telemetry and trajectory presentation; `_format_value` is also consumed by the Flight Deck and metric drill-down. |
| `FinancialResilienceAssessor` | Mission-specific | Owns resilience evidence interpretation, reserve milestones, stress telemetry, margin, confidence and recommendation policy. | Financial Resilience only, registered behind `MissionAssessmentRegistry`. |
| `FinancialIndependenceAssessor` | Mission-specific | Owns Financial Independence telemetry, milestones, trajectory, forecast, schedule and scenario recommendation policy. | Financial Independence only, registered behind `MissionAssessmentRegistry`. |
| `MortgageFreedomAssessor` | Mission-specific | Owns mortgage evidence interpretation, acquisition/current/equity telemetry, repayment schedule, margin and overpayment recommendation policy. | Mortgage Freedom only, registered behind `MissionAssessmentRegistry`. |

No mission-specific HTML renderer exists. Mission-specific assessors project
the common Core contract; the shared Mission Detail components render that
contract without branching on mission name, slug or policy id.

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

## PR #21 review remediation — 2026-07-30

Independent review identified that `_MissionHeroView` described every input as
escaped at render even though some inputs are trusted, pre-rendered Mission
Control fragments. The presentation contracts now distinguish:

- plain text values escaped by the component renderer; and
- trusted internal fragments whose field names end in `_html`.

The same explicit naming and contract is applied to Mission Hero, Flight
Analysis and Mission Data. Provider- and evidence-derived text is escaped
before entering a trusted fragment. Focused regressions cover plain-text
escaping, escaped provider text, preserved internal structure and absence of
double escaping.

No Mission Detail content, layout or interaction changed. Financial
Resilience, Financial Independence and Mortgage Freedom are byte-identical
before and after the remediation except for the shared footer's expected test
count increasing from 460 to 462 when two tests were added. No Pension
Independence logic was introduced.

### Remediation validation

- `.venv/bin/python --version`: **Python 3.12.13**
- `.venv/bin/python -m pytest tests/test_mission_control.py -q`:
  **84 passed**, with the existing Starlette TestClient deprecation warning
- `.venv/bin/python -m pytest tests/test_docs_governance.py -q`:
  **4 passed**
- `.venv/bin/python scripts/validate_security_docs.py`:
  security documentation, repository structure and documentation
  **COMPLETE**
- `.venv/bin/python -m pytest tests -q`:
  **553 passed**, with the existing Starlette TestClient deprecation warning
- `git diff --check`: **clean**
- `./validate.sh`: security/documentation checks and **553 tests passed**;
  deterministic replay and the event-log hash chain passed; the script then
  returned its documented exit 1 because no real-model API keys were present,
  so this is not represented as V1.0 real-model validation
