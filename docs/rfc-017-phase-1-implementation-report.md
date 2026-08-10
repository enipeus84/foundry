# RFC-017 — Value Provenance Framework: Phase 1 Implementation Report

**Status:** Pending TELMU re-validation.  This report records the initial
implementation and its bounded remediation against frozen authority
`b8cc0ed9c63b10d2fbc03ec9440c154826c7efd6`.  It authorises no Phase 2 work.

## Delivered Phase 1 boundary

The Core-only framework provides the five RFC-017 shapes, four closed
vocabularies, explicit explainer registration, resolver-owned completeness and
residual derivation, bounded lazy expansion, and mock-domain evidence.  It
adds no event, persistence path, production explainer, calculation change,
consumer, `MetricResult` change, or RFC-006 change.

## TELMU remediation

| Finding | Severity | Root cause | Remediation | Executable evidence | Criterion restored |
|---|---|---|---|---|---|
| Recursive coordinate substitution | Critical | The resolver trusted a child `ValueReference` supplied by an explainer | Verify equal `Subject`, `as_of`, and `known_at` before every recursive dispatch; refuse a mismatch | `test_telmu_refuses_recursive_scope_and_temporal_substitution`, per-coordinate, nested and contextual probes | P1-F |
| Provider-declared completeness/residual | High | Resolver returned observed nodes before replacing helper-supplied fields | Recompute or clear both fields on every resolved node, including observed nodes | `test_telmu_refuses_explainer_declared_completeness_on_observed_node` | P1-C |
| Unavailable value reported complete | High | Status and quantity were not normalised together | `unavailable` and `unsupported` results are emitted with absent quantity, completeness and residual | `test_telmu_unavailable_node_cannot_make_a_completeness_claim` and parametrised status probe | P1-C / §4.5 |
| Stateful ownership declaration | Low | Registration called `explainable_value_ids()` twice | Capture, validate and register one `frozenset` declaration | `test_telmu_rejects_an_explainer_that_changes_its_owned_value_ids_during_registration` | Deterministic registry ownership |

The TELMU adversarial conditions remain as ordinary tests; none was deleted or
weakened.  The resolver does not overwrite malformed child coordinates: it
refuses them, preserving the failure evidence rather than concealing it.

## Scope preserved

The remediation changes only `core/value_provenance.py` and RFC-017 test and
report artefacts.  It does not alter frozen contracts, existing calculations,
Finance, RFC-006, canonical events, write paths, or any presentation surface.

## Validation

Focused and full results are recorded at handoff after TELMU-targeted tests,
relevant Core tests, and the full suite complete.  The next gate is TELMU
re-validation, not SAFE or merge authority.

## TELMU remediation loop 2

| Finding | Severity | Root cause | Required RFC behaviour | Code remediation | Executable evidence |
|---|---|---|---|---|---|
| Expanded additive quantity conflict | Medium | The resolver treated a valid expanded-child magnitude disagreement as a generic validation error | The parent resolves `unavailable` with absent quantity, completeness and residual | Keep structural validation errors as refusals; return the unavailable parent projection only when a valid expanded additive child disagrees with its declared quantity | `test_revalidation_expanded_additive_disagreement_makes_parent_unavailable`, increases/decreases, tolerance, nested and sibling probes |

This is a provenance conflict discovered during resolution, not a conversion,
substitution or correction of either magnitude.  Unit mismatch, malformed
shapes and other contract-invalid inputs retain their existing refusal paths.

## SAFE remediation

**SAFE review SHA:** `dfbaeab34041eb654f26a57afa541ca4c5ede28b`.
**Verdict:** REMEDIATE.  The frozen architecture remains unchanged.

| Finding | Disposition | Remediation evidence |
|---|---|---|
| SAFE-017-01 — status coherence | Only `available` and `stale` may carry usable magnitude and coverage; every other current or future `METRIC_STATUS` value normalises to the non-usable shape | `test_safe_017_01_only_positive_usable_statuses_may_claim_magnitude`; domain-added status probe |
| SAFE-017-02 — emitted coordinates | Every contribution is validated before output regardless of expansion state; exclusions preserve the requesting subject, the only coordinate carried by their frozen shape | unexpanded, contextual, depth-bound, nested and exclusion probes |
| SAFE-017-03 — registry ownership | One declaration snapshot is normalised, collision-checked and used as the registry key | cross-explainer whitespace, internal collision and stateful-declaration probes |
| SAFE-017-04 — recursive amplification | Accepted debt, not implemented in Phase 1 | [`rfc-017-technical-debt.md`](rfc-017-technical-debt.md) |

SAFE LOW-1 through LOW-4 and OBS-1 through OBS-4 remain advisory.  This burn
does not alter them except where the authorised coordinate hardening naturally
extends the previous recursive-substitution defence.
