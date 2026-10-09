# SOTA 02: Patents and Commercial/OSS Products

Researched 2026-10-01 by prior-art-researcher. Tooling: WebSearch + WebFetch only. Source status: [read] = page fetched and summarized by the fetch tool (a small-model summary, not a raw full-text read); [snippet] = search-result summary only; [unavailable] = could not be fetched. No claim here is a legal opinion. Nothing in this file clears gate G2.

## A. PATENTS

### A.0 Tooling limits (stated plainly)
- Google Patents search UI (patents.google.com/?q=...) is JS-rendered: WebFetch returned an empty shell. Query-based search of Google Patents, USPTO PatFT/PPUBS, Espacenet and WIPO Patentscope was NOT possible. Individual Google Patents document pages (/patent/USxxxx/en) CAN be fetched; Justia returned HTTP 403; USPTO image-ppubs PDFs return binary.
- Consequence: patent coverage below is what general web search surfaced plus document-page reads. It is a sample, not a landscape search. Absence of a hit is NOT evidence of absence. No claim-by-claim reading was done; claim summaries are from the fetch tool's abstract-level summary.

### A.1 Patents/applications found
| Number | Title | Assignee | Dates | Status | Abstract-level claim summary | Overlap with AgentMirror | Source status |
|---|---|---|---|---|---|---|---|
| US12450494B1 (also US20260017525A1) | Validating autonomous AI agents using generative AI | Citibank NA | Priority 2024-04-11; filed 2024-12-17; published/granted 2025-10-21 | Active (per fetch) | Validation layer receives constraints (regulations/guidelines), maps agent-proposed actions to risk categories, generates expected actions, identifies gaps vs proposed actions, modifies proposals using AI models | Low-medium: pre-execution validation of proposed actions against rules, uses generative AI in the loop. Not claim-vs-observed-reality, no snapshot binding, no counter-state search | [read] |
| US20250335185A1 | Automated code review using artificial intelligence | Capital One Services LLC (inventor T. Turner) | Filed 2024-04-26; pub 2025-10-30 | Pending | PR received; context about change and codebase extracted; embedding vector; "scrutiny level" from embedding space; AI review at that level; modify or commit change | Low-medium: risk/impact-scaled review of AI/PR changes. Impact is estimated by embeddings, not by evidence-backed reality graph; no agent-claim checking | [read] |
| US20230370274A1 -> US12192372B2 | Provable provenance for AI model assessments | Credo AI Corp | Filed 2022-05-12; pub 2023-11-16; granted 2025-01-07 | Granted | Hash of dataset and model, signed assessment results, certificate for independent verification | Low: hash/sign provenance of assessment results (tamper-evidence, not state freshness for code agents) | [read] |
| US12688261 | Methods and systems for authorizing invocation of a tool by an autonomous AI agent | Not confirmed in my read (a search snippet adjacent to a Daon press item suggests Daon, UNVERIFIED) | Issued 2026-07-21 (per Justia snippet) | Granted (per snippet) | Obtains fidelity/integrity signals to decide whether the agent is behaviorally bound to a person; action-level authorization producing a scoped, time-limited "permission slip"; human-readable binding message shown to approver (per snippet) | Medium for E6 (human-readable approval of scoped action). It is authorization of the action, not explanation of claim-vs-reality divergence | [snippet] (Justia 403, Google page 404) |
| US12563045 | Methods and systems for maintaining behavioral integrity of autonomous AI agents | Unknown | Unknown | Unknown | Snippet: signed hash written to immutable ledger linking snapshot state, decisions and actions for auditor verification | Low-medium: audit-record snapshot binding, ledger-anchored | [snippet] |
| US12547703 | Runtime environment for execution of autonomous agents | Unknown | Issued 2026-02-10 (snippet) | Granted | Agent runtime with internal state | Low | [snippet] |

Not found (as of this search, with the limits above): any patent or application on (i) comparing a coding agent's claims with independently collected system state with SUPPORTED/CONTRADICTED/UNKNOWN verdicts, (ii) snapshot-bound reuse of verification evidence across agents, (iii) counterfactual/alternative-state enumeration to decide whether an approval decision would change. Searches for these returned only the items above or arXiv papers. This is a weak negative.

