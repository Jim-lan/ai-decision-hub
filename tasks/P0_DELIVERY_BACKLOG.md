# Proposed P0 Delivery Backlog and Dependency Order

**Status:** Draft, must be reviewed and expanded into individual task cards before G1 freeze.  
**Scope:** Core multiple-model comparison MVP, not complete long-term memory or hierarchical agent org.

```mermaid
flowchart LR
  D1[D-001 Source inventory] --> D2[D-002 Rebaseline]
  D2 --> D3[D-003 ADR / contract review]
  D3 --> D4[D-004 Freeze APIs/schema/tests]
  D4 --> D5[D-005 Task cards + G1]
  D5 --> C1[C-001 Scaffold]
  C1 --> C2[C-002 DB]
  C1 --> C4[C-004 CI]
  C2 --> C3[C-003 Auth]
  C2 --> C5[C-005 Conversations]
  C2 --> C6[C-006 Registry]
  C6 --> C7[C-007 API Provider]
  C5 --> C8[C-008 Manual Import]
  C7 --> C9[C-009 Fanout]
  C8 --> C9
  C9 --> C10[C-010 Budget/Idempotency]
  C9 --> C11[C-011 Consensus]
  C11 --> C12[C-012 UI]
  C12 --> C13[C-013 Decisions/History]
  C13 --> C14[C-014 E2E/Security]
  C10 --> C14
  C14 --> C15[C-015 Backup/Release]
```

| ID | Deliverable | Main dependency | Mandatory acceptance / integration evidence |
|---|---|---|---|
| D-001 | Source inventory + missing-content report | Supplied docs | All three source versions recognized |
| D-002 | FR/NFR traceability and P0/P1/P2 decisions | D-001 | No silently dropped FR IDs |
| D-003 | ADRs and component boundaries | D-002 | No cross-layer SDK leakage |
| D-004 | Frozen OpenAPI, schemas, workflow states, test fixtures | D-003 | Contracts validate; all P0 testable |
| D-005 | Task cards and G1 approval candidate | D-004 | DAG acyclic; owner-facing freeze checklist |
| C-001 | Frontend/backend baseline | D-005 | Local dev boot and smoke checks |
| C-002 | PostgreSQL + migrations | C-001 | Fresh/upgrade migration test passes |
| C-003 | Auth + scoped access | C-002 | Unauthorized access denied |
| C-004 | CI + fake providers | C-001 | Deterministic tests run in CI |
| C-005 | Projects/conversations/messages | C-002,C-003 | Reopen after restart; scoped history |
| C-006 | Provider/model identity registry | C-002 | Correct family and provenance flags |
| C-007 | First real permitted provider adapter | C-004,C-006 | Contract test plus opt-in smoke test |
| C-008 | Manual import adapter | C-005,C-006 | Imported answer is explicitly user-declared |
| C-009 | Independent fan-out + run persistence | C-007,C-008 | Partial failure, timeout and independence |
| C-010 | Budget, idempotency, outbound privacy | C-009,C-003 | Over-budget blocked, duplicate submit safe |
| C-011 | Consensus comparison | C-009 | Agreement/disagreement linked to raw response IDs |
| C-012 | UI results flow | C-011,C-005 | Ask -> responses -> comparison in browser |
| C-013 | Owner decision + history | C-012 | Decision persisted with run and rationale |
| C-014 | Integration/contract/security/E2E regression suite | C-010–C-013 | Requirement mapped tests passing |
| C-015 | Backup/restore, installation, rollback and release | C-014 | Fresh install and restored database pass smoke |

## Vertical release slices

- **Slice A:** project + one API provider + manual provider + raw responses, with real persistence.
- **Slice B:** independent fan-out + comparison report, partial result support, budget limit.
- **Slice C:** user decision saved + history reopen + e2e, auth and export.
- **Slice D:** backup/restore + release gate + known-limit documentation.

**Rule:** Run cross-feature integration tests at the end of **every** slice, not only at the final release. Produce a stable demo and report before beginning the next slice.
