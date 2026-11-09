# Requirement traceability · ADH v2.0 G1 candidate

**D-002 · Proposed for owner approval.** All P0 cases are specified, pending implementation and execution. A case has a positive and a negative assertion in the [test matrix](../testing/test-matrix.md). Each named C-ticket owns implementation within its scope. C-014 collects integrated evidence. Future rows name the responsible domain and its admission test. The owner assigns a future ticket only after approving that phase. No future table, endpoint or service is required to reserve a port.

The first column of each catalogue preserves the source ID. The v1.2 functional priorities are original classifications. Its non-functional catalogue has no separate priority per row. The phase column records the candidate disposition. The [architecture](../architecture/baseline-v2.0.md), [API](../api/openapi.yaml) and [conflict log](conflict-log.md) carry the design and unresolved decisions. Owner signature, date and frozen Git reference are pending in the [freeze review](../G1_FREEZE_REVIEW.md).

## Functional catalogue

Source: v1.2 §3.1. The future conditions in the last column are positive and negative gate examples for the deferred part of a row. P0 case IDs refer to both directions of the test.

| ID | Original | Requirement | Proposed phase | Design and contract | Owning work | Cases and future gate |
|---|---|---|---|---|---|---|
| FR-001 | P0 | Unified web chat; create and select projects and conversations | P0 | Workspace · projects, conversations, messages, runs | C-005, C-012 | P0-01, P0-16 |
| FR-002 | P0 | Select multiple models and show actual family/model/version | P0 | Registry · provider list, target and response identity snapshots | C-006, C-012 | P0-03, P0-11 |
| FR-003 | P0 | Run independent first-round model requests concurrently | P0 | RunRepository/ProviderPort · create run and dispatch isolated inputs | C-009, C-010 | P0-06, P0-09 |
| FR-004 | P0 | Support official API adapters and manual response import | P0 | ProviderPort · API target and manual-responses operation | C-007, C-008 | P0-04, P0-05, P0-24 |
| FR-005 | P0 | Preserve full original responses, failures, and progress | P0 | RunRepository · responses, targets, progress and raw viewer | C-008, C-009, C-012 | P0-07, P0-11, P0-16 |
| FR-006 | P0 | Produce structured agreement, disagreement, uncertainty, evidence, recommendation | P0 | ConsensusPort · run report with claims, source references and coverage | C-011, C-012 | P0-12, P0-16 |
| FR-007 | P0 | Persist original conversations and messages | P0 | ConversationRepository · ordered messages and immutable sources | C-002, C-005 | P0-01, P0-14, P0-20 |
| FR-008 | P0 | Retrieve relevant history across sessions | P0 + P1 | P0 project history, lexical search and reopen; P1 MemoryPort semantic retrieval | C-005, C-013; P1 memory | P0-14. P1 retrieves approved relevant sources across sessions and excludes expired or inaccessible versions. |
| FR-009 | P0 | Keep six memory categories logically distinct | P1 | MemoryPort · typed memory and category policies | P1 memory | Round-trip each of six categories; reject retrieval of operational scratch as approved user knowledge. |
| FR-010 | P0 | Extract reviewable memory candidates | P1 | MemoryPort · source-linked candidates | P1 memory | Extract a candidate from a cited excerpt; an unsupported model claim stays unverified. P0-12 protects the current evidence boundary. |
| FR-011 | P0 | Let owner approve, edit, reject, and delete memory | P1 | MemoryPort · approval and immutable revisions | P1 memory | Approve/edit/reject/delete a candidate; reject stale revision, suppress tombstone from index and retrieval on retry. |
| FR-012 | P0 | Persist decisions with options, rationale, status, and supersession | P0 + P1 | P0 decision links owner choice/rationale to run; P1 alternatives, revisions and supersession | C-013; P1 decisions | P0-13. P1 changes active choice while preserving earlier evidence; rejects cyclic supersession. |
| FR-013 | P0 | Build privacy-aware, token-bounded context packages | P0 + P1 | ContextPort · bounded provider-specific outbound snapshots; P1 rich manifest and retrieval | C-009, C-010; P1 memory | P0-06, P0-09. P1 opens exact selected source versions; omits disallowed history even if highly ranked. |
| FR-014 | P0 | Handle failures, deadlines, and partial results | P0 | RunRepository · run/target deadline, cancellation, terminal reporting | C-009, C-012 | P0-07, P0-11; RUN and TGT transition tables |
| FR-015 | P0 | Track tokens, estimated spend, quotas, and hard budgets | P0 | BudgetPort · usage, reservations and bounded retries | C-010 | P0-08, P0-10 |
| FR-016 | P0 | Maintain provider/model registry and family deduplication | P0 | Registry · immutable per-run routing/identity and family grouping | C-006, C-011 | P0-03, P0-12 |
| FR-017 | P0 | Export, backup, import, and restore owned data | P0 | Operations · portable owned-data files, clean import and encrypted database recovery | C-015 | P0-17, P0-18, P0-20 |
| FR-018 | P0 | Owner login, secret protection, and audit trail | P0 | AuthorizationPort · sessions, all scoped objects, secret files and audit | C-003, C-010, C-014 | P0-02, P0-09, P0-23 |
| FR-019 | P1 | Background memory consolidation/curator | P1 | MemoryPort · curator proposals and revision review | P1 memory | Detect stale facts, duplicates and contradictions on a seeded timeline; high-impact proposals cannot self-approve. |
| FR-020 | P1 | Optional independent fact and evidence verification | P1 | Evidence verification · versioned source checks | P1 evidence | Independently checked claim links to a dated source; fabricated, conflicting or unavailable sources cannot earn verified status. |
| FR-021 | P1 | Route selectively by question type, cost, and model family | P1 | Routing policy · selected targets and cost limits | P1 providers | Route within applicable family/cost constraints with unchanged P0 run contract; reject ineligible fallback. |
| FR-022 | P1 | Continue, branch, or question one model from prior run | P1 | Run service · parent run and historical context | P1 runs | Branch to one target and keep parent originals; reject foreign-project parent. |
| FR-023 | P1 | Critic, debate, and adversarial review modes | P1 | Run service · labeled later rounds | P1 runs | Label critic/debate rounds independently of first round; prohibit later feedback in first-round inputs. |
| FR-024 | P1 | Memory Explorer and temporal/conflict views | P1 | Memory Explorer · historical revisions/conflicts | P1 memory | Open earlier approved state and sources; reject foreign source reference. |
| FR-025 | P1 | Document and web RAG with citations | P1 | RetrievalPort · versioned permitted document and web chunks | P1 retrieval | Cite exact document revision/span; exclude unauthorized or deleted chunks. |
| FR-026 | P1 | Secure remote access | P1 | Operations · private access and TLS | P1 operations | Remote authenticated browser can reopen history; external probe cannot access DB/admin and cleartext credentials. |
| FR-027 | P1 | Cross-language semantic/keyword retrieval | P1 | RetrievalPort · multilingual hybrid ranking | P1 retrieval | Find corresponding permitted Chinese/English passages; deny foreign and stale bilingual hits. |
| FR-028 | P2 | Scheduled/background activities and notifications | P2 | TaskPort · authorized scheduler, notifications | P2 tasks | Retry a scheduled job once across restart; revoked scope or duplicate effect is denied. |
| FR-029 | P2 | Browser, code, mail, or connector tools with approvals | P2 | Tool runtime · allowlists, isolated workers and owner approvals | P2 tools | Allow approved scoped action exactly as authorized; reject forged, expired or reused approval and disallowed destinations. |
| FR-030 | P2 | Multi-user or shared projects | P2 | AuthorizationPort · explicit sharing/workspace boundary | P2 identity | Share an explicitly authorized project; revocation denies nested data and export. |


