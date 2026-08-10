# RFC-017 — Value Provenance Framework: Phase 1 Implementation Report

**Status:** SAFE remediation applied; pending SAFE Confirmation.  This report
records the initial implementation and its bounded remediations against frozen
authority `b8cc0ed9c63b10d2fbc03ec9440c154826c7efd6`.  It authorises no Phase 2
work and claims no merge authority.

**Reviewed candidate:** `dfbaeab34041eb654f26a57afa541ca4c5ede28b` — SAFE
verdict **REMEDIATE** (1 HIGH, 3 MEDIUM, 4 LOW, 4 observations).

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

Bounded to the three findings the Governor authorised.  No other change is
carried, and no LOW finding was acted on: none was inseparable from an
authorised remediation.

| Finding | Severity | Root cause | Remediation | Executable evidence |
|---|---|---|---|---|
| **SAFE-017-01** | HIGH | Status coherence was a **deny-list** of the two known failure statuses. `METRIC_STATUS` is an *extensible* vocabulary, so `error` — and anything a domain adds later — inherited a fail-open default and could balance its parts into a confident `complete` with a real quantity | `MAGNITUDE_BEARING_STATUS = {"available", "stale"}` states positively which statuses may carry magnitude and coverage; everything else normalises through the existing path to absent quantity, completeness and residual | `test_safe_017_01_no_failure_status_can_carry_a_coverage_claim` (parametrised over every non-authorised member of `METRIC_STATUS`), `…_authorised_statuses_still_report_coverage`, `…_status_allow_list_is_closed_against_vocabulary_extension` |
| **SAFE-017-02** | MEDIUM | Coordinate verification ran immediately before a recursive dispatch, so a contributor that was never expanded — no registered explainer, or the depth bound reached — reached the caller unchecked. A node could present a foreign `Subject` or a `known_at` outside the requested frame inside an otherwise `complete` explanation | `_verify_emitted_references` runs during structural verification, before any expansion decision, over **every** contribution and exclusion. The now-redundant pre-dispatch call is removed rather than left as dead code | `test_safe_017_02_unexpandable_contributor_coordinates_are_verified` (all three roles), `…_depth_bound_does_not_suspend_coordinate_verification` (each coordinate), `…_exclusion_subject_is_verified`, `…_conforming_references_still_resolve` |
| **SAFE-017-03** | MEDIUM | `register()` validated each `value_id` but discarded the normalised result and registered the raw key, while `ValueReference` normalises its own. Two explainers could own ids differing only by surrounding whitespace: the duplicate guard did not fire and one owner became unreachable | The single ownership declaration is normalised once into a `frozenset` before duplicate validation and before registration. The R4 single-read property is preserved | `test_safe_017_03_ownership_is_normalised_before_duplicate_validation`, `…_normalised_ownership_routes_a_padded_declaration`, `…_ownership_is_read_exactly_once` |

**SAFE-017-04** is accepted as debt and recorded with measured evidence against
watch item **W4** in [`rfc-017-technical-debt.md`](rfc-017-technical-debt.md).
The measurement contradicts W4's stated mitigation: depth limits alone do not
bound the work, and thirteen distinct values can cost 797,161 resolutions.

Every SAFE reproducer is retained as an ordinary test.  No existing test was
deleted or weakened, and the three refusal paths added refuse strictly more
than before — no input that previously resolved now fails.

### Raised, not remediated — requires a Governor decision before Phase 2

Core requires a contributor's `Subject` to **equal** its parent's.  RFC-017
§7.1 and §7.2 both decompose a `party:household` value into
`resource:obligation` and `resource:account` contributors, so **the frozen
architecture's own worked examples are inexpressible**:

```text
RFC-017 §7.1 shape REFUSED: ValueProvenanceError -
  recursive contributor must preserve subject, as_of, and known_at
```

This predates this remediation and was not created by it; SAFE-017-02 extended
the existing rule's coverage without altering the rule.  It is recorded as
**OBS-017-A** and is a Phase 2 blocker: a property-equity explainer cannot be
written under the current rule.  RFC §9 states that Core *cannot* verify domain
scope containment and assigns it to the domain, which points at temporal
equality plus a non-broadening subject rule — but that is an architectural
decision and **is not taken here**.

## Validation after remediation

| Run | Result |
|---|---|
| RFC-017 focused (BOOSTER + TELMU + SAFE remediation) | **57 passed** (40 pre-existing, unchanged; 17 added) |
| Full regression | **762 passed, 2 failed** |
| The 2 failures | `test_demo_data.py::test_unwritable_path_fails_visibly` and `::test_maybe_seed_demo_data_propagates_the_failure` — environmental, not candidate defects. The suite ran as `euid 0`, and root writes into a `0500` directory, so the tests' premise cannot hold. Neither file is touched by this candidate, and both fail identically before the remediation |
| `git diff --check` | clean |

## Scope boundary

Changed: `core/value_provenance.py`, one new test module, this report and the
new technical-debt register.  Unchanged: every frozen contract, `MetricResult`,
RFC-006, `MissionTarget`, all existing calculations, Finance, canonical events,
write paths and every presentation surface.  No Phase 2 work is begun and no
merge authority is claimed.
