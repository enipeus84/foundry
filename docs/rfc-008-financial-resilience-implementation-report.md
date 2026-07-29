# RFC-008 — Financial Resilience Mission Implementation Report

Status: Phase 2 implementation complete on the RFC branch; no PR opened.

## Scope

Implemented Financial Resilience as the third live Mission Assessment
provider. It is a steady-state mission whose quantitative destination is
eighteen months of the existing `finance.liquidity_runway` metric.
Pension Independence remains metadata-only and Children remains outside the
fixed hierarchy.

Phase 1's applicability framework is checkpointed separately at `efcb373`.
Phase 2 changes that framework only where live FI and Mortgage out-of-horizon
assessments exposed a genuine integration defect: an absent but meaningful ETA
is now declared `unavailable` by those providers, preserving the rest of the
assessment. Their normal all-applicable output remains unchanged.

## Repository and baseline

- Canonical repository: `/Users/chrisparker-brads/Projects/foundry`
- Phase 1 checkpoint: `efcb373`
- Branch: `rfc-008-financial-resilience-mission`
- Declared environment: `.[dev,web]`
- Baseline before RFC-008: **453 collected, 453 passed**
- Phase 1 focused checkpoint: **107 passed**

## Architecture result

- Finance owns the resilience evidence envelope, four published metrics,
  deterministic stress arithmetic, reserve bands, margin, confidence and
  recommendation policy.
- Core retains one domain-neutral Mission Assessment model. Financial
  Resilience declares ETA, Delta-v and forecast `not_applicable`, and
  trajectory `unavailable`.
- Mission Control renders those declared states without mission-name,
  mission-slug, policy-id, truthiness or empty-tuple inference.
- The existing authenticated generic mission route renders Financial
  Resilience. No route, authentication, dependency, connector, model,
  credential or outbound network surface was added.
- No assessor imports or calls another assessor. Cross-mission constraints
  remain metrics plus consumer-local thresholds.
- The Event Log, Canon and Kernel are unchanged.

## Evidence and metrics

The manual evidence envelope records a household id, governed field, value,
effective date, confidence, source, lineage and optional currency, due date and
description. Validation occurs before append. Replay is tolerant:
party-attributable malformed envelopes remain quarantined and lower confidence,
future records are disclosed but excluded, and equal-time ties follow append
order. Current income declarations supersede by the explicit `source` envelope
field; no display text is parsed to infer source identity.

`FinanceResilienceMetricProvider` owns exactly:

- `finance.essential_outflow_monthly`
- `finance.emergency_reserve_target`
- `finance.emergency_reserve_gap`
- `finance.deployable_surplus`

The published outflow metric delegates to the exact existing
`FinanceMetricProvider._average_essential_outflow` basis, so
`liquid holdings ÷ essential outflow` reproduces the unchanged
`finance.liquidity_runway`. The target is fixed at eighteen months. The gap is
signed. Deployable surplus is the conservative GBP stock remaining after the
full target and recognised dated commitments, clamped at zero. A missing or
out-of-horizon commitment term is zero only with an explicit limitation.
Provider-local memoisation removes repeated dependency calculation within one
request without persisting a second source of truth.

## Assessment result

Reserve milestones are exactly Exposed `[0,1)`, Fragile `[1,3)`, Buffered
`[3,6)`, Secure `[6,18)` and Fortified `[18,+∞)`. Fortified alone completes the
mission. Completion is recomputed from the read model and reverses without an
event append; six months remains operational resilience rather than
completion.

Worst-factor margin uses reserve coverage, attributable income concentration,
liquid commitment coverage and obligation headroom with no weights.
Protection is explicitly not assessed, never inferred and never treated as
evidence of absence. Confidence is capped at Supported. Four deterministic
stress telemetry values remain observations, not probability forecasts or
Finance Scenario entities.

The Financial Resilience recommendation exposes its declared action, amount,
monthly cadence, evidence, eighteen-month threshold and reserve-position
effect. Estimated Delta-v is omitted. Mortgage Freedom received only the
separately approved D7 wording amendment.

## Three-live-mission performance envelope

Measured locally on Python 3.12 against the fixed synthetic household at
`as_of=1_750_000_000`, a 564-event log, three registered assessors, 50 warmed
assessment samples and 20 warmed HTTP samples per route:

| Operation | Median | p95 |
|---|---:|---:|
| Build projections and assess all three missions | 36.331 ms | 39.213 ms |
| Homepage render | 52.585 ms | 53.816 ms |
| Financial Resilience detail | 34.450 ms | 35.023 ms |
| Financial Independence detail | 29.468 ms | 30.784 ms |
| Mortgage Freedom detail | 18.399 ms | 18.823 ms |

This is a measurement, not a service-level objective. Per-request replay
remains documented debt; no persistent cache or snapshot was introduced.

## Security by Design checklist

### Security Considerations

- **Authentication:** unchanged. The existing generic mission route remains
  protected by the configured single-account session check; `/health` and
  authentication routes remain the only public surfaces.
