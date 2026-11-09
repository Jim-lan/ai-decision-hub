# Implementation backlog

The baseline is [PAIDH-SAD-001 v1.2](../architecture/baseline-v1.2.md). Use the IDs below in issues, commits and verification notes. Each row is an independently checkable deliverable. An open box includes work awaiting verification. Close a row when its acceptance check passes. The GitHub Project tracks the sprint issues. The rows carry the details and dependencies within each issue.

## Sprint 0 · A durable local workspace

| Done | ID | Depends on | Work and acceptance check | Coverage |
|---|---|---|---|---|
| [x] | F01 | — | Version the supplied English baseline and eight embedded diagrams. Cross-check Word and Markdown requirement IDs. Record stack choices and open questions. | §3, §17, App. B |
| [ ] | F02 | F01 | Create the private Jim-lan repository and linked GitHub Project. Publish this backlog and populate the board with sprint issues. Open the remote main branch to verify the files. | §15 |
| [ ] | F03 | F01 | Define the first HTTP resources and errors. Check in OpenAPI generated from FastAPI and detect drift in CI. Require stable UUIDs, UTC timestamps and opaque cursor pagination for history. | FR-001, NFR-008 |
| [ ] | F04 | F01 | Provision local PostgreSQL with pgvector, a named volume and one-shot Alembic migration. Verify a clean bootstrap and a second upgrade to head. | NFR-001, NFR-009 |
| [ ] | F05 | F04 | Create owner, session, project, conversation, message and audit tables. Allocate a sequence under a conversation lock. Enforce append-only evidence and store its hash. Race two appends and check order. | FR-007, NFR-002 |
| [ ] | F06 | F04 | Initialize a single owner using an injected secret and Argon2id. Implement expiring, revocable cookie sessions, same-origin write checks and redacted audit events. Test denied access, login, logout and cross-site writes. | FR-018, NFR-005/006 |
| [ ] | F07 | F05, F06 | Implement create/list/read for owner-scoped projects and conversations, plus append/read for messages. Check a foreign owner gets 404 and a subsequent session sees the same IDs and text. | FR-001/007, NFR-013 |
| [ ] | F08 | F07 | Build the React project/conversation picker, login and message form. Serve through a same-origin proxy bound to loopback. Check keyboard navigation, API failures and history after refresh. | FR-001, NFR-015 |
| [ ] | F09 | F07 | Configure CI with an isolated database and synthetic owner. Run migrations, API integration tests, OpenAPI drift check and the frontend build on each push and PR. | NFR-008/009 |
| [ ] | F10 | F08 | Back up the DB to a separate destination. Restore into a fresh database, compare IDs, text, hashes and versions, and record duration. Restart the original stack and reread the same conversation. | FR-017, NFR-002/003, T-09/10 |

**Gate** — A new local checkout can start the web app, save a question, restart and recover it. The restore rehearsal must use a different database from the live workspace.

## Sprint 1 · Independent responses

| Done | ID | Depends on | Work and acceptance check | Coverage |
|---|---|---|---|---|
| [ ] | Q01 | F07 | Specify the provider registry and per-response identity snapshot. Include gateway, requested/resolved identity, family, routing, acquisition and verification date. Mark manual declarations and unknown families explicitly. | FR-002/016 |
| [ ] | Q02 | Q01 | Accept an async run with project-owned conversation, question, selected targets and deadline. Persist the question and run atomically. Replay the same key and reject a different payload using that key. | FR-003/007, T-08 |
| [ ] | Q03 | Q02 | Implement manual originals first. Store exact pasted text, hash and declared model in a participating target once. Test a retry, conflicting duplicate, unseen run and two manual targets. | FR-004/005 |
| [ ] | Q04 | Q02 | Add durable jobs, leases and run events. Recover expired leases, keep attempts bounded and resume LangGraph via its supported checkpointer. Simulate worker death on either side of a dispatch. | FR-014, UC-06 |
| [ ] | Q05 | Q01 | Verify Gemini account eligibility, currently allowed model IDs, rates, quotas, privacy and retention against official sources. Record dated facts and secret-file reference before enabling dispatch. | R-01/03, FR-004 |
| [ ] | Q06 | Q02, Q05 | Implement ProviderPort and LiteLLM adapter. Snapshot the resolved identity, normalize provider errors and usage, and test with deterministic transport fixtures. Exercise one opted-in real call separately. | FR-004/016, T-11 |
| [ ] | Q07 | Q02 | Reserve worst-case cost atomically before network access across run/day/month. Reconcile known actuals, retain uncertain charges and reject unknown pricing or exhausted caps. Race overlapping requests at the limit. | FR-015, NFR-004, T-07/08 |
| [ ] | Q08 | Q03, Q04, Q06, Q07 | Freeze an allowed question-only manifest per target until richer retrieval lands. Fan out independently. Test one timeout, one success, a pending manual target, cancellation and a late response. | FR-003/013/014, T-01/02/14 |
| [ ] | Q09 | Q08 | Add progress via replayable SSE or documented polling, raw-response viewer, missing-target indicators and usage details. Verify a refresh mid-run and a partial report after deadline. | FR-002/005/014, NFR-007/014 |

