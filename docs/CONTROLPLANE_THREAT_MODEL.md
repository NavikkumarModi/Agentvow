# Control-plane threat model (phase 0 draft, 2026-10-22)

Scope: the paid, hosted service described in `docs/strategy/MONETISATION_PLAN_2026-10.md` and mocked in `controlplane/mock_server.py`. It **never executes customer code and never holds source code**: customers' own runners run Agentvow and upload a receipt (`agentvow-receipt/1`: verdicts, bases, counts, coverage numbers, category names of what was not reproduced; no free text, no environment values, no paths). Items marked **[assumption]** are my understanding of GitHub behaviour and must be confirmed against GitHub's documentation before phase 1; nothing here was verified against a live GitHub App.

## 1. What is protected
Integrity of the merge decision (a required check must not turn green because someone forged evidence); confidentiality of receipt metadata (repository names, file-category names, verdicts; sensitive but not code); availability of the check (a down service must not silently allow merges); the operator's account and signing material.

## 2. Actors
A malicious pull-request author (can change code, workflow files, requirements files, test output); a compromised or careless coding agent (same, plus can write any receipt it likes locally); a malicious or curious customer user; an outsider with network access; a compromised operator or dependency; GitHub itself (out of scope, trusted for identity and tree hashes).

## 3. Threats and mitigations
| # | Threat | Mitigation in the design | Residual risk |
|---|---|---|---|
| 1 | **Forged receipt**: the pull request edits its workflow to upload "reproduced" | Receipts are accepted only with a GitHub Actions OIDC token whose `job_workflow_ref` names the vendor's **reusable gate workflow at a pinned ref** **[assumption: the claim identifies the called reusable workflow]**, so a workflow written in the pull request cannot post. The mock enforces the prefix check. | Customers must call the pinned workflow; a customer who inlines their own steps gets no check |
| 2 | **Receipt for the wrong state** (stale, another commit, another repo) | The receipt carries the git tree hash; the service compares it with the tree of that commit **as GitHub reports it** (API) **[assumption]**, and the token's `repository` must equal the receipt's repository. Mock: `Oracle.tree_of`. | If GitHub's API is unavailable the check fails closed |
| 3 | **Policy weakened by the pull request** (the known ProofRun limitation) | The policy is read from the **base branch**, never from the change; changes to the policy file are themselves a gated event. The mock takes it from an admin endpoint. | Admins of the repository can edit the policy: by design |
| 4 | **Pull request controls the test output and exit code** | Not solvable by the service: stated in the product ("evidence to weigh, not verification"); policy can require reproducibility from the captured and the repository contexts; unauthenticated captures are flagged. | A hostile change can print passing tests; a human still reviews |
| 5 | **Replay of an old receipt or acknowledgement** | Receipts are content-addressed (id = hash of the receipt); an acknowledgement binds to one receipt hash; a changed receipt or commit invalidates it; the check reads the **latest** receipt for the commit | A rollback of the service's database (see 9) |
| 6 | **Acknowledgement by the wrong person** | The identity comes from the authenticated user token, never from the request body; only listed acknowledgers count; a contradiction can never be acknowledged. Phase 1: GitHub OAuth identity and an org-membership check **[assumption]** | An acknowledger can accept a risk knowingly: audited |
| 7 | **Denial of service / cost abuse** | 64 KB body cap, strict schema, idempotent content-addressed storage; phase 1 adds per-repository rate limits and quotas | Needs real limits before launch |
| 8 | **Data exposure** | Minimal receipt; nothing executed or stored beyond it; per-tenant isolation in the database; retention set per plan; export and delete on request; TLS | Repository names and category names are still sensitive metadata; a privacy policy and a data-processing statement are required before customers |
| 9 | **Operator compromise / database tampering** | Receipts are content-addressed (a changed row no longer matches its id); the audit export lists ids so a customer can compare; backups; later: signed audit logs | A fully compromised operator can still lie to the check; SOC 2 style controls come later |
| 10 | **A down service allows merges** | The required check is created by the App: no result means the required check is pending and the merge blocked; the mock answers "no receipt" as `action_required` | The customer can remove the requirement |
| 11 | **Malicious package names in a capture bundle** | Bundles hold plain `name==version` pins only (strict validation); the verifier replays in its sandbox, so this is the same exposure class as any install the replay already does (documented in `SECURITY_MODEL.md`) | An sdist build runs code at install time |
| 12 | **The local signing key leaves the machine** | It never does: the portable bundle and the receipt are unsigned and content-bound; authenticity at upload comes from the OIDC token | None by design |

## 4. What the mock does not model
Real OIDC (RS256 keys from GitHub), the GitHub API oracle, the base-branch policy read, user OAuth, rate limits, tenancy, persistence, billing, logging and alerting, and the installation flow. Those are phase 1 and need accounts the owner has not set up.

## 5. Out of scope on purpose
Hosting execution of customer code (a different and much larger threat model: a sandbox as a service); storing source; acting on a pull request beyond setting the check.
