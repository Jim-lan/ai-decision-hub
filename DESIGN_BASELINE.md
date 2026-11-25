# Design baseline register

**G1 approved by the project owner on November 9, 2026.** Annotated tag `g1-design-v2.0` points to `9edbcd4b9a142d107df219bc64bd6730b39689cd`. P0 delivers the local Decision Hub, P1 rich continuity and P2 the multi-agent platform. Changes to frozen scope or contracts follow the CR process.

The owner requested a working Decision Hub first, with manual import and Gemini as the first API candidate. P0 covers independent originals, evidence-aware comparison, explicit owner choice, same-project history, privacy, spending controls and local recovery. Rich memory and decision supersession are P1. The multi-agent organization is the next platform direction at P2. Its staged ledger, research pilot, registry, factory and remote protocols are described in v1.4 §11. The P0 release does not depend on those platform milestones.

## Authorities and inputs

- [Proposed governance](docs/IMPLEMENTATION_GOVERNANCE_AND_DESIGN_BASELINE_v2.0.md), [review prompt](docs/CODEX_FINAL_DESIGN_REVIEW_PROMPT.md) and [candidate requirement matrix](docs/requirements/traceability.md).
- [v1.2 architecture](docs/architecture/baseline-v1.2.md), [v1.3 research](docs/handoff/v1.4/baseline/v1.3_Multi_Agent_Organization_Research_EN.md), [v1.4 roadmap](docs/handoff/v1.4/AI_Decision_Hub_Multi_Agent_Implementation_Roadmap_v1.4_EN.md). Keep historical versions intact.
- Draft decisions [scope](docs/adr/ADR-201-scope.md), [storage](docs/adr/ADR-202-durability.md), [identity](docs/adr/ADR-203-providers.md), [policy and budgets](docs/adr/ADR-204-policy-budget.md), [report and decision](docs/adr/ADR-205-comparison.md), [recovery](docs/adr/ADR-206-operations.md).

The [G0-01 conflict log](docs/requirements/conflict-log.md) records the proposed disposition and verification obligations for each row.

The independent reviewer verified closure of the design blockers in [the freeze review](docs/G1_FREEZE_REVIEW.md). Product acceptance cases below belong to subsequent implementation gates.

## Conflict and decision index

| ID | Evidence and candidate resolution | Outstanding check |
|---|---|---|
| DB-01 | v1.2 FR-008–013 prioritizes rich memory; v2.0 §3 splits basic history/decision/context from P1 retrieval/revisions. v1.3 §6 and v1.4 M4–M9 introduce agent capabilities. Their future requirements remain in the matrix. | Audit phase/acceptance links, including MA-FR-15 comparison continuity. Do not repeat the catalog. |
| DB-02 | Historical /api/v1 in v1.4 §7 and the prototype /v1 routes differ. Governance §4 uses /v1. Existing prototype run status, target minimum and response shape need a compatibility decision. | Specify affected routes, old-data migration and exact polling/response/error contract. |
| DB-03 | Prototype calculates manual completion from target presence. G1 needs durable queued/running/manual/synthesis/terminal states, atomic cancellation, late imports, failure and restart behavior. | Specify terminal immutability, successor-run semantics, race ordering and tests for every transition. |
| DB-04 | ADR-204 reserves cost/quota before dispatch; the packaged draft backlog orders budgeting after fanout. Revised cards make C-010 a dependency of C-007 and C-009. | Demonstrate recovery from unknown external outcome without double billing or releasing the hold prematurely. |
| DB-05 | ADR-205 proposes deterministic local synthesis, explicit abstention and evidence-linked owner choice. | Define examples and minimum comparison quality. Reconcile required versus optional rationale in ADR, task and API. |
| DB-06 | ADR-206 separates portable export/import from full encrypted recovery. Prototype storage predates G1. | Specify sensitive field exclusions, restore isolation, session invalidation, rollback, and measurable recovery gate. |
| DB-07 | Gemini is a candidate. Permitted account, capped price/quota and privacy conditions remain unverified. | Block live activation until verified. This does not block offline design or tests. |

New features enter the queue as a proposal with phase, affected FRs, alternatives, migration impact and tests. After freeze preserve the prior tag and record the approved CR and successor revision.

The [owner review packet](docs/OWNER_DESIGN_REVIEW.md) consolidates the candidate and dated research. C-007, C-010 and C-011 carry the resulting qualification cases.

## Implementation alignment

C-009 post-claim recovery alignment, November 25, 2026: forward revision
`0010_post_claim_recovery` and atomic claim/attempt writes implement the existing
DB-03/DB-04 obligations. Recovery relies on durable claims, fences stale workers,
preserves uncertain budget holds, and does not retry ambiguous delivery. No frozen
public contract or phase boundary changes. The full C-009 lifecycle gate remains open;
see `docs/test-reports/C-009-post-claim-recovery.md`. No CR is required.

November 25, 2026: the owner explicitly requested public GitHub visibility for
Jim-lan/ai-decision-hub. The repository was changed to public and anonymous API access
verified. This is source distribution only; it does not deploy the application, expose
runtime data or credentials, or alter the G1 product architecture or P0/P1/P2 scope.
No design exception is required for this operational owner instruction.

C-002 adopted the prototype database through forward migration `0003_storage_contract` on November 10, 2026. The implementation adds the frozen same-scope relational invariants and append-only evidence enforcement, and removes the inherited pgvector requirement from greenfield migration while preserving existing installed extensions. No public contract changed and no Change Request was opened. Lifecycle expansion, audit metadata, export, and recovery remain with their assigned later cards; the G1 tag and P0/P1/P2 phase boundaries are unchanged.

