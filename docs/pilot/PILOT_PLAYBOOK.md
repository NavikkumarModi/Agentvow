# Pilot playbook: delivering the 30-day pilot with what exists today

Status 2026-10-23: everything below uses released software (Agentvow 0.4.2 from PyPI, `gate.yml`, `agentvow policy`, `agentvow pilot-report`). The hosted control plane is optional and **not used in a first pilot** (no data leaves the customer). Who does what: the person marked *you* talks to the customer, signs and invoices; *I* prepared the material and can generate the files and reports; the customer's own people merge and acknowledge.

## Before the pilot
* Signed pilot letter (terms in `PAID_PILOT_OFFER.md` section 6, with a lawyer's review), the price agreed, one named contact and one named acknowledger on their side. *You.*
* Their repository: Python, tests runnable on a Linux GitHub-hosted runner, agents already open pull requests. If tests need services or secrets, say so now: the replay will report UNKNOWN for those, and the pilot should say it early, not at the readout.

## Week 0: setup (about two hours with them)
1. **Install the gate.** Add `.github/workflows/agentvow-gate.yml` calling the **local-decision** workflow, pinned to a full commit sha of the Agentvow repository (never a branch; a sha is also what a security review expects). It needs no credential at all:
   ```yaml
   name: agentvow-gate
   on: pull_request
   permissions: { contents: read }
   jobs:
     gate:
       uses: NavikkumarModi/Agentvow/.github/workflows/gate.yml@<40-character commit sha>
       with: { fail-on: block, policy-path: agentvow-policy.json }
   ```
   `gate.yml` (two jobs, `contents: read` only) is new on 2026-10-26; **it has not yet been run on GitHub in this form**: run it on a throwaway repository first (`docs/GOLDEN_PATH.md`). The earlier single workflow ran in local mode with an `id-token: write` grant that the new file no longer needs. `docs/GATE_WORKFLOW.md`.
2. **Write the first policy with them**, in the repository's **default branch**: `agentvow-policy.json` at the root (not under `.agentvow/` on versions before 0.4.1). Start from `agentvow policy init`: contradictions block; UNKNOWN needs acknowledgement; list their acknowledger's GitHub login. Ask what they want stricter (for example a minimum share of changed lines run by tests) and write down why.
3. **Run a test pull request together** that is true, one that is false (break a test), one the replay cannot confirm. Show them each outcome and the plain-language comment.
4. **Write the replay notes**: what the replay can and cannot recreate for this project (services, secrets, generated files, system packages). This list is the most valuable output of week 0.
5. **Set the success criteria** (`PAID_PILOT_OFFER.md` section 5) in writing, including "would you keep this on, and what would you pay".
6. **Optional, with the customer's agreement:** `fail-on: needs_acknowledgement` once the team is comfortable; make the check a required status only after two weeks of watching.

## Weeks 1 to 4
* Each agent pull request gets the gate's summary. Once a week send a note (template below) listing the pull requests that needed attention and what you saw.
* Collect receipts: the gate uploads `agentvow-gate` artifacts (receipt and result) per run; download them with `gh run download` for the period into one folder (names must be unique: put each run's files in its own subfolder, then copy the `receipt.json` files into `receipts/` renamed by run id). Acknowledgements made by comment are visible on the pull requests; for a local-policy pilot record them as `agentvow-ack/1` files (`docs/GATE_WORKFLOW.md`) or in the weekly note.
* Watch for: runs that fail to start (permissions), UNKNOWN caused by missing dependencies (a project-setup fix would turn them into supported), tests that need secrets, and timeouts. Fix the cause with them; each fix is a recommendation for the report.
* If something breaks, treat it as a bug in the product and tell the customer plainly; do not paper over it.

### Weekly note (template)
"Week N: [count] agent pull requests went through the gate: [x] allowed, [y] needed an acknowledgement ([z] acknowledged, median time [..]), [b] blocked. The ones that needed attention: [PR links with one line each, in plain words]. What the replay could not check this week: [list]. One change we suggest: [..]. Anything you want different in the policy?"

## End of week 4: report and readout (45 minutes)
1. Build the report from the receipts: `agentvow pilot-report --receipts receipts/ --acks acks/ --policy agentvow-policy.json --title "<Customer>: 30-day agent pull request evidence" -o report.md`. Read it before sending; add nothing it does not show. It states its own limits and claims no defects prevented and no time saved. A real example of the shape: `SAMPLE_REPORT_LIVE_TEST.md`.
2. Readout agenda: what the gate decided; the three most useful findings (and honestly, whether any was something they would not have noticed); what the replay could not recreate; what to change in the policy or setup; **the question**: would you keep this on, and what would you pay.
3. Decision matrix, agreed in week 0: **continue** (subscription terms; the hosted service only if they want receipts stored and have signed the data terms), **change** (policy, scope or product feature: write down what), **stop** (they keep receipts, report and the free tool; ask why in one sentence).

## After the pilot
Write a 1-page internal debrief: the buyer, the trigger, what they used, what they asked for, the price they said, what failed. Update `PROSPECTS_TEMPLATE.csv`. No case study or number leaves the pilot without the customer's written consent.

## What I can prepare for each pilot on request
The gate and policy files for their repository, the replay notes draft from reading their CI and requirements files (`agentvow` has a project-native baseline reader), the report from receipts, and fixes for any defect the pilot exposes. I cannot contact the customer, sign anything, or run anything on their infrastructure.
