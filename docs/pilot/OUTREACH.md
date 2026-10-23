# Outreach scripts (drafts; nothing has been sent; you send them)

Rules for every message: say what it does in one sentence, say what it does **not** do, ask for 20 minutes to *learn*, never claim defects prevented or time saved (the product has not shown either), never attach customer data. Replace the brackets.

## A. Cold email to an engineering or security lead
**Subject:** How do you decide an agent's pull request is safe to merge?

Hi [name],

[One sentence on why them: for example, "your team's public repositories show agent-authored pull requests" or "you wrote about reviewing AI-generated code".]

I build an open-source tool that re-runs a coding agent's "all tests pass" in a locked-down sandbox on your own CI and tells you whether it reproduces, what could not be checked, and what a person still has to confirm. It does not review the code or claim it is correct. On a pull request it is one required check: a contradicted claim blocks the merge, an unconfirmed one waits for a named person.

I am looking for one team that already merges agent-written pull requests for a 30-day paid pilot on one repository, with a written evidence report at the end. Before anything else I would like 20 minutes to learn how you decide today whether an agent's pull request is safe to merge, and who owns that decision.

Short demo (a real pull request blocked by the check): [link to the README].
[Your name]

## B. Short message (LinkedIn, Slack community, X)
"Building an open-source check that re-runs a coding agent's 'all tests pass' on your own CI and says reproduced / contradicted / could not confirm. Looking for one team that merges agent PRs to learn how you decide what is safe to merge. 20 minutes? Demo: [link]"

## C. Asking for an introduction
"I am looking for a team that already merges pull requests written by coding agents, ideally in a setting where someone has to show how those were checked. I would like to ask them how they decide today. Do you know one person I should talk to? Two lines you can forward: [paste A's second paragraph]."

## D. After a first call
"Thank you for the time. What I heard: [their words: the trigger, who decides, what they use today]. If useful, the next step is a free 30-minute run of the gate on one public repository of yours (or a fork) so you can see what the output looks like on your own code; nothing is installed on your infrastructure. If it is not useful, I would still value one sentence on why." (Only offer the free run if the discovery rubric in `DISCOVERY_CALL.md` scores them as a fit.)

## E. Follow-up after silence (once, after 7 days)
"Following up once: if agent pull requests are not a decision you own, who does? A name is as useful as a meeting."

## What not to say
"Prevents bugs", "saves review time", "verifies agent code", "AI-powered" (no model decides), "secure" (it is a prototype and says so), any customer name or number we do not have, any comparison to a named competitor's quality. If asked about competitors: say what Agentvow does differently (independent replay, no model in the verdict, a stated list of what could not be reproduced) and that you have not benchmarked against them.

## Where to find the first five (suggestions to test, not a list I verified)
Teams whose public repositories show agent-authored pull requests (the dataset behind the study came from there); companies that publish engineering posts about governing AI-generated code; regulated-sector engineering leads you already know (finance, health, public sector) where customer security questionnaires ask how code is checked; maintainers of open-source projects overwhelmed by agent pull requests (free use, for proof and adoption, not revenue). Track every contact in `PROSPECTS_TEMPLATE.csv`.
