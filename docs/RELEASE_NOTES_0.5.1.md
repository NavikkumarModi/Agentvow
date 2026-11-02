# Agentvow 0.5.1

Agentvow checks what a coding agent says it did against what it can independently observe. It informs you; it never approves, rejects or merges, and no language model decides a verdict. Still a prototype, not a safety verdict.

## New: `agentvow queue`, a ranked list of what needs a person
`agentvow queue --receipts ./receipts` reads a folder of receipts and your policy and lists the agent pull requests in order: **stop** (a check contradicted the agent), **needs a person**, **acknowledged**, **no flag raised**, each with the policy's plain-language reasons. The latest receipt per commit counts. The exit code is 1 when anyone is needed, and `--markdown` writes a page you can share. It re-evaluates receipts with the existing policy engine and adds no judgement of its own. "No flag raised" means no rule asked for a person; it is never described as safe.

## Improved: the TypeScript public-API check (optional engine from 0.5.0)
- A **name-limited re-export** (`export { a } from "./x"`, or importing a name and exporting it) makes only that name public. Other names in the same file are reported as "not re-exported from the package entry" instead of as breaking changes. `export *` passes on whatever is public in the re-exporting file.
- **Every subpath in `package.json` `exports`** is an entry, not only the root (data and style targets are ignored).
- A wildcard re-export is a **gap only when it changed**. Before, any `export *` in an entry made the result UNKNOWN.
- **How much this helps is not established.** On the 15 real pull requests flagged earlier, nothing changed (3 public-API findings kept, 12 explained as private, not re-exported or no entry). Recall against real breaking changes has not been measured.

## Known limits
Python and, optionally, TypeScript only for the public-API check; behaviour changes stay unchecked. A re-export alias is not tracked through a second hop (this can only over-include names). The queue's order is the policy's order, not a reliability ranking.