### A.2 Exact queries to run manually (patent-attorney / librarian grade)
Run on Google Patents (use "Similar documents" on US12450494B1 and US20250335185A1), USPTO PPUBS, Espacenet (CPC G06F11/36, G06F8/70, G06F21/57, G06N20/00, G06F11/3668), WIPO Patentscope. Date filter >= 2022.
1. ("agent" OR "autonomous agent") AND ("claim" OR "assertion" OR "self-report") AND ("verify" OR "verification") AND ("system state" OR "observed state" OR "ground truth") AND ("code" OR "repository")
2. ("evidence") AND ("snapshot" OR "commit" OR "revision") AND ("stale" OR "invalidat" OR "freshness") AND ("verification result" OR "test result") AND ("reuse" OR "cache") AND ("agent" OR "language model")
3. ("counterfactual" OR "alternative state" OR "plausible state") AND ("approval" OR "approve" OR "review decision") AND ("code change" OR "pull request" OR "agent action")
4. ("dependency graph" OR "knowledge graph" OR "system model") AND ("claim" OR "statement") AND ("language model generated" OR "agent generated") AND ("unverified" OR "unknown") AND ("reviewer")
5. ("approval" AND "plain language" OR "natural language explanation") AND ("scope" OR "not authorized") AND ("agent action" OR "tool call")
6. ("independence" OR "independent verification") AND ("language model") AND ("verifier" OR "judge") AND ("same model" OR "correlated")
7. ("audit trail" OR "provenance") AND ("agent") AND ("tool call") AND ("hash chain" OR "signed") AND ("evidence")
8. Assignee sweeps: Microsoft, Amazon, Google, OpenAI, Anthropic, GitHub, Atlassian, JetBrains, Snyk, Datadog, Citibank, Capital One, JPMorgan, IBM, SAP for ("coding agent" OR "agentic") AND ("verification" OR "validation").
Also run an FTO-style search by a registered patent practitioner before any public novelty claim.

## B. COMMERCIAL / OSS PRODUCTS

Field abbreviations in tables: Claims-vs-reality = checks agent CLAIMS against independently observed state; Snapshot = evidence binding to a commit/state; Indep = independence mechanism; Arch/Policy/State = awareness; UX = decision UX; Reuse = prior-work reuse; CF = counterexample / counter-state support.

