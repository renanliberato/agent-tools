---
name: backlog-add
description: Capture a new feature, bug, or tweak idea as an issue file in the project's kanban repo at <project>-kanban/issues/<id>-<slug>.backlog.md. Runs a short grilling pass against the existing domain model so the entry is sharper than a one-liner. Uses sequential IDs (via flock(1)) so files sort naturally even with concurrent agents.
---

# Backlog Add

Capture an idea into the project's **kanban repo** as `<project>-kanban/issues/<NNNNNN>-<slug>.<state>.md`.

Every issue gets a single sequential ID at creation time — that ID never changes regardless of state transitions (backlog → active → done). The `.backlog.md` suffix denotes state; renaming the file changes its state.

PRDs are separate: they live in `<project>-kanban/prds/` with their own independent counter.

## Prerequisites

This skill requires `flock(1)` for atomic ID reservation. Install it if missing:

```bash
# macOS (Homebrew)
brew install discoteq/tap/flock

# Linux — flock is usually in util-linux (pre-installed on most distros)
which flock || sudo apt-get install -y util-linux   # Debian/Ubuntu
which flock || sudo yum install -y util-linux        # RHEL/Fedora
```

The companion tools live under this skill's directory:
- `reserve-backlog-id` — **deprecated**, kept for migration. Replaced by `reserve-issue-id` (see below).
- `/Users/renan.liberato/projects/renan/agent-tools/scripts/reserve-issue-id` — the new atomic issue ID reservation script.

The skill copies `reserve-issue-id` into the kanban repo's `.tools/` on first use.

## Process

### 1. Get the seed

The user will pass a one-liner or a short paragraph as the idea. If they passed nothing, ask for the seed in one sentence and stop until they reply.

### 2. Ensure kanban repo + tools exist

Resolve the kanban repo path from the current project root:

```bash
# From project root (git top-level or cwd)
PROJECT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")
KANBAN_DIR="$(dirname "$PROJECT_DIR")/$(basename "$PROJECT_DIR")-kanban"
```

If `$KANBAN_DIR` does not exist, run `init-kanban-repo` to create it:

```bash
~/projects/renan/agent-tools/scripts/init-kanban-repo
```

Ensure `reserve-issue-id` is available in the kanban repo:

```bash
mkdir -p "$KANBAN_DIR/.tools"
cp ~/projects/renan/agent-tools/scripts/reserve-issue-id "$KANBAN_DIR/.tools/reserve-issue-id"
chmod +x "$KANBAN_DIR/.tools/reserve-issue-id"
```

### 3. Pick a slug

Slugify the idea into 3–6 lowercase-hyphen words (e.g. `customer-cancel-partial-order`). The full filename will be `<ID>-<slug>.backlog.md` where the ID is reserved atomically in step 5.

### 4. Grill — but keep it short

Run a focused grilling pass following the spirit of the `grill-with-docs` skill, with these constraints to keep capture cheap:

- **Cap at 5 questions.** This is a backlog entry, not a PRD. Stop early once the entry has enough shape.
- Ask **one question at a time** and wait for the user's answer before continuing.
- Skip questions you can answer yourself by reading `CONTEXT.md`, `CONTEXT-MAP.md`, `docs/adr/`, or the code — answer them silently and move on.
- Challenge fuzzy or overloaded terms against the existing glossary in `CONTEXT.md`. If the user uses a term that conflicts with a defined one, call it out and resolve it.
- Probe for the **one or two** decisions that would block writing a PRD later (the user the feature serves, the scope boundary, the success signal). Anything beyond that is premature.
- Probe for **blockers** — if the idea depends on another issue being done first, note it for step 7. Ask: "Does this depend on another issue?" when coupling is plausible from context.

If during grilling a domain term is resolved or an ADR-worthy decision crystallises, update `CONTEXT.md` / `docs/adr/` inline as `grill-with-docs` would. Do not batch.

If the user says "skip the grilling" or "just save it", skip step 4 entirely and go to step 5 with whatever shape the seed has.

