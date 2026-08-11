# RFC-017 Phase 2 — Pension Provenance Implementation Report

**Status:** Candidate for TELMU validation. **Authority:** Governor amendment
`6b35850eba8ecd3654143699f7ca186e5571ccd8` (GD-P2-A through GD-P2-I).

## Delivered boundary

`finance.pension_wealth` now has a Finance-owned RFC-017 explainer. It
replays canonical events into fresh Core, Finance and pension-evidence
projections limited to `event.ts <= ValueReference.known_at`, then delegates
the root value to `FinancePensionMetricProvider`. Finance provides a root
quantity, attributed account contributions, contextual references and typed
exclusions; Core derives completeness and residual.

The explainer registers through `web.py:_build_console()` with a
`CanonicalSubjectAuthority` built from the canonical Core party and asset
registration read views. It adds no route, API, Flight Deck, Operations or
Mission Assessment consumer.

## Governor rulings applied

GD-P2-A adds the one authorised Core vocabulary value, `conflicting`.
GD-P2-B/C use the deliberately unregistered terminal value id
`finance.pension_account_attributed_contribution` for every attributed
additive account edge (`expandable=False`). The registered contextual raw
valuation id is `finance.pension_account_raw_valuation`; ownership context is
a same-resource terminal reference, with the retained canonical ownership-link
event ids anchored on the root.

GD-P2-D maps DB-entitlement/pot-valuation conflicts to `conflicting`, missing
qualifying valuations to `unobserved`, future-only valuations to
`out_of_period`, and unavailable currency conversion to `incommensurable`.
GD-P2-E is satisfied by replaying every canonical event known at the request
coordinate, including account declaration, update, link and closure events.

GD-P2-F governs the numerical rule: attributed contribution is calculated by
the same narrow provider helpers and filtered ownership links used by
`finance.pension_wealth`. RFC-017 Phase 2 does **not** correct pension
weighting semantics. OBS-PENSION-01 is reproduced as a regression: a retained
implicit person ownership link can receive full attribution when the existing
metric has filtered out a co-owner's link.

GD-P2-G/H/I add descriptor-scoped numeric reconciliation. Composition registers
`ExplanationDescriptor("finance.pension_wealth", "GBP", tolerance=1e-6)`.
The tolerance affects only Core's completeness classification for this value;
it does not change the metric root, per-account attributed quantities,
exclusions, or the literal residual. Thus representation-level float drift may
be `complete` while its non-zero residual remains disclosed. A £0.01 mismatch
remains `partial`, and values without this descriptor retain exact comparison.
This is not a Finance or Core reducer change. GD-P2-F/P2-L and
OBS-PENSION-01 are unchanged; TELMU-P2-02 remains outside this burn.

TELMU-P2-01's root cause is retained, not hidden: Finance aggregates with
sequential `total += contribution`, while Core reconciles additive edges with
`sum()`. Identical economic quantities can therefore retain a
representation-level raw residual. The accepted remedy classifies that residual
through the authorised descriptor tolerance; it does not eliminate floating
point arithmetic. Python versions may expose different insignificant residual
bits, but must retain the same tolerance-aware completeness classification.

## Evidence not used

Employee contributions, employer contributions, tax relief, transfers,
withdrawals and fees are not read. Investment growth is not derived. Pension
wealth remains a valuation rollup, not a contribution-history explanation.

## Tests and probes

`tests/test_rfc_017_phase_2_pension_provenance.py` proves household,
fractional-person and OBS-PENSION-01 equivalence; contextual raw valuation and
ownership-link evidence; conflict/missing/out-of-period/incommensurable
distinctions; ownership and valuation `known_at` replay; terminal-id registry
consistency; SubjectAuthority refusal; deterministic read-only execution.

The numeric-reconciliation regressions exercise the production pension
descriptor and composition path: `0.1 + 0.2 + 0.3` is complete within the
authorised tolerance while retaining its raw residual; a £0.01 mismatch remains
partial; exclusions still force partial; another value id remains exact; and FX,
large and small pension values retain the same absolute `1e-6 GBP` boundary.
Raw residual bits may vary across Python versions, but the tolerance-aware
complete/partial classification is the acceptance contract.

The terminal-id probe deliberately registers an explainer for the terminal
identifier and confirms the existing resolver rejects its conflict with the
non-expandable edge when traversal is requested. No resolver rule is relaxed.

## Remaining limitations

`ValueReference` has no attribution dimension, so the attributed edge remains
terminal by design. Ownership context is anchored by the canonical link events
that the metric actually retains; provenance neither restores discarded links
nor decides whether Finance's filter-before-weight behaviour is desirable.
No contribution, growth, tax-relief, transfer, withdrawal or fee provenance is
provided by this phase.
