# System Architecture (proposal; do not implement before G2)

```
ingest (transcript | git | fs | test/CI/SARIF | OTel)
   → normalized events
   → Agent Graph  (Goal→Plan→Action→Tool→Artifact→Claim)
   → Work Harvester → Evidence Store (snapshot-bound, hashed)
   → Reality Graph (components, deps, invariants, policies, tests, state)
        built by importing: dependency tools, archagent-style invariants, coverage, OPA/Cedar
   → Reconciler (claim ↔ evidence: SUPPORTED/CONTRADICTED/INCOMPLETE/UNKNOWN)
   → Reality Challenge (counter-reality search + decision rules)
   → Decision object
   → Translator (technical / business / plain) → CLI, later VS Code/desktop
```

## Principles
- Core is a library + CLI, independent of any agent vendor or editor.
- Language: TypeScript or Python — undecided; pick after collector survey (Python has import-linter/pytest, TS has dependency-cruiser/fast-check). Decide in a short ADR.
- Verdicts: deterministic. LLM optional, only for claim extraction and counter-reality *proposals*, each proposal validated by evidence checks.
- Evidence validity: snapshot (commit/tree hash), environment, scope, artifact hash, freshness, reproducibility. Status VALID / STALE / OUT_OF_SCOPE / UNVERIFIABLE.
- Independence vector per evidence: framing, evidence, mechanism, authority ∈ {same, separate, unknown}. Independent support for a claim requires ≥1 evidence separate on evidence+mechanism; agent statements and agent-selected tool results cap at "claim-only".
- Decision rules: explicit, versioned table; decision-flip evaluated against it, not by a model.
- Schemas (G4): event, claim, evidence, work-item, reality-state, divergence, decision — JSON Schema with provenance on all.

## Evaluation hooks
Each mechanism behind a flag for ablations (reality graph, reuse, independence, challenge, sensitivity filter, translation). Benchmark scenarios store hidden ground truth; baselines B0–B9 per master plan.

## Open decisions
Language; evidence format (own schema vs in-toto/PROV/ATP mapping); ACP adapter priority (verify ACP/A2A status).