### 5. Reserve the next sequential issue ID

```bash
ID=$("$KANBAN_DIR/.tools/reserve-issue-id")
```

`$ID` will be a zero-padded 6-digit string like `000042`.

If the tool fails, abort with a clear error message telling the user to install `flock` (see Prerequisites).

### 6. Determine PRD reference (optional)

If the issue belongs to an existing PRD, determine the PRD ID. Read `$KANBAN_DIR/prds/` for existing PRDs and ask the user which one (or "none"). The PRD reference goes into the frontmatter as `prd: <ID>-<slug>`.

If no matching PRD exists, omit the field — the issue is standalone. A PRD can be created later with `to-prd`.

### 7. Determine blockers (optional)

Check whether this issue depends on another issue that must be completed first. Read the existing issues in `"$KANBAN_DIR/issues/"` for candidates.

Probe during grilling (step 4) with a question like "Does this depend on another issue?" if the domain suggests coupling. If the user says yes, capture the dependency.

When this issue has one or more blockers, add a `## Blocked by` section to the file (see template in step 8). Each blocker is a markdown link to the other issue file:

```
## Blocked by

- [000042-other-issue-slug.backlog.md]
```

The `kanban-parse-deps.py` orchestrator reads this section to build the dependency graph. Both `[file.md]` links and bare `\d{6}` IDs are supported.

### 8. Write the file

Write `"$KANBAN_DIR/issues/$ID-$slug.backlog.md"` using this template:

```markdown
---
type: feature | bug | tweak | chore
state: backlog
created: <YYYY-MM-DD>
prd: <optional: 000008-slug>
---

# <Title — short, descriptive>

## Summary

One or two sentences capturing the idea in its sharpest form after grilling.

## Why

The motivating problem, observed pain, or user signal. Skip if the seed truly had no "why" attached.

## Blocked by

(Optional — remove if no blockers. List files this issue depends on.)
- [000042-other-issue-slug.backlog.md]

## Acceptance criteria

(Optional at backlog stage — filled in before moving to active.)

## Open questions

- Question 1 (if any survived grilling)
- Question 2

Or "None" if grilling resolved everything.

## Notes

Anything that came out of grilling that doesn't fit above — adjacent decisions, related code paths, links to ADRs or `CONTEXT.md` terms. Skip the section entirely if empty.
```

Pick `type` based on the seed: a new capability is `feature`, a defect is `bug`, a small adjustment to existing behaviour is `tweak`, anything purely internal is `chore`.

**Important:** Remove the `## Blocked by` section entirely (not just leave it empty) when the issue has no blockers — the parser reads its presence as a signal.

### 9. Commit and confirm

Commit the new issue file to the kanban repo:

```bash
cd "$KANBAN_DIR"
git add issues/
git commit -m "backlog: add $ID-$slug"
```

Then tell the user:

- The full file path that was written (including the kanban repo path and ID)
- The current count of issues in `$KANBAN_DIR/issues/` across all states
- The commit hash
- If the issue has blockers, list them

Do not run `to-prd` — PRD creation is a separate step.

## Guardrails

- Never write outside `<project>-kanban/issues/`.
- Never modify or delete other issues — this skill only adds.
- Never reuse an ID — the tool guarantees uniqueness via `flock`.
- Do not invent acceptance criteria unless the user explicitly provides them. That detail belongs in the active state.
- Issues always get the `.backlog.md` suffix at creation time. State transitions (`.backlog.md` → `.active.md` → `.done.md`) are handled by other skills or scripts (they also commit to the kanban repo).
- If the user invokes this skill repeatedly in one session, treat each invocation independently — fresh slug, fresh ID reservation, fresh grilling pass.
- **Always check for blockers** in step 7 before writing the file. If the issue has dependencies, they must be captured in `## Blocked by` for the orchestrator to schedule correctly.
- **Remove `## Blocked by` entirely** (not just leave it empty) when there are no blockers. An empty section is treated as a signal by `kanban-parse-deps.py`.
