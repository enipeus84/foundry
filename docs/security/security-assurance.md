# Security Assurance Register

This register records what Foundry's controls currently do, the evidence
that supports each statement, the control's maturity for its present
scope and work that remains. It does not convert proposed improvements
into existing controls.

The register uses the repository's component-level maturity vocabulary:

- **Prototype** — partial or procedural control with important gaps.
- **Beta** — implemented and tested for the current narrow scope.
- **Production** — evidence-backed and complete for its stated scope.

No entry is promoted by documentation alone.

## Authentication

**Objective.** Restrict application data routes to the configured
identity.

**Current implementation.** Google authentication is brokered through
Supabase using PKCE. The callback exchanges the code server-side.
Protected routes require a signed session whose email matches the single
configured email. Authentication and health routes are public.

**Evidence.** `src/foundry/webauth.py`,
`src/foundry/mission_control.py`, and `tests/test_webauth.py`.

**Maturity.** Beta for a single configured email.

**Missing or future control.** There is no multi-account configuration,
central route policy or household identity model.

## Authorisation

**Objective.** Ensure an authenticated identity can access only its
permitted household data and actions.

**Current implementation.** Authorisation is all-or-nothing: the single
configured email can reach all current application data routes; other
emails cannot. The current product surface is read-only.

**Evidence.** Route checks in `src/foundry/mission_control.py` and allowed,
disallowed and stale-email cases in `tests/test_webauth.py`.

**Maturity.** Prototype against Foundry's household-scoped ambition.

**Missing or future control.** No member isolation, roles, object-level
permissions, sharing policy or audited grant/revocation model exists.

## Session integrity

**Objective.** Reject forged and expired sessions and limit the lifetime
of a stolen session.

**Current implementation.** Stateless HMAC-SHA256 signed cookies carry
email and expiry. Cookies are HttpOnly, SameSite=Lax and Secure when the
configured base URL is HTTPS. The session lifetime is 12 hours.

**Evidence.** `src/foundry/webauth.py`; forged, expired-configuration,
cookie-attribute and logout cases in `tests/test_webauth.py`.

**Maturity.** Beta.

**Missing or future control.** No individual revocation exists and secret
entropy is documented but not enforced.

## Event integrity

**Objective.** Detect unintended modification of the ordered event
history.

**Current implementation.** Events contain a SHA-256 hash of canonical
event content and the previous event hash. `EventLog.verify()` recomputes
the chain.

**Evidence.** `src/foundry/eventlog.py`,
`tests/test_eventlog.py::test_edit_detection`,
`tests/test_eventlog.py::test_insertion_detection`, and
`tests/test_foundry.py::test_tamper_detection`.

**Maturity.** Beta as an internal consistency check.

**Missing or future control.** The chain is not signed, can be recomputed
by a writer, cannot detect valid-tail truncation and has no external
anchor. General appends assume one writer and have no fsync or
transaction-level crash guarantee.

## Provenance

**Objective.** Explain which source events and model actor produced a
claim.

**Current implementation.** Claim events store source-event identifiers,
evidence strings and the model name as the event actor. `Canon.explain()`
returns source and revision events.

**Evidence.**
`tests/test_foundry.py::test_4_provenance_on_every_claim`,
`tests/test_foundry.py::test_retrieval_returns_provenance_not_chunks`,
and `tests/test_foundry.py::test_claims_evolve_events_never_do`.

**Maturity.** Beta.

**Missing or future control.** Actor strings are not authenticated.
Real-model evidence strings are parsed but not checked for verbatim
presence in the source event.

## Audit trail

**Objective.** Preserve application-owned state changes as ordered events.

**Current implementation.** Ingestion, claim derivation, claim updates,
supersession and linking append events. Canon and domain projections
rebuild from the event log.

**Evidence.** `src/foundry/kernel.py`, `src/foundry/canon.py`,
`tests/test_canon.py::test_deterministic_replay`, and
`tests/test_foundry.py::test_claims_evolve_events_never_do`.

**Maturity.** Production for the current Kernel mutation surface.

**Missing or future control.** Filesystem-level changes are outside the
application audit trail. The actor field is supplied by the caller rather
than bound to an authenticated identity.

## Secrets handling

