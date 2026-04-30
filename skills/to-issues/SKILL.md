---
name: to-issues
description: Break a plan, spec, or PRD into independently-grabbable issue files using tracer-bullet vertical slices. Saves one markdown file per issue to .planning/issues/ in the project root. Use when user wants to convert a plan into issues, create implementation tickets, or break down work into issues.
---

# To Issues

Break a plan into independently-grabbable GitHub issues using vertical slices (tracer bullets).

## Process

### 1. Gather context

Work from whatever is already in the conversation context. If the user passes a GitHub issue number or URL as an argument, fetch it with `gh issue view <number>` (with comments).

### 2. Determine PRD context

Check if `.planning/.latest-prd` exists. If it does, read the `<prd-slug>` from it. This tells you which PRD the issues belong to (e.g. `multi-tenant-auth`). If there is no `.planning/.latest-prd` file, derive a short kebab-case slug from the current conversation and write it to `.planning/.latest-prd` yourself so subsequent issues use the same slug.

### 3. Explore the codebase (optional)

If you have not already explored the codebase, do so to understand the current state of the code.

### 4. Draft vertical slices

Break the plan into **tracer bullet** issues. Each issue is a thin vertical slice that cuts through ALL integration layers end-to-end, NOT a horizontal slice of one layer.

Slices may be 'HITL' or 'AFK'. HITL slices require human interaction, such as an architectural decision or a design review. AFK slices can be implemented and merged without human interaction. Prefer AFK over HITL where possible.

<vertical-slice-rules>
- Each slice delivers a narrow but COMPLETE path through every layer (schema, API, UI, tests)
- A completed slice is demoable or verifiable on its own
- Prefer many thin slices over few thick ones
</vertical-slice-rules>

### 5. Quiz the user

Present the proposed breakdown as a numbered list. For each slice, show:

- **Title**: short descriptive name
- **Type**: HITL / AFK
- **Blocked by**: which other slices (if any) must complete first
- **User stories covered**: which user stories this addresses (if the source material has them)

Ask the user:

- Does the granularity feel right? (too coarse / too fine)
- Are the dependency relationships correct?
- Should any slices be merged or split further?
- Are the correct slices marked as HITL and AFK?

Iterate until the user approves the breakdown.

### 6. Create the issue files

For each approved slice, write a markdown file to `.planning/issues/` in the project root. Create the directory if it doesn't exist.

Name files with:
- A zero-padded number prefix in dependency order (blockers first)
- The `<prd-slug>` from `.planning/.latest-prd`
- A short description slug

For example: `01-multi-tenant-auth-setup-schema.md`, `02-multi-tenant-auth-api-endpoint.md`

Use the template below for each file. Reference the correct PRD file path (the one with the slug).

<issue-template>
## Parent

[prd-<prd-slug>.md](../prd-<prd-slug>.md) (if `.planning/.latest-prd` exists, otherwise `[prd.md](../prd.md)` or omit)

## What to build

A concise description of this vertical slice. Describe the end-to-end behavior, not layer-by-layer implementation.

## Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Blocked by

- Blocked by [01-<prd-slug>-setup-schema.md](./01-<prd-slug>-setup-schema.md) (use the same `<prd-slug>` prefix for all blocker references)

Or "None - can start immediately" if no blockers.

</issue-template>
