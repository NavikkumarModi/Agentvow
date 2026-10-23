# Agentvow 0.4.2

Agentvow checks what a coding agent says it did against what it can independently observe. It informs you; it never approves, rejects or merges, and no language model decides a verdict. Still a prototype, not a safety verdict.

## Fixed
- **A receipt made after a check that could not collect is valid again.** When a check has no usable base or too little history (for example the first commit of a repository) it reports its commit as `?`. 0.4.1's stricter receipt validation turned such a receipt into a `block`; `agentvow receipt` now records the commit that is checked out, so the receipt is valid and the policy decides as in 0.4.0 (an UNKNOWN claim needs an acknowledgement). Pull requests with a base were not affected. Found by installing 0.4.1 from PyPI after publishing it.

Everything in 0.4.1 is included (content hash counts files the commit tracks under `.agentvow/`, stricter receipts, claim cap, gate workflow audience binding and service-URL allow-list; see its release notes).

## Known limits
As 0.4.0: Python repositories only; capture covers Python packages, not system packages, services, generated files or secrets; running tests needs macOS or Linux; a pass is evidence to weigh, not verification.
