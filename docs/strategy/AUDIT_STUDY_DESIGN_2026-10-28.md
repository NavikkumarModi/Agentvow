# Audit study design: does Agentvow's claim audit give a human overseer a correct, useful record? (2026-10-28)

Status: **design; pre-registered and frozen in `docs/research/AUDIT_STUDY_PREREG.md`. Amendment A1 (2026-10-28): the owner has no human readers, so labelling is done by labelling agents, Q4 (the human reading study) is not run, and results are "against evidence-grounded LLM labels".** It supersedes `SHADOW_STUDY_DESIGN_2026-10-27.md` (autonomy-gating arms). Framing: Agentvow is an independent claim-verification audit for human oversight of semi-autonomous and autonomous coding systems (`VISION_AUDIT_2026-10-28.md`). It is not judged by safety or autonomy rates. Nothing in the study merges, approves or blocks anything.

## Questions (one study, four parts)
- **Q1 Correctness.** When the audit says CONTRADICTED / SUPPORTED / NOT_CONTRADICTED, is it right?
- **Q2 Coverage.** What share of what a system says about its work gets any verdict path, and what share is left unaddressed?
- **Q3 Reach.** On a change the audit has never seen, how often can it produce a verdict at all, and why not?
- **Q4 Human value.** Does a reviewer reading the audit record judge the system's claims more correctly, or faster, than a reviewer with the diff and CI alone?

Q1 to Q3 need no recruited users. Q4 does, and is the only part that supports a claim about value; without it the product claim stays "an independent audit that is honest about what it could not check".

## Unit and sources
**Unit: one statement** extracted from a coding system's message (PR description, final message, commit message) that makes a checkable claim (tests, impact, API, files changed or left alone, docs updated, lint clean). Statements, not pull requests, are the analysis unit; pull requests and repositories are the clustering units for every interval.
Sources, in order of independence from this repository's earlier work:
1. **Reused, already labelled.** The ~1,300 AIDev pull-request descriptions hand-reviewed over five precision rounds, and the 152 labelled B6 statements. Reuse is allowed (CLAUDE.md), but these were used to *fix* the checkers, so they are **development data** and may not support held-out claims.
2. **Fresh held-out set.** New AIDev pull requests (other repositories, other agent families where present: Copilot, Codex, Claude Code, Cursor, Devin), sampled by seeded random draw before any checker is run, stratified by agent and by language. Target ≥ 400 statements from ≥ 100 pull requests in ≥ 60 repositories.
3. **Partner pull requests** (plain-pip repository, real agent output), run in shadow mode: the audit is produced and recorded; no workflow changes. Target ≥ 50 pull requests. Needs the owner to supply a partner.