**Gate** — A real eligible Gemini target and a manual target share a run with attributable originals. A simulated timeout preserves completed answers. An offline fixture alone cannot close the real-provider gate.

## Sprint 2 · Reviewable memory and continuity

| Done | ID | Depends on | Work and acceptance check | Coverage |
|---|---|---|---|---|
| [ ] | M01 | F07 | Add canonical source references, candidates, memory items and immutable revisions. Enforce six categories, scope, sensitivity, validity and provenance. Reject adopted records without a source. | FR-009/010, NFR-012 |
| [ ] | M02 | M01, Q03 | Implement native extraction behind MemoryPort. Link candidates to exact source IDs/spans, exclude sensitive content by default and label model-derived assertions unverified. | FR-010, T-06 |
| [ ] | M03 | M02 | Provide a review inbox with source preview, approve/edit/reject and version preconditions. Record actor, reason, old version and audit event in the same transaction. Race two reviewers. | FR-011, T-05 |
| [ ] | M04 | M03 | Tombstone deletion immediately. Queue cleanup of indexes/cache, check absence from retrieval and document backup expiry. Verify idempotent cleanup after a retry. | FR-011, T-13 |
| [ ] | M05 | M01 | Implement owner/project-scoped RetrievalPort over core blocks, decisions and prior episodes. Rank keyword and vector hits, deduplicate and reject expired, superseded and foreign records. | FR-008/009, NFR-011/013, T-03/04 |
| [ ] | M06 | M05, Q08 | Assemble a token-bounded immutable manifest with source revisions, redactions and per-provider differences. Snapshot each actual outbound request and inspect denied-content fixtures. | FR-013, T-03/14 |
| [ ] | M07 | M06 | Build manifest/source navigation. Verify a new conversation can cite an approved earlier constraint and, after revision, retrieves the new value and still links to history. | FR-008/011/013, T-04/05 |
| [ ] | M08 | M05 | Benchmark native search against optional Mem0 and embedding adapters. Capture model/version/dimension, cost, precision and Recall@k on redacted bilingual examples. Test staged reindex. | R-04/05/06/12, T-12 |

**Gate** — New sessions cite the right source version. Captured provider requests show zero cross-project or denied disclosures on the isolation suite.

## Sprint 3 · Comparisons and owner decisions

| Done | ID | Depends on | Work and acceptance check | Coverage |
|---|---|---|---|---|
| [ ] | D01 | Q08 | Extract claims with exact response IDs, spans and initial evidence grades. Preserve minority observations and original answers; regression-test a confidently false assertion. | FR-006, T-06 |
| [ ] | D02 | D01, M06 | Generate a blind report with agreements, disagreements, uncertainties, coverage, evidence and optional recommendation. Deduplicate families, flag unequal contexts and test a missing respondent. | FR-006/014, T-01 |
| [ ] | D03 | D02 | Display a report beside its originals and manifests. Each claim opens its source; missing evidence stays visible. | FR-005/006, NFR-012/015 |
| [ ] | D04 | M01 | Add decision alternatives, selection, rationale, supporting source, status and supersedes link. Require owner confirmation, idempotency and optimistic concurrency. | FR-012, NFR-012 |
| [ ] | D05 | D03, D04, M05 | Add decision entry/history and retrieve the current version across sessions. Change an assumption and verify both the earlier rationale and new selection. | FR-008/012, UC-03, T-04/05 |
| [ ] | D06 | Q07, D02 | Show estimated, reserved and actual spend. Test hard stops with parallel runs, failure and retry; match accounting to each request and run. | FR-015, NFR-004/007 |

