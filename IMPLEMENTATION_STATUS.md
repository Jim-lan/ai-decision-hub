# Implementation status

G1 approved · 2026-11-09 · C-001 through C-008 and C-010 completed by November 14, 2026.

## Recovery

Read [AGENTS.md](AGENTS.md), this file, [design decisions](DESIGN_BASELINE.md) and [task queue](TASK_BACKLOG.md), in order. Use the existing remote main branch as the durable checkpoint. The owner changed Jim-lan/ai-decision-hub to public on November 25, 2026; anonymous API access was verified. Runtime secrets and backups remain excluded from Git. Run `git status --short --branch`, `git log -5 --oneline` and `git tag --list 'g1-*'`. Review subsequent commits before using a status entry. The project board still contains the six original sprint issues and is a historical planning aid. The root queue gives the current execution order.

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
| C-004 reproducible verification gates | Commit `57f4d5f` adds pinned Ruff/mypy/OpenAPI/schema tools, transport-neutral ProviderPort types, deterministic provider/API fixtures, external-network denial, and separate CI quality/foundation gates. The final PostgreSQL suite passed 18 tests; fresh vanilla migration and isolated browser gates passed. GitHub Actions Workspace run 10 passed both jobs in 2m09s. Separate re-review signed off after five findings were fixed. See `docs/test-reports/C-004.md`. | Complete; C-005 and C-006 were unblocked, no CR |
| C-005 projects, conversations and bounded history | Checkpoint message `C-005 persist bounded project history` adds the substitutable ConversationRepository/PostgreSQL adapter, stable exact message pages, bounded project-literal search, dedicated-key authenticated cursors, query-safe proxy logs, and the generated history contract. The final PostgreSQL suite passed 21 tests; runtime contract/health and a request+Referer privacy canary passed. Separate re-review signed off after all findings were fixed. See `docs/test-reports/C-005.md`. | Complete; no CR |
| C-006 provider registry and immutable identity snapshots | Checkpoint message `C-006 freeze provider identity snapshots` adds truthful registry metadata, disabled Gemini candidate, immutable target snapshots, nullable resolved identity/usage fields, distinct verified-family counting, compatible legacy writers, and forward revisions `0005_provider_identity` plus `0006_identity_constraints`. The final PostgreSQL suite passed 27 tests; fresh/populated migrations, generated contract, runtime health, and separate re-review passed. See `docs/test-reports/C-006.md`. | Complete; no CR |
| C-010 context, replay, budget and dispatch authorization | Checkpoint message `C-010 guard context replay and spend` adds exact provider-specific sanitized projections, versioned replay compatibility, conservative atomic reservations, UTC/Pacific quota windows, authoritative post-lock clocks, one-shot durable grants/claims, held unknown-delivery liabilities, evidence-safe reconciliation, default-zero owner policy, and `/v1/usage` through forward revision `0007_context_budget`. The final PostgreSQL suite passed 40 tests; fresh vanilla migration, contract/quality gates, and separate re-review passed. See `docs/test-reports/C-010.md`. | Complete; C-007 is next, no CR |
| C-007 disabled Gemini adapter | Checkpoint message `C-007 add disabled Gemini adapter` adds the pinned official SDK behind ProviderPort, fail-closed qualification, a required C-010 authorization claim committed before transport, hardened one-request routing, truthful identity/usage mapping, and raw-receipt observation for C-009. The final PostgreSQL suite passed 70 tests; fresh vanilla migration, rebuilt runtime health/contract checks, quality gates, and separate re-review passed. See `docs/test-reports/C-007.md`. | Complete; live activation remains blocked pending owner qualification and smoke approval; C-008 is next, no CR |
| C-008 exact manual originals | Checkpoint message `C-008 preserve manual originals` adds the RunRepository seam, owner-scoped run/target locking, exact content and digest preservation, truthful user-declared provenance, stable concurrent replay, deadline recovery, wrong-kind rejection, and the canonical response contract. The final PostgreSQL suite passed 71 tests; runtime health/contract, quality gates, and separate re-review passed. See `docs/test-reports/C-008.md`. | Complete; C-009 is next, no CR |
| C-009 durable lifecycle and dispatch preparation | In-progress checkpoint messages `C-009 add durable lifecycle foundation`, `C-009 fence pre-send recovery`, and `C-009 prepare fenced dispatch attempts` add revisions `0008_run_lifecycle` and `0009_attempt_fencing`, guarded lifecycle/events/leases, reservation-level one-send enforcement, and atomic grant-bound attempt preparation with exact frozen input. The PostgreSQL suite passed 75 tests; lint, strict typing, boundary, API, domain, and coverage gates passed. See `docs/test-reports/C-009-lifecycle-checkpoint.md`. | In progress; do not count as a completed card. Provider execution, receipt/post-claim crash handling, synthesis, full transition coverage, and separate review remain. No CR. |

## Current handoff

### Latest checkpoint · November 25, 2026

