# ADR-203 · Independent first-round inputs and honest identity

**Status:** Proposed for G1; owner signature pending. **Sources:** v1.2 §2.1–2.2, §8.2–8.3, §9; Governance §3, §4.2; historical local ADR 0001.

**Decision.** Manual import first, then one eligible official API adapter. Gemini is a candidate, not an entitlement. Use ProviderPort with a native documented transport or compatible SDK inside the adapter; an abstraction library is not an entitlement, price ceiling or mandatory new service. Resolve registry selections and persist per-attempt snapshots: application, gateway, requested and returned provider/model, family, routing, confidence, verification date and acquisition path. Never substitute an alias for missing returned identity. Keep declared manual labels distinct from API-attested identity. The app cannot attest to independent prompts used in an external consumer chat.

Freeze independent per-target inputs before collecting a first answer; use an immutable set of same-project source IDs/revisions for the round and a per-target permitted projection. Never copy sibling responses to first-round requests, even on recovery. Independent-family counts require verified, attributable distinct families with known resolution. Multiple targets can be valid comparison inputs without supplying multiple independent confirmations. Preserve sources with unknown identity and surface that limitation. No implicit provider fallback.

**Alternatives.** Consumer chat automation, counting product names as votes, and silent rerouting would confound identity and access; forcing verified identity on manual input would discard useful originals. A common transcript containing returned answers would invalidate first-round independence.

**Cost and trigger.** No live verification in this review. Require a dated, owner-specific eligibility and cost/privacy record plus bounded explicit opt-in before enabling external calls. If model resolution, terms, free-tier ceiling or retention changes, disable and reverify. A live smoke cannot be replaced by a fake for the hybrid release demonstration; a manual-only demonstration still works independently.
