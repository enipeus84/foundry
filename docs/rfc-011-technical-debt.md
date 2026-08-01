# RFC-011 Phase 1 Reference Slice — Technical Debt

## Accepted debt

**TD1 — Governed correction workflow.** A wrong confirmed observation remains
corrected by the existing append-only event discipline. The confirmation
surface intentionally does not yet expose a separate correction review flow.

**TD2 — Single-writer log.** The existing JSONL substrate remains single
writer. Manual acquisition is low-volume; multi-channel concurrent capture
requires substrate-level serialization work, not a provider workaround.

**TD3 — Semantic reconciliation workflow.** A duplicate proposal is blocked
and visible, but an operator can currently reject it rather than choose a
dedicated reconcile action with an explanatory link.

**TD4 — Accessibility profile authoring.** Core reads the common lifecycle;
the bounded UI reviews proposals but does not provide a separate profile
editor. Domain events remain the sole lifecycle transition authority.

**TD5 — Instrument registry.** Exact typed aliases resolve tracker-fund
identities. Corporate actions, symbol changes, and broader instrument
reference data remain deliberately out of scope.

**TD6 — Private evidence operations.** Redaction is append-only and fail
closed, but Governor-per-artefact authorization is represented by the vault
authorizer integration point rather than a dedicated multi-party approval
workflow.

## Governor ruling — S6, not technical debt

Evidence Vault encryption at rest is deferred to RFC-011 Phase 2 by Governor
ruling. Phase 1 retains permission-hardened `0700` storage and `0600` blobs,
does not claim encryption, and carries no implementer-owned encryption debt.

## Non-debt boundaries

The absence of PayPal RSUs, model interpreters, email/PDF, APIs, CSV, OCR,
Open Banking, cash/bank accounts, bills, precious metals and private/director
equity is scope discipline, not deferred implementation hidden in this burn.

## SAFE remediation disposition — 2026-08-01

**Closed: B3 — Information Honesty.** Missing material market inputs now
remain unknown through every derived lens and reconciliation; they do not
become a monetary zero. The confidence cap is `Insufficient` until the input
exists.

**Closed: B4 — Identity Resolution availability.** Duplicate detection is a
required dependency of interpretation. Missing inbox state now refuses the
operation rather than disabling the guard.

**Closed: S2 — URL CSRF transport.** The signed form credential is submitted
in the POST body only. URL parsing cannot satisfy the check.

**Closed: B1 — Core neutrality.** Finance canonical event validation moved
to the Finance adapter. Core retains only the generic domain-contract seam.

**Governor decision required, not technical debt: B2 — phase sequencing.**
The implementation combined frozen RFC phases 1–4 in one branch. This cannot
be repaired by a code change or honestly called a Phase 1-only burn. The
Governor must decide whether to reclassify and review the combined burn; no
Phase 5 work is authorized meanwhile.

**Not actionable from supplied evidence: S7 only.** No SAFE finding text was
published locally or on PR #27. It is not silently accepted debt and no
speculative change was made. A concrete finding can be assessed against the
frozen RFC in a later, bounded remediation burn.

## SAFE remediation burn 2 disposition — 2026-08-01

**Closed: S1 — Secret detection.** Credential names and obvious credential
values are rejected before vault persistence, deterministically and without
model detection.

**Closed: S3 — Confirmation evidence.** The authenticated review surface
reads the referenced artefact through the Vault, fails closed, escapes output
and redacts credential-shaped legacy content.

**Closed: S4 — Confirmation policy.** The three frozen policy modes are now
enforced by the Confirmation Gate.

**Closed: S5 — Provenance chain.** Evidence, proposal, interpreter,
confirmation and canonical event are reconstructable and rendered for an
authorized reviewer.

**Applied: S6 — Governor ruling.** Encryption is Phase 2 work by explicit
Governor decision, not outstanding Phase 1 technical debt.
