# TASK-XXX — Short, testable title

| Field | Value |
|---|---|
| Status | Draft / Blocked / Ready / In progress / Review / Done |
| Milestone | P0-M0 through P0-M4 |
| Design baseline | ADH-v2.0@`<approved-git-tag-or-sha>` |
| Requirement IDs | FR-xxx, NFR-xxx |
| Responsible role | Coding Agent / Reviewer / Integrator |
| Dependencies | TASK-xxx IDs |
| Planned change surface | Specific files/modules |

## Business outcome

One observable result of this task. Avoid vague goals such as "improve architecture."

## Scope

- Explicit functions and user-visible behavior to implement.

## Out of scope

- Explicitly excluded behavior, especially adjacent P1/P2 capabilities.

## Inputs / prerequisites

- Approved API or schema section; fixtures, existing interfaces, prior tasks.

## Deliverables

- Source files, tests, migration/config/doc changes and commands.

## Acceptance criteria (verifiable)

1. Given [fixture/starting state], when [action], then [expected result].
2. Given [failure/edge case], when [action], then [safe observed outcome].
3. All listed requirements are covered by corresponding tests or verified inspection.

## Constraints and architectural invariants

- Allowed dependencies; no model/provider SDK in domain layer.
- No change to frozen API/schema without approved CR.
- No secrets in repository or logs; hard cost limits applied before dispatch.

## Test plan

| Type | Test/fixture | Expected result |
|---|---|---|
| Unit | | |
| Contract | | |
| Integration | | |
| Regression | | |
| Negative/security | | |

## Integration impact

Upstream/downstream consumers, events, data migrations, UI effects, feature flags and required release-slice retest.

## Rollback / recovery

Revert procedure; reversible migration or restore path; impact on durable data.

## Evidence of completion

- Commands and actual results; CI/build references; response examples; updated requirement traceability row.

## Exceptions / change requests

CR number or `none`; unresolved blocker and severity.

## Next eligible tasks

Tasks unblocked by this task's approval.
