# RFC-010 Phase 1 Implementation Report

## Scope and gate

Phase 1 implements the shared Mission Console contracts, the pure Mission
Console Model, shared server-rendered console primitives, and the Pension
Independence reference migration. Financial Resilience, Mortgage Freedom and
Financial Independence remain on the legacy Mission Detail renderer. The
Governor visual review is the blocking gate before any further migration.

## Shared implementation

- Core adds the `essential` telemetry region, trajectory-movement vocabulary,
  margin applicability, and the domain-neutral margin value, unit, format and
  provider label.
- `MissionConsoleModel` owns region order, visibility, card priority,
  telemetry grouping, disclosure placement and disclosure order. It is frozen,
  deterministic, side-effect free and emits no markup.
- The renderer consumes the model's order and provides the five universal
  regions, a composed trajectory panel, a bounded supporting rail, a capped
  essential telemetry grid, one dominant Next Burn, and native disclosure
  controls.
- Provider strings stay plain text and are escaped at render. Pre-rendered
  fragments are marked with `TrustedHtml` and are constructed only inside
  Mission Control.

## Pension Independence migration

Pension declares Current Pension, Required Retirement Wealth and Funding Ratio
as essential telemetry. Its Mission Margin is presented as Income Gap using the
shared margin quantity. Supporting telemetry is provider-grouped into
projection, income composition, contributions, requirements and margin
evidence disclosures. The cross-mission liquidity precedence case is an
explicit suppressed burn rather than an incomplete recommendation.

## Behaviour intentionally preserved

The generic authenticated route, page shell, Earthrise asset, navigation,
formatters, trajectory geometry, evidence scope and read-only behaviour remain
unchanged. The three non-reference Finance missions do not declare essential
telemetry and therefore continue through their existing renderer without a
mission-name branch.

## Validation

- Baseline: 594 tests passed on Python 3.13.
- Final: 602 tests passed on Python 3.13.
- Route goldens remain deterministic for all four Finance missions.
- Browser QA covered the live Pension route, native disclosure interaction,
  desktop composition and a 321 CSS-pixel viewport with no horizontal scroll.

## Security considerations

- **Authentication and authorisation:** unchanged; session validation remains
  first in the route and household scope is selected before dispatch.
- **Sensitive data and secrets:** no new persistence, logging, client storage,
  outbound destination or credential. Disclosure is presentation, not access
  control; its content is already authorised page content.
- **Auditability:** assessment remains read-only and all values retain existing
  evidence and assumption references.
- **Trust boundaries:** no dependency, connector or public route added.
- **Failure and abuse:** provider envelope validation caps essential telemetry
  at six, rejects non-current essential evidence, enforces margin consistency
  and preserves per-mission fail-closed isolation.
- **Deferred work:** Decision 15 retirements that require migration of the
  remaining missions stay behind the Governor gate. The deprecated margin
  numerics remain for the approved compatibility release.
