# C-006 · Register targets and snapshot identity

| Field | Value |
|---|---|
| Status | Awaiting G1 or prerequisite evidence |
| Milestone | P0-M1 |
| Baseline reference | g1-design-v2.0 (usable only once the approved annotated tag exists) |
| Requirement IDs | FR-002, FR-016, NFR-010, NFR-012 |
| Responsible role | Implementer, separate reviewer, CI integrator |
| Dependencies | C-002, C-004 |
| Planned change surface | registry, model identity types, provider catalog |
| Test matrix | P0-03 |

## Outcome and deliverables

Record alias, provider, gateway, requested/resolved ID, family, routing, confidence, verification time and enabled state. Keep identity immutable per attempt. Deliver the scoped implementation, regression fixtures, and a verification record in docs/test-reports/C-006.md. Treat the pre-G1 prototype as input requiring conformance review.

## Inputs and limits

Use the tagged traceability matrix, architecture, OpenAPI, test matrix and merged dependencies above. Excluded work includes subscription inference, silent fallback, agent registry.

## Acceptance and verification

Two aliases resolving to the same family count once. Unknown dynamic identities are visibly unknown. Editing the catalog does not relabel a prior result. Run the assertions in the named matrix cases that exercise this card’s deliverables, using fixtures for later dependencies. Run isolated unit and contract checks for modified ports and PostgreSQL integration for durable changes. At each milestone rerun the preceding completed slice. The full cross-feature cases remain open until their integration checkpoint. Record command, revision, sanitized outputs and CI URL. Completion requires passing evidence and reviewer sign-off.

## Integration and recovery

Context, UI and comparison consume snapshots. Disable a bad registry entry and preserve historical snapshots.

## Change control

A change to the tagged contract opens a CR describing affected IDs, migration/compatibility, risks and regression tests. Credentials stay outside logs, Git and exports. Store actual evidence and any exception in the task record before marking it complete.
