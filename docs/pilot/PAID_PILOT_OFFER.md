# Paid pilot: independent evidence for your agent pull requests (DRAFT for the owner; nothing here has been sent to anyone)

Status: a draft offer. Price, dates, legal terms and the entity are placeholders for the owner and a lawyer. It can be delivered with the product as it will exist at release 0.4.0 (the gate workflow, receipts, policy and `agentvow pilot-report`); **it cannot be delivered before that release is published.** No hosted service is needed for the pilot: receipts are collected from the workflow's artifacts.

## 1. The offer in plain words
For 30 days, every pull request your coding agents open on one repository goes through a check that **re-runs the agent's "tests pass" in a separate, locked-down sandbox on your own CI runner**, compares it with what your repository's own files can reproduce, and records a small receipt. A policy you write decides what is allowed, what needs a named person's acknowledgement, and what is blocked (a contradiction always blocks). At the end you get a written evidence report and a 45-minute readout. The tool is open source (MIT); you can read it and keep using the free parts afterwards.

## 2. What you get
1. **Setup (week 0):** the gate installed on one repository; a first policy written with you; a test pull request run together; written notes of what the replay can and cannot recreate for your project.
2. **Weeks 1 to 4:** the gate runs on every agent pull request; each gets a comment with the verdict, the reason, what could not be reproduced and a next step; a short weekly note listing the changes that needed attention.
3. **Evidence report (end of week 4):** see `docs/pilot/EXAMPLE_REPORT.md` (synthetic data): decisions, verdicts, how reproducible the results were, how much of the changed code the tests ran, what the replay could not recreate, the changes that were not simply allowed, rule-based recommendations, and the limits.
4. **Readout and a go/stop/change decision** with you (section 5).

## 3. What we need from you
One repository (Python; tests that can run on a Linux runner); permission to add one workflow file; the agents you use and who reviews their pull requests; one named person who will acknowledge UNKNOWN results; a first policy decision (what blocks, who acknowledges); about two hours in setup and one in the readout.

## 4. What is and is not promised
**Promised:** the tool runs only on your runners (the workflow installs Agentvow from PyPI at a version we agree; in the pilot nothing is uploaded to any service); no code leaves your infrastructure; the receipt contains verdicts, counts and category names and nothing else (no source, no free text, no environment values; the example report and `docs/GATE_WORKFLOW.md` list every field); you can read, change and delete the policy; the report is built mechanically from the receipts.
**Not promised:** that any change is correct, that defects will be prevented, or that review time will fall. A pass means the replay passed; the pull request's own code writes the test output. Results behind the product are feasibility-scale (one model family, Python, small samples). Known limits: Python only, Linux and macOS runners, Python packages captured but not system packages, services, generated files or secrets; a replay that needs credentials or network will say UNKNOWN. **Not yet verified on GitHub:** the hosted control plane (not used in the pilot) and a fork pull request.

## 5. Agreed success criteria (set with you in week 0, written down, reviewed at the readout)
Examples to choose from, not promises: at least N agent pull requests gated; the named acknowledger responds to needs-acknowledgement results within one working day; at least one result per week that the team says it would not have noticed otherwise; the share of UNKNOWN results falling after the recommended changes; the team's own answer to "would you keep this on, and what would you pay for it?". At the readout: **continue** (subscription), **change** (the policy, the scope, or the product), or **stop** (you keep the receipts, the report and the free tool).

## 6. Terms (placeholders for the owner and a lawyer)
Price: [ ] one-off for setup and the 30 days, then [ ] per active contributor per month or [ ] per gated pull request (to be decided with the first partner; see `docs/strategy/MONETISATION_PLAN_2026-10.md`). Founding-partner discount: [ ]. Payment terms, liability limit, confidentiality (the receipts and the report belong to the customer; no case study without written consent), data handling (receipts stay in the customer's artifacts; if a hosted service is later used, a data-processing statement), termination at the end of any week.

## 7. Outreach note the owner can adapt (not sent)
> I build an open-source tool that re-runs a coding agent's "all tests pass" in a locked-down sandbox on your own CI and tells you whether it reproduces, what could not be checked, and what a human still has to confirm. It does not review the code or claim it is correct. I am looking for one team that already merges agent-written pull requests to run a paid 30-day pilot on one repository, with a written evidence report at the end. Could we talk for 20 minutes? What I would want to learn from you first: how you decide today whether an agent's pull request is safe to merge, and who owns that decision.

## 8. Owner checklist before the first conversation
Release 0.4.0 published (receipt, policy, gate, pilot-report); a price you are willing to say; the entity and a contract template; a named prospect list (five); a fixed 30-minute demo on a public repository using the gate and `EXAMPLE_REPORT.md` (clearly labelled synthetic); the questions of section 7 of `docs/strategy/STAGE1_CAPTURE_PLAN.md` as the interview guide.
