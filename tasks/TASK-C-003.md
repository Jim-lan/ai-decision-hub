# C-003 · Enforce owner authentication and access scope

| Field | Value |
|---|---|
| Status | Done |
| Milestone | P0-M0 |
| Baseline reference | g1-design-v2.0 @ 9edbcd4b9a142d107df219bc64bd6730b39689cd |
| Requirement IDs | FR-018, NFR-005, NFR-006, NFR-013 |
| Responsible role | Implementer, separate reviewer, CI integrator |
| Dependencies | C-002 |
| Planned change surface | apps/api security, audit repository, session API |
| Test matrix | P0-02, P0-23 |

## Outcome and deliverables

Implement session expiry/revocation, origin/CSRF checks, scoped authorization and append-only audit metadata. Keep secret material out of validation errors. Deliver the scoped implementation, regression fixtures, and a verification record in docs/test-reports/C-003.md. Treat the pre-G1 prototype as input requiring conformance review.

## Inputs and limits

Use the tagged traceability matrix, architecture, OpenAPI, test matrix and merged dependencies above. Excluded work includes multi-tenant membership, OIDC or internet exposure.

## Acceptance and verification

Valid owner can log in and revoke the session. Expired/replayed cookies, cross-origin writes and guessed foreign UUIDs fail. Inputs, password, cookie and keys are absent from logs and export. Run the assertions in the named matrix cases that exercise this card’s deliverables, using fixtures for later dependencies. Run isolated unit and contract checks for modified ports and PostgreSQL integration for durable changes. At each milestone rerun the preceding completed slice. The full cross-feature cases remain open until their integration checkpoint. Record command, revision, sanitized outputs and CI URL. Completion requires passing evidence and reviewer sign-off.

## Integration and recovery

Every business endpoint calls AuthorizationPort before resource access. Roll back the build and revoke incompatible sessions.

## Change control

A change to the tagged contract opens a CR describing affected IDs, migration/compatibility, risks and regression tests. Credentials stay outside logs, Git and exports. Store actual evidence and any exception in the task record before marking it complete.

## Completion evidence

Completed November 10, 2026. Session expiry and revocation, exact-origin write protection, durable login throttling, owner/project authorization, typed scoped audit evidence, append-only enforcement, and sanitized unexpected-error handling are implemented. The final PostgreSQL suite passed 13 tests; the migration chain passed twice on a fresh vanilla PostgreSQL 16 database; the isolated browser journey passed; and C-001 bootstrap regressions passed. A separate reviewer confirmed that the five initial security/migration findings were resolved with no remaining blocking or major issue. See `docs/test-reports/C-003.md` for commands, scope, and residual limits.

The full export redaction assertion in P0-02 remains assigned to C-015, and the remaining cross-feature authorization coverage in P0-23 remains assigned to C-010, C-013, and C-014. No frozen contract changed and no Change Request was required.
