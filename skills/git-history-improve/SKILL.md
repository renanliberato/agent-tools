---
name: git-history-improve
description: Plan and execute a full git history squash job — analyze commits between two refs, group them into ~10 semantically meaningful squashes, drop irrelevant directories or paths, cherry-pick each group with conflict resolution onto a new branch, and verify the final tree matches the original modulo dropped paths. Use when the user says "reduce commits", "squash branch history", "clean up git history", "rewrite branch", "compress commits", or wants to consolidate a messy branch before merge.
---

# Git History Improve

## Overview

One-shot git history compression: analyze, group by topic, drop irrelevant paths, cherry-pick-squash each group, resolve conflicts, verify.

**Prerequisite**: a clean working tree (stash or commit pending changes before starting).

---

## Phase 1 — Analyze

1. **Understand the range**: confirm the base ref (e.g. `champs`, `main`, `origin/main`) and the branch `HEAD`.
   ```bash
   git log --oneline <base>..HEAD | wc -l
   git log --format="%h %ai %s" <base>..HEAD
   ```

2. **For each commit, list touched files**:
   ```bash
   for c in $(git log --reverse --format="%H" <base>..HEAD); do
     echo "=== $(git log --format='%h %s' -1 $c) ==="
     echo "Files:"
     git diff-tree --no-commit-id --name-only -r $c
     echo
   done
   ```

3. **Identify droppable directories**: directories that were created-and-then-deleted, or that the user wants to exclude from history entirely (e.g. `tools/soul-calibration-webui/`). These commits can be skipped.

4. **Identify the groups**: group commits by topic/subdirectory, following these rules:
   - Core feature work (architecture refactors, engine, prompts, pipeline wiring)
   - Asset changes (moves, migrations, schema changes)
   - Cleanup/removal commits
   - Tool/CLI work (one group for foundation, one for tests, one for final enhancements)
   - Independent additions (scripts, skills, reports)
   - Planning/administrative artifacts (optional — can be dropped)

5. **Output the plan** for user review before execution: list each group with commit count, files touched, and proposed title.

---

## Phase 2 — Execute

For each group, in chronological order:

1. **Cherry-pick all commits in the group without committing**:
   ```bash
   git cherry-pick -n <hash1> <hash2> <hash3> ...
   ```

2. **If a conflict occurs**:
   - Use `git status` to find conflicted files.
   - Decide the correct resolution:
     - If the conflict is in files from a **dropped path** — accept `--ours` and move on.
     - If the conflict is in a **kept file** — examine both sides and resolve manually (the conflict is usually in `CHANGELOG.md`; keep `--ours` and discard incoming webui/noise entries).
   - After resolving each conflicted file: `git add <file>`
   - Check if there are still remaining commits to apply in the sequencer:
     ```bash
     cat $(git rev-parse --git-dir)/sequencer/todo 2>/dev/null
     ```
   - If the sequencer exists, continue:
     ```bash
     git cherry-pick --continue --no-edit
     ```
   - If the sequencer is gone but cherry-pick was interrupted, the remaining commit needs separate handling:
     ```bash
     # Temporarily commit resolved changes, then pick remaining commit, then squash
     git commit -m "temp"
     git cherry-pick -n <remaining_hash>
     git reset --soft HEAD~1   # squash temp into this batch
     ```

3. **After all commits in the group apply cleanly** (no sequencer active), commit with the group's title:
   ```bash
   git commit -m "<group title>"
   ```

---

## Phase 3 — Verify

1. **Check the new log looks clean**:
   ```bash
   git log --oneline <base>..HEAD
   ```

2. **Compare final tree with the original branch**:
   ```bash
   git diff <original-branch>..HEAD --stat | tail -5
   ```

3. **Inspect any deltas**: the only differences should be:
   - `CHANGELOG.md` — entries for dropped features are absent (expected)
   - `.gitignore` — entries for dropped paths are absent (expected)
   - Nothing else should differ

4. **Report the results**: commit count before/after, list of each squashed commit with its constituent hashes, any conflicts encountered, and the verification diff.

---

## Example Trigger Phrases

- `reduce the commits on branch X since Y`
- `squash my branch history down to ~10 commits`
- `clean up the git history dropping directory Z`
- `rewrite branch X from ref Y with better grouping`
- `compress commit history on this branch`

## See also

- [group-commits skill](../group-commits/SKILL.md) — analysis-only grouping (use instead of Phase 1 if you prefer lightweight analysis first)
- [squash-message skill](../squash-message/SKILL.md) — single-message synthesis (use for individual group messages)
