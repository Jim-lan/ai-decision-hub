# C-004 · Install reproducible verification gates

| Field | Value |
|---|---|
| Status | Awaiting prerequisite evidence |
| Milestone | P0-M0 |
| Baseline reference | g1-design-v2.0 @ 9edbcd4b9a142d107df219bc64bd6730b39689cd |
| Requirement IDs | FR-005, NFR-007, NFR-008, NFR-010 |
| Responsible role | Implementer, separate reviewer, CI integrator |
| Dependencies | C-001 |
| Planned change surface | CI, contract tests, deterministic provider fixtures |
| Test matrix | P0-19, P0-22, P0-24 |

## Outcome and deliverables

Build checks for typed boundaries, lint, OpenAPI/schema validation, migrations, mock provider and browser smoke. Split opt-in live checks from offline CI. Deliver the scoped implementation, regression fixtures, and a verification record in docs/test-reports/C-004.md. Treat the pre-G1 prototype as input requiring conformance review.

## Inputs and limits

Use the tagged traceability matrix, architecture, OpenAPI, test matrix and merged dependencies above. Excluded work includes live paid CI, remote deployment and performance claims.

## Acceptance and verification

Run without provider secrets. A seeded timeout and identity mismatch are reproducible. Introduce an incompatible response in a fixture and confirm contract validation fails. Run the assertions in the named matrix cases that exercise this card’s deliverables, using fixtures for later dependencies. Run isolated unit and contract checks for modified ports and PostgreSQL integration for durable changes. At each milestone rerun the preceding completed slice. The full cross-feature cases remain open until their integration checkpoint. Record command, revision, sanitized outputs and CI URL. Completion requires passing evidence and reviewer sign-off.

## Integration and recovery

All later tasks use these gates. Restore the last passing CI config and retain the failing regression case.

## Change control

A change to the tagged contract opens a CR describing affected IDs, migration/compatibility, risks and regression tests. Credentials stay outside logs, Git and exports. Store actual evidence and any exception in the task record before marking it complete.
