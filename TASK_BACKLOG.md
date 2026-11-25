# Task backlog

**Next action: continue [C-009](tasks/TASK-C-009.md) from the validated lifecycle,
prepared-attempt, and post-claim recovery checkpoints. Recover prepared-but-unclaimed
attempts, then execute providers outside transactions and persist receipts/outcomes.**

November 25 checkpoint: `C-009 freeze ambiguous claimed dispatch` preserves current and
legacy claimed calls as unknown delivery without another send or released liability.
33 focused and 81 full PostgreSQL tests passed, alongside quality/contract/migration
gates and separate re-review. Details: [recovery evidence](docs/test-reports/C-009-post-claim-recovery.md).
Code commit `9bf741e` is remotely verified; hosted Workspace run 45724826439 passed
both jobs, including browser and recovery integration.
This is an in-progress checkpoint; the card count remains 9 of 15. The older summary
below describes the prior committed checkpoints; post-claim recovery is now delivered,
while provider execution, raw/late receipts, pre-claim recovery, synthesis and remaining
transition/release coverage still need implementation.

| Task | Status | Exit evidence / dependency |
|---|---|---|
| STATE-001 · recovery checkpoint | Complete in this commit | Three root records, updated AGENTS.md, archive comparison, ID coverage and task dependency audit. |
| G0-01 · targeted gap triage | Complete · [conflict log](docs/requirements/conflict-log.md) | For each open DB item cite surviving ADR/FR or precise source section, affected task/test, remaining decision and disposition. Write docs/requirements/conflict-log.md. |
| G0-02 · consolidate architecture | Design complete | docs/architecture/baseline-v2.0.md with modules/ports, scoped data, threats, migration, future seams and editable Mermaid. Build on six existing ADRs. |
| G0-03 · complete contracts | Design complete | docs/api/openapi.yaml, domain/event schemas and lifecycle/compatibility notes; run an OpenAPI validator and validate positive/negative fixtures. contracts/openapi.json describes the prototype only. |
| G0-04 · close test links | Design complete | Complete docs/testing/test-matrix.md, account for every P0 test referenced by traceability and all allowed and denied transitions; audit card links. |
| G0-05 · independent adversarial pass | Design complete | Fresh reviewer inspects versioned candidate, records severity, failure scenario and blocking verdict; resolve blockers and verify corrections. |
| G1 · freeze | Approved at g1-design-v2.0 | docs/G1_FREEZE_REVIEW.md, reviewed matrix, approved ADRs, validation evidence, exact approved SHA and annotated tag. |
| G2/G3 · implement and integrate | C-001 through C-008 and C-010 complete; C-009 in progress | Task evidence is in `docs/test-reports/`. The validated C-009 lifecycle foundation is not task completion. Continue its official fan-out/crash-recovery slice next and record every integration gate. |
| G4 · release | Pending integration and owner acceptance | End-to-end decision, privacy/budget/partial failure, portable export, encrypted restore and rollback evidence. |

Use the [15 implementation cards and dependency order](tasks/README.md) for P0. C-001 through C-008 and C-010 are complete and C-009 is in progress, so 9 of 15 cards are complete. Its checkpoints supply guarded durable lifecycle state, ordered events, fenced leases, manual parking, cancellation/deadline settlement, deterministic import collision handling, reservation-level one-send enforcement, and atomic grant-bound prepared attempts with exact frozen input. It does not yet supply provider execution, receipt/post-claim crash recovery, synthesis, full transition coverage, or reviewer sign-off. C-007's live-provider qualification remains a G4 owner-evidence gate and does not enable dispatch. The existing prototype must qualify against the same tests. Treat [the v1.2 sprint list](docs/requirements/tasks.md) and [the packaged draft backlog](tasks/P0_DELIVERY_BACKLOG.md) as historical inputs. Deferred P1/P2 work remains mapped in [traceability](docs/requirements/traceability.md); activate it only through a separate version decision.

When finishing a task, enter its result, evidence, blockers and next eligible task here or in the linked card, then update IMPLEMENTATION_STATUS.md. Keep DESIGN_BASELINE.md synchronized with gate and CR changes.

Owner review preparation complete. Review the [consolidated design and task list](docs/OWNER_DESIGN_REVIEW.md) before approving G1.