### B.1 Summary matrix
| Product | Date/status | Claims-vs-reality | Snapshot binding | Indep | Arch | Policy | State | UX | Reuse | CF | Overlap | Src |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Langfuse | OSS, ongoing | No (docs silent) | No | Code evaluators vs LLM-judge both available | No | No | No | Score dashboards, annotation queues | Datasets | No | Low | [read] |
| LangSmith | ongoing | No | No | Mixed: human, code, LLM-judge, pairwise | No | No | No | Annotation queues | Datasets | No | Low | [read] |
| Arize Phoenix | OSS | No | No | Same as above | No | No | No | Trace UI | Datasets/experiments | No | Low | [read] |
| Braintrust | ongoing | No | No | Scorers; Loop assistant | No | No | No | Dashboards | Datasets | No | Low | [read] |
| Helicone | ongoing | No | No | n/a (gateway/logging) | No | No | No | Dashboards | No | No | None | [read] |
| AgentOps | ongoing | No | No | n/a | No | No | No | Session replay/waterfall | No | No | Low | [read] |
| Datadog LLM Observability | ongoing | Docs silent on claim checks | No | n/a | Trace topology not stated | No | No | Traces, patterns | No | No | Low | [read] |
| Honeycomb / Grafana AI | - | not audited | - | - | - | - | - | - | - | - | Unknown | [unavailable] (not researched) |
| CodeRabbit | ongoing | No (reviews code, not agent claims) | No | Single vendor LLM + tools (SAST/linters per product claims, not verified here) | Partial (code graph claims, unverified) | Custom rules | PR diff | PR comments, Triage, Change Stack | Learnings | No | Low-med | [read] overview only |
| Greptile | ongoing | No | No | LLM | Yes: dependency graph of repo | Learned team prefs | Repo index | PR comments | Learns from reactions | No | Medium on graph/impact | [read] |
| Graphite | ongoing | not audited | - | - | - | - | - | - | - | - | Unknown | [unavailable] (docs 404) |
| Qodo | ongoing | No | No | Parallel agents + judge agent (LLM) | Yes: cross-repo impact | Rule Miner from PR history | Repo+PR history | Ranked findings | PR history prioritization | No | Medium | [read] |
| Cursor Bugbot | ongoing | No | No | Autofix cloud agent reproduces bugs in VM | Context of codebase | Team/BUGBOT.md/learned rules | PR diff | PR comments, check status | Learned rules | No | Low-med | [read] + [snippet] |
| GitHub Copilot code review | ongoing | No | No | Models; CodeQL as separate feature | Repo context | custom instructions | PR | PR comments | Copilot Memory | No | Low-med | [read] |
| Claude Code Review | research preview 2026 | No (reviews PRs) | No | Multi-agent + verification step against code behavior | Codebase context | CLAUDE.md/REVIEW.md | PR | Severity-tagged inline, neutral check | No | No | Low-med | [read] |
| Claude Code hooks/transcripts | ongoing | Hook can run any checker; no built-in | No | n/a (substrate) | No | permission rules | transcript_path | n/a | No | No | Integration point, not competitor | [read] |
| Devin / Factory / OpenHands | ongoing | Not shown | No | Factory: separate review droid (LLM) | - | - | - | - | - | - | Low | [snippet] |
| Sourcegraph / Codescene | ongoing | No | No | Codescene: deterministic Code Health baseline, MCP server | Codescene yes (health), Sourcegraph code intel | Gates | - | - | - | No | Low-med | [snippet] |
| Snyk (DeepCode, Invariant, Agent Scan) / Semgrep / CodeQL | ongoing | No | No | Symbolic + gen AI | Code-path analysis | Guardrails policy | - | - | - | No | Low | [snippet] |
| Microsoft Agent Governance Toolkit | OSS MIT | No | Audit records | Deterministic, outside LLM | No | Yes: YAML/OPA/Cedar | No | CLI | No | No | Policy collector candidate | [read] |
| AWS AgentCore Policy (+ Dogwood) | GA 2026-03; Dogwood ~2026-08 | No | No | Deterministic gateway interception outside agent code | No | Yes: Cedar, NL authoring | Session history (Dogwood temporal) | CloudWatch logs | No | No | Policy input only | [read] AgentCore docs; Dogwood [snippet] |

### B.2 Detail records (relevant products)

**StateProof (SurefireStudios, OSS MIT, 2026)** [read]
- Problem: action-taking agents claim success; verify real state. Mechanism: LLM compiles task into typed contract once (Zod), then deterministic, zero-model-call verification per run. Input: task, tool defs/schema, final response, tool trajectory, before/after state snapshots. Output: PASS/FAIL/NEEDS_REVIEW with evidence refs, per-requirement status, audit trail. Evidence: records and events actually touched; cannot cite nonexistent data. Independence: verifier is code, not LLM, at run time. Arch/policy awareness: schema and event ordering ("approval before action"). State: before/after snapshots (state diff, not freshness-bound reuse). Viz/UX: structured report. Reuse: compiled contract reused across runs (not evidence reuse). CF: none. Limits (self-stated): one synthetic domain, three task templates, not a real system of record. Overlap: HIGH for claim-vs-state with deterministic verdicts and NEEDS_REVIEW (unknown-like). Differentiation: domain is business records, not coding-agent repos; no reality graph, no counter-state search, no decision sensitivity.

**agent-claim-verifier (chiragborse1, MIT, 2026)** [read]
- Compares Claude Code/Codex session transcripts against git ground truth: 8 finding types (no-work, unmentioned-changes, claimed-untouched, no-verification, ...). Claim extraction by literal-path heuristic (no LLM). Output status VERIFIED/DISCREPANCIES/UNVERIFIED/INCONCLUSIVE plus JSON; usable as pre-merge hook. Limits: Claude Code format only modeled/unvalidated, post-completion only, gitignored files invisible. Overlap: HIGH for the narrow transcript-vs-git claim check (this is the same family as backcheck in PRIOR_ART). No snapshot-bound reuse, graph, or decision-sensitivity.

**claim-verifier (baby-zack-agent, MIT)** [read]. MCP server; verify_url / verify_github; boolean verdict + raw evidence; "best-effort snapshot of a live web". Overlap: low-medium (external-world claims only; freshness acknowledged, not enforced).

