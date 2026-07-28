# Engineering Security Checklist

Every RFC and every non-trivial pull request answers this checklist
before the Security Gate. Copy the block below into the RFC or pull
request description. `N/A` is a valid answer; an omitted question is
not.

If a change modifies a documented control, update
[`security-assurance.md`](security-assurance.md) in the same change. If
it moves a trust boundary or changes a residual risk, also update
[`threat-model.md`](threat-model.md).

## Reusable change template

```markdown
## Security Considerations

- **Authentication:** Does this change who can reach the application or
  how identity is established? Which routes remain public?
- **Authorisation:** Does this change what an authenticated identity can
  see or do? How is the intended scope enforced and evidenced?
- **Sensitive data and secrets:** What data enters, leaves or persists?
  Could credentials or private data enter the event log, output or logs?
- **Auditability:** Are state changes represented by events? Which actor,
  source and evidence fields can be trusted, and which are assertions?

## Threat Assessment

- **Trust boundaries:** Does this add untrusted input, an outbound
  destination, a dependency, a connector or external credentials?
- **Threat model:** Which entries in `docs/security/threat-model.md` does
  this affect? Does it introduce or alter a residual risk?
- **Failure and abuse:** What happens on malformed, hostile, repeated,
  concurrent or partial input? Does failure preserve existing evidence?

## Validation

- **Evidence:** Which automated tests or review evidence defend each
  security-relevant claim?
- **Deferred work:** Which missing controls or improvements remain, and
  where are they recorded without being described as implemented?
```

## Expected depth

Short, factual answers are preferred. A documentation-only process change
will usually have several `N/A` answers. A new connector, public route,
credential, persistence mechanism or authorisation scope requires a
deeper threat assessment.

## Example

For a hypothetical local CSV ingestor:

- **Authentication:** N/A; no route or identity change.
- **Authorisation:** N/A; local CLI input under the existing user.
- **Sensitive data and secrets:** Financial rows become permanent event
  payloads; operators must review the file before ingestion.
- **Auditability:** Each accepted row records its source; rejected input
  must leave the log unchanged.
- **Trust boundaries:** Adds a new untrusted local input format with no
  network or credentials.
- **Threat model:** T1, T8 and T10; no residual risk is accepted silently.
- **Failure and abuse:** Size limits and malformed-row behaviour must be
  specified before implementation.
- **Evidence:** Parser, provenance and no-partial-append tests.
- **Deferred work:** Any unsupported format is recorded explicitly.
