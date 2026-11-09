# AGENTS.md — Personal AI Decision Hub

> Repository-wide engineering instructions for Codex and other coding agents.
> Baseline: Governance v2.0, proposed until Gate G1 is approved. Language: English only.
> This file belongs at the Git repository root. Do not put it inside `docs/`.

## 1. Mission and priority

Build the smallest reliable personal AI Decision Hub that accepts a question once, sends it to selected independent LLM providers or accepts manual responses, preserves original answers, generates an evidence-aware comparison, and lets the owner make the final decision.

Deliver **P0** before implementing P1 or P2. Preserve clear extension seams for them, but do not implement speculative functionality:
- **P0 / Core Decision Hub:** provider registry; multiple independent model responses; manual import; comparison; conversation/run persistence; basic project-scoped history; minimal identity, privacy and budget safeguards; automated tests and local Docker deployment.
- **P1 / Rich continuity:** structured long-term memory, memory curator, vector retrieval, richer decision management, advanced validation and context retrieval.
- **P2 / Agent organization:** Chief of Staff, task ledger, Agent Registry, Skills, Agent Factory, hierarchical teams, remote tools and protocols.

Do not equate an AI app with an independent model. Record requested and resolved provider/model identity and label unknown provenance. Do not silently rely on consumer-chat subscriptions for API access.

## 2. Canonical repository documents and authority

Read in this order for relevant tasks:
1. `docs/IMPLEMENTATION_GOVERNANCE_AND_DESIGN_BASELINE_v2.0.md` (scope rules, gates, release policies).
2. `docs/baseline/` or `docs/architecture/` **approved frozen baseline** (when Gate G1 publishes it).
3. `docs/requirements/traceability.md` and signed ADRs.
4. `docs/api/openapi.yaml`, migration files, approved interface contracts.
5. The individual `tasks/TASK-*.md` assigned to this run.
6. Archived v1.2 architecture, v1.3 multi-agent research, v1.4 roadmap as historical inputs, not concurrent conflicting authority.

Until the baseline is approved, **do not code product features**. Perform the requested design review/reconciliation instead. If the files above are not yet in the repository, produce a missing-artifacts report rather than inventing their contents.

A direct current user request may supersede these repository instructions; otherwise resolve conflicts by the precedence above. Never resolve conflicting requirements by guessing. Log blockers with exact document sections and proposed resolution.

## 3. Design freeze and change management

- **G0: Review** — compare source documents, identify conflicts, trace requirements, settle MVP scope, design ports/contracts, define architecture decision records (ADRs).
- **G1: Freeze** — owner approves a tagged, versioned architecture baseline, signed traceability matrix, test plan and ordered task backlog. Record baseline commit/tag/hash in every task.
- **G2: Implement** — deliver one scoped task at a time. No architectural rewrites, cross-boundary shortcuts, extra frameworks or unrelated refactors.
- **G3: Integrate** — merge only on passing unit, contract, migration, security and relevant cross-component tests.
- **G4: Release** — prove end-to-end use case, restore, partial failure, privacy, quota and rollback procedures.

After G1, architecture is frozen by default. An exception is permitted only for a proven security issue, impossible contract, unacceptable data-loss behavior, release-blocking defect, or explicit new owner requirement. Open a Change Request (CR) with evidence, affected FRs, alternatives, backward-compatibility plan and updated tests. Pause only affected tasks. **Do not quietly change the baseline**.

## 4. Architectural boundaries (mandatory)

Use a modular monolith with explicit domain ports/adapters: `HTTP/UI -> application use cases -> domain ports <- infrastructure adapters`. Keep the core data model independent from model SDKs and LangGraph internals.

Canonical data remains owned by our database: projects, conversations, messages, runs, model responses, comparisons, decisions and audit records. LangGraph checkpoints are workflow execution state, **not** the source of truth. Store raw model responses immutably (subject to privacy/retention controls). Do not promote model claims into user facts automatically.

Required seams: `ProviderPort`, `ConsensusPort`, `ConversationRepository`, `RunRepository`, `ContextPort`, `AuthorizationPort`, `BudgetPort`; reserve optional `MemoryPort`, `TaskPort`, `AgentRegistryPort`, `RemoteAgentPort` interfaces without building their P1/P2 functionality.

