# Security

Foundry stores knowledge in an append-only event log and derives
rebuildable projections from it. Security work therefore starts with
protecting the confidentiality, integrity and availability of the log,
without overstating what the current implementation provides.

## Reporting a vulnerability

Use GitHub Private Vulnerability Reporting as the preferred reporting
channel: open the repository's **Security** tab, select
**Advisories**, then **Report a vulnerability**. This creates a private
discussion with the maintainer.

Do not include vulnerability details in a public issue.

## Supported versions

Foundry currently develops and ships from `main`. There are no maintained
security-support branches and no separate security maintenance policy for
older tags.

| Version | Supported |
|---|---|
| `main` | Yes |
| Older tags | No |

## Current security model

- The event log is the only source of truth. Application-owned state
  changes are appended as events; projections are disposable and
  rebuildable.
- Each event includes a SHA-256 link to the previous event. Verification
  detects accidental changes and edits that do not recompute the chain.
  It is not a signature, does not authenticate the writer and does not
  detect removal of a valid tail.
- Model-derived claims record source-event identifiers, an actor string
  and model-supplied evidence text. The implementation does not currently
  verify that evidence text is a verbatim excerpt or authenticate the
  actor string.
- Application data routes require a signed session for the single
  configured email address. Authentication routes and the health route
  are public by design.
- The core package has no mandatory third-party runtime dependencies.
  Web and model integrations are optional dependencies and execute in the
  same process when installed.

The detailed analysis is maintained in the
[threat model](docs/security/threat-model.md). Current controls and gaps
are recorded in the
[security assurance register](docs/security/security-assurance.md).

## Sensitive data and secrets

- Keep credentials and signing secrets out of source, tests, logs and
  ingested content.
- Treat ingestion as irreversible. Foundry has no supported operation for
  deleting an event from the log.
- If a credential enters the log, rotate or revoke it first. The original
  bytes remain in every copy and backup of that log.
- Model derivation sends selected source content to the configured model
  provider. Provider selection is therefore a data-disclosure decision.
- Protect backups to the same standard as the live log. Foundry does not
  currently provide an automated backup or restore mechanism.

## Dependency handling

The substrate's mandatory dependency set is empty by design. Optional
web, model and development dependencies are declared in
`pyproject.toml`. The repository does not currently automate dependency
updates, secret scanning or supply-chain analysis; those are recorded as
future improvements rather than claimed as existing controls.

## Engineering changes

Every RFC and non-trivial pull request should complete the
[Security by Design checklist](docs/security/security-checklist.md).
Changes that move a trust boundary should update the threat model, and
changes to a control should update the assurance register in the same
pull request.