## Non-functional catalogue

Source: v1.2 §3.2. The original quantitative targets apply to the phase listed here.

| ID | Source target | Proposed phase | Design and contract | Owning work | Cases and future gate |
|---|---|---|---|---|---|
| NFR-001 | Same code builds AMD64 and ARM64 containers; Compose deployment documented | P0 | Operations · local Compose and portable images | C-001, C-015 | P0-21 |
| NFR-002 | Committed messages/decisions survive normal container restarts | P0 | Repositories · Postgres restart and evidence invariants | C-002, C-013, C-015 | P0-14, P0-18 |
| NFR-003 | Initial targets: backup RPO ≤ 24 h, tested RTO ≤ 2 h | P0 | Operations · encrypted off-host backup and timed clean restore | C-015 | P0-18 |
| NFR-004 | Per-run, daily, monthly budgets and a hard stop; no unbounded fallback | P0 | BudgetPort · per-run/day/month reservations and hard stop | C-010 | P0-10 |
| NFR-005 | Provider-specific outbound permissions; sensitive content minimized/redacted | P0 | ContextPort/AuthorizationPort · per-target outbound policy | C-003, C-010 | P0-06, P0-09 |
| NFR-006 | HTTPS remotely, owner access control, secure cookies, CSRF consideration | P0 + P1 | P0 local sessions/cookies/CSRF; P1 private remote HTTPS | C-003, C-014; P1 operations | P0-02, P0-21. P1 refuses insecure remote login and verifies protected cookie delivery over TLS. |
| NFR-007 | Trace/run IDs, stage status, latency, model ID, usage, errors | P0 | Run/usage/audit records · redacted stage, latency, usage and error data | C-009, C-010, C-014 | P0-07, P0-15, P0-23 |
| NFR-008 | `/v1` and OpenAPI; additions within v1 are backward compatible | P0 | Versioned API, legacy responses, schema and client fixtures | C-004, C-014 | P0-19 |
| NFR-009 | Alembic migrations, pre-upgrade backup, rollback/restore procedures | P0 | Alembic · fresh, upgrade, pre-upgrade restore | C-002, C-015 | P0-18, P0-20 |
| NFR-010 | New provider/model requires no change to core memory or decision schema | P0 | ProviderPort · registry and adapter contract | C-006, C-007 | P0-22 |
| NFR-011 | Target ≥ 90% recall on curated critical facts; measured, not assumed | P1 | MemoryPort · versioned recall fixtures | P1 memory | Measure Recall@k on curated critical facts, with k and denominator fixed before evaluation; fail below 90% or on forbidden retrieval. |
| NFR-012 | Every adopted memory and final decision references at least one source | P0 + P1 | P0 decision/run/claim/response references; P1 adopted memory sources | C-011, C-013; P1 memory | P0-12, P0-13. P1 requires a resolvable source on each adopted revision and rejects orphan adoption. |
| NFR-013 | Cross-project retrieval respects owner and project ACLs | P0 + P1 | P0 scoped projects/messages and context; P1 same ACL for every index | C-003, C-005, C-010; P1 retrieval | P0-02, P0-09, P0-14. P1 injects a highly ranked foreign index hit and asserts zero leakage. |
| NFR-014 | Local non-LLM API P95 target < 500 ms; model execution remains async | P0 | Run service · async acceptance and bounded local queries | C-009, C-014 | P0-15 |
| NFR-015 | Accessible controls; UI can support multiple languages independently of English design docs | P0 | Workspace · keyboard, status/error announcements, Unicode and separable UI labels | C-012, C-014 | P0-16 |
| NFR-016 | Standard-format export includes original conversations, claims, memories, and decisions | P0 + P1 | P0 portable projects/history/originals/comparisons/decisions; P1 includes memory | C-015; P1 memory | P0-17, P0-18. P1 round-trips revisions; reject export of foreign or deleted memory. |


