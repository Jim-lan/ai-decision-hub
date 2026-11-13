# Implementation status

G1 approved · 2026-11-09 · C-001 through C-004 completed by November 12, 2026.

## Recovery

Read [AGENTS.md](AGENTS.md), this file, [design decisions](DESIGN_BASELINE.md) and [task queue](TASK_BACKLOG.md), in order. Use the private remote main branch as the durable checkpoint. Run `git status --short --branch`, `git log -5 --oneline` and `git tag --list 'g1-*'`. Review subsequent commits before using a status entry. The project board still contains the six original sprint issues and is a historical planning aid. The root queue gives the current execution order.

## Evidence ledger

| Work | Durable reference and actual evidence | Disposition |
|---|---|---|
| Initial repository, board and v1.2 plan | Commit 78be784; private Jim-lan/ai-decision-hub, Project 1 with issues 1–6; 49 original tasks in docs/requirements/tasks.md | Completed setup |
| Local workspace prototype | Commit f3c0677. A local Compose web/API/pgvector stack started and GET /v1/health returned ok. Five PostgreSQL integration tests passed during prototyping, covering scope/session, ordered immutable history, run replay and manual import/expiry. The typed response models and browser/restore scripts were added after that test run. | Historical evidence only. Current contract drift, full browser journey, recovery drill and hosted CI need fresh evidence before adoption. |
| Source handoffs | docs/handoff/v1.4 and docs/handoff/governance-v2 preserve package member contents. Canonical governance, prompt and task template are also installed at the working paths. | Imported |
| Design work | GPT-6 Astra High sessions wrote six proposed ADRs and docs/requirements/traceability.md. Fifteen proposed implementation cards and their dependency order are in tasks/. See STATE-001 commit for the exact snapshot. | Historical checkpoint; superseded by the independently reviewed G1 baseline. |
| Runtime interruption | Astra sessions stopped at their usage limit. The API specialist installed a temporary validator and discussed contracts but did not save docs/api/openapi.yaml at that checkpoint. | Historical interruption; later G0/G1 commits completed and froze the missing architecture, contract, and test artifacts. |
| C-002 canonical storage migration | Alembic `0003_storage_contract`, compatible run writes, vanilla PostgreSQL 16 gate, and migration fixtures. Three focused migration tests and the final eight-test API/PostgreSQL suite passed; four C-001 regressions also passed. Separate re-review signed off after two findings were fixed. See `docs/test-reports/C-002.md`. | Complete; C-003 unblocked, no CR |
| C-003 owner authentication and access scope | Alembic `0004_security_audit`, hashed/expiring/revocable sessions, exact-origin write protection, durable login throttling, owner/project authorization, typed scoped append-only audit events, and sanitized 500 responses. The final PostgreSQL suite passed 13 tests, fresh vanilla migration and isolated browser gates passed, and four C-001 regressions passed. Separate re-review signed off after five findings were fixed. See `docs/test-reports/C-003.md`. | Complete; C-004 was unblocked, no CR |
| C-004 reproducible verification gates | Pinned Ruff/mypy/OpenAPI/schema tools, transport-neutral ProviderPort types, deterministic provider/API fixtures, external-network denial, and separate CI quality/foundation gates. The final PostgreSQL suite passed 18 tests; fresh vanilla migration and isolated browser gates passed. Separate re-review signed off after five findings were fixed. See `docs/test-reports/C-004.md`. | Complete; C-005 is next and C-006 is independently eligible, no CR |

## Current handoff

G0-01 was published at be400d2. G0-02 through G0-05 are complete in the G0 closeout commit. The saved candidate includes architecture, API/domain contracts, migration/lifecycle notes, matrix and comparison fixtures. A separate reviewer inspected the fixes and reported no outstanding blocking inconsistencies in the reviewed candidate.

C-001 added a redacted local-start preflight, focused bootstrap tests, CI coverage, and the documented operator entry point. A fresh temporary checkout failed safely without secrets, then built and served healthy web/API entry points after initialization. Evidence is recorded in `docs/test-reports/C-001.md`.

C-002 adopted the prototype storage through forward revision `0003_storage_contract`. It backfills and requires run project scope, enforces composite owner/project/conversation/message links, validates source-digest storage, and makes audit evidence immutable. Empty vanilla PostgreSQL and populated prototype upgrades are idempotent; a malformed legacy scope aborts without a partial schema. Evidence is recorded in `docs/test-reports/C-002.md`.

C-003 hardened the owner boundary through forward revision `0004_security_audit`. Sessions are stored as hashes and expire or revoke durably; state-changing requests require the configured exact origin; failed logins use a durable serialized throttle; resource lookup is owner/project scoped; audit rows carry a typed action, outcome, project scope, and schema version and reject update, delete, truncate, and new legacy-format inserts. Unexpected server failures return and log only a trace identifier while rolling back business and audit writes. Fresh migration, focused and complete PostgreSQL suites, an isolated browser journey, and C-001 bootstrap regressions passed. Evidence is recorded in `docs/test-reports/C-003.md`.

C-004 installed a deterministic offline verification layer. CI validates lint, the typed transport-neutral ProviderPort boundary, candidate and runtime OpenAPI documents and fixtures, domain fixtures, requirement links, migrations, PostgreSQL integration, generated runtime contract drift, HTTP entry points, the browser journey, and recovery. Tests deny external network connections and keep live-provider qualification opt-in and outside CI. Deterministic results preserve unknown identity/usage, classify a returned model outside the request allowlist as invalid, and reproduce timeouts. Evidence is recorded in `docs/test-reports/C-004.md`. C-005 is next; C-006 is independently eligible; 4 of 15 P0 implementation cards are complete.

Validation: python3 docs/testing/check_coverage.py passed for 61 requirements, 24 P0 cases and 15 acyclic cards. With openapi-spec-validator 0.7.2 installed, python3 -m openapi_spec_validator docs/api/openapi.yaml passed. python3 docs/testing/check_domain.py passed schema validation and one positive plus three negative audit fixtures. No product test or live provider run was part of these design checks.

The owner approved the freeze. Verified remote annotated tag g1-design-v2.0 resolves to 9edbcd4b9a142d107df219bc64bd6730b39689cd. C-005 is the next assigned task under the approved execution plan; C-006 is also eligible. Historical interruption entries above describe the earlier STATE-001 checkpoint.

## Verification before owner approval

On November 9 the OpenAPI validator passed, the domain schema and four audit fixtures passed, and the coverage audit found 61 source requirements, 24 specified P0 cases and 15 acyclic cards. Five prototype PostgreSQL tests passed. A separate Compose stack passed the browser journey through login, manual comparison, import, refresh and logout. The synthetic encrypted restore took one second; project, conversation, run, message and response records matched after restart. This drills a small local fixture. Production-sized recovery, nightly off-host backups, independent live fan-out, billing bounds and comparator quality still require their named release tests.

The prototype runtime snapshot had stale response definitions on the same 16 paths. The review refreshed contracts/openapi.json from the built test image; docs/api/openapi.yaml remains the proposed target. No product feature changed during this review.
