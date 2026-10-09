# Direction chosen after a gap search (2026-10-09)

**Instruction from the project owner:** do not build what other papers already claim; find something unexplored and build the solution around it.

## Method
Generate problems from what Agentvow can uniquely observe, search for prior art on each, keep only what comes back thin. Absence in a web search is **not** proof of absence; every conclusion below is "no close match found in a limited search" (snippet/abstract level unless marked).

## Families searched and what was found
| Family | Closest prior work | Verdict |
|---|---|---|
| Forecast consequences of an edit, with counterfactual pairs | Software world models (2606.27406), SURGE, ThrowBench, Agent Retrieval Bench edit2ripple, SWE-Touch | Neighbours cover pieces; the paired-intervention forecast test looks open, but the idea is an extension of existing benchmark styles. Kept as a possible later paper. |
| Reverse direction: does the report disclose what the diff did | Kraishan & Jitkajornwanich 2609.12205 (self-reports mention ~1 in 11 actions; 5,851 sessions) | **Taken.** |
| Staleness of verified claims over time | EA-Graph (artifact-anchored verification memory), truth-mcp, ProofRun | **Taken.** |
| Does a visible verifier change what agents report (observer effects) | Hawthorne effect in reasoning models (2505.14617), "Noticing the Watcher", Kale et al., SchemeArena, StealthEval | General phenomenon well studied; the coding-agent claim-verifier case with announced/covert/feedback arms looks open. Runner-up. |
| Real-PR claim accuracy, omission, tampering | Gong et al. 2601.04886, Ogenrwot & Businge, "All Smoke, No Alarm", LessWrong misalignment-in-the-wild | Crowded. |
| Abstention-aware evaluation of verifiers | Selective labels, counterfactual comparison of abstaining classifiers, HALLMARK | Method exists; application is incremental. |
| **Agent-declared preconditions of a success claim, replayed independently** | reproducible-trajectories (byte-identical command replay), ProofRun receipts, Repo2Run/EnvBench (a *separate* agent builds the environment), dependency-gap-validation write-ups (13.5x expansion claim, secondary) | **No close match found** for: the *task agent itself declares* the conditions under which its claim holds; an independent clean-room replay tests **sufficiency** of the declaration; ablation tests its **necessity/honesty**; and the gap is measured as a property of the agent. Chosen. |

## The idea: claims with preconditions
Today an agent says "all tests pass". That sentence is true only under conditions the agent's own environment satisfies and the reader cannot see (installed packages, environment variables, generated files, network, a pinned Python). Our own study found the consequence: for **81% of real agent PRs an independent party could not obtain a determinate verdict**, mostly because the environment could not be reproduced, and one false alarm came from a dependency-version mismatch.

**Proposal:** a claim must carry its *preconditions*, a small machine-readable **recipe** written by the agent: how to set up and how to run the test it relied on. Agentvow replays the recipe in a clean sandbox (it can run only declared steps, network allowed for installs only) at the base and head commits and uses the independently executed result as evidence.

**What becomes measurable (the research object):**
1. **Sufficiency**: does the clean-room replay of the recipe reproduce the agent's claimed result? (Does the agent know what its own success depends on?)
2. **Necessity / honesty**: ablate declared steps; are they needed? Are undeclared installs present in the session (hidden state)?
3. **Accountability gap**: share of claims for which no determinate independent verdict is obtainable, with and without recipes.
4. **Hidden-state taxonomy**: why replays fail (undeclared package, env var, generated file, network, version drift, ordering).

**Why it is a solution and not just a study:** it attacks the measured bottleneck (reachability) without an LLM in the verdict path: the agent *proposes* the preconditions, deterministic sandboxed execution *decides*. Unknown stays unknown when no recipe exists.

**Honest risks:** frontier agents may write good recipes (then the finding is "recipes work", still useful); a hostile agent can declare a recipe that hides a gap (replay is still sandboxed and the base/head differential still applies); only Claude models are reachable for controlled runs here; neighbours (ProofRun, reproducible-trajectories, Repo2Run) overlap in parts and must be cited, not claimed away.

## Plan
1. Recipe schema + validator + sandboxed replay (`agentvow check --recipe`), deterministic tests. (this commit)
2. Hidden-state audit of a session transcript: installs/exports not in the declared manifest.
3. Controlled study: tasks with deliberate environment traps; Claude Code with/without a "write a recipe" instruction; replay fidelity, accountability gap, taxonomy. Pre-register first.
4. External validity: re-run the 140-PR set's failures to see how many a recipe would have resolved is not possible retrospectively; instead measure on fresh in-the-wild agent runs we generate.