**Objective.** Keep credentials out of repository content, logs and the
event log.

**Current implementation.** Auth and model integrations read credentials
from the process environment. Documentation warns against ingestion and
requires rotation after accidental disclosure.

**Evidence.** `src/foundry/webauth.py`, `src/foundry/models.py`,
`README.md`, and `SECURITY.md`.

**Maturity.** Prototype; primarily convention and review.

**Missing or future control.** No automated repository scan, pre-ingestion
warning, redaction or log-retention control exists.

## Dependency management

**Objective.** Minimise third-party code in the substrate and keep
optional dependencies reviewable.

**Current implementation.** `pyproject.toml` declares no mandatory
runtime dependencies. Web, model and development packages are optional
extras. CI installs the development and web extras.

**Evidence.** `pyproject.toml`, `.github/workflows/test.yml`, and
`tests/test_web.py::test_core_import_does_not_require_fastapi`.

**Maturity.** Production for the empty mandatory dependency set; Prototype
for update and lock management of optional dependencies.

**Missing or future control.** No lockfile, automated dependency update,
dependency scanning or immutable Action pinning is configured.

## Web hardening

**Objective.** Reduce exposure of the current server-rendered product
surface.

**Current implementation.** The web layer applies CSP, frame denial,
content-type protection, referrer policy and no-store headers for
non-health, non-static responses. Protected routes validate the current
session.

**Evidence.** `src/foundry/web.py`,
`tests/test_web.py::test_security_headers_on_authenticated_pages`, and
`tests/test_webauth.py`.

**Maturity.** Beta.

**Missing or future control.** There is no central inventory proving that
every future data route applies the access check; review and route tests
remain the enforcement mechanism.

## Mission assessment isolation

**Objective.** Prevent malformed mission metadata or one faulty provider
from crossing scope boundaries, disclosing internal failures or fabricating
state for another mission.

**Current implementation.** Mission route slugs are validated
lowercase-kebab definitions registered at composition time. Unknown routes
return a generic non-reflective 404. Provider results must match the request's
mission, policy, timestamp and `Subject`; nested milestones, series,
recommendations, references and metric evidence receive runtime type,
finiteness, availability/value consistency, ordering, direction, timestamp and
scope validation before rendering. Current values and telemetry must retain
the same household/member scope. `available` and `stale` metric evidence must
carry a finite value. Exceptions and malformed envelopes degrade only the
requested mission
to a deterministic unavailable result with Insufficient confidence and no
private exception detail.

**Evidence.** `src/foundry/core/mission_assessment.py`,
`src/foundry/mission_control.py`,
`tests/test_core_mission_assessment.py`, and generic-route/provider-isolation
cases in `tests/test_mission_control.py`.

**Maturity.** Beta for in-process providers in the current single-user,
read-only application.

**Missing or future control.** Provider registration is not a plugin trust or
signature system. Scope validation is not household/member authorisation;
multi-user ownership and object-level permission policy remain absent.

## Manual mortgage evidence

**Objective.** Preserve the basis of Mortgage Freedom observations and prevent
malformed or cross-household evidence from becoming rendered mission state.

**Current implementation.** Finance records governed manual mortgage fields
with obligation id, value, optional unit, effective date, asserted confidence,
source and lineage. The projection rejects unsupported or malformed envelopes
into an invalid-event list. Assessment requires one active household mortgage
whose borrowers and secured-property owners are active household members.
Missing, future-only, hostile or cross-scope evidence fails closed. Stale
balance/property evidence remains visible as stale and lowers Mission
Confidence independently of trajectory and margin. The demonstration evidence
keeps the £450,000 purchase price separate from the £436,638.42 HPI dated
valuation reference for March 2025; the reference is neither a live nor a
current valuation. The original 300-month term is governed evidence and must
match the Mission destination exactly; missing, fractional, subtly shifted or
otherwise conflicting values fail closed. The current 201-month term cannot
replace the original contractual destination. Optional schedule presentation
metadata is validated again at the provider boundary; non-finite or unpaired
values and calendar-unrepresentable timestamps isolate that provider to an
unavailable assessment. Provider-controlled current-value units are escaped at
every shared SVG insertion point.

