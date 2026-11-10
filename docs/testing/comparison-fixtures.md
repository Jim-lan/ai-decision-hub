# Acceptance examples for the local comparator

These synthetic fixtures exercise FR-006 and P0-12. Use immutable response IDs and exact excerpts for all positions. The examples define expected meaning. A passing implementation can use different wording. Review each expected relation, including abstention, independently of presentation.

| Example | Immutable input | Expected report | Failing outcome |
|---|---|---|---|
| Agreement with a condition | A: “Choose local storage if offline access is required.” B: “When offline access is required, choose local storage.” | Attribute the same conditional position to A and B. Preserve the offline condition and cite both excerpts. | Reports unconditional agreement on local storage. |
| Explicit opposition | A: “Use cloud storage for this project.” B: “Avoid cloud storage for this project.” | Surface opposing positions on the same project and cite the respective excerpts. | Treats token overlap as agreement. |
| Minority and correlation | A and B are verified aliases of family F, both asserting “Choose cloud.” C from distinct family G says “Choose local.” | Show all three originals, two attributable families, and C's dissent. | Attributes two independent votes to F or suppresses C. |
| Missing and unknown | A is manual with unknown family and cites a URL. B timed out. | Show one declared answer, one missing target, unknown independence and a supplied citation of unverified quality. Abstain on agreement. | Fabricates B's position or marks the URL independently verified. |
| Incomparable questions | A received a permitted cost constraint; B's projection omitted it. Each chooses a different option. | Describe the positions and context difference. Attribution of disagreement to model capability is unsupported. | Claims identical experimental conditions. |
| Unrelated evidence | A discusses latency. B discusses contract duration. Neither recommends an option. | Separate concerns, identify uncertainty and abstain from a specific choice. | Invents shared support or a preferred option. |

All six cases must meet their expected outcomes and produce zero invented citations. A local comparison that cannot establish a relation explicitly may report uncertainty in the ambiguous examples. It must still detect the controlled agreement and opposition examples. Persisting a report never records an owner decision. C-011 owns the comparison fixtures. C-014 repeats them at integration and verifies that each cited excerpt resolves to the same original after restart.
