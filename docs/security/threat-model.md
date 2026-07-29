# Foundry Threat Model

**Scope:** the current single-user Foundry application, its append-only
event log, derived projections, optional model adapters and web surface.

**Last reviewed:** 2026-07-29.

This model describes the implementation that exists today. Proposed
controls are kept separate from current mitigations, and residual risk is
retained explicitly.

## Assets

1. **Event log.** The only source of truth and the largest
   confidentiality, integrity and availability concern. It may contain
   source documents, conversations, financial data, decisions and
   derived claims.
2. **Signing and provider credentials.** The session-signing secret can
   mint sessions. Model-provider credentials can incur cost and may grant
   access to provider-side resources.
3. **Provenance.** Source-event references, evidence text and actor
   strings support explanation and audit, even though not every field is
   independently authenticated.
4. **Backups and copies.** Any copy of the event log has the same
   sensitivity as the original.
5. **Canon and domain projections.** Lower-value at rest because they are
   rebuildable from the log, but corrupted projections can still mislead
   a running process until rebuilt.

## Trust boundaries

```text
untrusted files and exports       identity provider       model providers
             |                          |                       |
             v                          v                       v
        ingestors                  web/auth layer           adapters
             |                          |                       |
             +--------------------------+-----------------------+
                                        |
                                        v
                         event log and derived projections
                                        |
                                        v
                       host filesystem and process environment
```

- **Ingestion boundary.** Input is untrusted and becomes permanent when
  appended. The file ingestor preserves file text; conversation-export
  ingestors normalise selected messages rather than retaining the source
  export byte-for-byte.
- **Model boundary.** Selected source text leaves the local process.
  Returned claim fields are untrusted model output. Parsing validates
  shape and bounds confidence, but does not verify statements or evidence
  against the source text.
- **Web boundary.** Application data routes check a signed session
  against one configured email address. Authentication and health routes
  remain public.
- **Host boundary.** The process environment and filesystem hold the log
  and credentials. Compromise of the host is outside the protection
  offered by the application-level hash chain.
- **Supply-chain boundary.** Optional packages and GitHub Actions are
  trusted code. The core's empty mandatory dependency set narrows, but
  does not remove, this boundary.
- **Manual mortgage evidence.** Governed values supplied by the operator
  become permanent Finance events. Shape, finiteness, scope and effective
  date are validated, but source, lineage, actor and confidence remain
  assertions. This is an in-process input boundary, not an external
  connector or authenticated lender feed.

## Threat actors

- Opportunistic scanners probing an internet-accessible web surface.
- A targeted attacker seeking the user's knowledge or financial data.
- An author of content that will be ingested.
- A compromised or unreliable model provider.
- A compromised dependency, build input or contributor account.
- The operator making a permanent ingestion, configuration or backup
  mistake.

## Threat catalogue

### T1 — Prompt injection and poisoned content

An ingested document or conversation can contain instructions intended
to steer claim extraction or later answers.

**Current mitigations.** Ingested text is not executed as code.
Unparseable model output produces no claims. Derived claims retain
source-event references, evidence text and model identity strings so a
reviewer can inspect the asserted basis and supersede a bad claim through
another event.

**Residual risk.** A plausible false claim can persist and influence
answers. Evidence text is supplied by the model and is not checked for
verbatim inclusion in the source. The poisoned source event cannot be
deleted through the supported API.

**Future improvement.** Validate evidence spans against source events and
design explicit review status for untrusted or disputed claims.

### T2 — Session theft or forgery

An attacker steals a valid session cookie or obtains the signing secret.

**Current mitigations.** Session cookies are HMAC-SHA256 signed,
HttpOnly, SameSite=Lax, time-bounded and marked Secure when the configured
base URL uses HTTPS. Protected routes also re-check that the session email
matches the configured email.

**Residual risk.** Sessions are stateless and cannot be revoked
individually before expiry. Rotating the signing secret invalidates all
sessions. The implementation accepts any non-empty signing secret and
does not enforce minimum entropy.

**Future improvement.** Define revocation and secret-strength requirements
if the authentication scope expands.

### T3 — Credential exposure

Credentials can leak through source, logs, environment access, backups or
accidental ingestion.

**Current mitigations.** Application configuration reads secrets from the
process environment. Repository documentation tells contributors not to
store or ingest them.

**Residual risk.** There is no automated secret scanning, ingestion
redaction or repository-enforced credential policy. A credential appended
to the log remains in all subsequent copies even after rotation.

**Future improvement.** Evaluate repository-native scanning and a
non-destructive pre-ingestion warning separately from this governance
change.

### T4 — Event-log modification or loss

An attacker or fault edits, inserts, reorders, truncates, replaces or
destroys event-log data.

**Current mitigations.** Each event hashes its own canonical content and
the previous event hash. `EventLog.verify()` detects edits, insertions and
reordering when the attacker does not recompute all affected hashes.
Deterministic replay makes projections reproducible from an intact log.

