# C-009 post-claim recovery checkpoint

Baseline: `g1-design-v2.0` at `9edbcd4b9a142d107df219bc64bd6730b39689cd`.
Validated November 25, 2026. Prior remote checkpoint: `fbb9ca8`.
Checkpoint commit message: `C-009 freeze ambiguous claimed dispatch`.
Status: C-009 in progress; this bounded checkpoint has separate review clearance.

## Behavior and integration

- Revision `0010_post_claim_recovery` allows terminal recovery of an older claimed
  attempt after a replacement worker takes a higher fence. The dispatch transition
  still requires the current unexpired fence; identity and terminal evidence remain
  immutable. Legacy prepared attempts may become unknown only with a matching claim.
- Authorization now creates the durable dispatch claim, advances the prepared attempt,
  and records the held liability within the same transaction before transport.
- Recovery uses `dispatch_claims` as authoritative evidence, including legacy records
  left prepared by the previous writer. It locks the run/work/attempt/target, records
  unknown delivery, preserves the existing hold and appends ordered lifecycle events.
- An all-unknown run fails visibly with `delivery_unknown`. Remaining manual slots
  park until deadline; remaining official slots remain eligible. Recovery creates no
  replacement grant or claim and makes no network call.
- No public wire-contract change or provider activation. This implements existing
  FR-005/FR-014 and DB-03/DB-04 recovery obligations; complete C-009 acceptance is open.

## Review

The separate read-only reviewer identified a P1: the original recovery query skipped
real claims because authorization did not advance the attempt state. The initial test
hid this with a manual SQL update. The correction makes claim/state advancement atomic,
supports legacy prepared+claimed rows and exercises the real authorization path.
Re-review found no remaining blocking finding for this checkpoint. A defensive
`UPDATE ... RETURNING` check also rejects an attempt no longer prepared.

## Executed verification

Docker Desktop was initially stopped; it was started before verification. The first
focused run failed on test fixture assumptions: manual sibling rows lacked their
awaiting-manual state, and a historical UTC-rollover fixture used an expired real
worker lease. Fixtures now match admission behavior and keep the worker lease current
while independently simulating the billing clock. No product guard was weakened.

| Gate | Command and outcome |
|---|---|
| Focused PostgreSQL | `docker compose --profile test run --rm -v "$PWD/apps/api:/app:ro" tests pytest -q -p no:cacheprovider tests/test_policy_budget.py tests/test_runs.py tests/test_migrations.py --tb=short` — 33 passed, one upstream warning. |
| Full PostgreSQL | Same source mount, `pytest -q -p no:cacheprovider` — 81 passed, three upstream Starlette/websockets deprecations. Isolated databases migrate to head twice. |
| Lint | Pinned image, repository mounted read-only: `ruff check --no-cache apps/api/app apps/api/tests docs/testing infra/tests` — passed. |
| Strict typing | `mypy --strict --python-version 3.12 --cache-dir=/tmp/mypy` on ports, Gemini, PostgreSQL runs and typed fakes — passed, four files. An initial invocation used an incorrect relative path and was corrected. |
| Contracts and boundaries | `python docs/testing/check_boundaries.py`, `check_openapi.py`, `check_domain.py`, `check_coverage.py` — passed; 61 requirements, 24 P0 cases and 15 acyclic cards. |
| Vanilla PostgreSQL | `docker compose --profile vanilla-test up --build --abort-on-container-exit --exit-code-from migrate-vanilla migrate-vanilla` — exit 0; upgrade head twice. |

Six recovery combinations cover current/legacy claim writers with no sibling, a pending
manual sibling, or a pending official sibling. They assert stale-fence rejection,
unknown attempt/target state, accurate run outcome, retained liability, correct work
scheduling and one unchanged dispatch claim. No live provider was enabled or called.
Hosted CI evidence will be checked after the checkpoint push; local gates above are
the actual executed evidence and do not imply G4 release readiness.

## Remaining work and rollback

Next: safe prepared-but-unclaimed recovery, then provider execution outside database
transactions, raw and late receipt persistence, known-usage reconciliation and synthesis
handoff. Deadline/cancel attempt terminalization, the full S/T matrix, hybrid fixture and
cross-component/browser/release gates remain open. Nine of fifteen P0 cards are complete.

Deploy migration 0010 before switching writers. Quiesce the worker before rollback;
preserve claims and holds. Database rollback remains restore-only from a verified
pre-migration backup; do not drop attempt evidence or release uncertain liabilities.
