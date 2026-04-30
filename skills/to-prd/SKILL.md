---
name: to-prd
description: Turn the current conversation context into a PRD with its own sequential ID and save it as <project>-kanban/prds/<id>-<slug>.md. Preserves history — old PRDs are never overwritten, they coexist. Use when user wants to create a PRD from context.
---

# To PRD

Synthesize the current conversation into a product requirements document and save it as a **versioned, numbered PRD** in the project's kanban repo.

Every PRD gets a unique sequential ID (`000001`, `000002`, …) independent from issue IDs. Old PRDs are never deleted or overwritten — they stay in `prds/` with `state: superseded` and a `superseded_by` pointer.

## Prerequisites

The kanban repo must exist. Run this from the project root:

```bash
# Ensure the kanban repo exists
~/projects/renan/agent-tools/scripts/init-kanban-repo

# Ensure reserve-prd-id is available
KANBAN_DIR="$(dirname "$PWD")/$(basename "$PWD")-kanban"
mkdir -p "$KANBAN_DIR/.tools"
cp ~/projects/renan/agent-tools/scripts/reserve-prd-id "$KANBAN_DIR/.tools/reserve-prd-id"
chmod +x "$KANBAN_DIR/.tools/reserve-prd-id"
```

## Process

### 1. Explore the repo

Understand the current state of the codebase, if you haven't already.

### 2. Sketch modules

Sketch out the major modules needed to complete the implementation. Look for opportunities to extract deep modules that can be tested in isolation.

Check with the user that these modules match their expectations. Check which modules they want tests written for.

### 3. Determine supersession

Check whether `$KANBAN_DIR/prds/` already has a PRD covering the same domain. If so, ask the user:

- **Supersede it**: the new PRD replaces the old one. The old PRD gets `state: superseded, superseded_by: <new-ID>`.
- **Independent**: this is a completely separate effort.

If none exists, skip.

### 4. Reserve the next PRD ID

```bash
KANBAN_DIR="$(dirname "$PWD")/$(basename "$PWD")-kanban"
ID=$("$KANBAN_DIR/.tools/reserve-prd-id")
```

`$ID` will be a zero-padded 6-digit string like `000008`.

### 5. Determine the slug

Derive from the topic: lowercase, replace non-alphanumeric runs with hyphens, trim edges (e.g. `piggy-bank-redesign`).

### 6. Write the PRD

Write `$KANBAN_DIR/prds/$ID-$slug.md` using this template:

```markdown
---
type: prd
state: draft | active | superseded
id: <ID>
slug: <slug>
created: <YYYY-MM-DD>
supersedes: <optional: 000001-previous-slug>
superseded_by: <optional: filled later when superseded>
issues: <optional: [000042, 000043] — filled when issues reference this PRD>
---

# PRD <ID>: <Title>

## Problem Statement

The problem that the user is facing, from the user's perspective.

## Solution

The solution to the problem, from the user's perspective.

## User Stories

A LONG, numbered list of user stories. Each user story should be in the format of:

1. As an <actor>, I want a <feature>, so that <benefit>

<user-story-example>
1. As a mobile bank customer, I want to see balance on my accounts, so that I can make better informed decisions about my spending
</user-story-example>

This list of user stories should be extremely extensive and cover all aspects of the feature.

## Implementation Decisions

A list of implementation decisions that were made. This can include:

- The modules that will be built/modified
- The interfaces of those modules that will be modified
- Technical clarifications from the developer
- Architectural decisions
- Schema changes
- API contracts
- Specific interactions

Do NOT include specific file paths or code snippets. They may end up being outdated very quickly.

## Testing Decisions

A list of testing decisions that were made. Include:

- A description of what makes a good test (only test external behavior, not implementation details)
- Which modules will be tested
- Prior art for the tests (i.e. similar types of tests in the codebase)

## Out of Scope

A description of the things that are out of scope for this PRD.

## Further Notes

Any further notes about the feature.
```

Set `state` based on user intent: `draft` if still rough, `active` if ready to guide implementation.

### 7. Update superseded PRD (if applicable)

If the new PRD supersedes an old one, also edit the old PRD file to add:

```yaml
superseded_by: <ID>-<slug>
```

and change its `state` to `superseded`.

### 8. Confirm

Tell the user:

- The full path of the new PRD file (`<kanban-dir>/prds/<ID>-<slug>.md`)
- If an old PRD was superseded, which one
- The total count of PRDs in `prds/`

Do not commit to the kanban repo.

## Guardrails

- Never overwrite an existing PRD file. Always create a new one with a new ID.
- Never write outside `<project>-kanban/prds/`.
- Never prompt for the PRD ID — it is reserved atomically.
- Do not create issue files. Issues are created separately via `backlog-add` or manually.
- If the user asks to iterate on an existing PRD, create a new PRD that supersedes the old one. The old one stays in the repo for history.