**Evidence.** `src/foundry/finance/mortgage_evidence.py`,
`src/foundry/finance/mortgage_assessment.py`,
`tests/test_mortgage_evidence.py`,
`tests/test_mortgage_assessment.py`, and Mortgage generic-route/isolation cases
in `tests/test_mission_control.py`.

**Maturity.** Beta for the explicit synthetic/manual proof-data scope.

**Missing or future control.** Source, lineage, actor and confidence are
assertions rather than authenticated attestations. There is no lender or
valuation connector, multi-mortgage policy, object-level authorisation,
automatic correction/supersession workflow or temporal-precision type.

## Manual resilience evidence

**Objective.** Preserve the attributed basis of Financial Resilience
observations while preventing malformed, future or cross-household evidence
from silently improving mission state.

**Current implementation.** Finance accepts a closed set of manual
essential-outflow cross-checks, income-source declarations, dated near-term
commitments and reserved unscored protection declarations. The writer validates
shape, finiteness, currency, confidence and due-date rules before append. The
tolerant projection quarantines malformed direct-log envelopes, filters by
exact household id and `as_of`, uses deterministic append-order tie-breaking
and supersedes current income declarations by explicit source. The assessor
revalidates every metric result's scope, timestamp, unit and availability,
discloses future/stale/invalid evidence, never infers cadence or protection,
and never appends an assessment or completion event.

**Evidence.** `src/foundry/finance/resilience_evidence.py`,
`src/foundry/finance/resilience_metrics.py`,
`src/foundry/finance/resilience_assessment.py`,
`tests/test_resilience_evidence.py`,
`tests/test_resilience_metrics.py`, and
`tests/test_resilience_assessment.py`.

**Maturity.** Beta for the explicit synthetic/manual, single-household,
read-only scope.

**Missing or future control.** Household id, source, lineage, confidence and
actor remain assertions; strings have no explicit size limits. Unattributable
quarantined envelopes are visible at projection/operator level only, because
assigning them to every household would cross scope. There is no authenticated
live provider, object-level authorisation, protection model or richer
commitment entity.

## Manual pension evidence

**Objective.** Preserve the observed and declared basis of Pension
Independence without allowing malformed, future, cross-basis or provider-like
text to become trusted mission state.

**Current implementation.** Finance accepts a closed set of account-scoped
contribution-rate, dated-payment, fee and DB-entitlement fields and
party-scoped State Pension fields. The in-process writer validates the field,
numeric finiteness, non-negativity, unit, confidence, source, lineage and
effective timestamp before append. Replay is deterministic and tolerant:
rates and entitlements supersede by effective date plus append order, dated
payments accumulate, future records are excluded visibly, and malformed
direct-log envelopes are quarantined. DC valuations remain existing Finance
valuation events; dated payments and annual rates are never added together.
The assessor derives completion and projection output without appending an
event. The existing authenticated generic Mission Detail route escapes
provider-declared text and does not render raw entity identifiers, evidence
payloads or assumption keys.

**Evidence.** `src/foundry/finance/pension_evidence.py`,
`src/foundry/finance/pension_metrics.py`,
`src/foundry/finance/pension_assessment.py`,
`tests/test_pension_evidence.py`, `tests/test_pension_metrics.py`,
`tests/test_pension_assessment.py`, and Pension route/escaping regressions in
`tests/test_mission_control.py`.

**Maturity.** Beta for the explicit synthetic/manual, single-household,
read-only scope.

**Missing or future control.** Subject id, source, lineage, confidence and
actor are assertions rather than authenticated attestations; free-text
envelope fields have no explicit size limits. No pension-provider connector,
policy-number field, annual-allowance rules, tax calculation, decumulation
model, regulated-advice workflow, multi-user object authorisation or operator
quarantine surface exists.

## Mission Target Management

**Objective.** Allow the authenticated operator to declare, replace and
withdraw a household Mission Target without giving the browser authority over
household scope, Mission semantics, lifecycle lineage or canonical event
shape.