**Praxen (open source, announced 2026-06-24)** [read via Help Net Security]. Compares an agent's declared policy ("Worker Remit") with source, deployment config, logs, governance docs; HTML/JSON reports with cited artifacts; runs as a Claude Code plugin, so analysis is LLM-driven and results vary between runs. Overlap: medium for claim(policy)-vs-reality reconciliation; not independent of an LLM in the verdict path.

**Microsoft Agent Governance Toolkit** [read: GitHub README summary]. Deterministic, stateless, fail-closed policy decision runtime (YAML/OPA/Cedar), tamper-evident audit records, identity (SPIFFE/DID), sandbox rings, MCP gateway, `agt verify` OWASP checks. Pre-action authorization, not claim checking. Overlap: policy evidence source and audit format; not competing on reconciliation.

**AWS AgentCore Policy / Dogwood** [read / snippet]. Cedar policy at AgentCore Gateway before tool access; natural-language-to-Cedar with automated-reasoning checks (overly permissive, unsatisfiable); decisions logged to CloudWatch. Dogwood (open source, Apache 2.0, reference interpreter "for exploration and testing, not production") adds session-aware temporal rules (prerequisite approval, rate limits, running totals). Overlap: policy awareness inputs; the "was approval granted before action" fact is a checkable event for a verifier. No claim reconciliation.

**Invariant Labs (acquired by Snyk, 2025) / Snyk Agent Scan** [snippet]. Guardrails policy engine for agent/MCP tool calls, Explorer observability, MCP-Scan (tool poisoning). Runtime policy, not claim verification. Lakera: not researched beyond the query ([unavailable]).

**Observability stack (Langfuse, LangSmith, Phoenix, Braintrust, AgentOps, Datadog, Helicone)** [read]. All trace and score LLM app behavior; evaluators are human, code, or LLM-as-judge. None of the fetched docs describe checking agent claims against external system state, evidence snapshot binding, or approval-decision support. Datasets/experiments give test-case reuse, not evidence reuse. Note: absence reflects what the overview pages said; deeper pages (e.g., custom code evaluators with external lookups) could implement ad hoc checks.

**AI code review (CodeRabbit, Greptile, Qodo, Bugbot, Copilot, Claude Code Review)** [read]. They review the DIFF/PR, not the agent's claims. Differences: Greptile builds a repo dependency graph (impact awareness); Qodo traces cross-repo impact and uses a judge agent and PR-history rules; Claude Code Review runs a verification step "against actual code behavior" to filter false positives and tags severity (check run is neutral, does not approve or block); Bugbot autofix spawns a VM agent to reproduce. Independence is LLM-based throughout. None documents snapshot-bound evidence reuse, UNKNOWN as a first-class outcome, or decision-flip filtering. Closest on E1/impact: Greptile, Qodo.

**Claude Code hooks / transcripts** [read hooks docs]. Hooks provide `transcript_path` (conversation JSON), `session_id`, PreToolUse allow/deny/ask/defer, PostToolUse, Stop; handler types command/http/mcp_tool/prompt/agent. This is the ingestion substrate for passive and attached modes. Transcript JSONL schema is not specified in the docs I read; agent-claim-verifier states both Codex and Claude formats are undocumented and change without notice. [read for hooks; transcript format unverified].

**Attestation / audit standards launched 2026** [snippet]: Dapr 1.18 verifiable execution (signed workflow histories, SPIFFE; June 2026); Linux Foundation TRACE (hardware-attested runtime evidence, 2026-08-25); Advanced AI Society Proof-of-Control v1.0 draft (comment to 2026-10-30); Proof x401 (authority behind agents). These attest identity/execution/authority, not claim-vs-reality for code changes. Candidate evidence formats, not competitors.

Not covered (no time/sources fetched): Honeycomb, Grafana AI, Graphite, Devin review internals, OpenHands review, Lakera, Sourcegraph/Codescene/Semgrep/Snyk docs (snippet-level only). Treat as unaudited.

## C. VERDICT: NOVELTY RISK