## Ground truth
- A **second reader** who did not write or tune the checkers (the first annotator is the owner's side of the project; every earlier number rests on one annotator). Blind to the audit's verdict; sees the statement, the diff, the repository at the head and base commits, and may run the tests. Labels each statement: TRUE / FALSE / CANNOT_TELL (what the statement says, versus the repository). Labelling rules (e.g. "removed X from file", checkbox templates, bare extensions) written down before labelling, taken from the misreading classes found in the five precision rounds.
- **Disagreements** between readers are resolved by a written rule (third reader or "CANNOT_TELL"); agreement reported (Cohen's kappa) per statement kind.
- **Seeded false statements** (for recall, since natural contradictions are rare): take a TRUE statement and make a minimally edited FALSE one by a fixed recipe (change the file named, claim a doc update that did not happen, claim "lint clean" on a change with a ruff finding, inflate a test count). Author and checker are not independent, so seeded recall is **pipeline sensitivity only** and is reported apart from natural recall. A natural-recall estimate comes from labelled held-out statements the second reader finds FALSE.

## Measures (all with Wilson or cluster-bootstrap 95% intervals, counts first)
Q1 Correctness, per statement kind and overall, by verdict class:
- Precision of CONTRADICTED = FALSE among CONTRADICTED. Target to report: ≥ 90% with a lower bound stated; the earlier 91% is development data, so this is the number to re-measure.
- Of NOT_CONTRADICTED and SUPPORTED: the share the reader finds FALSE (missed contradictions). Never reported as "safe".
- Recall of real contradictions (natural) and of seeded ones (separately).
- **UNKNOWN audit**: of UNKNOWN verdicts, the share the reader could settle as TRUE or FALSE from material the tool had (a missed obtainable answer), versus a genuine unknown. This tests that missing evidence is not hidden and not over-reported.
Q2 Coverage: statements with a verdict path ÷ all checkable-seeming statements, with statements by kind that have no path (what a change *does*). Report the unaddressed share, not only the addressed.
Q3 Reach: share of pull requests where the audit ran to a verdict on tests / impact; reason taxonomy for the rest (no tests, cannot rebuild environment, timeout, no claim found). Per repository, because reach clusters by repository (27 earlier reconstruction runs gained nothing outside plain-pip repositories).
Also: reproducibility (re-run on a second machine, same verdict ≥ 90% as in E2/E3); explanation quality (below).

## Q4 human reading study
Design: within-subject, counterbalanced. Reviewers read 12 to 20 pull requests each, each in one of two conditions: **A** diff + description + CI result; **B** the same plus the Agentvow audit record (the plain-language explanation and ledger). For each pull request they judge the 3 to 6 checkable statements TRUE / FALSE / CANNOT_TELL and give confidence; time is recorded. Pull requests are balanced across conditions per reviewer (Latin square); a third of the statements are TRUE-contradicted-by-design, a third have no real problem, a third are UNKNOWN-for-the-audit, so that an audit that only ever says "fine" cannot look good.
Reviewers: ≥ 8 working developers recruited by the owner (no recruitment has been done; earlier pilots were dropped), blind to which results are the tool's.
Outcomes (fixed before running): accuracy against the ground truth; time per statement; calibration of stated confidence; **over-reliance** (reviewer accepts a wrong audit verdict, tracked on the cases where the audit is wrong or UNKNOWN); under-reliance (ignores a right verdict). Analysis: mixed-effects model with reviewer and pull request as random effects; report effect sizes and intervals, not only p-values.
A positive result requires better accuracy or less time in B **without** an increase in over-reliance on wrong or UNKNOWN verdicts.

## Predictions and falsifiers (to be written into the pre-registration before any run)
- Precision of CONTRADICTED on held-out data is lower than the 91% development figure (misreading classes keep appearing); the pre-registration states the number below which a statement kind is withdrawn from CONTRADICTED and kept as attention-only.
- A statement kind is **withdrawn** if its held-out precision lower bound is under 80%, or reader agreement is too low (kappa < 0.6) to label it.
- Coverage gain from the new checkers on held-out data is roughly the earlier ~15 points, not larger; "what a change does" stays mostly unaddressed.
- Reach outside plain-pip repositories stays low; the study reports it as a limit of the audit, not a failure to hide.
- Q4 is falsified for the product if the record does not improve accuracy or time, or if reviewers over-rely on wrong verdicts.

## Threats and controls
- **Development-data leakage.** Held-out set drawn and frozen before any checker run; checker code frozen at a named commit (record the hash); no checker change between labelling and scoring.
- **Same-author circularity** (authors of checker and seeded claims): kept out of any value claim; second reader and held-out statements carry the claims.
- **Annotator drift:** labelling rules fixed first; a 10% overlap re-labelled blind after a week.
- **Agent family and language:** Python only for test and lint checks; other agent families only as available; reported by stratum, not pooled into one headline.
- **Selection of reviewers and pull requests:** random draw, seed recorded; exclusions listed.
- **Harness faults** (a recurring cost in earlier experiments): every audit run isolated (fresh evidence home), controls run, harness failures classed apart and never counted as verdicts.
- **No LLM in the verdict path** stays true; if an LLM is used to *propose* statements for labelling, its output is data and every proposed statement is read by a person.

## Sizing (rough, for planning, not a power analysis)
- Precision at ~90% with a Wilson half-width of ~7 points needs about 70 CONTRADICTED-class statements per kind-group; natural CONTRADICTED verdicts are rare, so expect to need the 400-statement held-out set and still report some kinds as "too few".
- Recall of natural contradictions needs the reader to find ≥ 30 FALSE statements; if the held-out set has fewer, say so and report recall as unestimated.
- Human study: 8 reviewers × 16 pull requests × ~4 statements ≈ 500 judgments; enough to detect a large accuracy or time effect, not a small one.

## Steps
1. Owner decisions: second reader (named person), reviewer pool for Q4, partner repository for the shadow part, whether the 0.4.5 checkers are in scope (they are, once released or run from a pinned commit).
2. Write labelling rules and the pre-registration (decision rules, withdrawal thresholds, analysis plan); freeze checker commit.
3. Draw the held-out set; second reader labels blind; compute agreement.
4. Run the audit (isolated, controlled); score Q1 to Q3; adversarial review of the analysis before reporting.
5. Q4 only if Q1 to Q3 leave the audit worth testing with people; recruit, run, analyse.
6. Report what failed with what succeeded; withdraw kinds that miss their thresholds.

## What this study cannot show
That the software the system produced is correct or safe; that the audit changes outcomes in a team's workflow over time; behaviour of languages other than Python; any result for an agent family not sampled.
