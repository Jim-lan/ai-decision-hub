# C-013 · Record the owner's decision and resume it

| Field | Value |
|---|---|
| Status | Awaiting G1 or prerequisite evidence |
| Milestone | P0-M3 |
| Baseline reference | g1-design-v2.0 (usable only once the approved annotated tag exists) |
| Requirement IDs | FR-008, FR-012, NFR-002, NFR-012 |
| Responsible role | Implementer, separate reviewer, CI integrator |
| Dependencies | C-005, C-011, C-012 |
| Planned change surface | decision service, persistence, /v1 decisions and UI |
| Test matrix | P0-13, P0-14 |

## Outcome and deliverables

Save the explicit choice and any owner-supplied rationale linked to a run and its scoped source/report. Reopen from a new session and show the exact supporting evidence. Deliver the scoped implementation, regression fixtures, and a verification record in docs/test-reports/C-013.md. Treat the pre-G1 prototype as input requiring conformance review.

## Inputs and limits

Use the tagged traceability matrix, architecture, OpenAPI, test matrix and merged dependencies above. Excluded work includes supersession graph, automatic revalidation and memory consolidation.

## Acceptance and verification

Recording a decision twice with the same key creates one record. A changed body or foreign source fails. Reading a recommendation alone never creates a decision. Run the named matrix cases, isolated unit and contract checks for modified ports, and real PostgreSQL integration for durable changes. Re-run the preceding milestone's vertical slice. Record command, revision, sanitized outputs and CI URL. Completion requires passing evidence and reviewer sign-off.

## Integration and recovery

Reopen decision in the UI and backup fixture. Roll back the writer and preserve readable records.

## Change control

A change to the tagged contract opens a CR describing affected IDs, migration/compatibility, risks and regression tests. Credentials stay outside logs, Git and exports. Store actual evidence and any exception in the task record before marking it complete.
