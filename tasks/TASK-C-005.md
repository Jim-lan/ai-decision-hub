# C-005 · Persist projects, conversations and bounded history

| Field | Value |
|---|---|
| Status | Awaiting G1 or prerequisite evidence |
| Milestone | P0-M1 |
| Baseline reference | g1-design-v2.0 (usable only once the approved annotated tag exists) |
| Requirement IDs | FR-001, FR-007, FR-008, NFR-002, NFR-013 |
| Responsible role | Implementer, separate reviewer, CI integrator |
| Dependencies | C-002, C-003, C-004 |
| Planned change surface | conversation repository, application use cases, /v1 history |
| Test matrix | P0-01, P0-14 |

## Outcome and deliverables

Provide create/list/select, stable ordered message history and bounded same-project history lookup. Keep exact content and source links across restarts. Deliver the scoped implementation, regression fixtures, and a verification record in docs/test-reports/C-005.md. Treat the pre-G1 prototype as input requiring conformance review.

## Inputs and limits

Use the tagged traceability matrix, architecture, OpenAPI, test matrix and merged dependencies above. Excluded work includes automatic extraction, embeddings and cross-project memory.

## Acceptance and verification

Two concurrent messages get distinct ordered IDs. Reopening a session returns original text. Foreign project, malformed cursor and stale references are rejected. Run the named matrix cases, isolated unit and contract checks for modified ports, and real PostgreSQL integration for durable changes. Re-run the preceding milestone's vertical slice. Record command, revision, sanitized outputs and CI URL. Completion requires passing evidence and reviewer sign-off.

## Integration and recovery

Run requests and context selection depend on these IDs. Preserve rows on application rollback.

## Change control

A change to the tagged contract opens a CR describing affected IDs, migration/compatibility, risks and regression tests. Credentials stay outside logs, Git and exports. Store actual evidence and any exception in the task record before marking it complete.
