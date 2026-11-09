# C-002 · Migrate canonical PostgreSQL storage

| Field | Value |
|---|---|
| Status | Awaiting G1 or prerequisite evidence |
| Milestone | P0-M0 |
| Baseline reference | g1-design-v2.0 (usable only once the approved annotated tag exists) |
| Requirement IDs | FR-007, NFR-002, NFR-009, NFR-012 |
| Responsible role | Implementer, separate reviewer, CI integrator |
| Dependencies | C-001 |
| Planned change surface | apps/api/migrations, storage adapters |
| Test matrix | P0-20 |

## Outcome and deliverables

Adopt prefreeze migrations through forward migration. Model cross-resource FKs, uniqueness, scoped reads, append-only evidence, UTC timestamps and auditable migration versions. Deliver the scoped implementation, regression fixtures, and a verification record in docs/test-reports/C-002.md. Treat the pre-G1 prototype as input requiring conformance review.

## Inputs and limits

Use the tagged traceability matrix, architecture, OpenAPI, test matrix and merged dependencies above. Excluded work includes vector retrieval, embedding jobs and destructive rollback.

## Acceptance and verification

Upgrade both an empty DB and a populated f3c0677 fixture twice. Observe stable UUIDs, unchanged source text and hashes, rejected orphan references and rejected evidence mutations. Run the named matrix cases, isolated unit and contract checks for modified ports, and real PostgreSQL integration for durable changes. Re-run the preceding milestone's vertical slice. Record command, revision, sanitized outputs and CI URL. Completion requires passing evidence and reviewer sign-off.

## Integration and recovery

Services depend on the repository contract. Restore a verified pre-upgrade archive into a fresh DB before switching the primary.

## Change control

A change to the tagged contract opens a CR describing affected IDs, migration/compatibility, risks and regression tests. Credentials stay outside logs, Git and exports. Store actual evidence and any exception in the task record before marking it complete.