C-003 adopted the owner-security boundary through forward migration `0004_security_audit` on November 10, 2026. The implementation preserves the frozen single-owner, local-only identity model while adding hashed expiring sessions, revocation, exact-origin state-change checks, durable login throttling, owner/project-scoped authorization, typed audit actions/outcomes, schema-versioned audit rows, and database enforcement against update, delete, truncate, or new legacy-format inserts. Existing unambiguous audit rows are upgraded; ambiguous historical rows remain explicitly `schema_version=0` with `outcome=unknown`. Sanitized failures expose and log only a trace identifier and roll back the request transaction. No public contract or phase boundary changed and no Change Request was opened. Portable export redaction and later cross-feature authorization assertions remain with C-015 and their named integration cards.

C-004 adopted the frozen transport-neutral ProviderPort types and deterministic verification obligations on November 12, 2026. Pinned offline CI gates now validate the typed boundary, vendor-import isolation, candidate/runtime OpenAPI documents and response fixtures, domain fixtures, requirement links, migrations, PostgreSQL integration, browser smoke, and recovery. Successful results preserve nullable unknown provenance/usage; a known returned identity outside the immutable request allowlist normalizes to `invalid_response`; timeouts are deterministic. Test execution denies external network egress except the test database and loopback servers. This is contract and test infrastructure only: no provider adapter, outbound dispatch, public API, storage schema, phase boundary, or live-provider entitlement changed, so no Change Request was opened.

C-005 adopted the prototype workspace through the frozen ConversationRepository boundary on November 13, 2026. The PostgreSQL adapter preserves exact immutable messages and stable sequence pages, while the existing frozen project-history route now performs bounded same-project literal search with stable source identifiers. Project/query/keyset cursors are authenticated with a dedicated durable secret and fail closed when modified, malformed, stale, or used across projects. Query and Referer values are excluded from proxy access logs. Decision search remains assigned to C-013, and P1 semantic memory remains deferred. No storage migration, frozen public-contract change, or phase-boundary change occurred, so no Change Request was opened.

C-006 adopted the frozen provider registry and identity contracts on November 13, 2026. Forward revisions `0005_provider_identity` and `0006_identity_constraints` preserve raw historical evidence, label unavailable historical registry state as unknown, snapshot new target identity and policy metadata immutably, and leave unresolved identity and measured usage null. Distinct-family confirmation requires included official API evidence with attributable provider-reported resolution; manual, dynamic-unknown, sentinel, and late-excluded inputs cannot inflate the count. Gemini is recorded only as a disabled unverified candidate with blocked privacy and unknown pricing. Adapter dispatch, entitlement, budget admission, manual replay, and comparison use remain with their assigned later cards. This implements the existing frozen contract and phase boundaries, so no Change Request was opened.

C-010 adopted the frozen context, replay, budget, and dispatch-authorization contracts on November 13, 2026. Revision `0007_context_budget` keeps prior run requests as explicit schema version 0, writes canonical normalized version-1 requests, and preserves old-writer compatibility during migrate-before-switch deployment. Prepared context is destination-specific and immutable: it binds the canonical question, exact ordered selected sources, current explicit release/redaction rules, sanitized bytes, policy version, bounds, omissions, and digest without claiming those bytes were transmitted. Conservative reservations serialize owner and provider-account exposure, use UTC owner periods and IANA provider periods, reprice and recheck current consent/caps/quota after critical locks, and authorize a single durable claim. A claim is held as unknown delivery before network execution, so crashes and period resets cannot release or duplicate exposure. Actual transmission snapshots and worker ordering remain C-009; provider adapter qualification remains C-007. The implementation does not enable Gemini or change any phase boundary, so no Change Request was opened.

C-007 adopted the frozen provider-adapter seam on November 14, 2026 without activating Gemini. The pinned official SDK remains inside infrastructure, and every invocation requires a current paid no-training qualification plus a matching C-010 one-shot claim committed as a held liability before transport. The transport pins the stable official host and version, disables redirects, environment routing, SDK retries, continuation, automatic function calls, and response storage, and permits only one request. Missing returned identity remains unknown, incomplete usage remains null, and every raw receipt is exposed to C-009 before identity validation. The registry candidate remains disabled with pricing unknown and privacy blocked until the owner supplies and approves current project, tier, region, model, quota, tariff, spend-policy, credential, and non-sensitive live-smoke evidence. This follows the existing frozen contract and DB-07 disposition; no public contract, migration, phase boundary, or Change Request changed.

C-008 adopted the frozen manual-original seam on November 14, 2026. RunRepository now
separates the application route from PostgreSQL locking and persistence. Imports are
owner scoped, lock run before target, prove manual eligibility before replay, preserve
the exact submitted bytes and digest, and record app/model provenance only as
user-declared while leaving unavailable provider resolution and measurements null.
Exact concurrent replay is stable and audit-idempotent; changed evidence, official
targets, foreign scope, and fresh post-deadline writes fail closed. The generated 201
response now uses the canonical OriginalDetails contract. Existing schema fields were
sufficient, so no migration, phase-boundary change, or Change Request was required.
The durable lifecycle and terminal/synthesis freeze remain assigned to C-009 under
DB-03; C-008 does not claim that cross-state behavior complete.