**Residual risk.** The chain is unkeyed, so a writer who can replace the
file can recompute it. A valid tail can be removed without detection.
There is no external head anchor, application-managed immutable storage,
automated backup or restore drill. The log assumes a single writer and
does not fsync or provide transaction-level crash guarantees.

**Future improvement.** External head anchoring and verified,
independently protected backups are already identified architectural
work; their design is deferred.

### T5 — Data exfiltration

An attacker reads the event log through the host, a valid session, an
unprotected copy, or content sent to a model provider.

**Current mitigations.** The substrate itself has no network listener.
Application data routes require the configured account. Model providers
are optional and selected at derivation time.

**Residual risk.** One readable log can disclose everything retained in
it. Foundry does not implement application-level encryption at rest.
External model derivation necessarily discloses selected content to that
provider. Backups and copied transcripts can duplicate the exposure.

**Future improvement.** Decide encryption, retention and provider-use
requirements in the Security Governance review rather than in this
preparation change.

### T6 — Authorisation failure

An authenticated identity accesses data or actions outside its intended
scope.

**Current mitigations.** The current model is intentionally narrow: one
configured email receives access and every other email is rejected.
There are no roles or partial permissions.

**Residual risk.** This is not household-scoped authorisation. It provides
no member separation, object-level permissions or sharing model. Route
protection is implemented by checks in the current route handlers rather
than one central policy layer.

**Future improvement.** Multi-member and household authorisation require
an explicit design and threat-model update before implementation.

### T7 — Supply-chain compromise

A malicious optional dependency, GitHub Action, package source or build
input executes with project privileges.

**Current mitigations.** The mandatory core dependency list is empty.
Web and model packages are optional extras, and the repository's CI
workflow is short and reviewable.

**Residual risk.** Optional dependencies run in the same process as the
substrate. Versions are ranges rather than a locked deployment set.
Actions use version tags rather than immutable commit SHAs. No automated
dependency update or supply-chain scanning is configured.

**Future improvement.** Dependency locking, update automation and
immutable Action references remain separate engineering decisions.

### T8 — Ingestor or future connector abuse

Malformed, excessive or hostile input can consume resources, create
misleading permanent events or abuse future standing credentials.

**Current mitigations.** Current ingestors read local files, parse known
export shapes and append through the Kernel. They do not hold service
credentials or make outbound requests. The manual Mortgage Freedom adapter
accepts only governed fields and validated finite envelopes; hostile direct
log events make that mission not evaluable without replacing existing
evidence or exposing payload details.

**Residual risk.** Inputs have no explicit size limit. ChatGPT exports
omit system messages and both export ingestors normalise messages into a
new text representation, so the source export is not preserved
byte-for-byte. Malformed structures can raise rather than produce a
standard rejection result.

**Future improvement.** Any credentialed or unattended connector needs a
separate threat assessment covering scopes, provenance, failure and
revocation before it ships.

### T9 — AI-assisted engineering attacks

AI-generated changes can introduce subtle vulnerabilities or misleading
documentation, while hostile content can be generated at scale.

**Current mitigations.** Significant changes pass automated tests,
architecture review, security review and human approval under the
[engineering review gates](../engineering/review-gates.md). Implementation
and review roles are separated.

**Residual risk.** Review is judgement, not proof. Tests cover stated
properties and can miss unstated assumptions. AI-generated claims retain
the same T1 limitations regardless of volume.

**Future improvement.** Keep review evidence tied to concrete code and
tests; do not treat model agreement as independent assurance.

### T10 — Operator error and unsafe concurrency

The operator can ingest a credential, expose a backup, select the wrong
data file or run unsupported concurrent writers.

**Current mitigations.** The append-only API makes destructive application
operations uncommon. Demo-data creation uses strict opt-in, preserves
non-empty files and publishes a prepared log atomically.

**Residual risk.** Those demo safeguards do not make general event
appends transactional or multi-writer safe. No application control can
remove an accidentally ingested secret. Backup handling is entirely
external to Foundry.

**Future improvement.** Operational recovery, backup and concurrency
requirements remain explicit deferred decisions.

## Residual risks requiring continued visibility

1. No individual session revocation and no enforced signing-secret
   strength.
2. Unkeyed hash chaining, tail-truncation blindness and no external
   anchor.
3. No automated backup or tested restore procedure.
4. Single-file confidentiality blast radius and no application-level
   encryption at rest.
5. Model-provider disclosure during derivation.
6. Model-supplied evidence is not verified against source text.
7. Single-email access control is not household-scoped authorisation.
8. Optional dependencies share the substrate process and are not locked.
9. Conversation exports are normalised rather than preserved verbatim.
10. General event appends assume a single writer and lack crash-durability
    guarantees.

These are current-state findings, not policy acceptances. Ownership,
acceptance and remediation priority are decisions for the Security
Governance review.

## Review triggers

Review this model when any of the following changes:

- authentication or authorisation scope;
- a route becomes public or gains write behaviour;
- a new model provider, ingestor or connector is added;
- log storage, backup, encryption or concurrency changes;
- a dependency or deployment trust boundary changes;
- at least one year has passed since the previous review.
