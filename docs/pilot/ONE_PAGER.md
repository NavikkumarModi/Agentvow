# Agentvow: a second check on "all tests pass"

*For an engineering or security lead whose team merges pull requests written by coding agents. One page; plain words. Nothing here is a promise of defects prevented or time saved.*

## The problem
Your agent says "I added the feature, all tests pass". The only evidence is the agent's own message and test output that the pull request's own code produced. Today a person either trusts it or re-runs everything.

## What Agentvow does
It re-runs the claim **outside the agent**, in a locked-down sandbox on **your own CI runner**, and tells you in plain language one of three things: the claim was **contradicted** (a test that passed before now fails), it was **supported** (the replay passed, with the basis stated), or it **could not be confirmed** (UNKNOWN, with the reason and the next step). It also says how much of the changed code the tests actually ran and what the replay could not recreate (services, secrets, system packages). No AI model decides any verdict.

On a pull request this becomes one required check, `agentvow/evidence`: a contradiction blocks the merge and cannot be waved away; an unconfirmed claim waits for a **named person** to acknowledge it, and that acknowledgement is recorded. The rules are a small policy file reviewed like code and read from your main branch, never from the pull request.

## What it is not
Not a code reviewer, not a security scanner, not a proof of correctness. A pass means the replay passed; the code under test writes the test output. It covers Python repositories today and runs on Linux and macOS runners. The results behind it are small-scale (one model family, small samples); we will show you the study and its limits.

## How a pilot works (30 days, one repository)
Week 0: we install the gate (one workflow file), write the first policy with you, run a test pull request together. Weeks 1 to 4: every agent pull request gets the check and a plain-language comment; a short weekly note lists the changes that needed attention. End: a written evidence report on **your** pull requests and a 45-minute readout where we decide together to continue, change or stop. If you stop you keep the receipts, the report and the free tool.

## What stays with you
The tool is open source (MIT) and runs only on your runners. In the pilot **no code and no data leaves your infrastructure**; the receipt holds verdicts, counts and category names only (no source, no free text, no environment values). A hosted service that stores receipts exists and has been run once against real GitHub; it is optional and not part of a first pilot.

## What we need
One Python repository whose tests run on a Linux runner, permission to add one workflow, one named person to acknowledge unconfirmed results, about two hours at the start and one at the end.

## Proof you can look at today
The recording and screenshots in the repository README (a real pull request blocked by the check), a sample report (`docs/pilot/SAMPLE_REPORT_LIVE_TEST.md`) and the limits (`docs/EVIDENCE_AND_LIMITS.md`). Price: [to be agreed with the first partner].