C-009 post-claim recovery is validated for checkpoint commit
`C-009 freeze ambiguous claimed dispatch`, based on prior remote SHA `fbb9ca8`.
Revision `0010_post_claim_recovery` permits a replacement worker to terminalize older
claimed attempts while preserving immutable attempt identity and terminal evidence.
Authorization now atomically advances the attempt with its dispatch claim. Recovery
also recognizes legacy committed claims whose attempt still says prepared. Both paths
retain the held liability, emit ordered target/run evidence, and never resend. Manual
siblings park until deadline and pending official siblings remain eligible.

Fresh evidence: 33 focused PostgreSQL tests and 81 full-suite tests passed; three
upstream warnings remain. Ruff, strict typing, boundaries, API/domain/coverage checks,
and the vanilla PostgreSQL double-upgrade gate passed. A separate read-only reviewer
found one blocking claim-state gap; it was corrected and re-reviewed with no remaining
blocking checkpoint finding. See `docs/test-reports/C-009-post-claim-recovery.md`.

C-009 remains in progress; 9 of 15 cards are complete. Next implement safe recovery of
prepared-but-unclaimed attempts, then provider execution outside transactions, raw and
late receipt persistence, accounting and synthesis handoff. Deadline/cancel attempt
terminalization and the complete transition/integration gates also remain outstanding.
No live provider was activated, no credits/reset were consumed, and no CR was needed.
Historical checkpoint entries below retain their original evidence counts.

G0-01 was published at be400d2. G0-02 through G0-05 are complete in the G0 closeout commit. The saved candidate includes architecture, API/domain contracts, migration/lifecycle notes, matrix and comparison fixtures. A separate reviewer inspected the fixes and reported no outstanding blocking inconsistencies in the reviewed candidate.

C-001 added a redacted local-start preflight, focused bootstrap tests, CI coverage, and the documented operator entry point. A fresh temporary checkout failed safely without secrets, then built and served healthy web/API entry points after initialization. Evidence is recorded in `docs/test-reports/C-001.md`.

C-002 adopted the prototype storage through forward revision `0003_storage_contract`. It backfills and requires run project scope, enforces composite owner/project/conversation/message links, validates source-digest storage, and makes audit evidence immutable. Empty vanilla PostgreSQL and populated prototype upgrades are idempotent; a malformed legacy scope aborts without a partial schema. Evidence is recorded in `docs/test-reports/C-002.md`.

C-003 hardened the owner boundary through forward revision `0004_security_audit`. Sessions are stored as hashes and expire or revoke durably; state-changing requests require the configured exact origin; failed logins use a durable serialized throttle; resource lookup is owner/project scoped; audit rows carry a typed action, outcome, project scope, and schema version and reject update, delete, truncate, and new legacy-format inserts. Unexpected server failures return and log only a trace identifier while rolling back business and audit writes. Fresh migration, focused and complete PostgreSQL suites, an isolated browser journey, and C-001 bootstrap regressions passed. Evidence is recorded in `docs/test-reports/C-003.md`.

C-004 installed a deterministic offline verification layer. CI validates lint, the typed transport-neutral ProviderPort boundary, candidate and runtime OpenAPI documents and fixtures, domain fixtures, requirement links, migrations, PostgreSQL integration, generated runtime contract drift, HTTP entry points, the browser journey, and recovery. Tests deny external network connections and keep live-provider qualification opt-in and outside CI. Deterministic results preserve unknown identity/usage, classify a returned model outside the request allowlist as invalid, and reproduce timeouts. Evidence is recorded in `docs/test-reports/C-004.md`.

C-005 moved canonical workspace persistence behind the frozen ConversationRepository seam and added bounded same-project literal history with stable source links. Search cursors are scoped and HMAC-authenticated with a dedicated durable key; malformed, modified, stale, and cross-project positions fail closed. Proxy logs omit request queries and Referer values. Exact Unicode content, hashes, concurrent sequence allocation, pagination, session reopen, and invalid-write rollback behavior passed the real PostgreSQL suite. Evidence is recorded in `docs/test-reports/C-005.md`.

C-006 adopted the frozen provider registry and identity evidence rules through forward revisions `0005_provider_identity` and `0006_identity_constraints`. New target rows receive database-authoritative immutable registry snapshots; historical rows remain explicitly unknown where no historical fact exists. Manual results remain user-declared, unknown measured values remain null, and only included official API evidence with attributable nonsentinel resolution can count a distinct model family. Gemini remains a disabled candidate with blocked privacy and unknown pricing. Fresh and populated migrations, 27 PostgreSQL regressions, contract/quality gates, runtime health, and separate re-review passed. Evidence is recorded in `docs/test-reports/C-006.md`.

C-010 adopted the frozen context, idempotency, budget, and dispatch-authorization boundaries through forward revision `0007_context_budget`. It preserves exact legacy replay while normalizing new requests, stores immutable destination-redacted prepared bytes and their ordered recipe, reserves bounded worst-case exposure under serialized owner/provider-account locks, rechecks consent/tariffs/caps/quotas after authoritative lock-time clocks, and permits only one durable claim. A claim becomes an unresolved held liability before dispatch and carries across UTC and provider-local resets. Exact settlement, proof-gated release, overrun quarantine, usage accounting, fresh migration, 40 PostgreSQL regressions, contract/quality gates, and separate re-review passed. Evidence is recorded in `docs/test-reports/C-010.md`.

