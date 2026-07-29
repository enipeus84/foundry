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
