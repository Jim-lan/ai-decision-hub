# C-009 lifecycle foundation checkpoint

Baseline `g1-design-v2.0` at
`9edbcd4b9a142d107df219bc64bd6730b39689cd`. Validated November 14, 2026.
The durable checkpoints use commit messages `C-009 add durable lifecycle foundation`
`C-009 fence pre-send recovery`, and `C-009 prepare fenced dispatch attempts`.
This record is an in-progress recovery checkpoint, not C-009 completion or reviewer
approval.

## Delivered in this checkpoint

- Forward migration `0008_run_lifecycle` backfills canonical run and target state,
  protects valid transitions and terminal state, and adds immutable ordered run events.
- Fenced `run_work` leases and immutable provider-attempt evidence establish the durable
  recovery substrate. Provider-attempt deletion, update, and truncate protections fail
  closed at the database boundary.
- Run creation persists initial run/target events and work intent atomically. Manual
  import transitions the target and appends `original_saved` in the same transaction.
- Owner-scoped polling returns sequence-ordered canonical events. Deadline settlement
  and idempotent cancellation distinguish proven-unsent work from in-flight unknown
  delivery and release only eligible reservations through `BudgetPort`.
- The worker leases with a monotonic fence and parks manual-only work until the run
  deadline. Unsupported official work is rolled back and never dispatched.
- Runtime OpenAPI now exposes canonical run/target state, cancellation, and event
  polling. A synchronization barrier makes the concurrent manual-import collision test
  deterministic.

## Evidence

| Check | Result |
|---|---|
| Complete PostgreSQL regression suite | The latest `pytest -q` passed 74 tests. Three warnings are upstream Starlette/websockets deprecations. Fresh isolated databases run Alembic head twice. |
| Lifecycle and migration coverage | Tests cover backfill, immutable provider attempts, initial and import events, paging sequence, deadline settlement, idempotent cancellation, terminal database guards, fenced lease, manual parking, and deterministic concurrent import. |
| Lint | `ruff check apps/api/app apps/api/tests docs/testing infra/tests` passed. |
| Strict typing | `mypy --strict --python-version 3.12` passed for ports, Gemini, PostgreSQL runs, and typed provider fakes after concrete budget wiring was moved to the composition boundary. |
| Boundary and contracts | Provider boundary, candidate/runtime OpenAPI, incompatible fixture, domain fixtures, and coverage gates passed. Coverage reports 61 requirements, 24 P0 cases, and 15 acyclic cards. |
| Generated contract | `contracts/openapi.json` was regenerated from current source and is checked again in the final checkpoint gate. |

## Pre-send recovery evidence

Forward revision `0009_attempt_fencing` removes the one-grant-per-reservation recovery
dead end while preserving a stronger one-send invariant. Multiple immutable grants may
exist only as recovery evidence before dispatch; `dispatch_claims.reservation_id` is
unique, so only one attempt can ever claim transport for the reservation. Authorization
requires a prepared attempt bound to the current unexpired work fence. The focused
policy/migration slice passed 17 tests and the complete PostgreSQL suite passed 74 tests.
The same lint, strict-type, boundary, API, domain, and coverage gates passed.

## Prepared-attempt evidence

The repository now prepares one official target under the current lease without
crossing the network: it revalidates context/budget, writes the grant-bound immutable
attempt, records T03 and the context snapshot, and returns the exact
`GenerationRequest`. The focused preparation/recovery tests passed 2 tests; the complete
PostgreSQL suite passed 75 tests. Lint, strict typing, boundary, API, domain, and coverage
gates passed. No live provider was enabled or called.

## Outstanding C-009 work

- Prepare provider attempts from immutable context snapshots and budget reservations,
  bind dispatch to the C-010 one-shot authorization grant, and fan out independently.
- Persist response/receipt outcomes without leaking first-round answers across targets.
- Prove kill/restart behavior before dispatch and after ambiguous dispatch; never resend
  an unknown billable request.
- Complete synthesis handoff, partial completion, all required S01–S15 and T01–T14
  edge tests, the named three-target fixture, and relevant integration gates.
- Obtain the required separate read-only review, resolve blocking findings, and only
  then mark C-009 complete.

## Recovery and rollback

Resume from the checkpoint message above after reading the root state files and the
actual diff/log. Preserve migrations `0008_run_lifecycle` and
`0009_attempt_fencing`; the next slice extends their attempt and work records rather
than rewriting their evidence. Quiesce the worker before application rollback. Database
rollback is restore-only from the verified pre-migration backup, as documented by the
migrations; never drop new evidence tables in place.