## Governance additions and release controls

These local IDs identify explicit v2.0 obligations with no separately numbered source row. Every row is proposed P0. Source sections refer to ADH-GOV-002. The case column supplies both positive and negative evidence.

| ID | Source | Obligation | Design and contract | Owning work | Cases |
|---|---|---|---|---|---|
| GOV-01 | §§3, 4.4 | Idempotent submission, conflicts and safe recovery | RunRepository, key fingerprint, attempt record and ledger | C-009, C-010 | P0-07, P0-08, P0-10 |
| GOV-02 | §§3, 4.4 | Deadline, cancellation, late manual inputs and publication policy | Run and target states; terminal report/version | C-008, C-009, C-011 | P0-05, P0-07, P0-12 |
| GOV-03 | §§3, 4.2 | Disable unsafe/unauthorized API dispatch; zero paid spend by default | Registry, AuthorizationPort, BudgetPort | C-006, C-007, C-010 | P0-04, P0-09, P0-10 |
| GOV-04 | §§4.1–4.4 | Canonical records survive workflow and provider replacement | PostgreSQL repositories, reference-only workflow and reserved future ports | C-002, C-007, C-009 | P0-14, P0-20, P0-22 |
| GOV-05 | §§5–8 | Reproducible isolated tests and cross-slice gates | Fake transport, schema checks, CI evidence, local deployment | C-001, C-004, C-014, C-015 | P0-19, P0-21, P0-24 |
| GOV-06 | §§3, 4.2 | Consequential operations leave immutable redacted audit evidence | Session, dispatch, usage, cancellation and decision audit | C-003, C-010, C-013, C-014 | P0-02, P0-10, P0-23 |

