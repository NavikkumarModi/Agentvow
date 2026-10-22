# Monetisation plan (2026-10-22): the owner's priority is revenue; this is the fastest honest path

Decision (owner, 2026-10-22): monetisation is not optional and comes first. Unchanged by it: Agentvow's core stays open source (MIT), no hosted execution of customer code yet, and every claim made to a customer or in marketing stays within what the studies measured (feasibility scale, Python, reproduction is not correctness). Market facts are `[snippet]` (see `MARKET_AND_MONETIZATION_2026-10.md`); two platform facts below are also snippets: branch protection can require a status check from one named GitHub App, and a paid GitHub Marketplace plan needs an organisation that is a verified publisher, with a guidance of 100 installations for an app and a 5% fee reported (unverified; read the Marketplace Developer Agreement).

## 1. What is sold (working name: Agentvow Gate)
The open tier stays free: CLI, hooks, the Action (with the opt-in `run-tests`), local receipts. The **paid tier is a hosted control plane that never executes customer code**: execution happens in the customer's own runner or machine, as today. It does four things the open tier cannot:
1. **A required check from a named GitHub App** that turns the evidence into a merge decision under a policy ("reproduced, or UNKNOWN acknowledged by a named human, or blocked"; per repository or organisation).
2. **A receipt store and audit export** per agent pull request: what ran, on which exact state, which contexts reproduced, what was not reproduced, who acknowledged what, with retention and JSON, CSV or PDF export for an auditor.
3. **Policy as a file** reviewed like code, with exceptions and escalation, versioned.
4. **An organisation view** of agent PR volume and the reproduced, unknown and contradicted rates over time.
Receipts reach the service from the customer's workflow, authenticated with the GitHub Actions OIDC token (proves repository, ref and workflow without a shared secret), so the local HMAC key is never shared. What is uploaded is the decision record only (no source code, no environment values; file names and variable names are in it, so it is treated as sensitive).
**Why someone might pay (unproven):** governance and audit pressure for agent-written code is reported by vendor guides and surveys; a deterministic, non-LLM gate that an auditor can point at differs from an LLM reviewer's comment; the receipt's "what was NOT reproduced" list is a stated-limits record. **Unproven:** that any team will pay for this, and that a reviewer vendor or GitHub will not ship the same.

## 2. Pricing hypotheses (to test with the first paying customers, not to decide)
Benchmarks: reviewers $24 to $48 per user per month; Semgrep-style team tier about $35 per contributor; usage add-on about $1 per review. Hypothesis A: free for public repositories and one private repository with 30-day retention; **Team $15 to $25 per active contributor per month with a $100 monthly minimum**; **Business about $35** with audit export, longer retention and SSO later. Hypothesis B: per gated agent PR ($0.50 to $1) because the value unit is an agent PR. First five paying teams: a founding discount (for example half price for twelve months) in exchange for a case study and a monthly call. Which value metric works is learned from the first partners.

## 3. The fastest route to the first revenue
Not a self-serve marketplace; that needs 100-ish installs and verification first. **A paid pilot sold by the owner:** fixed-price setup (policy file, Action and App installed, a month of monitoring, a written evidence report on the team's real agent PRs), then a subscription. It gives revenue and the learning (buyer, trigger, value metric) at once. I cannot sell, contact anyone or open accounts; the owner does. Targets: teams already using coding agents on real PRs with a review or approval step; start with the owner's own network and open-source maintainers who run agent PRs, then communities where agent-PR pain is discussed.

## 4. Build sequence (what I do, in order; each step ships value alone)
| Phase | Work (mine) | Needs from the owner | Exit check |
|---|---|---|---|
| 0, now, no accounts | Gate B0 from `STAGE1_CAPTURE_PLAN.md`: the portable, content-bound receipt and the key-less verifier; a **policy engine** (open, local, tested) that turns a receipt into allow / block / needs-acknowledgement; a mock control plane in the repository; threat model of the control plane | the policy vocabulary you want customers to see | tests green; B0 pass criteria met |
| 1, accounts | Spec and code of the hosted service (receipt upload with OIDC verification, store, policy evaluation, check-run creation, audit export), small stack on a managed host | an organisation or entity for billing, a domain, a hosting account, a payment route (Stripe or Marketplace), Terms and a privacy policy (a lawyer) | service passes its own security tests; a private repository shows the check on a test PR |
| 2, private beta | GitHub App registered, required check enforced on a pilot repository; the evidence report generator | one to three paying design partners | a real merge blocked or allowed by the gate with the reason shown |
| 3, self-serve | Marketplace listing (verified publisher) and billing events, pricing page, docs | verified-publisher status, install base | first self-serve subscriber |
Gate A (the instructed-agent capture test) waits until a partner needs cloud-agent capture. Hosting execution of untrusted code is out of scope until a customer will not run it themselves.

## 5. Distribution that needs no budget
The measured, honest results are the content: the 91% against 55% study and its limits, the Linux and cross-day checks, the fault-regression and the "what we could NOT verify" habit. Channels: a technical write-up and a Show HN style post, the GitHub Action on the Marketplace (free listing), the MCP and agent-tool directories, the VS Code Marketplace listing, the short paper if accepted. Never claim "verified" or "unique"; say "reproduced, not reproduced, unknown".

## 6. Targets and stop rules (replace the earlier "pause paid development")
Set by the owner: a revenue goal and a date. Proposed defaults: **day 45: at least one signed paid pilot; day 90: at least three paying teams or one team at the Business tier.** If ten qualified conversations produce no paid commitment, change the product or the buyer before writing more code (the problem, not the effort, is what is being tested). Leading indicators to track from day one: installs, Action runs on other repositories (opt-in count only), conversations, pilots, paid pilots. No telemetry is added to the open tool without a published opt-in design.

## 7. Risks, said plainly
Demand is unmeasured; a solo operator has little sales capacity; GitHub or a reviewer vendor can ship a gate; the paid layer stores sensitive metadata and so carries privacy, security and compliance obligations (and later SOC 2) that cost more than the code; Marketplace billing needs a verified organisation; the evidence behind the product claims is feasibility-scale. The mitigations are the gates above, the minimal data uploaded, and not scaling before a paying customer exists.

## 8. Decisions for the owner now
1. A revenue goal and a date; 2. the legal and billing entity and the payment route; 3. five names you can approach, and whether you will sell the first pilot yourself; 4. whether the hosted service may be closed source while the CLI and Action stay MIT; 5. hosting and domain accounts; 6. whether I may start phase 0 (B0 and the policy engine) now. Phase 0 needs none of the accounts.
