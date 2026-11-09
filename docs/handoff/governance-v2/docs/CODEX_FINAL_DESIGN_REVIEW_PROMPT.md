# Codex kickoff: final design review, P0 rebaseline and freeze proposal

**Recommended execution:** GPT-6 Astra, High reasoning. Use a separate independent adversarial review, escalating to Extra High only for unresolved material issues. Do not implement product code during this review.

## Prompt to give Codex

> You are the Lead Solution Architect and Independent Design Reviewer for the Personal AI Decision Hub repository. Read the following complete source documents from the repo, plus root AGENTS.md:
>
> - English Requirements & Solution Architecture v1.2
> - Multi-Agent Organization Research v1.3
> - Multi-Agent Implementation Roadmap v1.4
> - `docs/IMPLEMENTATION_GOVERNANCE_AND_DESIGN_BASELINE_v2.0.md`
>
> **Business objective:** one question to multiple independent LLMs or manually imported chat answers; preserve originals; identify agreements, disagreements, supporting evidence, uncertainty and recommendations; user decides. Build P0 first. Future rich memory is P1; hierarchical agents, Agent Factory and tool execution are P2. Preserve P1/P2 adapter seams without implementing speculative future features.
>
> **Your task is DESIGN ONLY.**
>
> 1. Inventory and read the supplied files. List missing/ambiguous sources, unresolved research and version conflicts; cite exact sections or FR IDs.
> 2. Propose a requirements rebaseline and produce a complete requirement traceability matrix across every existing FR/NFR. Distinguish P0 scope, P1/P2 deferred work, and interfaces reserved now. Do not discard existing requirements.
> 3. Conduct a threat/security review and identify provider/API-access assumptions requiring verification.
> 4. Review modular monolith boundaries, project/owner isolation, canonical tables, LangGraph P0 run workflow, model identity, quotas, partial failures, comparison/report quality, and future memory/agent integration ports.
> 5. Finalize implementation-ready P0 OpenAPI, domain schemas, event/state transitions, DB migration plan, UI states and workflows, and concrete positive/negative test cases. Keep all architecture diagrams editable in Mermaid.
> 6. Produce/resolve Architecture Decision Records and a risk register with mitigation and escalation triggers.
> 7. Define a frozen baseline candidate with exact file paths/versions, semantic version policy and release acceptance gates.
> 8. Convert the approved scope into discrete implementation task cards with scope, non-scope, inputs, deliverables, acceptance criteria, constraints, dependencies, tests, integration impact and rollback. Ensure dependency graph has no cycles. Do not start feature implementation.
> 9. Run an adversarial second-pass review against the draft (independent reviewer/session where possible), a requirement-to-test coverage audit and OpenAPI/schema validation. Show remaining issues, explicitly marking release blockers.
>
> **Required deliverables**
> - `docs/requirements/traceability.md`
> - `docs/requirements/conflict-log.md`
> - `docs/architecture/baseline-v2.0.md` (Mermaid source embedded or linked)
> - `docs/adr/ADR-*.md`
> - `docs/api/openapi.yaml`
> - `docs/testing/test-matrix.md`
> - `tasks/TASK-*.md` plus dependency summary
> - `docs/G1_FREEZE_REVIEW.md` with exact scope, critical tradeoffs, unresolved issues and a proposed Git tag
>
> **Acceptance:** no unmapped P0 requirements; no unresolved blocking contradictions; each P0 endpoint has request/response/error contracts; each state transition has a test; every high-risk behavior has a negative test; P1/P2 additions must not force P0 core redesign; test and deployment steps are reproducible.
>
> Do **not** silently amend the current architecture or mark the freeze approved on your own. Return the freeze package and short owner decision checklist. No production implementation before the G1 approval.

## Second-pass independent review prompt

> Act as a skeptical architecture reviewer who did not write the design. Inspect the G1 freeze candidate and original v1.2/v1.3/v1.4 sources. Identify contradictory priorities, unimplementable contracts, hidden paid API assumptions, privacy leaks, incomplete state transitions, model identity errors, data loss, flaky test assumptions, incompatible database migrations, and speculative P1/P2 complexity. For each issue: severity, evidence, affected artifact, failure scenario, smallest corrective action, blocking/nonblocking verdict. Do not modify source files in this pass.

## After owner approval: model switch and implementation prompt

**Suggested execution:** available efficient coding model (GPT-5.6 Sol or GPT-6.1 Sol), Medium/High for bounded work.

> The design baseline is approved as `<git-tag-or-sha>`. Follow root AGENTS.md and the frozen baseline. Implement only task `<TASK-ID>` from `tasks/<TASK-ID>.md`. Inspect dependencies and current tests before modifying code. Make the smallest compatible change. Run unit and contract tests for touched components plus specified integration tests. Report exact commands/results, altered files, requirements verified, interface changes, risks and any Change Request. Do not expand scope, invent features, or rewrite architecture. If acceptance cannot be satisfied without a contract change, stop the affected task and propose a CR rather than silently changing it.

## Human approval boundary

The owner need only approve (a) P0 product scope, (b) major architectural tradeoffs, (c) external-spend/security permissions, (d) breaking-change exceptions, and (e) final release. Codex owns the detailed technical review and task planning; CI and automated tests provide evidence.
