# C-005 · Persist projects, conversations and bounded history

| Field | Value |
|---|---|
| Status | Done |
| Milestone | P0-M1 |
| Baseline reference | g1-design-v2.0 @ 9edbcd4b9a142d107df219bc64bd6730b39689cd |
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

Two concurrent messages get distinct ordered IDs. Reopening a session returns original text. Foreign project, malformed cursor and stale references are rejected. Run the assertions in the named matrix cases that exercise this card’s deliverables, using fixtures for later dependencies. Run isolated unit and contract checks for modified ports and PostgreSQL integration for durable changes. At each milestone rerun the preceding completed slice. The full cross-feature cases remain open until their integration checkpoint. Record command, revision, sanitized outputs and CI URL. Completion requires passing evidence and reviewer sign-off.

## Integration and recovery

Run requests and context selection depend on these IDs. Preserve rows on application rollback.

## Change control

A change to the tagged contract opens a CR describing affected IDs, migration/compatibility, risks and regression tests. Credentials stay outside logs, Git and exports. Store actual evidence and any exception in the task record before marking it complete.

## Completion evidence

Completed November 13, 2026. Workspace persistence now consumes the frozen
`ConversationRepository` through a composition factory backed by a PostgreSQL adapter. Projects,
conversations, immutable exact-content messages, stable sequence pages, and bounded
case-insensitive literal project history are available through the approved routes. Search pages
use project/query-bound HMAC-authenticated keyset cursors backed by a dedicated durable signing
secret; malformed, stale, cross-project, and modified cursors return the documented error.

The final PostgreSQL suite passed 21 tests. Ruff, strict port typing, boundary, OpenAPI, domain,
coverage, bootstrap, runtime-contract equality, Compose health, and diff gates passed. A live
proxy canary placed sensitive values in both the request query and Referer; nginx logged only the
path. Separate review findings about repository substitution, cursor authentication and key
separation, malformed fields, query/Referer logging, and the generated snapshot were resolved;
re-review reported no blocking or major issue. See `docs/test-reports/C-005.md`.

This closes the C-005 portions of P0-01 and P0-14. Decision hits remain deferred to C-013, and the
full restart/recovery release assertion remains with C-015. No embeddings, semantic memory,
cross-project retrieval, P1/P2 behavior, frozen public-contract change, or Change Request was
introduced.
