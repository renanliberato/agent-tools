---
name: backlog-add
description: Capture a new feature, bug, or tweak idea into the project backlog at .planning/backlog/<id>-<slug>.md. Runs a short grilling pass against the existing domain model (CONTEXT.md, ADRs, code) so the entry is sharper than a one-liner. Uses sequential IDs (via flock(1)) so files sort naturally even with concurrent agents. Use when user wants to add to the backlog, capture an idea, log a bug or tweak for later, or build up a queue of work to later promote into a PRD.
---

# Backlog Add

Capture an idea into `.planning/backlog/<NNNNNN>-<slug>.md` after grilling it briefly against the codebase. Each entry gets a sequential ID (atomically reserved via `flock`) so files sort naturally regardless of creation order or concurrency.

The output is a self-contained markdown file that can later be picked up by `backlog-promote` to feed into `to-prd` and `to-issues`.

## Prerequisites

This skill requires `flock(1)` for atomic ID reservation. Install it if missing:

```bash
# macOS (Homebrew)
brew install discoteq/tap/flock

# Linux — flock is usually in util-linux (pre-installed on most distros)
which flock || sudo apt-get install -y util-linux   # Debian/Ubuntu
which flock || sudo yum install -y util-linux        # RHEL/Fedora
```

The companion tool `reserve-backlog-id` lives at:
`/Users/renan.liberato/.agents/skills/backlog-add/reserve-backlog-id`

The skill copies it into the project on first use.

## Process

### 1. Get the seed

The user will pass a one-liner or a short paragraph as the idea. If they passed nothing, ask for the seed in one sentence and stop until they reply.

### 2. Ensure the tool is in the project

On first use in this project, copy the companion tool into the project's `.planning/` directory:

```bash
mkdir -p .planning/.tools
cp /Users/renan.liberato/.agents/skills/backlog-add/reserve-backlog-id .planning/.tools/reserve-backlog-id
chmod +x .planning/.tools/reserve-backlog-id
```

If `.planning/.tools/reserve-backlog-id` already exists, skip this step.

### 3. Pick a slug

Slugify the idea into 3–6 lowercase-hyphen words (e.g. `customer-cancel-partial-order`). The full filename will be `<ID>-<slug>.md` where the ID is reserved atomically in step 5.

If `.planning/backlog/` does not exist, create it.

### 4. Grill — but keep it short

Run a focused grilling pass following the spirit of the `grill-with-docs` skill, with these constraints to keep capture cheap:

- **Cap at 5 questions.** This is a backlog entry, not a PRD. Stop early once the entry has enough shape to be promoted later.
- Ask **one question at a time** and wait for the user's answer before continuing.
- Skip questions you can answer yourself by reading `CONTEXT.md`, `CONTEXT-MAP.md`, `docs/adr/`, or the code — answer them silently and move on.
- Challenge fuzzy or overloaded terms against the existing glossary in `CONTEXT.md`. If the user uses a term that conflicts with a defined one, call it out and resolve it.
- Probe for the **one or two** decisions that would block writing a PRD later (the user the feature serves, the scope boundary, the success signal). Anything beyond that is premature for a backlog entry.

If during grilling a domain term is resolved or an ADR-worthy decision crystallises, update `CONTEXT.md` / `docs/adr/` inline as `grill-with-docs` would. Do not batch.

If the user says "skip the grilling" or "just save it", skip step 4 entirely and go to step 5 with whatever shape the seed has.

### 5. Reserve the next sequential ID

Reserve the next ID atomically (safe across concurrent agents):

```bash
ID=$(.planning/.tools/reserve-backlog-id)
```

`$ID` will be a zero-padded 6-digit string like `000042`.

If the tool fails (e.g. `flock` not installed), abort with a clear error message telling the user to install `flock` (see Prerequisites above).

### 6. Write the file

Write `.planning/backlog/<ID>-<slug>.md` using this template:

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

### 7. Confirm

Tell the user:

- The file path that was written (including the ID prefix)
- The current count of items in `.planning/backlog/` (excluding `archive/`)

Do not commit. Do not run `to-prd` or `to-issues` — promotion is a separate step.

## Migration: add IDs to existing backlog items

If the project has existing backlog files without the ID prefix (e.g. `customer-cancel-partial-order.md`), you can migrate them automatically. Run this once to preserve the existing order and assign sequential IDs:

```bash
# From project root
TOOL=.planning/.tools/reserve-backlog-id
if [ ! -f "$TOOL" ]; then
  mkdir -p .planning/.tools
  cp /Users/renan.liberato/.agents/skills/backlog-add/reserve-backlog-id "$TOOL"
  chmod +x "$TOOL"
fi

cd .planning/backlog
for f in *.md; do
  # Skip files that already have an ID prefix (NNNNNN-*)
  if echo "$f" | grep -qE '^[0-9]{6}-'; then
    echo "SKIP (already has ID): $f"
    continue
  fi
  ID=$("$TOOL")
  mv "$f" "${ID}-${f}"
  echo "MIGRATED: $f → ${ID}-${f}"
done
```

The migration preserves the creation date in the frontmatter — only the filename changes. After migration, the output list will look like:

```
MIGRATED: customer-cancel-partial-order.md → 000001-customer-cancel-partial-order.md
MIGRATED: retry-on-429.md → 000002-retry-on-429.md
```

Run this only when the user asks for it, or mention it as an option if you detect existing unprefixed files in `.planning/backlog/`.

## Guardrails

- Never write outside `.planning/backlog/`.
- Never modify or delete other backlog entries — this skill only adds.
- Never reuse an ID — the tool guarantees uniqueness via `flock`.
- Do not invent acceptance criteria, user stories, or implementation plans. That detail belongs in the PRD/issues that come out of `backlog-promote`, and adding it now will rot before promotion.
- If the user invokes this skill repeatedly in one session, treat each invocation independently — fresh slug, fresh ID reservation, fresh grilling pass.
