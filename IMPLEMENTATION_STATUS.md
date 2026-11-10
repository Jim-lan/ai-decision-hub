# Implementation status

G1 approved · 2026-11-09 · Implementation started with C-001.

## Recovery

Read [AGENTS.md](AGENTS.md), this file, [design decisions](DESIGN_BASELINE.md) and [task queue](TASK_BACKLOG.md), in order. Use the private remote main branch as the durable checkpoint. Run `git status --short --branch`, `git log -5 --oneline` and `git tag --list 'g1-*'`. Review subsequent commits before using a status entry. The project board still contains the six original sprint issues and is a historical planning aid. The root queue gives the current execution order.

## Evidence ledger

| Work | Durable reference and actual evidence | Disposition |
|---|---|---|
| Initial repository, board and v1.2 plan | Commit 78be784; private Jim-lan/ai-decision-hub, Project 1 with issues 1–6; 49 original tasks in docs/requirements/tasks.md | Completed setup |
| Local workspace prototype | Commit f3c0677. A local Compose web/API/pgvector stack started and GET /v1/health returned ok. Five PostgreSQL integration tests passed during prototyping, covering scope/session, ordered immutable history, run replay and manual import/expiry. The typed response models and browser/restore scripts were added after that test run. | Historical evidence only. Current contract drift, full browser journey, recovery drill and hosted CI need fresh evidence before adoption. |
| Source handoffs | docs/handoff/v1.4 and docs/handoff/governance-v2 preserve package member contents. Canonical governance, prompt and task template are also installed at the working paths. | Imported |
| Design work | GPT-6 Astra High sessions wrote six proposed ADRs and docs/requirements/traceability.md. Fifteen proposed implementation cards and their dependency order are in tasks/. See STATE-001 commit for the exact snapshot. | Candidate artifacts; no independent review verdict |
| Runtime interruption | Astra sessions stopped at their usage limit. The API specialist installed a temporary validator and discussed contracts but did not save docs/api/openapi.yaml. No final architecture or test matrix exists at this checkpoint. | Resume from disk; recreate any temporary tooling from pinned versions. |

## Current handoff

G0-01 was published at be400d2. G0-02 through G0-05 are complete in the G0 closeout commit. The saved candidate includes architecture, API/domain contracts, migration/lifecycle notes, matrix and comparison fixtures. A separate reviewer inspected the fixes and reported no outstanding blocking inconsistencies in the reviewed candidate.

Validation: python3 docs/testing/check_coverage.py passed for 61 requirements, 24 P0 cases and 15 acyclic cards. With openapi-spec-validator 0.7.2 installed, python3 -m openapi_spec_validator docs/api/openapi.yaml passed. python3 docs/testing/check_domain.py passed schema validation and one positive plus three negative audit fixtures. No product test or live provider run was part of these design checks.

The owner approved the freeze. Verified remote annotated tag g1-design-v2.0 resolves to 9edbcd4b9a142d107df219bc64bd6730b39689cd. GPT-6.1 Sol is assigned C-001. Historical interruption entries above describe the earlier STATE-001 checkpoint.

## Verification before owner approval

On November 9 the OpenAPI validator passed, the domain schema and four audit fixtures passed, and the coverage audit found 61 source requirements, 24 specified P0 cases and 15 acyclic cards. Five prototype PostgreSQL tests passed. A separate Compose stack passed the browser journey through login, manual comparison, import, refresh and logout. The synthetic encrypted restore took one second; project, conversation, run, message and response records matched after restart. This drills a small local fixture. Production-sized recovery, nightly off-host backups, independent live fan-out, billing bounds and comparator quality still require their named release tests.

The prototype runtime snapshot had stale response definitions on the same 16 paths. The review refreshed contracts/openapi.json from the built test image; docs/api/openapi.yaml remains the proposed target. No product feature changed during this review.
