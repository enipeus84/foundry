# Foundry Documentation

A map of this directory. Each category below is a distinct kind of
document with its own lifecycle — this index links to the canonical
location for each rather than restating their content.

## Permanent architecture

- [`architecture.md`](architecture.md) — the thesis, the layers, and the
  **canonical statement of the constitutional invariants**. Any other
  document that mentions these invariants (`CONTRIBUTING.md`, historical
  reports) links here rather than restating them.
- [`design/design-constitution.md`](design/design-constitution.md) — the
  product/visual design constitution (Flight Deck language, visual
  identity, information-honesty rules). Governs *design* decisions, as
  distinct from the *engineering* invariants in `architecture.md`.
- [`specifications/`](specifications/) — adopted domain specifications
  (`000-core-domain-model.md`, `001-finance-domain-model.md`). These are
  the specs RFC-001 and RFC-002 implemented.
- [`roadmap.md`](roadmap.md) — living record of what's deliberately not
  built yet, and why.

## Security

- [`../SECURITY.md`](../SECURITY.md) — public reporting,
  supported-version and current-security-model document.
- [`security/`](security/) — canonical security documentation index.
- [`security/threat-model.md`](security/threat-model.md) — assets, trust
  boundaries, architectural threats and residual risks.
- [`security/security-assurance.md`](security/security-assurance.md) —
  evidence-backed register of current and missing controls.
- [`security/security-checklist.md`](security/security-checklist.md) —
  reusable review prompt for RFCs and non-trivial pull requests.

## Engineering process

- [`rfcs/RFC-100-flight-operations-manual.md`](rfcs/RFC-100-flight-operations-manual.md)
  — the Flight Operations Manual: Mission Control roles, burn
  classification, mission lifecycle, Flight Rules, pre-flight,
  checkpoints, SAFE, Governor authority, post-flight and standard
  reports. Governs the engineering governance of future product RFCs and
  *engineering process*, as distinct from the
  *engineering invariants* in `architecture.md`. Organised in three
  governance layers — Constitution, Operations Manual, Engineering Standards &
  Templates. **Revision 2; Governor-approved and frozen; documentation
  implementation in progress.**
- [`rfc-100-implementation-report.md`](rfc-100-implementation-report.md) —
  the bounded Documentation Implementation Burn record for the frozen manual.
- [`engineering/review-gates.md`](engineering/review-gates.md) — the
  current architecture/security review-gate process every change goes
  through before merge. Canonical for gate mechanics; RFC-100 cites it
  rather than restating it.
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — the practical contribution
  rules (stays at the repo root, per convention).

## RFCs

- [`rfcs/index.md`](rfcs/index.md) — every RFC, its status, and links to
  its spec, architecture doc, implementation report(s), technical-debt
  register, PR, and release tag, wherever each exists. Individual RFC
  documents remain at their existing paths under `docs/`; this index only
  points to them.

## Historical record

- [`history/`](history/) — point-in-time documents preceding the RFC
  process (Prototype Alpha assessment, the V1.0 validation runbook, the
  V1.0 final engineering review). Preserved verbatim; each carries a
  banner noting what, if anything, supersedes it.
- [`../CHANGELOG.md`](../CHANGELOG.md) — the version-by-version record of
  what shipped.

## Terminology note

RFC-004's reports refer informally to an "Engineering Constitution" —
that means `architecture.md` + `CONTRIBUTING.md` together; no separate
document by that name exists. The "Design Constitution" is the specific
document at `design/design-constitution.md`. The two are independent:
one governs substrate/domain engineering, the other governs product and
visual design.
