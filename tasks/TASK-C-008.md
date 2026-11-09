# C-008 · Import a manual original

| Field | Value |
|---|---|
| Status | Awaiting G1 or prerequisite evidence |
| Milestone | P0-M1 |
| Baseline reference | g1-design-v2.0 (usable only once the approved annotated tag exists) |
| Requirement IDs | FR-002, FR-004, FR-005, FR-007 |
| Responsible role | Implementer, separate reviewer, CI integrator |
| Dependencies | C-005, C-006 |
| Planned change surface | manual adapter, run target/response repository |
| Test matrix | P0-05, P0-11 |

## Outcome and deliverables

Bind pasted original and user-declared identity to one eligible target in a scoped run. Make replay safe and preserve whitespace/Unicode exactly. Deliver the scoped implementation, regression fixtures, and a verification record in docs/test-reports/C-008.md. Treat the pre-G1 prototype as input requiring conformance review.

## Inputs and limits

Use the tagged traceability matrix, architecture, OpenAPI, test matrix and merged dependencies above. Excluded work includes chat-login automation and asserting verified provenance for manual input.

## Acceptance and verification

Concurrent identical imports return a single stable response ID; changed payload conflicts. Wrong owner, target or elapsed deadline cannot amend a published original. Run the named matrix cases, isolated unit and contract checks for modified ports, and real PostgreSQL integration for durable changes. Re-run the preceding milestone's vertical slice. Record command, revision, sanitized outputs and CI URL. Completion requires passing evidence and reviewer sign-off.

## Integration and recovery

Use repository fixtures until C-009 wires the orchestration. Disable new imports on rollback and preserve existing evidence.

## Change control

A change to the tagged contract opens a CR describing affected IDs, migration/compatibility, risks and regression tests. Credentials stay outside logs, Git and exports. Store actual evidence and any exception in the task record before marking it complete.