**Current implementation.** Six routes under `/missions` require the existing
signed session and configured-email equality. Each POST accepts only
`application/x-www-form-urlencoded`, rejects multi-valued and unexpected
fields, and uses one of three non-transferable CSRF purposes for review,
declaration and withdrawal. Household, Mission metric, unit, dimension,
direction, horizon kind, approval-time `effective_from` and `supersedes` are
derived from current canonical state. Review writes nothing. Approval reloads
the projections and compares the current in-force predecessor with the plain
review-time assertion; mismatch refuses and requires a fresh review. That
assertion is compared only: it is absent from event payloads and cannot select
the predecessor. Mission status is rechecked at every write. Cross-household,
unknown, conflicted and inactive state refuses without disclosure or append.
Only `core.mission_target.declared` and `core.mission_target.closed` can be
written. The optional `basis` is escaped, bounded to 500 Unicode characters,
never interpreted, and disclosed as permanent append-only history before
approval.

**Evidence.** `src/foundry/mission_targets_web.py`,
`src/foundry/finance/mission_targets.py`, `src/foundry/web.py`, and the named
authority, CSRF, field-forgery, hostile-log, staleness, empty-world and replay
cases in `tests/test_rfc_016_phase_3_mission_target_management.py`.

**Maturity.** Candidate for TELMU and SAFE; not merged. The control set is
Beta-shaped for the current single configured operator and single-writer log,
but no maturity promotion occurs before independent review.

**Missing or future control.** Foundry still has no multi-member
authorisation model. Household selection remains the platform-wide
last-declared-active-household rule. The staleness assertion is plain rather
than separately signed because it grants no authority and can only match
server-derived truth or cause refusal; SAFE target S2 must challenge that
choice. The active-Mission check is a surface mitigation only;
`DEBT-016-P3-01` must be resolved before the first production consumer of
`in_force` Mission Target state.

## Operational logging

**Objective.** Support diagnosis without copying household content,
credentials or tokens into another store.

**Current implementation.** Application log messages are sparse and do
not intentionally include event payloads. Demo-data startup paths emit
seeded, skipped and failure states.

**Evidence.** Logging calls in `src/foundry/eventlog.py`,
`src/foundry/kernel.py`, `src/foundry/models.py`,
`src/foundry/demo_data.py` and related assertions in
`tests/test_demo_data.py`.

**Maturity.** Prototype.

**Missing or future control.** No repository logging standard, systematic
sensitive-data review or retention requirement exists.

## Validation

**Objective.** Continuously exercise architectural, product and
documentation guarantees.

**Current implementation.** Pytest covers the substrate, domains, web
surface and authentication across supported Python versions in the
existing CI workflow. `validate.sh` runs the suite and the architectural
demonstration. The security-document validator checks required files,
completion status and relative links without rejecting placeholders.

**Evidence.** `.github/workflows/test.yml`, `validate.sh`,
`scripts/validate.py`, `scripts/validate_security_docs.py`, and
`tests/test_docs_governance.py`.

**Maturity.** Beta.

**Missing or future control.** Real provider calls, hostile-input fuzzing
and restoration exercises are not part of CI.

## Backup and recovery

**Objective.** Recover an intact log after host or storage loss while
protecting every retained copy.

**Current implementation.** Deterministic replay can rebuild projections
from an intact copied log. The repository provides no automated backup,
off-host retention or restore procedure.

**Evidence.** Replay tests in `tests/test_canon.py` and
`tests/test_foundry.py`.

**Maturity.** Prototype.

**Missing or future control.** Backup schedule, storage, encryption,
retention, integrity verification and restore drills are all deferred to
the Security Governance review.

## Ingestors and connectors

**Objective.** Preserve useful provenance while constraining untrusted
inputs and any future external authority.

**Current implementation.** The file ingestor preserves file text.
ChatGPT and Claude export ingestors read local JSON and construct
normalised conversation text; they do not make network requests or hold
external credentials.

**Evidence.** `src/foundry/ingestors.py`,
`tests/test_foundry.py::test_ingest_file_preserves_verbatim`,
`tests/test_foundry.py::test_ingest_chatgpt_export`, and
`tests/test_foundry.py::test_ingest_claude_export`.

**Maturity.** Beta for the current local ingestors.

**Missing or future control.** No input-size policy, raw-export retention,
standard malformed-input result or standing connector permission model
exists.

## Maintenance rule

Update an entry in the same pull request that changes its implementation
or evidence. Update the threat model when a trust boundary or residual
risk changes. Maturity changes require concrete implementation and
validation evidence.
