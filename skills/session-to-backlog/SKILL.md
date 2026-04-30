---
name: session-to-backlog
description: Read the last pi agent session for the current project, extract what was discussed or done, and create issue files (as <project>-kanban/issues/<id>-<slug>.backlog.md) for any work items, bugs, or follow-ups it uncovered. Use when a session ended without wrapping everything up, when the user wants to capture session outcomes, or when you need to preserve context across sessions.
---

# Session to Backlog

Read the most recent pi session for the current project, derive standalone work items from it, and write each as an issue in the project's kanban repo.

**This skill runs fully autonomously.** It does not prompt the user for confirmation.

## Process

### 1. Find the last session

Determine the current project root. The project root is the git root of `$PWD`. If `$PWD` is not inside a git repo, use `$PWD` itself.

Build the session folder name from the project root's absolute path:

1. Strip the leading `/`.
2. Replace every remaining `/` with `-`.
3. Prepend `--` and append `--`.

For example:
- Project root `/Users/renan.liberato/projects/foo-bar` → folder `--Users-renan.liberato-projects-foo-bar--`
- Project root `/Users/renan.liberato/projects/renan/agent-tools` → folder `--Users-renan.liberato-projects-renan-agent-tools--`

The session directory is `~/.pi/agent/sessions/<folder>/`.

Within it, list all `*.jsonl` files, pick the one with the most recent creation/modification time (the latest session).

If the session folder does not exist, or has no `.jsonl` files, report that and stop — there is no prior session to analyse.

### 2. Read and summarise the session

Read the `.jsonl` file line by line. Each line is a JSON event.

**Event types to read:**

- **`type: "session"`** (first line) — contains `cwd` (working directory at session start) and `timestamp`.
- **`type: "message"`** — each has a nested `message` object.

**Message roles and how to handle each:**

| Role | Content structure | What to extract |
|------|-------------------|-----------------|
| `user` | `content` is a list of parts, one of which is `{"type":"text","text":"..."}` | The user's request text |
| `assistant` | `content` is a list of parts with these `type`s: `thinking`, `text`, `toolCall` | The **`text`** parts (actual response). Also scan **`toolCall`** parts for which tools were invoked (`name` field, e.g. `bash`, `edit`, `read`) to understand what work was done. Optionally scan **`thinking`** parts for reasoning traces — can reveal what the agent considered or discovered, which informs items. |
| `toolResult` | `content` is text or a list of parts. Has fields: `toolName`, `isError` | **Error signals only** — check `isError`. If `true`, the session hit a bug; note it. Otherwise skip the content (raw file dumps and command output are noise). |

Extract the essential narrative:

- The **session timestamp** and **working directory** from the `session` event.
- Each **user message** in order.
- Each **assistant `text` part** in order — this is the actual conversation.
- Each **assistant `toolCall`** — which tools were invoked and roughly how many.
- Each **assistant `thinking`** — skim for insights: bugs discovered, design decisions, alternatives considered, things the agent learned.
- Any **`toolResult` with `isError: true`** — note as a potential bug or issue.

Build a concise bullet list of:
- What the user asked for (paraphrase each distinct request)
- What was implemented or decided (from assistant text + tool calls + thinking)
- Any bugs or issues that were discovered but not fully resolved
- Any follow-ups or open questions mentioned

Keep the summary readable and high-level.

### 3. Derive work items

From the summary, identify **distinct work items** that should be captured as issues. A work item is anything that:

- Was a **new feature or capability** built in the session
- Was a **bug** discovered, even if fixed (it may need a follow-up in another context)
- Was a **tweak or refactor** that could be generalised or applied elsewhere
- Was an **architectural decision** or **design choice** that should be documented
- Was explicitly mentioned as **"next"** or **"follow-up"** work
- Was an **unresolved question**, **edge case**, or **technical debt** that warrants tracking

For each work item, determine:

- **type**: `feature`, `bug`, `tweak`, or `chore`
- **title**: A short, descriptive slug-able name
- **summary**: 1–2 sentences capturing the work
- **why**: The motivating problem or use case (can be inferred from the user's request)
- **prd**: If the work relates to an existing PRD in the kanban repo, reference it by ID-slug
- **open questions**: Any unresolved questions from the session
- **notes**: Key context from the session

Do NOT write more than 6 items. Pick the 6 most impactful.

### 4. Ensure kanban repo exists

```bash
PROJECT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")
KANBAN_DIR="$(dirname "$PROJECT_DIR")/$(basename "$PROJECT_DIR")-kanban"
```

If `$KANBAN_DIR` does not exist, run `init-kanban-repo`:

```bash
~/projects/renan/agent-tools/scripts/init-kanban-repo
```

Ensure `reserve-issue-id` is available:

```bash
mkdir -p "$KANBAN_DIR/.tools"
cp ~/projects/renan/agent-tools/scripts/reserve-issue-id "$KANBAN_DIR/.tools/reserve-issue-id" 2>/dev/null || true
chmod +x "$KANBAN_DIR/.tools/reserve-issue-id" 2>/dev/null || true
```

### 5. Write issue files (autonomous — no confirmation)

For every derived item:

a. Reserve the next ID: `ID=$("$KANBAN_DIR/.tools/reserve-issue-id")`
b. Derive the slug: 3–6 lowercase-hyphen words from the title
c. Check if `"$KANBAN_DIR/issues/$ID-$slug.backlog.md"` already exists. If it does, **skip silently** — do not overwrite or prompt.
d. Write the file:

```markdown
---
type: feature | bug | tweak | chore
state: backlog
created: <YYYY-MM-DD>
prd: <optional: 000008-slug>
---

# <Title>

## Summary

<Derived summary>

## Why

<The motivating problem or user signal, taken from the session context>

## Open questions

- <Any unresolved questions from the session, or "None">

## Notes

- Derived from pi session: <session-filename>
- <Any other relevant context — files changed, decisions, links>
```

### 6. Report

Print a summary:

```
[session-to-backlog] Derived from <session-filename>
  ✓ <ID>-<slug> — <title>
  ✓ <ID>-<slug> — <title>
  ⊘ <slug> — already exists, skipped
  --> <N> items written, <M> skipped
```

## Guardrails

- Never read a session that is not the last one for the current project.
- Never prompt the user. This skill is fully autonomous.
- Never include raw tool output or file contents in the issue file. Summaries only.
- Never modify or delete other issue files.
- Never overwrite an existing issue file. If the full path already exists, skip it.
