# ADR-205 · Evidence-linked reports are derived; decisions belong to the owner

**Status:** Approved under g1-design-v2.0. **Sources:** Governance §3–4; v1.2 FR-005, FR-006, FR-012, NFR-012, §7.3, §8.3.

**Decision.** Use a local ConsensusPort for P0. Validate stable response references and exact source text for every extracted position and comparison finding. Present meaningful overlap, opposing positions, minority views, missing support, uncertainty and conditional next steps, including a justified abstention where warranted. A provider's citation is a claim of support, not an independent check. Render missing answers and context differences. Persist an immutable report version and exact inputs. The owner's separate decision links back to evidence and, if supplied, rationale. Do not write claims to memory or silently adopt the recommendation.

**Alternatives.** A paid remote judge would require explicit permission to disclose multiple providers' answers and reserve another call; P0 must work entirely offline with pasted originals. A majority counter over app names misreports correlated answers. A screen that only lists originals does not satisfy the comparison requirement.

**Cost and trigger.** Local analysis can miss paraphrase, irony and novel semantic contradictions. Abstain on unsupported classifications rather than defaulting to agreement. Require mixed, contrary, paraphrased, cited, uncited and single-success fixture review before release. If the local comparator cannot pass FR-006 quality gates, block release and propose a scoped alternative under a CR; never invoke a remote judge implicitly.
