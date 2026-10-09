# Prior Art (updated 2026-10-01; detail in sota/02, sota/01)

## Claim-element overlap

| Element | Closest prior art | Overlap |
|---|---|---|
| E1 Persistent reality model | Assay (module Merkle cones), roam-code (SQLite code graph), archagent, Greptile/Qodo graph review | High for module-level; typed claim-facing model not found |
| E2 Snapshot-bound evidence reuse | **Assay** (assertion build cache), **EA-Graph**, Aga, Receipts, Looping-Is-Not-Reliability | **Very high** |
| E3 Claim–reality reconciliation | backcheck, agent-receipts, claimcheck, StateProof, agent-claim-verifier, claim-verifier, Praxen, EBTE | **Very high** for claim↔evidence verdicts |
| E4 Counter-reality search | Counterfactual/abductive explanation (classifiers), CFC (tabular), SWE-ABS, BMC-Agent, Assurance 2.0 defeaters | Shape and pieces exist; combined SE-agent form not found |
| E5 Decision-sensitivity filter | Pivotal-vote analysis (2608.06940), Planfence frontier, CFC margin | Partial; suppression by decision flip not found |
| E6 Plain-language approval semantics | US12688261 (scoped, human-readable authorization; assignee unverified), AGT/AgentCore permission UX | Medium; reconciliation-based explanation not found |
| Independence typing | Statistical after-the-fact (judge-correlation); Assay role separation; 2608.29912 labelling | Structural vector not found; N-version/common-cause literature unsearched |

## Patents (sample only; **database search not possible with available tools**)
- US12450494B1 Citibank — validating agent actions with generative AI (gap check on proposed actions) [read]
- US20250335185A1 Capital One — impact-scaled AI code review [read]
- US20230370274A1 / US12192372B2 Credo AI — hash/sign provenance of AI assessments [read]
- US12688261 — scoped human-readable tool-invocation authorization (assignee unverified) [snippet]
- US12563045 — ledger-anchored snapshot of agent state/decisions [snippet]
- US12547703 — agent runtime [snippet]

No patent found on claim-vs-state verdicts, cross-agent snapshot-bound reuse, or decision-flip counter-state enumeration. **This is a weak negative, not clearance.** Manual queries and CPC classes: `sota/02_patents_commercial.md` §A.2. A registered practitioner should run a prior-art/FTO search before any public novelty statement. Large banks are filing around agent validation and AI code review, so the area is actively patented.

## Source-status caveat
Only EA-Graph, ClaimReceipt (PDF), Assay and 2608.29912 were read as extracted full text. Other items are page/abstract-level via a summarizing fetch tool; some are snippet-only. Not paper-ready.
