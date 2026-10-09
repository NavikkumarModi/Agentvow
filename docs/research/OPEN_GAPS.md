# Open Gaps (updated 2026-10-01). All are "Potential gap requiring further verification".

1. **Decision-gated UNKNOWN via counter-state search for agent claims.** No full implementation found. Pieces exist (Assurance 2.0 defeaters, SWE-ABS, CFC, EA-Graph UNPROVABLE, classifier counterfactuals). Main risk: for "no downstream impact" it reduces to Assay/roam-code/RTS impact analysis + a rule.
2. **Decision-impact suppression** (show only unknowns that can flip the approve/reject rule) and its effect on review burden and alert fatigue. Neighbours: pivotal-vote analysis, Planfence frontier. Not found as a human-evaluated mechanism.
3. **Structural independence typing** capping SUPPORTED. Existing work is statistical or role-based. N-version diversity and common-cause failure literature unsearched and likely has analogues.
4. **Claim-vs-reality view for humans.** Visualization SOTA is process-centric; no claim-vs-reality decision view found.
5. **Human-centred evaluation** with seeded divergences, Agentvow-error trials (constant-reliability verifiers breed complacency), an LLM-reviewer arm, Need-for-Cognition and difficulty covariates, appropriate-reliance metrics. Tension: forcing functions reduce overreliance but add burden; the research question's "without increasing review burden" must be tested as a trade-off, not assumed.
6. **Approval-scope semantics** (what approval does NOT authorize): US12688261 is adjacent; not otherwise audited.

## Open decisions flowing from the SOTA
- Choose claim classes where enumeration is non-trivial (e.g. "tests cover this change", stale/discriminative evidence, runtime/config divergence), not only "no downstream impact".
- Treat the Claude Code transcript as agent-adjacent evidence (hooks can rewrite tool output; transcript is written asynchronously). Independent evidence must come from repo, CI, or runtime.
- Evidence format: in-toto Statement + custom predicates (independence vector as custom field), CloudEvents transport.
- Protocol adapters: pin OTel GenAI (still "Development"); MCP spec 2026-07-28; A2A (Linux Foundation); Zed's Agent Client Protocol is active and distinct from IBM's Agent Communication Protocol (the one folded into A2A). Earlier docs conflated these; corrected here.

## Corrections to earlier docs
- EA-Graph does NOT claim verifier-vs-agent independence (full text).
- "13.6% vs 89%" human-vs-auto-mode figure is not in Anthropic's source; excluded. Source says ≈93% of permission prompts approved, auto mode ≈83% catch, sandbox −84% prompts.
- VIGIL: three different papers share the name; cite by arXiv ID (2606.26524 is the runtime-enforcement one).

## Review limits
- Patents not searchable with available tools.
- Mostly page/abstract-level reads; full-text list in NOVELTY_BOUNDARY "Next gates".
- Not searched: safety-assurance / N-version, RTS (Ekstazi-style) in depth, counter-abduction, ICSE/FSE/ASE proceedings, Google Scholar/DBLP/ACM DL.
- Adversarial pass (master plan §30) not run; RISKS.md not written.

## Adversarial review (2026-10-01)
Full findings in `RISKS.md`. Changes to the gap list:
- Gap 1 downgraded from "potential gap" to "application of known idea": eliminative argumentation / Assurance 2.0 defeaters with residual doubt, and CoDefeater (LLM-proposed defeaters, ASE 2024), already cover the shape. The remaining question is empirical: does it beat Assay + RTS + mutation testing + a rule-aware LLM reviewer?
- Gap 2 (decision-impact suppression) survives only with a human study; added risk that suppression induces automation bias (RISKS G1).
- Gap 3 (independence typing): Knight and Leveson plus N-version-with-coding-agents show structural separation does not imply failure independence; vector must model shared inputs or be renamed provenance labels.
- Gap 5 (human study): add power analysis, non-inferiority margin on time, tool-error trials, real-PR items; seeded-only items are insufficient.
- New gaps: (7) closed counter-state vocabulary with scope-labelled soundness (E1); (8) fail-closed UNKNOWN preservation under collector faults (H); (9) evidence contamination by agent-controlled tests, config, hooks, environment (D1); (10) snapshot binding of environment/non-determinism (I1); (11) construct validity of "decision-changing" and DCDR tautology (C1).
- Open decision resolved: pilot P0 (RISKS K) runs before any enumerator implementation; kill criteria in RISKS L.
- Review limits: web checks were snippet-level; Assay repo page read, not code; patents still unsearched.
