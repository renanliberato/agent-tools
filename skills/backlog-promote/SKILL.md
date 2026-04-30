---
name: backlog-promote
description: Promote one or more backlog entries from .planning/backlog/ into a PRD plus issue files, then archive the originals so the backlog reflects only un-promoted work. Bridges backlog-add and the existing to-prd / to-issues skills. Use when user wants to pick items off the backlog, turn backlog items into a PRD, ship a slice of the backlog, or convert captured ideas into actionable issues.
---

# Backlog Promote

Pick one or more `.planning/backlog/<id>-<slug>.md` entries and turn them into:

1. A PRD at `.planning/prd.md` (via the `to-prd` skill)
2. Issue files under `.planning/issues/` (via the `to-issues` skill)
3. Archived backlog entries under `.planning/backlog/archive/`

This skill does not re-do the work of `to-prd` and `to-issues` — it orchestrates them.

## Process

### 1. List the backlog

Read every `.md` file directly under `.planning/backlog/` (skip `archive/`). For each, parse the frontmatter (`type`, `status`, `created`) and the `# Title` heading.

Present the list to the user as a numbered table:

| # | type | title | id-slug |
|---|------|-------|---------|

If `.planning/backlog/` is missing or empty, tell the user there is nothing to promote and stop.

### 2. Get the selection

If the user already passed slugs or numbers as arguments, parse them directly. Otherwise, ask the user which item(s) to promote — accept:
  - **numbers** from the table (`1, 3`)
  - **full id-slug** (`000042-customer-cancel-partial-order`)
  - **slug only** (`customer-cancel-partial-order`) — resolves to the only matching entry, or errors if ambiguous.

Confirm the final selection back to the user as a short bullet list and ask "promote these?" before proceeding. This is a destructive-ish operation (the entries leave the backlog) — confirm explicitly even if the user listed slugs in the original message.

### 3. Pre-flight check on `.planning/`

Before invoking the downstream skills, check whether `.planning/prd.md` already exists:

- **If it does not exist**, proceed normally.
- **If it exists**, read it and ask the user whether to:
  - **replace** it (the new PRD covers a different scope), or
  - **extend** it (the picked items belong to the same effort and should be appended as new sections / user stories), or
  - **abort** so they can rename/move the existing PRD first.

Same check for `.planning/issues/`: if non-empty, ask whether new issue files will conflict with existing numbering or whether to continue numbering from the highest existing prefix.

### 4. Run `to-prd`

Read each selected backlog file in full and load its content into the conversation context. Then invoke the `to-prd` skill, treating the combined contents of the selected entries as the source material.

When `to-prd` runs, it expects to synthesise from conversation context — which now contains the picked entries — so this is the correct seam.

If the user chose **extend** in step 3, instruct `to-prd` to append new user stories and implementation decisions to the existing `prd.md` rather than rewriting it.

### 5. Run `to-issues`

Once `prd.md` is written (or extended), invoke the `to-issues` skill. It will quiz the user on the slice breakdown — let it run its full flow. Do not short-circuit the quiz.

If extending an existing issues set, tell `to-issues` to start numbering from the next available prefix in `.planning/issues/` (e.g. existing `01–04` → new files start at `05`).

### 6. Archive the promoted entries

Once both `to-prd` and `to-issues` have completed successfully, move every selected backlog file from `.planning/backlog/<id>-<slug>.md` to `.planning/backlog/archive/<id>-<slug>.md`. Use `git mv` if the project is a git repo, otherwise plain `mv`. Create the `archive/` directory if it does not exist.

Before moving, append a small footer to each archived file so the trail is preserved:

```markdown

---
promoted: <YYYY-MM-DD>
into: prd.md + issues/<the issue slugs to-issues created>
```

### 7. Report

Report to the user:

- Which backlog entries were promoted (slugs)
- Where the PRD ended up and whether it was created or extended
- How many issue files were created and the range of prefixes (e.g. `05-… through 09-…`)
- Remaining count in `.planning/backlog/` after archiving

Do not commit. Leave staging to the user.

## Guardrails

- **Never delete a backlog entry.** Always archive — the trail matters for retros.
- **Never run `to-prd` or `to-issues` on an empty selection.** If the user's selection resolves to zero files, stop and ask again.
- **Never overwrite `.planning/prd.md` without asking** (step 3). The user may have unfinished work in there.
- If `to-issues` is aborted by the user partway through (they reject the breakdown and bail), do **not** archive the backlog entries — leave them in place so the user can retry. Tell the user the items are still in the backlog.
- Do not re-grill the entries here. Grilling happened at capture time in `backlog-add`; this skill trusts that work.
