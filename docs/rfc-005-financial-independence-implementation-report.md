# RFC-005 — Financial Independence Vertical Slice

Status: adversarial-review remediation implemented; automated verification
complete; manual visual review accepted.

## Branch and base

- Repository:
  `/Users/chrisparker-brads/Documents/~:Projects:foundry/foundry`
- Branch: `rfc-005-financial-independence-mission-assessment`
- Base: `origin/main` at `5d74d6d11e7076225daeae9f4e938a3cc7db8b19`
- `security/agent-safety-controls` resolved to the same commit at branch
  creation. RFC-005 has no unmerged dependency on that branch.

## Architecture

The slice adds the approved `MissionAssessment` seam to Core. It does not add
a second Mission Engine:

1. Core owns immutable assessment request/result contracts and a fail-closed
   `MissionAssessmentRegistry`.
2. Finance owns the Financial Independence policy, accessible-assets metric,
   deterministic projection, phase/status/margin/delta-v calculations, and
   scenario recommendation assessment.
3. The web composition root registers Finance's provider.
4. Mission Control requests an assessment from Core and renders it without
   importing Finance or calculating mission state.

The detailed decision and calculation semantics are recorded in
[`rfc-005-financial-independence-architecture.md`](rfc-005-financial-independence-architecture.md).

## Implementation

- Added optional `assessment_policy_id` and `assumption_set_id` references to
  Core Mission declarations and replay.
- Added Core assessment contracts for mission status, phase, margin, delta-v,
  trajectory, low/base/high forecast, telemetry, recommendations, limitations,
  calculation version, and lineage.
- Added additive, event-sourced Finance `AssumptionSet` and `Scenario`
  entities.
- Added `finance.accessible_assets`, with the V1 inclusion policy restricted
  to owned liquid and near-liquid accounts/assets and explicit exclusions for
  pensions, property, vehicles, and illiquid holdings.
- Added configurable £450k/£750k/£1.5m phase thresholds. Lifestyle spending
  and withdrawal rate remain separate assumptions and cannot silently rewrite
  those policy bands.
- Added deterministic low/base/high real-return sensitivity paths. They are
  labelled as a sensitivity envelope, never a probability or confidence
  percentage.
- Added a scenario-backed highest-value recommendation. Its ETA impact is
  calculated in Finance and carries Assumption Set and Scenario provenance.
- Remediated the adversarial-review findings without changing the approved
  seam: phase presentation and structured recommendation data now travel in
  the domain-neutral assessment contract, while Finance remains the sole owner
  of policy and projection rules.
- Replaced the decorative forecast blur with a true two-dimensional
  low/high polygon. Low and high values map to distinct vertical geometry,
  corridor width follows their calculated divergence, and identical or
  insufficient inputs collapse to an explicit no-range state.
- Removed all Scenario-name amount parsing. The displayed amount is the
  structured `monthly_contribution_delta` used by the projection; incomplete
  or currency-mismatched structured data fails honestly.
- Bound `monthly_contribution_delta` to the Finance-owned canonical cadence
  `month`. Contradictory weekly, yearly, non-canonical, or malformed cadence
  declarations fail before the append-only log is mutated; Mission Control
  performs no corrective logic.
- Removed Financial Independence phase labels, thresholds, currency, and
  policy-id routing literals from Mission Control. The complete ordered
  milestone plan is rendered from the assessment.
- Separated Current Phase from Flight Status on the hero and homepage card;
  retained percentage-based Mission Margin and removed the legacy
  tolerance/distance language from the assessment-backed card.
- Reworked trajectory accessibility so the SVG is a labelled group rather
  than an image that hides descendants. Today and each milestone are
  keyboard-focusable, named, and disclose the same phase/threshold/date
  information on focus and pointer interaction.
- Aligned user-facing delta-v and recommendation impact to the monthly
  projection grid. Raw day conversions remain available only in the
  provenance drill-down for audit.
- Added the authenticated `/missions/financial-independence` route, linked
  only from the existing Financial Independence mission lane.
