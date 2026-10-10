# Stage B3 (attempt-time capture vs after-the-fact reconstruction) — results, 2026-10-11

Pre-registration: `STAGE_B3_PREREG.md` (committed before the run; deviations logged there). 19 tasks attempted from the 199 candidates that Stage B0 rejected for lack of a reconstructable environment (seed 2029, at most 2 per repository, 17 repositories), Claude Code under the S0 sandbox, empty virtualenv, prompt C1P, one run each. **Cost $16.49 against the $15 cap**: the cap is checked between runs, and the last two runs (about $1.3 and $1.5 each) started under it; this overshoot is a deviation. 2 runs ended with an agent error. Raw data stay local.

## Which runs count
Pre-registered validity: the agent's target tests pass in its own environment **and** fail on the baseline without its changes. Of 19 attempts: 16 passed in the agent's environment; of those, 5 were trivial (the tests also passed without the changes, excluded); **11 valid runs**. (3 attempts did not pass in the agent's environment.) The agent therefore solved 16/19 of these harder tasks, 11 non-trivially.

## Primary result (11 valid runs; same scoped target command in every context)
| context | reproduces | 95% CI | outcomes |
|---|---|---|---|
| E_repo: reconstruction from the repository (zero-config ladder) | **0/11 = 0%** | 0-26 | 10 inconclusive, 1 fail |
| **E_capture: the agent's exact `pip freeze`** | **5/11 = 45%** | 21-72 | 5 pass, 6 inconclusive |
| E_recipe, scoped command | 4/11 = 36% | 15-65 | 4 pass, 4 inconclusive, 3 no replay (recipe rejected) |
| E_recipe, own command | 4/11 = 36% | 15-65 | same |
Paired (repo, capture): both fail 6; only capture reproduces 5; repo-only 0.

**Pre-registered reading:** "supports the hypothesis" required capture >= 70% and a >= 30-point lead over reconstruction; "not supported" was capture <= reconstruction + 10 points. Capture is +45 points but 45% < 70%, so the result falls in the **inconclusive middle band**. N = 11, descriptive only.

## What happened to the 6 capture failures (classified by hand from saved summaries; not re-run)
- 2 (sshpilot#630, #244): Agentvow's isolation guard refused because the environment imports `packaging` from outside the venv (an instrument-side refusal in the replay, not shown to be a property of the agent's environment).
- 1 (RAGEN#112): `pkg_resources` missing: **the capture itself dropped `setuptools`** (the freeze filter, inherited from B1, removes `pip`, `setuptools`, `wheel`), a capture-design flaw.
- 2 (sqlmesh#4713, #4712): `ImportError: cannot import name 'SQLMESH_VERSION'` from the project's own code: consistent with the frozen list installing a different copy of the project, shadowing the patched source (not verified).
- 1 (bellows#693): collection error, cause not examined.
At least three of the six therefore look like limits of this **crude capture and of the replay's guards**, not evidence that a fuller capture could not reproduce them; none of this was tested, and it is not used to adjust the primary result.

## Other observations
- Recipes were rejected for vocabulary in 3 of the 11 valid runs and in other attempts: `HOME` declared (3, including sqlmesh#4712 and UltraPlot#325), `&&` in the test command (autogen), `--ignore-requires-python` (serena). The same vocabulary-friction pattern as B1/B2.
- Reconstruction failed on these tasks by construction (that is how they were selected); the contrast is therefore against a population where it is known to fail, and the 0% shows the selection worked, not that reconstruction is always 0.

## Reading
- On tasks where reconstructing the environment from the repository failed, **recording what the agent actually installed made 5 of 11 non-trivial results independently reproducible that were otherwise not**, with a crude pip-freeze capture and no system packages, services or generated files. That is directionally consistent with the hypothesis in `GAP_ANALYSIS_VOLUME.md` but **does not meet the pre-registered bar** (>= 70%).
- Whether a fuller capture (container snapshot, installed project handled correctly, build tools kept) reaches the bar is untested; the failures that could be classified point to the capture and the guards rather than to irreducible hidden state, but that is a hypothesis for a next, pre-registered step.
- Limits: N = 11 valid runs from 19 attempts; budget overshoot; one model; one run per task; reconstruction tasks, not natural bug reports; 5 attempts excluded as trivial and 3 as not solved.
