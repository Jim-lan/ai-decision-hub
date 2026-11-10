# C-011 · Compare attributable original evidence

| Field | Value |
|---|---|
| Status | Awaiting G1 or prerequisite evidence |
| Milestone | P0-M2 |
| Baseline reference | g1-design-v2.0 (usable only once the approved annotated tag exists) |
| Requirement IDs | FR-005, FR-006, NFR-012 |
| Responsible role | Implementer, separate reviewer, CI integrator |
| Dependencies | C-009 |
| Planned change surface | ConsensusPort, comparison repository and report API |
| Test matrix | P0-12 |

## Outcome and deliverables

Produce a versioned report with supported agreement/disagreement, uncertainties, limitations, coverage and conditional recommendation using frozen evidence IDs. Use the local deterministic path. Deliver the scoped implementation, regression fixtures, and a verification record in docs/test-reports/C-011.md. Treat the pre-G1 prototype as input requiring conformance review.

## Inputs and limits

Use the tagged traceability matrix, architecture, OpenAPI, test matrix and merged dependencies above. Excluded work includes external fact verification, paid judge and model-generated decisions.

## Acceptance and verification

For same-family copies, unknown identities, a minority position and a missing response, show coverage without added votes. Every proposition has a valid source span; insufficient support yields abstention. Run the assertions in the named matrix cases that exercise this card’s deliverables, using fixtures for later dependencies. Run isolated unit and contract checks for modified ports and PostgreSQL integration for durable changes. At each milestone rerun the preceding completed slice. The full cross-feature cases remain open until their integration checkpoint. Record command, revision, sanitized outputs and CI URL. Completion requires passing evidence and reviewer sign-off.

## Integration and recovery

UI consumes published report versions. Disable new publication on regression and retain prior versions.

## Change control

A change to the tagged contract opens a CR describing affected IDs, migration/compatibility, risks and regression tests. Credentials stay outside logs, Git and exports. Store actual evidence and any exception in the task record before marking it complete.
