# C-009 · Orchestrate independent durable runs

| Field | Value |
|---|---|
| Status | In progress · lifecycle foundation checkpoint validated |
| Milestone | P0-M2 |
| Baseline reference | g1-design-v2.0 @ 9edbcd4b9a142d107df219bc64bd6730b39689cd |
| Requirement IDs | FR-003, FR-005, FR-014, NFR-002, NFR-007, NFR-014 |
| Responsible role | Implementer, separate reviewer, CI integrator |
| Dependencies | C-005, C-007, C-008, C-010 |
| Planned change surface | run service, worker, LangGraph adapter, /v1 runs and polling |
| Test matrix | P0-06, P0-07, P0-11, RUN/TGT suites |

## Outcome and deliverables

Persist run, question, targets and durable dispatch intent before network I/O. Fan out approved snapshots, persist partials, apply deadlines/cancellation, claim work by lease and reconcile recovery. Deliver the scoped implementation, regression fixtures, and a verification record in docs/test-reports/C-009.md. Treat the pre-G1 prototype as input requiring conformance review.

## Inputs and limits

Use the tagged traceability matrix, architecture, OpenAPI, test matrix and merged dependencies above. Excluded work includes general task ledger, delegated agents, unbounded retries.

## Acceptance and verification

Three-target fixture delivers completed, timeout and pending manual entries independently. Kill worker before and after external dispatch. Restart never resends ambiguous billable requests. Every terminal state and transition has a test. Run the assertions in the named matrix cases that exercise this card’s deliverables, using fixtures for later dependencies. Run isolated unit and contract checks for modified ports and PostgreSQL integration for durable changes. At each milestone rerun the preceding completed slice. The full cross-feature cases remain open until their integration checkpoint. Record command, revision, sanitized outputs and CI URL. Completion requires passing evidence and reviewer sign-off.

## In-progress checkpoint · November 14, 2026

The first implementation checkpoint adds forward migration `0008_run_lifecycle`,
canonical run/target state fields, database transition guards, immutable ordered events,
fenced worker leases, cancellation/deadline settlement, and a worker that safely parks
manual-only runs. Run creation and manual import now publish their lifecycle evidence in
the same transaction. The public runtime contract includes canonical state, event
polling, and cancellation. The run repository depends on the frozen `BudgetPort` seam;
concrete PostgreSQL wiring remains at the application boundary.

This checkpoint is not task completion. Official-provider fan-out, prepared-attempt and
dispatch-grant orchestration, crash recovery before/after dispatch, synthesis handoff,
the complete S01–S15/T01–T14 transition matrix, the named three-target fixture, and
separate reviewer sign-off remain outstanding. The worker deliberately rolls back an
official target claim rather than dispatching through an incomplete sequence. See
`docs/test-reports/C-009-lifecycle-checkpoint.md` for executed evidence and recovery
instructions.

### Pre-send recovery checkpoint · November 14, 2026

Forward revision `0009_attempt_fencing` binds a provider attempt to its immutable grant
and current work fence. It permits a new grant only when the prior grant has no dispatch
claim, while a reservation-level unique claim ensures at most one eventual send across
all recovered attempts. Dispatch authorization now rejects stale, expired, non-prepared,
or unfenced attempts before transport and moves the reservation to held atomically with
the one accepted claim. The complete PostgreSQL suite passes 74 tests. Network fan-out,
receipt persistence, post-claim crash handling, and synthesis remain outstanding.

## Integration and recovery

Consumes C-010 leases/reservations and publishes run events atomically. Quiesce worker and release only confirmed-unused reservations before rollback.

## Change control

A change to the tagged contract opens a CR describing affected IDs, migration/compatibility, risks and regression tests. Credentials stay outside logs, Git and exports. Store actual evidence and any exception in the task record before marking it complete.