Never send one provider's independent first-round answer to another first-round provider. Do not claim all models saw identical context if provider-specific redaction differed.

## 5. Coding task contract

Every task must have: ID; requirement IDs; baseline version; milestone; scope and non-scope; inputs/dependencies; exact deliverables; acceptance criteria; test evidence; constraints; integration impact; rollback notes; task owner; status. Use `tasks/TASK_TEMPLATE.md`.

At start: inspect relevant current code, docs and tests; verify assumptions and dependencies. At finish: provide files changed, contract/schema changes, commands run and outcomes, coverage evidence, known limitations, and any proposed change requests.

Implementation must be small and testable. Never represent unrun tests as passing. Do not declare completion based only on generated code or plausible narrative.

## 6. Tests and integration discipline

Each task: isolated unit tests and relevant contract tests. Each feature merge: component integration tests and type/lint checks. Each completed vertical slice/milestone: real Postgres and mock-provider integration, database migration checks, partial-failure checks and UI/API smoke tests. Each P0 release candidate: end-to-end comparison, history persistence, idempotency, auth/privacy, cost limits, backup/restore and rollback rehearsal.

Use deterministic fake model providers in CI; optional live-provider smoke tests only via explicit opt-in, minimum quota and non-sensitive fixtures. Track tests against requirements, not just code modules. Preserve evidence in CI artifacts and `docs/test-reports/`.

## 7. Provider/API, privacy, and cost rules

- Prefer official provider APIs and documented adapters. Manual import is a first-class P0 path.
- Unknown/dynamic underlying models are labeled unknown, never counted as independent confirmations without provenance.
- Keep all credentials out of git, logs, prompts, exceptions and exports; commit `.env.example` only.
- Authorization, context filtering and budget rejection occur before requests are dispatched; permit partial results.
- Use request idempotency and record resolved model, elapsed time, usage, response status and retry attempt; avoid retrying non-idempotent operations blindly.
- No arbitrary external tool writes, browser automation of consumer chats, or autonomous Agent Factory in P0.

## 8. Documentation, model usage, and review

All project design documents, diagrams, code comments, API descriptions, task cards and implementation summaries MUST be in English. Keep editable Mermaid source with architectural documents; regenerate derived images/Word only when needed.

Recommended human-selected workflow: use a high-reasoning model for architecture/traceability/freeze reviews; a more efficient coding model for small fixed-contract implementation tasks; escalate ambiguous defects or security concerns for targeted higher-reasoning review. Do not rely on model names or usage allowances as executable requirements; these can change.

Codex can perform the review and prepare the freeze package; **the owner approves the business scope and any material architecture exception**. A review by the same model that wrote the design is not equivalent to independent verification: run a distinct adversarial review and automated contract checks.

## 9. Standard completion response

Return: `Task ID / baseline / status`, `Changes`, `Tests executed + outcomes`, `Requirements verified`, `Integration impact`, `Risks or blockers`, `Next eligible tasks`. Never start the next unrelated coding ticket without an explicit task assignment or an approved execution plan covering it.

## 10. Persistent project state

At session start, and on recovery after a usage limit, context compaction or model change, read this file, then IMPLEMENTATION_STATUS.md, DESIGN_BASELINE.md and TASK_BACKLOG.md at the repository root. Compare the recorded revision to git log, git status and the actual files. Resolve drift before starting work. These indexes describe progress; only the approved Git baseline governs frozen design.

At the end of every task or milestone update the affected root records with the task ID, actual evidence and commands, remaining work, gate/approval state and next eligible task. Commit validated changes and their state update together. Record the completed commit by task ID/message or previous SHA to avoid self-referential hashes. Push the checkpoint to the existing private remote and verify its SHA before reporting remote recovery.

On Astra resumption, start with the open question IDs in DESIGN_BASELINE.md and missing deliverables in TASK_BACKLOG.md. First identify which gaps remain. Read only relevant source sections for those gaps. Reopen completed analysis only for a named contradiction, changed requirement or failed check. For each new feature, record phase, affected requirements/contracts/tests and CR disposition before changing frozen behavior.