- Reused the production `earthrise.webp` asset in the hero and trajectory
  composition. No replacement image was created.
- Integrated the actual path, dashed base forecast, widening low/high
  sensitivity envelope, current position, and four phase milestones into the
  Earthrise hero. The former separate chart surface and duplicate
  status/ETA/margin rail were removed.
- Refined actual and forecast onto one continuous cubic orbital arc, removed
  the persistent legend, and rendered the low/high envelope as two feathered,
  low-opacity blue-grey layers. Today remains the dominant marker while
  milestones are restrained mission-plan annotations.
- Reduced the first analysis row to delta-v, phase completion, next action,
  and scenario-modelled impact. Deeper telemetry and provenance are collapsed
  behind one explicit drill-down.
- Simplified Next Burn to action, monthly amount, and estimated delta-v;
  Scenario id, declared source action, assumption references, and calculated
  detail remain available in the collapsed provenance drill-down.
- Extended the existing authenticated review renderer with a `--route`
  argument; no production authentication bypass was introduced.

## Migration and backwards compatibility

No event-log migration or rewrite is required.

- The two new Mission fields are optional. Historical Mission events replay
  with both values as `None` and continue through the legacy scalar
  evaluation path.
- Assumption Sets and Scenarios are additive Finance event types.
- Structured Scenario presentation fields are additive. Legacy Scenario
  events replay with those fields unset and return an honest unavailable
  recommendation instead of being parsed from prose.
- Existing valid monthly Scenarios replay unchanged. New structured
  `monthly_contribution_delta` Scenarios must declare the exact Finance-owned
  cadence `month`; invalid declarations are rejected before event append.
- New assessment, phase, delta-v, flight-status, and recommendation fields
  have defaults, so existing Core providers and callers remain source and
  replay compatible.
- The assessment registry returns an explicit unavailable result when no
  provider owns a policy id.
- The mission detail route renders an honest unavailable/undeclared state
  when its required Mission policy or Assumption Set is absent.
- Existing authentication, household scope, no-store rendering, CSP/security
  headers, provenance, event replay, and read-only rendering behaviour are
  unchanged and covered by regression tests.

## Verification

- Full suite: **341 passed** in 5.34 seconds.
- Focused Core Mission Assessment/Finance assessment/Finance
  metrics/Mission Control suite: **133 passed** in 2.68 seconds.
- Full-suite warning: one existing Starlette `httpx` compatibility
  deprecation warning.
- `git diff --check`: passed.
- The authenticated review fixture renders successfully through FastAPI's
  signed test session at `/missions/financial-independence`.

## Visual review status

The first manual review found that the hero and trajectory read as two
separate surfaces. The refinement now makes Earth, actual path, dashed base
forecast, widening sensitivity range, current position, and phase milestones
one composition. Milestones have text labels and keyboard focus; mobile stacks
the briefing above the integrated Earth/trajectory visual and reveals compact
milestone detail on focus.

The authenticated fixture renders successfully. The user accepted the manual
visual review after inspecting the local preview. Codex browser automation
cannot access the local `http://127.0.0.1` origin under the active enterprise
network policy; no alternate browser surface or policy workaround was used.

To regenerate the exact authenticated fixture:

```bash
.venv312/bin/python scripts/render_flight_deck_review.py \
  /private/tmp/foundry-fi-review \
  --route /missions/financial-independence
```

Manual visual review is accepted for the RFC-005 vertical slice.

## Adversarial review disposition

