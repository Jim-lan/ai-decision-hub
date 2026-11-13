# Task backlog

**Next action: implement [C-005](tasks/TASK-C-005.md) under the approved freeze. C-006 is independently eligible after C-004.**

| Task | Status | Exit evidence / dependency |
|---|---|---|
| STATE-001 · recovery checkpoint | Complete in this commit | Three root records, updated AGENTS.md, archive comparison, ID coverage and task dependency audit. |
| G0-01 · targeted gap triage | Complete · [conflict log](docs/requirements/conflict-log.md) | For each open DB item cite surviving ADR/FR or precise source section, affected task/test, remaining decision and disposition. Write docs/requirements/conflict-log.md. |
| G0-02 · consolidate architecture | Design complete | docs/architecture/baseline-v2.0.md with modules/ports, scoped data, threats, migration, future seams and editable Mermaid. Build on six existing ADRs. |
| G0-03 · complete contracts | Design complete | docs/api/openapi.yaml, domain/event schemas and lifecycle/compatibility notes; run an OpenAPI validator and validate positive/negative fixtures. contracts/openapi.json describes the prototype only. |
| G0-04 · close test links | Design complete | Complete docs/testing/test-matrix.md, account for every P0 test referenced by traceability and all allowed and denied transitions; audit card links. |
| G0-05 · independent adversarial pass | Design complete | Fresh reviewer inspects versioned candidate, records severity, failure scenario and blocking verdict; resolve blockers and verify corrections. |
| G1 · freeze | Approved at g1-design-v2.0 | docs/G1_FREEZE_REVIEW.md, reviewed matrix, approved ADRs, validation evidence, exact approved SHA and annotated tag. |
| G2/G3 · implement and integrate | C-001 through C-004 complete | Task evidence is in `docs/test-reports/`. Implement C-005 next; C-006 is independently eligible. Record tests and integration gate at every slice. |
| G4 · release | Pending integration and owner acceptance | End-to-end decision, privacy/budget/partial failure, portable export, encrypted restore and rollback evidence. |

Use the [15 implementation cards and dependency order](tasks/README.md) for P0. C-001 through C-004 are complete; C-005 is next and C-006 is independently eligible, so 4 of 15 cards are complete. The existing prototype must qualify against the same tests. Treat [the v1.2 sprint list](docs/requirements/tasks.md) and [the packaged draft backlog](tasks/P0_DELIVERY_BACKLOG.md) as historical inputs. Deferred P1/P2 work remains mapped in [traceability](docs/requirements/traceability.md); activate it only through a separate version decision.

When finishing a task, enter its result, evidence, blockers and next eligible task here or in the linked card, then update IMPLEMENTATION_STATUS.md. Keep DESIGN_BASELINE.md synchronized with gate and CR changes.

Owner review preparation complete. Review the [consolidated design and task list](docs/OWNER_DESIGN_REVIEW.md) before approving G1.