C-007 implemented the frozen Gemini candidate seam without enabling live traffic. The official SDK is isolated behind ProviderPort; qualification, provider/model bounds, and the C-010 one-shot claim fail closed before a single hardened transport request. Returned identity and measured usage remain truthful, including unknown provenance and incomplete usage, and the raw receipt reaches the C-009 observer before validation. The complete PostgreSQL suite passed 70 tests; fresh migration, quality/contract gates, rebuilt runtime checks, and separate adversarial re-review passed. Evidence is recorded in `docs/test-reports/C-007.md`. Live activation remains blocked until the owner supplies and approves the dated account, tariff, privacy, quota, spend-policy, credential, and non-sensitive smoke evidence listed in the qualification record.

C-008 moved manual-original persistence behind RunRepository. The adapter serializes
run then target access, validates manual eligibility before replay, preserves exact
submitted bytes and their digest, keeps provenance user-declared and unknown
measurements null, and makes exact replay stable without duplicate audit evidence.
Changed evidence, wrong-kind targets, foreign runs, and fresh post-deadline imports fail
closed. The complete PostgreSQL suite passed 71 tests; quality/contract gates, rebuilt
runtime contract/health, and separate re-review passed. Evidence is recorded in
`docs/test-reports/C-008.md`. C-009 is next; 9 of 15 P0 implementation cards are
complete. C-009 owns lifecycle/terminal freeze and its deterministic collision gate.

C-009 now has a validated, recoverable lifecycle foundation. Forward revision
`0008_run_lifecycle` backfills existing runs, protects canonical transitions and
terminal state, and introduces immutable sequence-ordered events, fenced work leases,
and durable provider-attempt evidence. Run creation, manual import, polling, deadline
settlement, and idempotent cancellation exercise that state. A worker entry point safely
leases and parks manual-only runs; it intentionally rolls back if it encounters an
official target because the complete authorization/attempt/fan-out sequence is still
outstanding. The complete PostgreSQL suite passed 73 tests and all local quality and
contract gates passed. This remains C-009 in progress, so the count stays 9 of 15. Resume
with official-provider prepared attempts, grant-bound dispatch, unknown-delivery crash
recovery, synthesis handoff, remaining lifecycle edges, and separate review. Evidence
and exact recovery scope are in `docs/test-reports/C-009-lifecycle-checkpoint.md`.

The next C-009 checkpoint closes pre-send recovery fencing through revision
`0009_attempt_fencing`. A reservation may receive a replacement grant only while every
earlier grant remains unclaimed. The accepted transport claim is unique by reservation,
is bound to a prepared provider attempt and the current unexpired worker fence, and
atomically converts the reservation to held. A stale worker or stale prepared attempt
therefore cannot send, while a crash before any claim can be recovered without consuming
the only grant identity. The complete PostgreSQL suite now passes 74 tests. C-009 remains
in progress at 9 of 15 cards; continue with actual independent network fan-out, receipt
persistence, post-claim unknown-delivery recovery, synthesis, transition completeness,
and separate review.

The prepared-attempt checkpoint adds a transport-neutral `DispatchWork` contract and
atomic repository operation. Under the current unexpired worker fence it revalidates
the C-010 reservation/context, persists the immutable grant-bound attempt, advances T03,
and returns the exact provider-visible input without claiming dispatch or crossing the
network inside the transaction. The complete suite now passes 75 tests. C-009 remains
in progress; wire the provider execution outside the transaction, persist raw receipt
and normalized outcome, handle post-claim unknown delivery, then complete synthesis and
the remaining transition/review gates.

Validation: python3 docs/testing/check_coverage.py passed for 61 requirements, 24 P0 cases and 15 acyclic cards. With openapi-spec-validator 0.7.2 installed, python3 -m openapi_spec_validator docs/api/openapi.yaml passed. python3 docs/testing/check_domain.py passed schema validation and one positive plus three negative audit fixtures. No product test or live provider run was part of these design checks.

The owner approved the freeze. Verified remote annotated tag g1-design-v2.0 resolves to 9edbcd4b9a142d107df219bc64bd6730b39689cd. C-009 is the next assigned task under the approved execution plan. Historical interruption entries above describe the earlier STATE-001 checkpoint.

## Verification before owner approval

On November 9 the OpenAPI validator passed, the domain schema and four audit fixtures passed, and the coverage audit found 61 source requirements, 24 specified P0 cases and 15 acyclic cards. Five prototype PostgreSQL tests passed. A separate Compose stack passed the browser journey through login, manual comparison, import, refresh and logout. The synthetic encrypted restore took one second; project, conversation, run, message and response records matched after restart. This drills a small local fixture. Production-sized recovery, nightly off-host backups, independent live fan-out, billing bounds and comparator quality still require their named release tests.

The prototype runtime snapshot had stale response definitions on the same 16 paths. The review refreshed contracts/openapi.json from the built test image; docs/api/openapi.yaml remains the proposed target. No product feature changed during this review.
