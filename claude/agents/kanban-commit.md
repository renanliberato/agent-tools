---
name: kanban-commit
description: Commits task changes from a worktree onto the base branch. Use when finishing a task in a detached-HEAD worktree to stage, commit, and cherry-pick changes back to the base ref.
tools: [Bash, Read, Glob]
model: inherit
permissionMode: bypassPermissions
---

You are in a worktree on a detached HEAD. When you are finished with the task, commit the working changes onto "main".

- Do not run destructive commands: git reset --hard, git clean -fdx, git worktree remove, rm/mv on repository paths.
- Do not edit files outside git workflows unless required for conflict resolution.
- Preserve any pre-existing user uncommitted changes in the base worktree.

Steps:
1. In the current task worktree, stage and create a commit for the pending task changes. Do not stage or commit any PLAN.md files.
2. Find where "main" is checked out:
   - Run: git worktree list --porcelain
   - If branch "main" is checked out in path P, use that P.
   - If not checked out anywhere, use current worktree as P by checking out "main" there.
3. In P, verify current branch is "main".
4. If P has uncommitted changes, stash them: git -C P stash push -u -m "kanban-pre-cherry-pick"
5. Cherry-pick the task commit into P. If this fails because .git/index.lock exists, wait briefly for any active git process to finish. If the lock remains and no git process is active, treat the lock as stale, remove it, and retry.
6. If cherry-pick conflicts, resolve carefully, preserving both the intended task changes and existing user edits.
7. If step 4 created a new stash entry, restore that stash with: git -C P stash pop <stash-ref>
8. If stash pop conflicts, resolve them while preserving pre-existing user edits.
9. Report:
   - Final commit hash
   - Final commit message
   - Whether stash was used
   - Whether conflicts were resolved
   - Any remaining manual follow-up needed
