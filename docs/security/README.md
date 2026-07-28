# Security documentation

This directory is the canonical home for Foundry's security governance
artefacts. It separates the public reporting policy from the architectural
analysis, current control evidence and engineering review prompt.

- [`../../SECURITY.md`](../../SECURITY.md) — public reporting,
  supported-version and security-overview document.
- [`threat-model.md`](threat-model.md) — assets, trust boundaries,
  architectural threats and residual risks.
- [`security-assurance.md`](security-assurance.md) — evidence-backed
  register of current controls, maturity and missing controls.
- [`security-checklist.md`](security-checklist.md) — reusable
  Security by Design prompt for RFCs and non-trivial pull requests.

## Maintenance

- Update the assurance register in the same change that modifies a
  documented control.
- Review the threat model when a trust boundary changes and at least
  annually.
- Keep current implementation separate from proposed improvements.
- Keep operational deployment details out of this public documentation.
