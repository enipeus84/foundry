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
