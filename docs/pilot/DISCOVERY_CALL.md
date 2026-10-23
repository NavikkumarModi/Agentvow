# Discovery call guide (20 to 30 minutes)

Purpose: learn whether agent pull requests are a decision someone owns, what triggers the need to show a check, and whether anyone would pay. **Listen; do not pitch.** Write the buyer's own words in the log. Demo only in the last five minutes, and only if they scored as a fit.

## Opening (1 minute)
"Thank you. I am building an open-source check that re-runs a coding agent's 'tests pass' on your CI. I do not know yet whether anyone needs it, so I mostly want to ask about how you work today. Is it fine if I take notes?"

## Questions (pick the ones that fit; the bold ones are the must-haves)
**Their use of agents**
1. **Which coding agents open or write pull requests in your repositories today, and roughly how many a week?** (Count and tool names, not adjectives.)
2. Is that growing, stable, or restricted? Who decided?

**How they decide today**
3. **Walk me through the last agent pull request you merged: who looked at it, what did they look at, how long did it take?**
4. When an agent says "all tests pass", what do you do with that sentence?
5. Has an agent-written change ever broken something after merge? What happened, who found it, what did it cost? (Ask for the specific story.)
6. What do you use today to check these changes (a reviewer tool, required CI, manual review, nothing)? What does it miss?

**Why now / who cares**
7. **Is anyone asking you to show how agent-written code is checked (a customer questionnaire, an auditor, a security team, a board, an insurer)?** Who, and by when?
8. Is there a written policy about AI-generated code? Who owns it?

**Money and decision**
9. **If this existed and worked, who would pay for it, from which budget?** Who else must say yes (security, legal, procurement)?
10. What do you pay today for tools in this area, and how did you decide to buy them?
11. What would make you stop a pilot after two weeks?

**Fit for a pilot**
12. Is there one Python repository with tests that run on a Linux runner and that agents already change? Could we add one workflow file?
13. Is there one named person who could acknowledge an unconfirmed result within a working day?

## Scoring (2 = clear, 1 = partial, 0 = none; a pilot needs 9 or more and a 2 on the starred items)
| Signal | Score |
|---|---|
| \* Agent pull requests are merged now, at a volume of at least a few a week | |
| \* Someone is asked to show how they are checked (a named trigger and date) | |
| \* The person you are talking to owns the merge decision or the budget, or can name who does | |
| A story of an agent change that cost them something | |
| Dissatisfaction with what they use now | |
| A Python repository fit and a named acknowledger | |
| Willingness to say a price range or a budget owner | |

## Red flags (say so in the log and stop spending time)
No agent pull requests yet ("we are exploring"); no trigger and no owner; interest in an LLM reviewer rather than an independent check; the only repository is not Python or its tests cannot run in CI; a request for a guarantee that defects will be prevented; wanting it free plus a case study.

## Closing (2 minutes)
"What I heard is [two sentences in their words]. Did I get it right? What would you want to see before you could say yes or no to a 30-day pilot? Who else should I talk to?" Never leave without a next step with a date, or an explicit "no".

## After the call (within a day)
Fill the log below and the row in `PROSPECTS_TEMPLATE.csv`; send message D from `OUTREACH.md` only if the score qualifies.

## Call log
Date / name / role / organisation:  
Agents and weekly volume:  
How they decide today (their words):  
Story of a cost or incident:  
Trigger (who asks, by when):  
Tools in use and their gaps:  
Budget owner / other approvers:  
Rubric score (and the starred items):  
Pilot fit (repository, runner, acknowledger):  
Price or budget range they said (if any):  
What they asked for that we do not have:  
Next step and date / outcome:  

## What counts as learning (the stop rule from the monetisation plan)
After ten qualified conversations, count: how many named a trigger, how many named a budget owner, how many asked for a pilot, how many asked for something else. If none asked for a pilot, change the buyer or the product before writing more code. If several asked for the same other thing (for example only the evidence report, or a different CI), follow that and say so.
