# RFC-011 Phase 1 Reference Slice — Technical Debt

## Accepted debt

**TD1 — Vault encryption adapter.** Phase 1 uses permission-hardened local
storage and does not invent cryptography. The deployment contract requires
encrypted backing storage; a future reviewed key-management adapter may make
encryption explicit without changing the envelope/vault seam.

**TD2 — Governed correction workflow.** A wrong confirmed observation remains
corrected by the existing append-only event discipline. The confirmation
surface intentionally does not yet expose a separate correction review flow.

**TD3 — Single-writer log.** The existing JSONL substrate remains single
writer. Manual acquisition is low-volume; multi-channel concurrent capture
requires substrate-level serialization work, not a provider workaround.

**TD4 — Semantic reconciliation workflow.** A duplicate proposal is blocked
and visible, but an operator can currently reject it rather than choose a
dedicated reconcile action with an explanatory link.

**TD5 — Accessibility profile authoring.** Core reads the common lifecycle;
the bounded UI reviews proposals but does not provide a separate profile
editor. Domain events remain the sole lifecycle transition authority.

**TD6 — Instrument registry.** Exact typed aliases resolve tracker-fund
identities. Corporate actions, symbol changes, and broader instrument
reference data remain deliberately out of scope.

**TD7 — Private evidence operations.** Redaction is append-only and fail
closed, but Governor-per-artefact authorization is represented by the vault
authorizer integration point rather than a dedicated multi-party approval
workflow.

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

**Not actionable from supplied evidence: S1, S3, S4, S5, S6, S7.** No SAFE
finding text was published locally or on PR #27. They are not silently
accepted debt and no speculative change was made. A concrete finding can be
assessed against the frozen RFC in a later, bounded remediation burn.
