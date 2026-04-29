---
name: backlog-add
description: Capture a new feature, bug, or tweak idea into the project backlog at .planning/backlog/<slug>.md. Runs a short grilling pass against the existing domain model (CONTEXT.md, ADRs, code) so the entry is sharper than a one-liner. Use when user wants to add to the backlog, capture an idea, log a bug or tweak for later, or build up a queue of work to later promote into a PRD.
---

# Backlog Add

Capture an idea into `.planning/backlog/<slug>.md` after grilling it briefly against the codebase. The output is a self-contained markdown file that can later be picked up by `backlog-promote` to feed into `to-prd` and `to-issues`.

## Process

### 1. Get the seed

The user will pass a one-liner or a short paragraph as the idea. If they passed nothing, ask for the seed in one sentence and stop until they reply.

### 2. Pick a slug and check for collisions

Slugify the idea into 3–6 lowercase-hyphen words (e.g. `customer-cancel-partial-order`). If `.planning/backlog/<slug>.md` already exists, surface that to the user and ask whether to append, overwrite, or pick a new slug — do not silently overwrite.

If `.planning/backlog/` does not exist, create it.

### 3. Grill — but keep it short

Run a focused grilling pass following the spirit of the `grill-with-docs` skill, with these constraints to keep capture cheap:

- **Cap at 5 questions.** This is a backlog entry, not a PRD. Stop early once the entry has enough shape to be promoted later.
- Ask **one question at a time** and wait for the user's answer before continuing.
- Skip questions you can answer yourself by reading `CONTEXT.md`, `CONTEXT-MAP.md`, `docs/adr/`, or the code — answer them silently and move on.
- Challenge fuzzy or overloaded terms against the existing glossary in `CONTEXT.md`. If the user uses a term that conflicts with a defined one, call it out and resolve it.
- Probe for the **one or two** decisions that would block writing a PRD later (the user the feature serves, the scope boundary, the success signal). Anything beyond that is premature for a backlog entry.

If during grilling a domain term is resolved or an ADR-worthy decision crystallises, update `CONTEXT.md` / `docs/adr/` inline as `grill-with-docs` would. Do not batch.

If the user says "skip the grilling" or "just save it", skip step 3 entirely and go to step 4 with whatever shape the seed has.

### 4. Write the file

Write `.planning/backlog/<slug>.md` using this template:

```markdown
---
type: feature | bug | tweak | chore
status: backlog
created: <YYYY-MM-DD>
---

# <Title — short, descriptive>

## Summary

One or two sentences capturing the idea in its sharpest form after grilling.

## Why

The motivating problem, observed pain, or user signal. Skip if the seed truly had no "why" attached.

## Open questions

- Question 1 (if any survived grilling)
- Question 2

Or "None" if grilling resolved everything.

## Notes

Anything that came out of grilling that doesn't fit above — adjacent decisions, related code paths, links to ADRs or `CONTEXT.md` terms. Skip the section entirely if empty.
```

Pick `type` based on the seed: a new capability is `feature`, a defect is `bug`, a small adjustment to existing behaviour is `tweak`, anything purely internal is `chore`.

### 5. Confirm

Tell the user:

- The file path that was written
- The current count of items in `.planning/backlog/` (excluding `archive/`)

Do not commit. Do not run `to-prd` or `to-issues` — promotion is a separate step.

## Guardrails

- Never write outside `.planning/backlog/`.
- Never modify or delete other backlog entries — this skill only adds.
- Do not invent acceptance criteria, user stories, or implementation plans. That detail belongs in the PRD/issues that come out of `backlog-promote`, and adding it now will rot before promotion.
- If the user invokes this skill repeatedly in one session, treat each invocation independently — fresh slug, fresh grilling pass.
