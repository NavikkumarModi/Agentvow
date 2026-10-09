# Agentvow Development Rules

## Mission

Agentvow is a research-first project. The goal is not to build a generic agent dashboard.

The central research question is whether an independent, evidence-grounded model of system reality can identify decision-changing divergences between agent claims and observable reality.

## Research before implementation

Never implement a research-critical mechanism before checking current literature, open-source systems, commercial products, standards and patents. Gate status lives in `docs/research/NOVELTY_BOUNDARY.md`.

## Evidence discipline

Never treat agent output as evidence merely because the agent states it confidently.

Separate: CLAIM / OBSERVATION / EVIDENCE / INFERENCE / ASSUMPTION / UNKNOWN.

## Reuse

Before doing new verification work: search existing work and evidence. Reuse valid evidence. Revalidate stale evidence. Never repeat work unnecessarily.

## Independence

Do not treat another LLM's agreement as independent verification. Prefer independent deterministic, external, runtime, structural or policy evidence. Independence is a vector (framing / evidence / mechanism / authority), never a single score.

## Unknown

UNKNOWN is a valid and important result. Do not convert missing evidence into confidence.

## User communication

The default UI must explain decisions in plain language. Simplify language without removing important uncertainty, scope, consequence or evidence.

## Human agency

Agentvow informs the human. It does not silently approve, reject, deploy, merge or alter the user's system.

## Research honesty

Never describe a component as novel until the SOTA and prior-art review supports that statement. When uncertain, write: "Potential gap requiring further verification."

Source-status labels used in docs: `[snippet]` = seen only in a search result summary; `[read]` = full source read. Do not cite `[snippet]` items as settled fact in a paper.

## Development discipline

Every significant feature requires: design, implementation, tests, evaluation, documentation.

Do not add dependencies without justification. Prefer existing open standards and mature tools. Do not build a replacement for an existing analyzer unless there is a demonstrated research reason.

## Verdict-path rule

No LLM sits in the verdict path. LLMs may propose (claim extraction, counter-reality hypotheses); deterministic collectors and checkers decide SUPPORTED / CONTRADICTED / STALE / UNKNOWN.

## Adversarial review

Run the adversarial-reviewer before every major milestone. Its job is to falsify the idea.
