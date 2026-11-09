# P0 execution order

Each C-number links to one implementation card. Every card resolves its baseline to the annotated g1-design-v2.0 tag before work begins. Record the resolved commit and card ID in the implementation evidence. Earlier prototype files must pass the same acceptance checks when adopted. The draft backlog shipped in the package is a review input.

| Sequence | Tasks | Integration checkpoint |
|---|---|---|
| Foundation | [C-001](TASK-C-001.md), [C-002](TASK-C-002.md), [C-003](TASK-C-003.md), [C-004](TASK-C-004.md) | Fresh and upgrade migrations, local HTTP smoke, secret rejection and deterministic CI |
| Protected inputs | [C-005](TASK-C-005.md), [C-006](TASK-C-006.md), [C-010](TASK-C-010.md) | Scope, bounded context, concurrent budget reservations, duplicate key and redaction before dispatch |
| Slice A | [C-007](TASK-C-007.md), [C-008](TASK-C-008.md), [C-009](TASK-C-009.md) | API and manual target share a run. Verify partial success, timeout, restart and traceable originals. Record the optional live qualification separately. |
| Slice B | [C-011](TASK-C-011.md), [C-012](TASK-C-012.md) | End-to-end comparison, raw evidence, uncertainty, cancellation, mobile and keyboard workflow |
| Slice C | [C-013](TASK-C-013.md), [C-014](TASK-C-014.md) | Explicit decision, reopened history and fault-injection regression evidence |
| Slice D | [C-015](TASK-C-015.md) | Portable export/import, encrypted restore, release/rollback rehearsal and G4 acceptance |

C-007 may deliver a disabled adapter with deterministic contract evidence while account qualification is pending. C-009 may proceed against its merged fake transport. A G4 claim of an operational real provider requires a permitted live success and dated evidence. The technical tests never imply permission for external spend.
