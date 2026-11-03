# Agentvow 0.5.1

Agentvow checks what a coding agent says it did against what it can independently observe. It informs you; it never approves, rejects or merges, and no language model decides a verdict. Still a prototype, not a safety verdict.

## New: `agentvow queue`, a ranked list of what needs a person
`agentvow queue --receipts ./receipts` reads a folder of receipts and your policy and lists the agent pull requests in order: **stop** (a check contradicted the agent), **needs a person**, **acknowledged**, **no flag raised**, each with the policy's plain-language reasons. The latest receipt per commit counts. The exit code is 1 when anyone is needed, and `--markdown` writes a page you can share. It re-evaluates receipts with the existing policy engine and adds no judgement of its own. "No flag raised" means no rule asked for a person; it is never described as safe.

`agentvow queue --github OWNER/NAME` reads the gate's receipts for a repository's open pull requests with `gh` (read-only), so no hand-made folder is needed. A receipt is kept only if it is valid and names that repository and head commit; pull requests without a usable receipt are listed as "no receipt", which is no information, not a clean result. **The receipts come from workflow artifacts and are not authenticated** (a pull request can edit its own workflow); the control plane is the authenticated path. **Tested against a fake `gh` only; not yet run against a repository with open gated pull requests.**

## Improved: the TypeScript public-API check (optional engine from 0.5.0)
- A **name-limited re-export** (`export { a } from "./x"`, or importing a name and exporting it) makes only that name public. Other names in the same file are reported as "not re-exported from the package entry" instead of as breaking changes. `export *` passes on whatever is public in the re-exporting file.
- **Every subpath in `package.json` `exports`** is an entry, not only the root (data and style targets are ignored).
- A wildcard re-export is a **gap only when it changed**. Before, any `export *` in an entry made the result UNKNOWN.
- **How much this helps is not established.** On the 15 real pull requests flagged earlier, nothing changed (3 public-API findings kept, 12 explained as private, not re-exported or no entry). Recall against real breaking changes has not been measured.

## New: the same public-API check reads JavaScript
`.js`, `.jsx` and `.mjs` files are compared with the same rules as TypeScript (only public package API counts; compiled output, bundles and tool configuration are never compared). **CommonJS exports (`module.exports`, `exports.x`) are a gap, not a pass**, and a file that does not parse is a gap. On 22 real pull requests with JavaScript source the engine found no public-API change, so the yield is low.

## Known limits
Python and, optionally, TypeScript and JavaScript only for the public-API check (no Go, Java or other languages; CommonJS is a gap); behaviour changes stay unchecked. A re-export alias is not tracked through a second hop (this can only over-include names). The queue's order is the policy's order, not a reliability ranking.
