# Exploring the proposed direction: what is missing between the tool and the claim (2026-10-20)

Direction under exploration (VISION update, section 8): an independent clean-room replay of an agent's claim from an environment recorded at claim time, with UNKNOWN as a first-class result, never claiming correctness. This note lists what the current tool and evidence do not yet support, ranks the ways to close each gap by evidence value and cost, and pre-registers the first cheap measurement. Status: a plan; one measurement (E1) is started with this note.

## 1. Gaps between the positioning and what exists (checked against the repository)
| gap | today | why it matters |
|---|---|---|
| Strong reconstruction baseline | the zero-config ladder (extras, a fixed requirements list, pytest) is what the tool ships; CI-derived recipes exist only in `research/preconditions/ci_recipe.py` | the paper's headline gap (91% vs 55%) is mostly a weak comparator; the strongest reviewer objection |
| Cross-time | captures pin versions; replay was measured same day only | "reproducible" needs to hold later (yanked or removed wheels) |
| Cross-machine | a Linux sandbox (bubblewrap) exists and CI-tests the tool; B6 replays were all on one macOS host | pinned wheels can differ by platform |
| Replay changes a decision | no run shows a CONTRADICTED caught through capture; `scripts/planted_faults.py` exists from earlier work | without it, the study measures replayability only |
| Second agent | test-time capture verified live on Claude Code only; a Copilot output format exists | one model family everywhere |
| Beyond Python packages | out of scope by design (system packages, services, generated files, secrets) | caps how many claims can be closed; the not-reproduced manifest names what was skipped |
| Real users | pilot kit written; no participants | whether people act on UNKNOWN is untested |

## 2. Ranked ways to close them (evidence value against cost; none needs a new agent run unless stated)
1. **E3, strong reconstruction baseline** (highest value). Add CI-config and Dockerfile-derived setup as a further replay context, pre-register, and re-replay the 22 valid B6 runs. Cost: engineering plus replay only. Answers the main objection; the result may shrink the 91-vs-55 gap, and that is a finding either way.
2. **E1, cross-time re-replay** (cheapest; time-dependent so it starts now). Re-replay the 22 valid B6 captures from the saved patches and pip freezes at +8 days now and +30 days later.
3. **E5, a replay that changes a decision.** Inject known faults into the B6 patches (the repository has a planted-fault harness) and test whether capture-based replay turns a false "tests pass" into CONTRADICTED where reconstruction returns UNKNOWN. No agent spend; design must be pre-registered and must not tune faults to the tool.
4. **E2, cross-machine (Linux).** Needs Docker running and an image download (not done; disk is tight, about 6 GB free), 22 replays.
5. **E4, a second agent family.** New agent runs (cost in dollars); only after E3 and E5.
6. **Pilot.** Needs participants the owner recruits.

## 3. Pre-registration of E1 (written before the run)
Population: the 22 valid B6 runs (capture originally passed in 20, inconclusive in 2). Procedure: `research/preconditions/stageb3_recapture.py stageb6 3` (the same fuller capture and 3 GB size limit as the registered B6 replay; runs with untracked files not in the patch are skipped and counted). Outcome: for each of the 20 originally passing captures, whether the replay still passes; for the 2 originally inconclusive ones, whether the result is unchanged. Reading, fixed now: stable if at least 18 of the 20 still pass (90%); any flip is reported with its reason (a missing or yanked package versus a platform or tool change). This is a cross-day check at +8 days (B6 ran on 2026-10-12 and -13), not a cross-month one; the second point at +30 days is added to this note when run. Nothing in E1 is a hypothesis test; it is a stability measurement with one threshold.
