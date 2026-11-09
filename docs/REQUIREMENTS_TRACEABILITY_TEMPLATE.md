# Requirements Traceability Matrix — Template

> Populate one row for *every* existing FR and NFR from v1.2, all applicable proposals from v1.3/v1.4, and every approved new v2.0 requirement. Preserve old IDs and show any reclassification.

| Req ID | Source section | Requirement | Baseline priority | Approved phase | Design component | API/data | Task IDs | Positive test | Negative test | Status | Review evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| FR-003 | v1.2 §3.1 | Independent first-round requests | P0 | P0 | Run/Provider | POST /v1/runs; responses | C-009 | INT-FANOUT-001 | NEG-LEAK-001 | Proposed | TBD |
| FR-008 | v1.2 §3.1 | Cross-session retrieval | P0 | Split P0/P1 | Conversation/Context | Messages; MemoryPort reserved | C-005, P1 TBD | INT-HISTORY-001 | NEG-PROJECT-001 | Needs approval | TBD |
| FR-009 | v1.2 §3.1 | Six categories of memory | P0 | P1 | MemoryPort | P1 schema | P1 TBD | TBD | TBD | Deferred proposal | TBD |

## Coverage controls

1. No P0 requirements without a design component, owner task and executable acceptance evidence.
2. A requirement may be **split** across phases but not silently deleted; add child sub-IDs if needed.
3. Every negative/security case must be traceable to at least one requirement.
4. Every task must reference at least one requirement and at least one test (unless pure design task).
5. Freeze candidate must report `unmapped P0 = 0` and `blocking open issues = 0`.

## Conflict log — recommended format

| Conflict ID | Documents/IDs | Nature | Options | Recommended resolution | Owner decision | ADR | Status |
|---|---|---|---|---|---|---|---|
| CONF-001 | v1.2 FR-009–FR-011 vs updated P0 scope | Advanced memory was P0; now intended P1 | Build now / defer with ports | Defer implementation to P1, reserve port and canonical history | Pending | ADR-xxx | Open |
