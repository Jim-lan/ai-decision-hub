# C-008 · Import a manual original

| Field | Value |
|---|---|
| Status | Done |
| Milestone | P0-M1 |
| Baseline reference | g1-design-v2.0 @ 9edbcd4b9a142d107df219bc64bd6730b39689cd |
| Requirement IDs | FR-002, FR-004, FR-005, FR-007 |
| Responsible role | Implementer, separate reviewer, CI integrator |
| Dependencies | C-005, C-006 |
| Planned change surface | manual adapter, run target/response repository |
| Test matrix | P0-05, P0-11 |

## Outcome and deliverables

Bind pasted original and user-declared identity to one eligible target in a scoped run. Make replay safe and preserve whitespace/Unicode exactly. Deliver the scoped implementation, regression fixtures, and a verification record in docs/test-reports/C-008.md. Treat the pre-G1 prototype as input requiring conformance review.

## Inputs and limits

Use the tagged traceability matrix, architecture, OpenAPI, test matrix and merged dependencies above. Excluded work includes chat-login automation and asserting verified provenance for manual input.

## Acceptance and verification

Concurrent identical imports return a single stable response ID; changed payload conflicts. Wrong owner, target or elapsed deadline cannot amend a published original. Run the assertions in the named matrix cases that exercise this card’s deliverables, using fixtures for later dependencies. Run isolated unit and contract checks for modified ports and PostgreSQL integration for durable changes. At each milestone rerun the preceding completed slice. The full cross-feature cases remain open until their integration checkpoint. Record command, revision, sanitized outputs and CI URL. Completion requires passing evidence and reviewer sign-off.

## Integration and recovery

Use repository fixtures until C-009 wires the orchestration. Disable new imports on rollback and preserve existing evidence.

## Change control

A change to the tagged contract opens a CR describing affected IDs, migration/compatibility, risks and regression tests. Credentials stay outside logs, Git and exports. Store actual evidence and any exception in the task record before marking it complete.

## Completion evidence

Completed November 14, 2026. Manual imports now pass through the frozen
RunRepository boundary and the PostgreSQL adapter locks the owner-scoped run before
the selected target. Eligible manual targets preserve the submitted content byte for
byte, including whitespace, CRLF, and Unicode, and record its UTF-8 SHA-256 digest.
User-declared app/model identity remains explicitly user-declared; provider resolution,
elapsed time, usage, and cost remain unknown rather than being fabricated.

Exact concurrent replay returns the same response ID and creates one audit record.
Changed content or identity, an ineligible official target, a fresh import after the
deadline, or a foreign run fails closed. An exact replay remains available after the
deadline so clients can recover a previously committed result. The public request now
rejects unknown fields and the 201 response returns the canonical OriginalDetails
shape. No database migration was necessary because the frozen schema already carried
the required fields.

The focused run/provider slice passed 15 tests and the complete PostgreSQL suite passed
71. Ruff, strict typing, boundary, OpenAPI, domain, coverage, runtime contract, health,
and migration-head checks passed. A separate reviewer signed off after the wrong-kind
replay path was fixed. See `docs/test-reports/C-008.md`.

C-009 remains responsible for durable lifecycle/terminal-state enforcement and for a
deterministically synchronized collision test at the orchestration integration gate.
No Change Request, P1, or P2 work was introduced.
