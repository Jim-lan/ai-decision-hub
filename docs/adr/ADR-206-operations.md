# ADR-206 · Local release and recoverable data come before cloud rollout

**Status:** Proposed for G1; owner signature pending. **Sources:** Governance §3, §5–7; v1.2 FR-017, NFR-001–003, NFR-009, NFR-016, §11; v1.4 §10–11.

**Decision.** Compose binds the UI to loopback, not PostgreSQL or admin services. Ship both ARM64 and AMD64 builds. Single-owner authentication is required locally. Versioned export/import and independent encrypted backup/restore have separate acceptance gates. Restore to a fresh isolated database, block egress, validate identifiers, hashes, budgets, privacy removals and schema version before enabling writes. Maintain one writable primary. Require nightly backup (RPO ≤24 h) and measured restore (RTO ≤2 h); verify rollback to the previous compatible deployment. Keep sensitive content and secrets out of operational logs. Define expiration and deletion for backups in the operator runbook.

**Alternatives.** Cloud-first deployment ties recovery to an unverified account and increases exposure. A same-volume database dump does not survive host failure. Exporting credentials, raw checkpoints and active sessions along with content breaks portability and confidentiality.

**Cost and trigger.** Encrypted backup keys must be recoverable independently of the primary; check by drill. Failed integrity checks, unreconciled sends on restore, broken old-client compatibility, RPO/RTO misses or unintended public ingress block G4. P1 remote access needs separate owner security/region/cost approval and tested private ingress/HTTPS.
