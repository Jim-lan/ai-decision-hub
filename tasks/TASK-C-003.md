# C-003 · Enforce owner authentication and access scope

| Field | Value |
|---|---|
| Status | Awaiting G1 or prerequisite evidence |
| Milestone | P0-M0 |
| Baseline reference | g1-design-v2.0 (usable only once the approved annotated tag exists) |
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
