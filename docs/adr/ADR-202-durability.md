# ADR-202 · Domain transactions own truth; workflow checkpoints hold references

**Status:** Approved under g1-design-v2.0. **Sources:** Governance §4.1–4.4; v1.2 §4, §6, §8.1; v1.4 §8.

**Decision.** Use React and FastAPI over one modular monolith with a separate worker process. PostgreSQL owns canonical data and versioned progress events. The API transaction commits the question, run, targets and initial work/event together. The worker leases work and invokes LangGraph using ID-only checkpoint state, fenced attempts and compare-and-set writes. Recovery reads the domain tables before resuming. Raw content remains readable without the graph; progress is a projection of durable events. Use scoped composite foreign keys and resource joins. Apply Alembic expansions after backup, backfill/verify, switch readers, then retire obsolete fields only after the compatibility window.

**Alternatives.** Using framework checkpoints as the database obscures ownership, erasure and migration. In-memory tasks lose accepted work after restart. Separate services or queue infrastructure introduce distributed coordination without an observed throughput problem.

**Cost and trigger.** There is no atomic transaction across PostgreSQL and a provider. An ambiguous attempted send consumes its reservation and must not replay blindly. Stop the adapter if recovery produces duplicate dispatch, lost originals or leaked checkpoint content. Only measured contention justifies replacing the work queue. No pgvector requirement for a fresh P0 installation; retain existing extensions where present rather than dropping prototype data.
