# Audit study (Q1 to Q3): pre-registration (DRAFT v1, 2026-10-28; becomes binding when frozen)

Design: `docs/strategy/AUDIT_STUDY_DESIGN_2026-10-28.md`. Labelling: `AUDIT_LABELLING_RULES.md`. Framing: Agentvow is an independent claim-verification audit for human oversight; it is judged by correctness, coverage, reach, honesty of UNKNOWN and reproducibility, **not** by safety or autonomy rates. Q4 (human reading study) has its own pre-registration, to be written only if Q1 to Q3 support running it.

**Status: DRAFT.** It is frozen by filling in section 0 and committing, **before** the held-out sample is drawn. Until then it is a proposal and nothing in it has been run or looked at. After freezing, a change is a dated amendment at the end, with the reason; decision rules (sections 5 and 6) are never amended after labels exist.

## 0. Freeze record (to be filled before drawing the sample; the study does not start while any field is empty)
- Checker/tool commit (full hash): ______
- Date and time frozen: ______
- Second reader name or id: ______; third reader (for disagreements) name or id: ______
- Sampling seed (random 64-bit, written before drawing): ______
- Corpus snapshot id/date (AIDev release or file hash): ______
- Environment for audit runs (OS, Python, `ruff`/`black`/`flake8` versions): ______
- Labelling rules version: v1 (no amendments) ______

## 1. Hypotheses (directional, each with a falsifier)
- **H1 (precision of CONTRADICTED).** Per statement kind, the held-out precision of CONTRADICTED is at least 80% (lower bound of the 95% interval). Falsified for a kind if the lower bound is below 80%.
- **H2 (no hidden answers in UNKNOWN).** Among UNKNOWN verdicts, at most 10% are statements the reader settled as TRUE or FALSE from material the tool had access to. Falsified if the point estimate exceeds 10%.
- **H3 (coverage).** Statements with any verdict path are between 15 and 40% of checkable statements on held-out data; impact statements remain mostly unaddressed. Falsified if coverage is outside the range (either direction is reported).
- **H4 (reach).** In plain-pip repositories the audit reaches a verdict on tests in at least 50% of pull requests with a tests claim; outside plain-pip repositories at most 20%. Both are reported; the first is falsified if below 50%.
- **H5 (reproducibility).** On a second machine the same verdicts are reproduced for at least 90% of audited statements. Falsified if below 90%.
- **H6 (extraction).** At least 85% of extracted spans are CLAIM (not NOT_A_CLAIM) by kind. Falsified per kind if below 85%.
These numbers are stated now; the earlier figures (91% precision, ~15-point coverage gain) are development data and are not used to tune them beyond this record.

## 2. Population and sampling
- **Population.** Agent-authored pull requests in the AIDev corpus whose messages (pull-request description; final message where available) contain at least one extractable statement of a kind in scope: `files_scope`, `docs_updated`, `lint_clean`, `tests_pass`, `impact`. Unit of analysis: the statement. Clustering units: pull request and repository.
- **Exclusions (listed before drawing):** every pull request used in the five development rounds or in B6; repositories with more than 3 draws are capped at 3; pull requests whose head commit is no longer fetchable are replaced by the next draw and counted.
- **Draw.** One seeded pseudo-random draw per stratum, with the seed of section 0, from the snapshot of section 0, recorded by script (`research/audit/draw.py`, to be written before freezing and committed with the freeze). Strata: agent (Copilot, Codex, Claude Code, Cursor, Devin, Jules, as available) × language of changed files (Python, other). Target: ≥ 100 pull requests, ≥ 60 repositories, ≥ 400 statements; at most 40% from one agent. No post-draw replacement except the rule above.
- **Plain-pip stratum.** A pull request is "plain-pip" if, at its base commit, the repository installs with `pip install .` or `pip install -r requirements.txt` plus `pytest`, determined by the rule in `research/audit/classify.py` (to be written and frozen with the checker commit) from the files at that commit, not from today's default branch. (The earlier classification read the wrong state; that error is not repeated.)
- **Audit runs** execute only the repository code the product already runs in its sandbox; clones and installs of third-party code follow the owner's explicit authorisation, which is recorded before the run.

## 3. Procedure
1. Freeze (section 0). 2. Draw. 3. Extract statements with the frozen checker (extraction output is stored, hash recorded) and strip the audit verdicts. 4. Reader labels per `AUDIT_LABELLING_RULES.md`, blind to verdicts; 20% of items are double-labelled by the second reader; 10% re-labelled after ≥ 7 days. 5. Labels locked and hash recorded. 6. Audit run on the frozen commit: isolated (fresh evidence home per check), unfaulted controls where relevant, harness failures classed apart and never counted as verdicts. 7. Join labels and verdicts. 8. Analysis per section 4. 9. Adversarial review of the analysis before reporting. 10. Report, including everything that failed.