1. Patents: HIGH uncertainty, not a clearance. Only a sample was reachable. No patent found on snapshot-bound evidence reuse or decision-flip counter-state search, but patent databases were not queryable, so this is a weak negative. Two adjacent granted/pending filings (Citibank US12450494B1 on gap-checking proposed agent actions; Capital One US20250335185A1 on impact-scaled AI review) show large banks are filing around agent validation and AI code review; a professional FTO/prior-art search on queries A.2 is required before any "novel" or "patentable" statement and before G2.
2. Claim-vs-reality reconciliation (E3): CONFIRMED CROWDED. StateProof, agent-claim-verifier, claim-verifier, Praxen, plus backcheck/Aga/AgentCheck already do deterministic or evidence-cited claim checks, several with INCONCLUSIVE/NEEDS_REVIEW outcomes. Do not claim novelty here.
3. Snapshot binding/reuse (E2): partially solved in tools above and in Aga/AgentCheck/EA-Graph per existing docs; nothing newly found that does cross-agent reuse, but community issue threads show the idea is widespread (rioX432/ai-dev-templates #28, amurshak/hephaestus #224, randomparity/adept #369 [snippet]). Engineering combination only.
4. Policy/audit (pre-action authorization, tamper-evident logs): SOLVED by Microsoft AGT, AgentCore Policy/Dogwood, Invariant/Snyk, Dapr, TRACE. Integrate, do not rebuild.
5. Code review/impact: Greptile and Qodo already offer graph-aware impact review (LLM-based). The Reality Graph differs only if it is claim-facing, evidence-typed and deterministic; otherwise it is a re-skin.
6. Observability vendors: no overlap found on claims/evidence/decisions; not a threat on the research mechanism.
7. Remaining potential gap (requiring further verification): decision-sensitive counter-reality search (E4/E5) and plain-language approval semantics tied to claim-vs-reality (E6). Nothing in the commercial or patent sample implements enumerating evidence-consistent alternative states and filtering by whether the approval decision flips. Closest: Dogwood/AgentCore temporal rules (decision depends on history, but history is trusted input), US12688261 (human-readable scoped approval, authorization not reconciliation), Qodo's judge agent (filters by confidence, not decision flip). Risk that mechanism reduces to dependency analysis plus a rule table for the first claim class remains, as already noted in NOVELTY_BOUNDARY.md.
8. Overall: novelty risk MEDIUM-HIGH for the system as a whole (every component has a close existing analogue), MEDIUM for E4+E5 as a combined mechanism pending a real patent search and the baselines B5/B6 (StateProof-like and agent-claim-verifier-like). Recommended: add StateProof, agent-claim-verifier, Praxen and claim-verifier to COMPETITOR_MAP/SOTA_MATRIX as baselines; avoid "first" language; pursue patent search per A.2.

## D. Sources
- https://github.com/SurefireStudios/StateProof [read]
- https://github.com/chiragborse1/agent-claim-verifier [read]
- https://github.com/baby-zack-agent/claim-verifier [read]
- https://www.helpnetsecurity.com/2026/06/24/praxen-open-source-ai-agent-behavior-verification/ [read]
- https://github.com/microsoft/agent-governance-toolkit [read]
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html [read]
- https://infoq.com/news/2026/08/aws-dogwood-agent-policy/ and thenewstack Dogwood article [snippet; New Stack fetch returned no article body]
- https://patents.google.com/patent/US12450494B1/en [read]; https://patents.google.com/patent/US20250335185A1/en [read]; https://patents.google.com/patent/US20230370274A1/en [read]
- https://patents.justia.com/patent/12688261 [unavailable, 403; snippet only]
- https://docs.coderabbit.ai/overview/introduction, https://www.greptile.com/docs/introduction, https://docs.github.com/en/copilot/concepts/agents/code-review, https://docs.qodo.ai/qodo-documentation/qodo-merge, https://cursor.com/docs/bugbot, https://code.claude.com/docs/en/code-review, https://code.claude.com/docs/en/hooks [read]
- https://langfuse.com/docs/evaluation/overview, https://docs.langchain.com/langsmith/evaluation-concepts, https://arize.com/docs/phoenix, https://www.braintrust.dev/docs, https://docs.helicone.ai/, https://docs.agentops.ai/, https://docs.datadoghq.com/llm_observability/ [read]
- Snyk/Invariant, Sourcegraph/Codescene, Semgrep/CodeQL, Dapr/TRACE/Proof-of-Control, Factory/Devin/OpenHands: search snippets only [snippet]
