# C-014 · Run cross-component adversity and compatibility suite

| Field | Value |
|---|---|
| Status | Awaiting G1 or prerequisite evidence |
| Milestone | P0-M3 |
| Baseline reference | g1-design-v2.0 (usable only once the approved annotated tag exists) |
| Requirement IDs | FR-003, FR-014, FR-015, FR-018, NFR-007, NFR-008, NFR-014, NFR-015 |
| Responsible role | Implementer, separate reviewer, CI integrator |
| Dependencies | C-003, C-004, C-009, C-010, C-011, C-012, C-013 |
| Planned change surface | CI, integration/evaluation suites, docs/test-reports |
| Test matrix | P0-15, P0-16, P0-19, P0-23, P0-24 |

## Outcome and deliverables

Combine adversarial fixtures for isolation, timeout, cancel/replay, provider identity, deterministic reports and owner confirmation; benchmark local non-LLM routes under stated load. Deliver the scoped implementation, regression fixtures, and a verification record in docs/test-reports/C-014.md. Treat the pre-G1 prototype as input requiring conformance review.

## Inputs and limits

Use the tagged traceability matrix, architecture, OpenAPI, test matrix and merged dependencies above. Excluded work includes p1 bilingual retrieval targets and production provider benchmarks.

## Acceptance and verification

Attach CI/commit, timings, redacted failing examples and outcome for each P0 row. Unexpected outbound content, duplicate billable attempt or a missing trace fails G3. Run the named matrix cases, isolated unit and contract checks for modified ports, and real PostgreSQL integration for durable changes. Re-run the preceding milestone's vertical slice. Record command, revision, sanitized outputs and CI URL. Completion requires passing evidence and reviewer sign-off.

## Integration and recovery

Re-run each completed vertical slice. Stop promotion and reopen the responsible card on failure.

## Change control

A change to the tagged contract opens a CR describing affected IDs, migration/compatibility, risks and regression tests. Credentials stay outside logs, Git and exports. Store actual evidence and any exception in the task record before marking it complete.
