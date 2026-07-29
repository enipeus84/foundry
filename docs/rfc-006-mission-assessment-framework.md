# RFC-006 — Mission Assessment Framework

Status: implemented for review.

## Decision

RFC-006 extends the RFC-005 seam without creating a second mission engine.
Core owns discovery and domain-neutral assessment contracts. Product domains
own definitions, policies, evidence selection and calculations. Mission
Control discovers and renders contracts without importing a product domain or
branching on a mission name.

The approved Core vocabularies are closed:

- Trajectory: Accelerated, Nominal, Constrained, Divergent, Critical,
  Complete.
- Mission Margin: High Margin, Adequate Margin, Low Margin, Negative Margin.
- Mission Confidence: Established, Supported, Provisional, Insufficient.

Mission Margin measures resilience, tolerance and operating buffer. Mission
Confidence measures confidence in the assessment itself. Neither is derived
from the other, and trajectory is not derived from either. A domain policy
must supply all applicable dimensions explicitly.

## Contracts and ownership

`MissionDefinition` carries the safe route slug, display label, canonical
order, destination direction, optional description and optional assessment
policy id. It contains no household state, target, threshold or assessment
result.

`MissionMilestone` replaces phase terminology in new consumers and adds an
explicit `higher_is_better` or `lower_is_better` destination direction plus
an optional destination value. `TelemetryItem` carries a metric result with
its label, format and qualifier, removing metric-specific presentation rules
from Mission Control.

`MissionAssessmentRegistry` owns definition discovery, stable ordering,
policy dispatch and the provider envelope. It validates result identity and
scope plus nested renderer-consumed values. Milestone direction must agree
with the registered definition. An exception, unsupported result, forged
request identity, malformed nested value or cross-scope metric result
degrades only that request to deterministic `unavailable` / `Insufficient`;
`available` and `stale` metric evidence must carry a finite value. Private
exception text is not rendered.

Finance owns this fixed definition order:

1. Financial Resilience
2. Financial Independence
3. Pension Independence
4. Mortgage Freedom

Children is not in the fixed Finance hierarchy. Only Financial Independence
declares a policy id or has an assessment provider in this RFC. The other
three definitions are discovery metadata and render as planned without
inventing policy.

## Financial Independence migration

The existing FI calculation remains the authority for accessible assets,
schedule status, ETA, milestones, low/base/high sensitivity forecast,
delta-v and scenario recommendations. Its schedule policy now emits the
legacy presentation status, Core trajectory and an explicit trajectory
presentation tone together from the underlying schedule inputs. Mission
Control consumes the tone; it never derives colour from legacy status,
trajectory, margin or confidence.

The former user-facing `Ahead` state is `Accelerated`. FI margin state is
calculated only from pace and schedule-buffer evidence. FI confidence is:

- Insufficient when required evidence or target-date policy is absent;
- Provisional when current evidence is stale;
- Supported when current declared evidence and active assumptions support
  the deterministic assessment.

`Established` is valid Core vocabulary but is not claimed by FI v1.
Forecasts remain distinct from observed trajectory and remain labelled as
sensitivity paths, not probabilities. Provider validation rejects any
observation after the assessment time and any forecast before it.

## Generic presentation and routing

The authenticated route is `/missions/{slug}`. The slug is resolved only
through registered definitions. Unknown or unsafe values return a generic
404 without reflection. A known definition without a provider renders a
planned state that explicitly says no target, threshold, evidence or mission
state was inferred.

Homepage mission rows are ordered from registered definitions. A live mission
is associated to a definition by its stable assessment policy id. Legacy
scalar missions are appended through one deprecated compatibility adapter;
they are never classified by name. Direction-aware trajectory geometry uses
the milestone contract after registry validation against the definition, so
a later lower-is-better implementation does not
require Mortgage Freedom branching in Mission Control or the Flight Deck.
Multiple active missions claiming one definition fail closed as ambiguous;
the renderer never silently chooses one.

## Compatibility

Historical Mission events remain unchanged and replay without assessment
fields. `MissionPhaseAssessment` is an alias for `MissionMilestone`, and the
RFC-005 `phase`, `phases`, and flight-status fields remain temporarily on the
assessment result. New Finance and Mission Control code consumes the new
fields.

The scalar `get_mission_status` path is reachable only through
`_legacy_scalar_mission_status` for active Missions with no assessment policy.
It is deprecated and must gain no new consumer.

Removal requires all of the following:

1. every supported active/replayed mission is linked to a registered
   `MissionDefinition` and provider;
2. repository and supported integration searches find no consumer of the
   RFC-005 alias/fields or scalar adapter;
3. migration guidance has shipped for at least one compatibility release;
4. removal occurs in an explicitly approved breaking change.

## Security Considerations

- **Authentication:** No identity flow changes. Every generic mission route
  performs the existing session check before definition lookup or rendering.
  Authentication and health routes remain the only public routes.
- **Authorisation:** The current single configured identity retains the same
  all-or-nothing read access. Assessment requests carry an explicit
  household/member `Subject`; provider results and telemetry must match that
  scope. This is representation and fail-closed validation, not a claim of
  multi-member authorisation.
- **Sensitive data and secrets:** No new persistence, outbound destination,
  credential or log payload is added. Provider exception text is suppressed.
- **Auditability:** Assessment remains deterministic and read-only. Existing
  input, evidence and assumption references remain separate; no view event or
  snapshot is invented.

## Threat Assessment

- **Trust boundaries:** The generic slug is untrusted route input and is
  resolved against validated definitions. In-process provider output is
  treated as an untrusted envelope. No external trust boundary is added.
- **Threat model:** T6 (authorisation failure) is narrowed by scope-envelope
  validation but remains a residual risk because Foundry still has no
  household/member authorisation model. T8-style malformed input handling is
  applied to route and provider data. No residual risk is silently accepted.
- **Failure and abuse:** Unsupported/forged definitions fail at construction;
  unknown routes return a non-reflective 404; one malformed provider returns
  NOT EVALUABLE for only its mission. Existing evidence is never mutated.

## Validation

- **Evidence:** Core contract/vocabulary tests; Finance definition/order
  tests; FI schedule, margin, confidence, stale/absent evidence and
  behavioural regression tests; generic-route, provider-isolation,
  lower-is-better geometry, source-boundary and repeated-render tests.
- **Deferred work:** Multi-household/member authorisation, provider lifecycle,
  historical reconstruction, persisted assessments and all non-FI assessment
  implementations remain explicit in the technical-debt register.

This completes every question in the repository Security by Design checklist.
The threat model's trust boundaries do not move; the assurance register is
updated because the web/assessment control and its evidence changed.
