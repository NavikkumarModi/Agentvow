# Monetisation update (2026-10-23): what is built, what GitHub requires, and the routes to revenue

Supersedes nothing: it updates `MONETISATION_PLAN_2026-10.md` with what has happened since (phases 0 and 1 are built) and with GitHub Marketplace requirements read on 2026-10-23 from GitHub's documentation. Everything about willingness to pay is still **unproven**: nobody outside this project has used the product.

## 1. Where the plan stands
| Plan phase | State |
|---|---|
| 0: receipt, bundle, policy engine, gate workflow, pilot report, mock | **Done and published** (0.4.0 to 0.4.2) |
| 1: hosted control plane service | **Built, reviewed twice, run once against real GitHub**; also has account plans, retention, erasure after uninstall, a dashboard, backup, a deployment recipe. **Not deployed** |
| 2: private beta with paying design partners | Blocked on you: an entity, a price, five prospects, a domain and hosting |
| 3: self-serve / Marketplace | Later; see section 2 |

What is sellable today without any further code: the open tool (free), a **paid pilot** (setup, a month of monitoring, an evidence report on a team's real agent pull requests; offer drafted in `docs/pilot/PAID_PILOT_OFFER.md`), and, once a host exists, the hosted gate for a small number of named customers whose plan you set by hand (`cli set-plan <owner> team`).

## 2. What GitHub Marketplace requires (GitHub documentation, read 2026-10-23)
* **Free listing:** the app must be public (not preview or invite-only), the Developer Agreement accepted, webhooks for plan changes and cancellations handled. **No publisher verification and no minimum installs are stated.**
* **Paid plans:** the app must be **owned by an organisation that is a verified publisher** (a personal-account app must be transferred); GitHub Apps "should have at least 100 installations"; financial onboarding; the app must handle purchase events for new purchases, upgrades, downgrades, cancellations and free trials, and **support monthly and annual billing**; customers pay with the payment method on their GitHub account; only organisation owners can submit. Revenue share and review time are **not stated** on the pages read (an earlier snippet said about 5%: unverified).
* Consequence: **register the production App under a GitHub organisation from the start** (moving it later is a transfer, and an organisation is needed for any sale), list it free to collect installs, and bill the first customers directly. Marketplace paid plans are a later channel, not the first revenue.

## 3. Routes to revenue, in the order I recommend
| # | Route | What it needs | Speed | Main risk |
|---|---|---|---|---|
| R1 | **Paid pilot sold by you** (fixed fee, then a subscription) | an entity or sole-trader invoicing, a price you can say aloud, 5 names | days to weeks | you are the sales team; the first buyer may want a different product |
| R2 | **Hosted subscription, billed directly** (invoice or payment link; plan set by CLI) | a deployed service, terms and privacy policy, a payment route | weeks | privacy and security obligations cost more than the code |
| R3 | **Support and private deployment** (the service runs in the customer's own environment; you sell setup, updates, support) | the container (done), a support offer, a licence decision (below) | weeks | small customers will self-host for free and never pay |
| R4 | **Marketplace** (free listing first, paid plans later) | an organisation-owned App; for paid: verified publisher, about 100 installs, billing events | months | install base takes distribution you do not have yet |
| R5 | **Evidence reports as a service** (the pilot report on its own, no subscription) | nothing new | immediate | consulting does not scale; it does teach |

## 4. The decision that shapes everything: the licence of `controlplane/`
The service is in the public repository under **MIT**: anyone can self-host it free, and a competitor could host it. That is fine if what is sold is **trust and convenience**, not code: a hosted instance you operate, backups, retention, named support, an audit export an auditor accepts, organisation features (SSO later), and the stated limits. It is a problem if the plan is to charge for the code. Options, **your call**: (a) keep MIT and sell hosting and support (maximum adoption, lowest moat); (b) move `controlplane/` to a source-available licence (for example BSL or ELv2) that forbids offering it as a hosted service, while the CLI, hooks and gate stay MIT (open core; some users will object); (c) keep the service private. I would choose (b) if you want a business and (a) if you want adoption first; I will not change a licence without your decision.

## 5. Value metric and price hypotheses (to test, not to decide)
* **Cost to serve is tiny:** one small host, SQLite, receipts of a few KB. Marginal cost per repository is cents; the costs are legal documents, support, sales time, and your attention. So price on **value and risk**, not on cost.
* **Value metric candidates:** per repository (simple, but gameable), per active contributor (matches reviewer tools; $24 to $48 per user per month and about $35 per contributor are `[snippet]` benchmarks), per agent pull request (matches the pain, volatile). For the first customers use **a flat monthly fee per organisation** (simplest to sell and invoice), and move to per-contributor when there are ten.
* **Starting hypotheses:** pilot: fixed setup fee plus a first month, in the low thousands; subscription: Team about $100 to $300 per organisation per month, Business about $500 to $1,500 with longer retention, audit export and priority support. The code already enforces plan limits (receipts per month, retention 30/365/730 days, private repositories need a paid plan). **Arithmetic, not a forecast:** at $300 per organisation per month, ten organisations is $3,000 a month.
* **Free tier:** public repositories and one private repository, 30-day retention. It exists to create installs and proof.

## 6. Who buys and how to reach them (no budget)
Buyer hypothesis: an engineering or security lead at a team that already lets coding agents open pull requests and has a reason to show a gate (regulated sector, customer security questionnaires, an incident). Reach them with what is real and measured: the staged gate recording, the live pull-request screenshot, the 91% against 55% capture study with its limits, the honest "what could not be reproduced" list. Channels: a technical write-up, a Hacker News style post, the GitHub Action listing, the VS Code Marketplace listing, the MCP and agent-tool directories, the short paper if accepted, and **direct conversations** (the only channel that tests willingness to pay). Never claim defects prevented or time saved: the product has not shown either.

## 7. What I would build next for revenue (my part)
1. Deploy on your accounts once they exist and run the acceptance tests again on the real host.
2. An **audit PDF** of a repository's decisions (what an auditor asks for) and an **organisation view** of agent pull-request volume and reproduced/unknown/contradicted rates over time.
3. **Notifications** (a Slack or email message when a pull request needs acknowledgement), because the acknowledgement flow is where a human waits.
4. Fork pull requests (a designed, reviewed path), and **GitLab or other CI** if conversations show GitHub-only is the limit.
5. A third adversarial review after any further change to the service, and before the first customer's receipts.
Not now: hosted execution of customer code, a billing integration (no payment route chosen), SSO.

## 8. Decisions I need from you, with my recommendation
1. **Revenue goal and date** (the plan proposed: a signed paid pilot by day 45, three paying teams by day 90). *Recommend: keep them; a goal is what makes the stop rule below real.*
2. **Entity and payment route.** *Recommend: whatever lets you issue an invoice this month (even sole trader); Stripe payment links or bank invoice; defer Marketplace billing.*
3. **Licence of `controlplane/`** (section 4). *Recommend (b) if you want a business.*
4. **Five names** you can approach and whether you will run the first conversations yourself. I can prepare the pilot offer, a one-page overview, an outreach script, a discovery-call question list and a pilot evidence report on your own repositories.
5. **Organisation for the production App**, a domain and a host (the deployment recipe is `docs/DEPLOY.md`).
6. **Privacy policy, terms and a data-processing statement** from a lawyer before any customer sends receipts.

## 9. Stop and change rules
If ten qualified conversations produce no paid commitment, change the buyer or the product before writing more code: that tests the problem, not the effort. If a buyer pays for something other than the gate (for example only the evidence report), follow the money and say so. If GitHub or a reviewer vendor ships a comparable required check, the differentiator that remains is the independent replay and the stated-limits record, and the plan must say whether that is enough.
