# C-007 · Qualify one official Gemini adapter

| Field | Value |
|---|---|
| Status | Awaiting G1 or prerequisite evidence |
| Milestone | P0-M1 |
| Baseline reference | g1-design-v2.0 (usable only once the approved annotated tag exists) |
| Requirement IDs | FR-002, FR-004, FR-015, FR-016, NFR-010 |
| Responsible role | Implementer, separate reviewer, CI integrator |
| Dependencies | C-004, C-006, C-010 |
| Planned change surface | ProviderPort, Gemini adapter, dated account eligibility record |
| Test matrix | P0-04, P0-22 |

## Outcome and deliverables

Map official requests/results/errors/usage to ProviderPort. Verify current account, quota, terms, retention and resolved model. Separate a disabled adapter from a released live configuration. Deliver the scoped implementation, regression fixtures, and a verification record in docs/test-reports/C-007.md. Treat the pre-G1 prototype as input requiring conformance review.

## Inputs and limits

Use the tagged traceability matrix, architecture, OpenAPI, test matrix and merged dependencies above. Excluded work includes unverified free entitlements, credential collection in chat, additional providers.

## Acceptance and verification

Fake transport exercises timeout, disabled/unverified target, rate limit and identity mismatch. A separately authorized non-sensitive live fixture returns a traceable original within approved ceilings before real-provider acceptance. Run the assertions in the named matrix cases that exercise this card’s deliverables, using fixtures for later dependencies. Run isolated unit and contract checks for modified ports and PostgreSQL integration for durable changes. At each milestone rerun the preceding completed slice. The full cross-feature cases remain open until their integration checkpoint. Record command, revision, sanitized outputs and CI URL. Completion requires passing evidence and reviewer sign-off.

Record Gemini project/tier/region, model, applicable data terms and quotas. Deny data classes prohibited for the selected tier.

## Integration and recovery

Fanout consumes the same fixture contract. Disable adapter for rollback; never resubmit an uncertain external attempt.

## Change control

A change to the tagged contract opens a CR describing affected IDs, migration/compatibility, risks and regression tests. Credentials stay outside logs, Git and exports. Store actual evidence and any exception in the task record before marking it complete.
