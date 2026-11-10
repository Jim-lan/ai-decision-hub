# C-012 · Ship the browser comparison workflow

| Field | Value |
|---|---|
| Status | Awaiting prerequisite evidence |
| Milestone | P0-M2 |
| Baseline reference | g1-design-v2.0 @ 9edbcd4b9a142d107df219bc64bd6730b39689cd |
| Requirement IDs | FR-001, FR-002, FR-005, FR-006, FR-014, NFR-015 |
| Responsible role | Implementer, separate reviewer, CI integrator |
| Dependencies | C-005, C-009, C-011 |
| Planned change surface | apps/web, browser contract fixtures |
| Test matrix | P0-15, P0-16 |

## Outcome and deliverables

Deliver project selection, question, target selection, progress, raw originals, manual import, timeout/cancel, report and source inspection against the G1 API. Deliver the scoped implementation, regression fixtures, and a verification record in docs/test-reports/C-012.md. Treat the pre-G1 prototype as input requiring conformance review.

## Inputs and limits

Use the tagged traceability matrix, architecture, OpenAPI, test matrix and merged dependencies above. Excluded work includes memory Explorer, multi-agent dashboard and hosted launch.

## Acceptance and verification

Browser reload during a partial run returns same run and answers. Keyboard-only navigation reaches every target and source. Auth loss and failed imports give accessible feedback without losing saved originals. Run the assertions in the named matrix cases that exercise this card’s deliverables, using fixtures for later dependencies. Run isolated unit and contract checks for modified ports and PostgreSQL integration for durable changes. At each milestone rerun the preceding completed slice. The full cross-feature cases remain open until their integration checkpoint. Record command, revision, sanitized outputs and CI URL. Completion requires passing evidence and reviewer sign-off.

## Integration and recovery

Exercise Slice B through real HTTP and PostgreSQL. Redeploy previous web image against compatible API.

## Change control

A change to the tagged contract opens a CR describing affected IDs, migration/compatibility, risks and regression tests. Credentials stay outside logs, Git and exports. Store actual evidence and any exception in the task record before marking it complete.
