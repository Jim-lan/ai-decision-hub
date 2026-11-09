# C-015 · Export, restore and rehearse a local release

| Field | Value |
|---|---|
| Status | Awaiting G1 or prerequisite evidence |
| Milestone | P0-M4 |
| Baseline reference | g1-design-v2.0 (usable only once the approved annotated tag exists) |
| Requirement IDs | FR-017, NFR-001, NFR-002, NFR-003, NFR-009, NFR-016 |
| Responsible role | Implementer, separate reviewer, CI integrator |
| Dependencies | C-013, C-014 |
| Planned change surface | portable export/import, encrypted recovery scripts, operations guide |
| Test matrix | P0-17, P0-18, P0-20, P0-21 |

## Outcome and deliverables

Export a project as versioned portable records; validate integrity and import into a fresh instance. Back up encrypted data, restore, restart and rehearse rollback. Record RPO/RTO evidence. Deliver the scoped implementation, regression fixtures, and a verification record in docs/test-reports/C-015.md. Treat the pre-G1 prototype as input requiring conformance review.

## Inputs and limits

Use the tagged traceability matrix, architecture, OpenAPI, test matrix and merged dependencies above. Excluded work includes cloud VM provisioning or unapproved recurring spend.

## Acceptance and verification

Corrupt export, foreign reference, missing recovery key and an existing restore destination fail safely. Restored instance reproduces UUIDs, originals, report and decision through the browser. Run the named matrix cases, isolated unit and contract checks for modified ports, and real PostgreSQL integration for durable changes. Re-run the preceding milestone's vertical slice. Record command, revision, sanitized outputs and CI URL. Completion requires passing evidence and reviewer sign-off.

## Integration and recovery

G4 requires owner acceptance plus the release evidence. Use verified backups and a single writable primary during switchover.

## Change control

A change to the tagged contract opens a CR describing affected IDs, migration/compatibility, risks and regression tests. Credentials stay outside logs, Git and exports. Store actual evidence and any exception in the task record before marking it complete.
