# C-001 · Reproduce the local workspace

| Field | Value |
|---|---|
| Status | Done |
| Milestone | P0-M0 |
| Baseline reference | g1-design-v2.0 @ 9edbcd4b9a142d107df219bc64bd6730b39689cd |
| Requirement IDs | FR-001, NFR-001, NFR-008 |
| Responsible role | Implementer, separate reviewer, CI integrator |
| Dependencies | — |
| Planned change surface | apps/web, apps/api, compose.yaml, README.md |
| Test matrix | P0-21 |

## Outcome and deliverables

Adopt and verify only the local React/FastAPI entry points. Show the local operator how to initialize secrets and start and stop the stack. Deliver the scoped implementation, regression fixtures, and a verification record in docs/test-reports/C-001.md. Treat the pre-G1 prototype as input requiring conformance review.

## Inputs and limits

Use the tagged traceability matrix, architecture, OpenAPI, test matrix and merged dependencies above. Excluded work includes feature routes, remote hosting and provider calls.

## Acceptance and verification

New checkout plus synthetic credentials serves the web shell and readiness endpoint through loopback. Missing bootstrap configuration fails with a redacted actionable error. Run the assertions in the named matrix cases that exercise this card’s deliverables, using fixtures for later dependencies. Run isolated unit and contract checks for modified ports and PostgreSQL integration for durable changes. At each milestone rerun the preceding completed slice. The full cross-feature cases remain open until their integration checkpoint. Record command, revision, sanitized outputs and CI URL. Completion requires passing evidence and reviewer sign-off.

## Integration and recovery

Compose and README are inputs to all subsequent tasks. Revert container/config changes and retain the named data volume.

## Change control

A change to the tagged contract opens a CR describing affected IDs, migration/compatibility, risks and regression tests. Credentials stay outside logs, Git and exports. Store actual evidence and any exception in the task record before marking it complete.

## Evidence of completion

Verified in [C-001 verification record](../docs/test-reports/C-001.md). No change request was required. C-002 and C-004 are eligible.