## 4. Analysis plan
- **Per statement kind** (and overall only as a secondary summary): counts first, then proportions with Wilson 95% intervals; when statements cluster within pull requests, cluster-bootstrap intervals by repository (10,000 resamples, seed recorded). The headline uses the bootstrap interval.
- **Confusion table** of reader label (TRUE/FALSE/CANNOT_TELL) × audit verdict (CONTRADICTED/SUPPORTED/NOT_CONTRADICTED/UNKNOWN), by kind. CANNOT_TELL items are reported but excluded from precision and recall denominators; their share is reported.
- Precision of CONTRADICTED = FALSE ÷ (FALSE + TRUE) among CONTRADICTED. Miss rate of NOT_CONTRADICTED/SUPPORTED = FALSE ÷ all in those verdicts. Natural recall = CONTRADICTED ÷ all reader-FALSE statements, reported only if ≥ 30 reader-FALSE statements exist; otherwise "not estimated".
- **UNKNOWN audit (H2):** for each UNKNOWN, the reader's label plus a second check by a script-recorded flag "answerable from the material the tool had" (a person confirms each flagged case); report counts of obtainable-but-missed answers.
- **Seeded false statements** (separate table): minimal false variants of TRUE statements by the fixed recipe (file named, doc update, lint on a change with a real finding, inflated count), made **after** freezing by someone other than the labelling reader; recall of seeded falsehoods is pipeline sensitivity only and never mixed into H1 to H6.
- **Agreement:** Cohen's kappa (inter-reader, per kind) and percent agreement; intra-reader on the 10% overlap. A kind with kappa < 0.6 cannot be scored for H1: it is reported as "labels unreliable".
- **Reach (H4):** per pull request, verdict reached yes/no with the reason taxonomy; per repository for the plain-pip and non-plain strata.
- **Reproducibility (H5):** the audit rerun on a second machine (different OS or hardware where available); verdict identity rate with intervals.
- No multiple-comparison adjustment is claimed; hypotheses are descriptive and reported as such. Subgroup results (by agent, language) are secondary and labelled as such.

## 5. Decision rules (fixed now, never amended after labels exist)
- **Withdraw from CONTRADICTED (keep as attention only)** a statement kind whose held-out precision lower bound is below 80%, or whose labels are unreliable (kappa < 0.6), or that has fewer than 20 CONTRADICTED verdicts with precision below 90% (insufficient evidence to keep a blocking verdict).
- **Keep a kind in CONTRADICTED** only if the lower bound is at least 80% and kappa is at least 0.6; the report states that this is evidence about these pull requests, not a guarantee.
- A kind with too few items (< 20 reader-labelled TRUE/FALSE) is reported as "too few to evaluate"; it is neither kept nor withdrawn on this evidence.
- If H2 is falsified, UNKNOWN reasons that hide obtainable answers are listed and become development items; no claim of "honest UNKNOWN" is made for those paths.
- If the labelled sample is smaller than 250 statements, or the second reader's overlap is under 20%, the study reports mechanics only and makes no claim about H1 to H6.

## 6. What would count as a negative result, stated now
H1 false for files_scope or docs_updated (these are the most-tuned kinds); H2 false; H4 false in the plain-pip stratum; coverage within 5 points of zero gain. Each is reported as such and changes the product description (withdraw a kind, or state the narrower reach) rather than being explained away.

## 7. Threats, controls and honest limits
Development-data leakage (excluded and frozen commit); checker/seeded-claim author circularity (seeded recall separate); annotator drift (overlap relabel); single corpus (AIDev) and Python-only test and lint checks; the reader sees the repository and can be wrong too (kappa, disagreements reported); the audit's environment may differ from the reader's (versions recorded; disagreement is analysed, not hidden); one second reader means reader effects remain; a harness mistake can still happen (controls, isolation, adversarial review). Results are about statements in these pull requests and say nothing about whether the software is correct or safe.

## 8. Roles and approvals
Owner: names the readers, authorises third-party clones and installs, decides whether the 0.4.5 checkers are in scope (they are, run from the frozen commit even if unreleased). Claude: writes the scripts, runs the audit, produces the tables; does not label held-out statements, does not edit checker code after freezing, and runs the adversarial review before the report.

## Amendments
(none)
