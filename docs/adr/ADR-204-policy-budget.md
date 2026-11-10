# ADR-204 · Deterministic authorization and reservations precede every network call

**Status:** Approved under g1-design-v2.0. **Sources:** Governance §3–4, §7; v1.2 FR-013, FR-015, FR-018, NFR-004–006, NFR-013, §9.3, §10.

**Decision.** Login and project ownership precede resource access. Check sensitivity, approved recipient, current registry entitlement, price/quota freshness and a bounded request before calling. Project history is opt-in per source; redact per destination, deny if the core question cannot be sent safely. Revalidate on dispatch after queueing. Restrict outbound destinations to configured official HTTPS endpoints; never follow model-provided URLs or silently enable an adapter.

Reserve worst-case cost and independent call/token quotas atomically against run and owner UTC day/month limits before a first byte can leave. Default paid cap is zero. Unknown price, unbounded tokens, fallback billing, missing policy or quota are grounds to block. A checkbox does not make an unknown upper bound safe. Record actual or unknown usage separately from the held upper bound. Do not retry an ambiguous send, including after a crash. Keep its hold until trusted final accounting. Reuse this gate for **any** future paid synthesis or embedding, which are absent in P0.

**Alternatives.** A usage dashboard after dispatch cannot prevent spend. Checking each worker's current total without locking oversubscribes the budget. A consumer subscription or ambiguous free tier gives no enforceable hard ceiling. Giving an LLM a policy prompt does not enforce authorization.

**Cost and trigger.** Conservative holds can block legitimate calls; manual remains available. If billed usage exceeds a reservation or the provider cannot cap a request, quarantine it, record the discrepancy, escalate to the owner and do not start further sends. A nonzero ceiling requires a separate owner spend decision; approving G1 alone sets none.