- **Authorisation:** unchanged. Server-side replay selects the household scope,
  provider envelopes revalidate exact scope and timestamp, and the current
  single-account deployment still has no member/object-level authorisation.
- **Sensitive data and secrets:** liquid holdings, outflow, income and
  commitments are personal-confidential; stress outputs are derived-sensitive.
  They remain in the event log or ephemeral read models. No credential,
  connector, parser, external destination or log payload emission was added.
- **Auditability:** accepted declarations are immutable events carrying
  asserted actor, source, confidence, effective date and lineage. Assessments
  and completion are derived observations and never append events.

### Threat Assessment

- **Trust boundaries:** the manual evidence writer is an in-process,
  operator-supplied input boundary. It accepts no files, network data or
  credentials and is not exposed by an HTTP write route.
- **Threat model:** T6, T8 and T10 are relevant. Read-time scope checks,
  closed-field validation, quarantine and fail-closed provider dispatch are
  implemented; single-user/object-authorisation and manual-attribution risks
  remain explicit.
- **Failure and abuse:** malformed manual input is rejected before append;
  hostile direct-log envelopes are quarantined; future/stale input cannot
  improve a band; one provider failure leaves the rest of the deck intact.
  Unattributable invalid envelopes remain projection-level operator evidence
  and are never assigned across households.

### Validation

- **Evidence:** focused evidence/metric/assessment tests, cross-scope and
  hostile-envelope cases, deterministic/read-only assertions, source
  supersession, out-of-horizon commitment disclosure, output escaping,
  applicability contract tests and the full regression suite.
- **Deferred work:** authenticated evidence attribution, bounded manual
  envelope strings, an operator quarantine surface, multi-user/object-level
  authorisation, live ingestion, protection evidence and richer commitment
  entities are recorded in
  [`rfc-008-technical-debt.md`](rfc-008-technical-debt.md).

## Adversarial-review disposition

| Review finding | Disposition |
|---|---|
| Architecture C1: commitment factors double-counted conservative surplus | Corrected: commitment funding uses liquid holdings while reserve coverage separately enforces the full eighteen-month destination; M4 remains frozen and conservative. |
| Architecture H2: income restatement fabricated plurality | Corrected: latest declaration per explicit source wins deterministically; regression test added. |
| Architecture H3: income-loss stresses contradicted gross runway | Corrected: stresses now model declared-duration cash shortfalls against essential outflow; all four values are numerically asserted. |
| Architecture H4: repeated metric dependency fan-out | Corrected with provider-request-local memoisation; benchmark improved and is recorded above. |
| Architecture M1/M2/M4: invalid scope/dead branch/horizon silence | Corrected with exact invalid-party scoping, dead-code removal and explicit out-of-horizon limitation. |
| Security H1: FI/Mortgage absent ETA collapsed the whole assessment | Corrected: each provider declares ETA `unavailable` only when its legitimate ETA is absent; registry-level provenance-preservation regressions added. |
| Final Architecture H1: negative runway fell outside all milestones | Corrected: every value below the Fragile threshold selects Exposed; a negative-runway regression pins Critical/red output and preserved provenance. |
| Final Architecture H2: absent income fabricated a reduction stress | Corrected: the income-dependent stress is omitted with an explicit limitation when attributable income evidence is absent; the other three stresses remain. |
| Final Architecture H-A: limitation predicate differed from stress predicate | Corrected: missing income and unavailable employer concentration have separate, truthful limitations; an income-present/concentration-unavailable regression pins the stress as present with no false exclusion copy. |
| Security M1–M3 and L1–L3 | Deferred with current single-user/no-write-route justification in the RFC-008 debt register; the checklist now states projection-level visibility precisely. |

Final Architecture and Security Gate verdicts are recorded in
[Verification](#verification).

## Verification

- Focused Core/FI/Mortgage/Resilience/Mission Control suite:
  **259 passed**
- Full suite: **529 collected, 529 passed**, with the existing Starlette
  TestClient deprecation warning
- Focused selector:
  `tests/test_core_mission_assessment.py`,
  `tests/test_finance_mission_assessment.py`,
  `tests/test_mortgage_assessment.py`, all three `test_resilience_*.py` files,
  and `tests/test_mission_control.py`
- Security documentation validation: **COMPLETE**
- `git diff --check`: clean
- Golden assessment JSON: byte-identical for FI and Mortgage
- FI and Mortgage detail-route bodies and homepage lanes: byte-identical;
  expected footer version/metric/test/commit metadata excluded
- No Mission Control branch on mission name, slug or policy id; no renderer
  applicability state inferred from a missing value
- Architecture Gate: **APPROVE (Production)** — no Critical or High findings;
  final predicate/limitation and degraded-path remediations verified
- Security Gate: **APPROVE** — no Critical or High findings; remaining
  fail-closed FI provenance edge and Low risks recorded in technical debt

No push or pull request is part of this phase.