| Finding | Severity | Disposition | Rationale | Tests added | Follow-up owner / RFC |
|---|---|---|---|---|---|
| C1 | Critical | Fixed | Low/base/high values now produce distinct two-dimensional geometry; the corridor area and width are data-driven, and collapsed/partial/missing states are explicit. | `test_sensitivity_geometry_uses_distinct_low_and_high_paths`; collapsed, partial, missing, and single-point tests | RFC-005 |
| C2 | Critical | Fixed | Recommendation amount comes from the structured Scenario adjustment used by Finance projection, never Scenario prose. Finance binds `monthly_contribution_delta` to canonical cadence `month` and rejects contradictory or malformed cadence before event append. | Structured replay, misleading-name, changed-amount, missing-data, non-GBP, monthly acceptance, weekly/yearly/non-canonical/malformed rejection tests | RFC-005 |
| H1 | High | Fixed | Complete phase labels, bounds, unit, order, completion state, and versioned policy reference flow through `MissionAssessment`; Mission Control contains no FI policy literals. | Configurable policy and assessment-driven milestone/source-literal tests | RFC-005 |
| H2 | High | Fixed | Current Phase, Flight Status, Mission Margin, and delta-v now have separate labels and semantics on detail and homepage surfaces. | Ahead/nominal/at-risk/complete and homepage/detail vocabulary tests | RFC-005 |
| H3 | High | Fixed | Focusable milestones are no longer descendants of `role="img"`; Today and each milestone have accessible names and focus disclosure. | Keyboard/name/parent-role/focus styling/mobile disclosure tests | RFC-005 |
| H4 | High | Fixed | User-facing delta-v and recommendation impact use the engine’s month resolution; raw days are drill-down audit data only. | Below-one/one/multiple/delayed/unavailable/completed boundary tests | RFC-005 |
| M1 | Medium | Deferred | V1 cannot reconstruct a fully historical portfolio when entity revisions lack effective dates; the limitation remains disclosed. | Existing `as_of`/read-only/trajectory tests | Finance valuation-history RFC |
| M2 | Medium | Deferred | The underlying projection remains monthly by explicit scope. This remediation fixes presentation precision, not engine granularity. | Month-resolution boundary tests | Future projection-resolution RFC |
| M3 | Medium | Deferred | Per-request event replay and assessment cost is acceptable for the single read-only slice; caching needs broader lifecycle design. | Deterministic replay and read-only route regression | Platform performance RFC |
| M4 | Medium | Deferred | Household-level Assumption Set and Scenario scope redesign is outside this slice; current household scope remains fail-closed. | Authenticated route and synthetic-household regressions | Multi-tenant assumptions RFC |
| M5 | Medium | Deferred | Mission amendment lifecycle requires event and policy semantics beyond this remediation. | Existing legacy/additive replay tests | Mission authoring RFC |
| M6 | Medium | Deferred | Persisted assessment snapshots/reproducibility need an explicit retention and invalidation policy; V1 assessment remains deterministic and read-only. | Repeated-render and event-log immutability tests | Assessment persistence RFC |
| M7 | Medium | Deferred | V1 intentionally models only `monthly_contribution_delta`; unsupported adjustment keys are ignored rather than guessed. | Structured adjustment validation and unavailable-state tests | Recommendation catalogue RFC |
| M8 | Medium | Deferred | Accessible-asset classification remains structural V1 policy; broader product classification requires a dedicated policy lifecycle. | Pension/property/vehicle exclusion regression | Accessible-assets policy RFC |

No review finding was silently ignored. No finding was rejected in this
remediation pass.

## Deferred work

- Financial Resilience, Pension Independence, and Mortgage Freedom assessment
  providers and detail routes.
- The `/missions` index and replacement of all four homepage lanes.
- Mission/policy/Assumption Set/Scenario authoring controls.
- A generalized cross-domain recommendation catalogue and ranking policy.
- Calibrated probabilistic forecasting; V1 intentionally provides sensitivity
  ranges only.
- Historical reconstruction of undated entity revisions. V1 history uses
  deterministic `as_of` filtering over the current entity projection and
  discloses that limitation.
- Higher-than-monthly projection resolution.
- Per-request replay/assessment caching and event-log performance redesign.
- Cross-household or multi-tenant Assumption Set and Scenario scoping.
- Mission amendment lifecycle.
- Persisted `MissionAssessment` snapshots and reproducibility retention.
- Additional Scenario adjustment keys and generalized recommendation
  ranking.
- Broader structural classification and lifecycle policy for accessible
  assets.
- Persistence or audit events for viewed assessments. V1 rendering is
  deliberately read-only.
