# Design baseline register

**G1 approved by the project owner on November 9, 2026.** Annotated tag `g1-design-v2.0` points to `9edbcd4b9a142d107df219bc64bd6730b39689cd`. P0 delivers the local Decision Hub, P1 rich continuity and P2 the multi-agent platform. Changes to frozen scope or contracts follow the CR process.

The owner requested a working Decision Hub first, with manual import and Gemini as the first API candidate. P0 covers independent originals, evidence-aware comparison, explicit owner choice, same-project history, privacy, spending controls and local recovery. Rich memory and decision supersession are P1. The multi-agent organization is the next platform direction at P2. Its staged ledger, research pilot, registry, factory and remote protocols are described in v1.4 §11. The P0 release does not depend on those platform milestones.

## Authorities and inputs

- [Proposed governance](docs/IMPLEMENTATION_GOVERNANCE_AND_DESIGN_BASELINE_v2.0.md), [review prompt](docs/CODEX_FINAL_DESIGN_REVIEW_PROMPT.md) and [candidate requirement matrix](docs/requirements/traceability.md).
- [v1.2 architecture](docs/architecture/baseline-v1.2.md), [v1.3 research](docs/handoff/v1.4/baseline/v1.3_Multi_Agent_Organization_Research_EN.md), [v1.4 roadmap](docs/handoff/v1.4/AI_Decision_Hub_Multi_Agent_Implementation_Roadmap_v1.4_EN.md). Keep historical versions intact.
- Draft decisions [scope](docs/adr/ADR-201-scope.md), [storage](docs/adr/ADR-202-durability.md), [identity](docs/adr/ADR-203-providers.md), [policy and budgets](docs/adr/ADR-204-policy-budget.md), [report and decision](docs/adr/ADR-205-comparison.md), [recovery](docs/adr/ADR-206-operations.md).

The [G0-01 conflict log](docs/requirements/conflict-log.md) records the proposed disposition and verification obligations for each row.

The independent reviewer verified closure of the design blockers in [the freeze review](docs/G1_FREEZE_REVIEW.md). Product acceptance cases below belong to subsequent implementation gates.

## Conflict and decision index

| ID | Evidence and candidate resolution | Outstanding check |
|---|---|---|
| DB-01 | v1.2 FR-008–013 prioritizes rich memory; v2.0 §3 splits basic history/decision/context from P1 retrieval/revisions. v1.3 §6 and v1.4 M4–M9 introduce agent capabilities. Their future requirements remain in the matrix. | Audit phase/acceptance links, including MA-FR-15 comparison continuity. Do not repeat the catalog. |
| DB-02 | Historical /api/v1 in v1.4 §7 and the prototype /v1 routes differ. Governance §4 uses /v1. Existing prototype run status, target minimum and response shape need a compatibility decision. | Specify affected routes, old-data migration and exact polling/response/error contract. |
| DB-03 | Prototype calculates manual completion from target presence. G1 needs durable queued/running/manual/synthesis/terminal states, atomic cancellation, late imports, failure and restart behavior. | Specify terminal immutability, successor-run semantics, race ordering and tests for every transition. |
| DB-04 | ADR-204 reserves cost/quota before dispatch; the packaged draft backlog orders budgeting after fanout. Revised cards make C-010 a dependency of C-007 and C-009. | Demonstrate recovery from unknown external outcome without double billing or releasing the hold prematurely. |
| DB-05 | ADR-205 proposes deterministic local synthesis, explicit abstention and evidence-linked owner choice. | Define examples and minimum comparison quality. Reconcile required versus optional rationale in ADR, task and API. |
| DB-06 | ADR-206 separates portable export/import from full encrypted recovery. Prototype storage predates G1. | Specify sensitive field exclusions, restore isolation, session invalidation, rollback, and measurable recovery gate. |
| DB-07 | Gemini is a candidate. Permitted account, capped price/quota and privacy conditions remain unverified. | Block live activation until verified. This does not block offline design or tests. |

New features enter the queue as a proposal with phase, affected FRs, alternatives, migration impact and tests. After freeze preserve the prior tag and record the approved CR and successor revision.

The [owner review packet](docs/OWNER_DESIGN_REVIEW.md) consolidates the candidate and dated research. C-007, C-010 and C-011 carry the resulting qualification cases.
