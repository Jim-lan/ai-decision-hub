# ADR-201 · The first release is a comparison workspace

**Status:** Approved under g1-design-v2.0. **Sources:** Governance §2–3, §7; v1.2 §3, §15; v1.3 §6; v1.4 §11–12.

**Decision.** Implement a single-owner, local, asynchronous question → independent originals → evidence-aware comparison → explicit owner decision flow. Manual import is a first-class route; reopening, basic search, explicitly selected same-project history, export and restore are in P0. Reserve MemoryPort, TaskPort, AgentRegistryPort and RemoteAgentPort at the domain boundary; there are no P0 implementations, schemas for speculative future records, or HTTP resources for these capabilities.

**Alternatives.** Delivering v1.2's entire memory sprint first adds extraction, classification, embeddings and correction workflows before the comparison works. Delivering the v1.4 chief/ledger pilot first incurs extra calls and a new authorization surface. Neither is required to preserve originals or reopen a project. An unscoped stateless comparison page cannot meet durability, provenance or owner control.

**Cost and trigger.** P0 does not automate rediscovery or establish truth. After usage evidence and a separate phase approval, P1 can project reviewed memory from versioned evidence; P2 can invoke the existing run use case by IDs. A change to resource ownership, release scope, or public contract requires a CR. See [conflicts](../requirements/conflict-log.md).
