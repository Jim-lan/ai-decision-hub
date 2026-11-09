# AI Decision Hub — Codex Governance Handoff v2.0

This package is the **third companion design/governance input**, not a replacement for the existing v1.2 requirements/architecture, v1.3 multi-agent research and v1.4 roadmap.

## Install into the existing Git repository

1. Place `AGENTS.md` at the repository root (`repo/AGENTS.md`). Review any existing root `AGENTS.md` and **merge rather than overwrite** incompatible guidance.
2. Copy `docs/IMPLEMENTATION_GOVERNANCE_AND_DESIGN_BASELINE_v2.0.md` and `docs/CODEX_FINAL_DESIGN_REVIEW_PROMPT.md` into `repo/docs/`.
3. Copy `docs/REQUIREMENTS_TRACEABILITY_TEMPLATE.md` to `repo/docs/requirements/` as a template; let Codex create the actual `traceability.md` and conflict log.
4. Copy `tasks/TASK_TEMPLATE.md` and `tasks/P0_DELIVERY_BACKLOG.md` into `repo/tasks/`.
5. Keep earlier English architecture documents under a clear versioned location, e.g. `repo/docs/source/v1.2/`, `v1.3/`, `v1.4/`.
6. Run the kickoff prompt with a high-reasoning Codex model **without product code changes**.
7. Approve the G1 freeze proposal before assigning bounded coding tickets to a more efficient coding model.

## Files

- `AGENTS.md` — permanent root-level Codex engineering instructions.
- `docs/IMPLEMENTATION_GOVERNANCE_AND_DESIGN_BASELINE_v2.0.md` — scope, governance, architecture invariants, tests, roadmap, freeze gates.
- `docs/CODEX_FINAL_DESIGN_REVIEW_PROMPT.md` — ready-to-paste kickoff, independent review, and implementation prompts.
- `docs/REQUIREMENTS_TRACEABILITY_TEMPLATE.md` — FR/NFR/test mapping format.
- `tasks/TASK_TEMPLATE.md` — executable unit of work format.
- `tasks/P0_DELIVERY_BACKLOG.md` — proposed task order and dependency Mermaid diagram.

## Critical distinction

This is a **proposed v2.0 design-governance baseline**. Codex must reconcile source documents, finalize contracts and submit G1 for owner approval. The architecture is not frozen merely because these files exist.

All project artifacts and Codex outputs must be in English. Future phases P1/P2 remain planned but do not block the P0 question-comparison MVP.
