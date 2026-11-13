# C-010 · Guard outbound context, replay and spend

| Field | Value |
|---|---|
| Status | Done · independently reviewed November 13, 2026 |
| Milestone | P0-M1 |
| Baseline reference | g1-design-v2.0 @ 9edbcd4b9a142d107df219bc64bd6730b39689cd |
| Requirement IDs | FR-013, FR-014, FR-015, FR-018, NFR-004, NFR-005, NFR-013 |
| Responsible role | Implementer, separate reviewer, CI integrator |
| Dependencies | C-003, C-004, C-005, C-006 |
| Planned change surface | ContextPort, BudgetPort, policy repository, run idempotency |
| Test matrix | P0-08, P0-09, P0-10 |

## Outcome and deliverables

Reserve worst-case spend across run/day/month; freeze scoped/redacted outbound snapshots. Persist idempotency and audit with the business write. Zero spend is the initial cap. Deliver the scoped implementation, regression fixtures, and a verification record in docs/test-reports/C-010.md. Treat the pre-G1 prototype as input requiring conformance review.

## Inputs and limits

Use the tagged traceability matrix, architecture, OpenAPI, test matrix and merged dependencies above. Excluded work includes agent tool permissions, learned routing, semantic retrieval.

## Acceptance and verification

Race requests at the last budget unit and observe at most one eligible dispatch. Unknown maximum price, absent consent or denied source prevents network I/O. Same key plus changed payload conflicts. Run the assertions in the named matrix cases that exercise this card’s deliverables, using fixtures for later dependencies. Run isolated unit and contract checks for modified ports and PostgreSQL integration for durable changes. At each milestone rerun the preceding completed slice. The full cross-feature cases remain open until their integration checkpoint. Record command, revision, sanitized outputs and CI URL. Completion requires passing evidence and reviewer sign-off.

Exercise shared Gemini project limits across two keys, including the interval between the owner UTC reset and the provider Pacific daily reset.

## Integration and recovery

C-007 and C-009 depend on preflight before dispatch. Switch outbound off and reconcile outstanding reservations during rollback.

## Change control

A change to the tagged contract opens a CR describing affected IDs, migration/compatibility, risks and regression tests. Credentials stay outside logs, Git and exports. Store actual evidence and any exception in the task record before marking it complete.

## Completion record

Revision `0007_context_budget` and the PostgreSQL policy adapters implement the approved context, budget, dispatch-authorization, replay, and usage boundaries without enabling an official provider or network fan-out. The final suite passed 40 PostgreSQL tests, the fresh vanilla migration ran twice, all pinned quality/contract gates passed, and a separate reviewer reported no remaining blocking or major issue. Detailed evidence and integration constraints are in `docs/test-reports/C-010.md`. No Change Request was required.