**Gate** — The owner can inspect independent evidence, record a choice and revise it in a later conversation. Model agreement cannot promote a claim to verified memory.

## Sprint 4 · Portability and release evidence

| Done | ID | Depends on | Work and acceptance check | Coverage |
|---|---|---|---|---|
| [ ] | H01 | M04, D05 | Export/import versioned JSON and files with IDs, hashes, references and schema version. Restore into a fresh instance; detect corrupt archives and interrupted imports. | FR-017, NFR-016 |
| [ ] | H02 | F10, H01 | Schedule encrypted off-host backups and retention. Rehearse full DB/files recovery and pre-upgrade rollback. Record measured RPO ≤24 h and RTO ≤2 h or track the gap. | NFR-003/009, T-09/10 |
| [ ] | H03 | Q09, M07, D05 | Create 100–200 privacy-safe golden cases with expected sources and transitions. Report critical fact recall (target ≥90%), leakage, identity accuracy, citation validity and cost. | NFR-011/012/013, §12 |
| [ ] | H04 | H03 | Instrument trace ID, latency, stage, model, token usage and redacted errors. Benchmark non-model local API P95 <500 ms with a defined data set and load. | NFR-007/014 |
| [ ] | H05 | M06, D06 | Threat-model sessions, secret files, prompt injection, ACLs and deletion. Verify redacted logs, CSRF rejection and restricted egress. Audit approval, dispatch, memory and decision transitions. | FR-018, NFR-005/006, T-14 |
| [ ] | H06 | F08, H02 | Build ARM64 and AMD64 images. Rehearse ARM64 Linux migration with one writable primary, restore data, private ingress, HTTPS and no published DB port. Verify account/region before provisioning. | NFR-001/006/009, R-08/11 |
| [ ] | H07 | H01–H06 | Run T-01–T-15, including an old client and pre-upgrade fixture. Record commit, environment, outcomes, exceptions and reproducible commands. Walk UC-01–UC-06 through the browser. | T-01–T-15, NFR-008/010/015 |

**Gate** — Publish an MVP tag only with test outcomes, restore timings, a verified ARM64 target and tracked exceptions. Record any unmet release criterion explicitly.

## After MVP

| Done | ID | Depends on | Work and acceptance check | Coverage |
|---|---|---|---|---|
| [ ] | P01 | M03, M04 | Schedule curator proposals for duplicates, staleness and conflicts. Review high-impact changes in a Memory Explorer with temporal and source views. | FR-019/024 |
| [ ] | P02 | D02 | Compare source citations against independent trusted evidence and display the verification date, grade and conflicting sources. | FR-020, R-07 |
| [ ] | P03 | Q09, D02 | Add selective routing and versioned prompts. Preserve first-round boundaries in follow-ups, branches and explicitly labeled critic/debate rounds. | FR-021/022/023 |
| [ ] | P04 | M08 | Ingest versioned documents and web chunks with ACLs and stable spans. Evaluate Chinese/English retrieval on the same projects and report regressions. | FR-025/027, T-12 |
| [ ] | P05 | H06 | Validate secure remote access from an external client. Document region, retention, restore and failover for the chosen host. | FR-026, R-08/11 |
| [ ] | P06 | Q04, H05 | Build permission-scoped scheduled jobs, notifications and decision revalidation. Verify retry deduplication, revocation and audit. | FR-028 |
| [ ] | P07 | P06 | Add ToolPort and isolated execution. Test allowlists, network policy, deadlines and explicit approval for consequential actions. | FR-029, R-10 |
| [ ] | P08 | H05 | Design tenant/workspace boundaries in a separate ADR. Migrate ownership and prove shared-project authorization under adversarial tests. | FR-030 |
| [ ] | P09 | Q01 | Resolve ambiguous agent/product names from owner-supplied URLs. Investigate consented official history imports with stable provenance before adding a connector. | R-02/09 |

## External decisions

The owner selected manual import first, Gemini as the first API candidate, and a private personal GitHub repository and Project under Jim-lan. Paid spend defaults to zero. Provider access, quota, release budget, cloud region and hosting eligibility require real account evidence. Keep local development independent of these decisions.
