# Run and target transitions

Use the run row lock, expected revision and worker fence for every transition. Write state, monotonic event sequence, raw receipt or report and accounting intent in the same transaction as applicable. A poll reads committed events. On simultaneous commands the first valid transaction wins. Check the deadline under lock. Existing identical idempotent requests can replay their recorded result after a deadline. Fresh manual submissions at or after it fail. Each table row is a parameterized contract test for each listed source/destination. Test every other ordered state pair for rejection with zero changes. A retry of an identical command returns the existing result without another event.

| Case | From | To | Trigger and expected observation |
|---|---|---|---|
| S01 | absent | queued | Commit admission, reservations, question and work together |
| S02 | queued | running | Fenced worker claims work |
| S03 | queued | cancelled | Owner cancels before dispatch |
| S04 | queued | failed | Deadline with zero accepted originals |
| S05 | running | awaiting_manual | Only pending manual slots remain |
| S06 | running | synthesizing | At least one original available and all slots settled or deadline reached |
| S07 | running | failed | No usable original after all slots settle |
| S08 | running | cancelled | Owner wins cancellation lock |
| S09 | awaiting_manual | synthesizing | Last import or deadline, at least one original |
| S10 | awaiting_manual | failed | Deadline with zero originals |
| S11 | awaiting_manual | cancelled | Owner cancels |
| S12 | synthesizing | completed | Publish version 1 with all targets successful |
| S13 | synthesizing | completed_partial | Publish version 1 with missing or unsuccessful targets |
| S14 | synthesizing | failed | Bounded synthesis recovery exhausted; originals remain readable |
| S15 | synthesizing | cancelled | Cancellation wins before atomic publication |

| Case | From | To | Trigger |
|---|---|---|---|
| T01 | absent | pending | Register API target |
| T02 | absent | awaiting_manual | Register manual target |
| T03 | pending | in_flight | Commit attempt and bounded reservation before transport |
| T04 | pending | blocked | Policy, budget or eligibility changed |
| T05 | pending | timed_out | Deadline before send |
| T06 | pending | cancelled | Cancel before send |
| T07 | in_flight | succeeded | Persist original and settle known usage |
| T08 | in_flight | failed | Definitive failure |
| T09 | in_flight | delivery_unknown | Ambiguous send, timeout or worker crash; preserve hold |
| T10 | in_flight | timed_out | Definitively expired attempt; reconcile only verified billing |
| T11 | in_flight | cancelled | Best-effort interruption; retain any uncertain liability |
| T12 | awaiting_manual | succeeded | Atomic exact-text import for selected target |
| T13 | awaiting_manual | timed_out | Deadline settles slot |
| T14 | awaiting_manual | cancelled | Owner cancels |

Close admission to new receipts when entering synthesis. Persist late API evidence with its excluded disposition and reconcile known charges even after terminal state. A new comparison after the deadline is a new run and key. Publication references an immutable set of input IDs. Terminal runs retain the original report. Resume synthesis from these IDs. Retrying a safe transport attempt creates a fenced attempt under the same target with the same immutable approved bytes and valid reservation. No automatic retry follows ambiguous delivery.

On deadline, lock the run and settle every open target before freezing input IDs. Pending and awaiting_manual expire to timed_out. In-flight attempts with uncertain delivery settle to delivery_unknown and retain their holds. A queued run with an already imported answer advances via S02 without dispatch, then S06 under the same lock. For safe bounded retries the target stays in_flight while new attempt records are appended. Commit T08 only when a definitive failure ends all retries. On cancellation settle every open target as cancelled and preserve outstanding liabilities. Late receipts cannot change terminal states.