## Multi-agent extension catalogue

Source: v1.3 §6. P2 owner approval is required for every agent feature. Future pass/fail examples are admission criteria for the named domain. Only the selectable comparison capability in MA-FR-15 enters current delivery.

| Source ID | Original phase | Requirement | Candidate phase | Owning domain and future positive/negative acceptance |
|---|---|---|---|---|
| MA-FR-01 | Pilot | One owner-facing Chief of Staff accepts goals and provides status/results | P2 | Chief · Submit a bounded goal, read status/results; reject an unauthorized goal. |
| MA-FR-02 | Pilot | Agent registry stores versioned roles, skills, descriptions, and model requirements | P2 | AgentRegistryPort · Resolve an immutable role/skill version; reject activation of a mutable draft. |
| MA-FR-03 | Pilot | Chief routes complex requests to bounded specialist subgraphs | P2 | Delegation · Split a complex goal into bounded specialist tasks; forbid cyclic or above-ceiling delegation. |
| MA-FR-04 | Pilot | Task ledger records goal, subtasks, dependencies, owner, criteria, status and provenance | P2 | TaskPort · Restore goal, dependencies, owner, criteria and provenance; reject a dependency cycle. |
| MA-FR-05 | Pilot | Team execution can resume after process restart using checkpoints | P2 | Workflow · Resume after crash from durable checkpoints; replay cannot repeat completed effects. |
| MA-FR-06 | Later | Factory drafts new agent definitions based on a capability gap | P2 | Agent Factory · Create a capability-gap draft; draft creation cannot activate a role. |
| MA-FR-07 | Later | Factory runs sandboxed evaluations before activation | P2 | Evaluation · Activate only a passing, reviewed version; fail sandbox escape or missing eval. |
| MA-FR-08 | Pilot/later | Owner approval required to activate sensitive roles and grant tools/credentials | P2 | Approvals · Approve scoped sensitive activation; reject model-issued authorization or credential grant. |
| MA-FR-09 | Pilot | Each task has deadlines, max depth, max fanout, model-call budget and kill switch | P2 | Policy/Budget · Enforce kill, depth, fanout, deadline and aggregate caps; reject recursive bypass. |
| MA-FR-10 | Pilot | Agents share approved project data but cannot read all personal memory by default | P2 | ContextPort · Grant narrowly scoped project data; deny sibling or private owner memory. |
| MA-FR-11 | Pilot | Independent QA / evidence review before promoting an output to trusted artifact/decision | P2 | Evaluation · Obtain independent review linking artifact and evidence; block self-review or unsourced promotion. |
| MA-FR-12 | Engineering phase | Tool workers run in isolated workspaces with explicit network and filesystem policy | P2 | Tool runtime · Execute allowlisted job in isolated workspace; deny unauthorized network, host files or shell. |
| MA-FR-13 | Later | Agent dashboard shows org chart, live tasks, trace, budget, evaluations and approvals | P2 | Workspace · Show live authorized traces/tasks/budgets/approvals; deny cross-project dashboard data. |
| MA-FR-14 | Future | Remote third-party agents can be discovered through a future A2A adapter | P2 | RemoteAgentPort · Discover allowlisted remote agent; reject untrusted discovery or capability escalation. |
| MA-FR-15 | Every phase | Existing v1.2 comparison-only mode remains functional and selectable | P0 + P2 | P0 C-009, C-011, C-012, C-014 · P0-12, P0-24. P2 regression replays comparison without any task/agent services. |
