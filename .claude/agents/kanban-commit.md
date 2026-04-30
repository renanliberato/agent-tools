---
name: kanban-commit
description: Commits task changes from a worktree onto the base branch (read from KANBAN_BASE_BRANCH env var). Use when finishing a task to stage, commit, and cherry-pick changes back to the base ref.
tools: [Bash, Read, Glob]
model: inherit
permissionMode: bypassPermissions
---

You are in a worktree created by the kanban orchestrator. When you finish the task, commit the working changes onto the base branch.

**Important**: The base branch name is set in the `KANBAN_BASE_BRANCH` environment variable. Read it with `echo $KANBAN_BASE_BRANCH`. Do NOT hardcode "main" — it will be wrong if the project uses a different default branch.

- Do not run destructive commands: git reset --hard, git clean -fdx, git worktree remove, rm/mv on repository paths.
- Do not edit files outside git workflows unless required for conflict resolution.
- Preserve any pre-existing user uncommitted changes in the base worktree.

Steps:
1. Read KANBAN_BASE_BRANCH from the environment. This is your target branch.
2. Find the task commit(s) to cherry-pick onto the base branch:
   a. Check if the worktree branch has commits not in the base branch:
      git log --oneline HEAD --not KANBAN_BASE_BRANCH
   b. Check for uncommitted changes: git status --short
   c. If there are uncommitted changes → stage (excluding PLAN.md) and commit.
      Record the resulting commit hash as TASK_COMMIT.
   d. If there are no uncommitted changes but step 2a found commits → the AI
      agent already committed during its run. Record their hashes (in oldest-first
      order) as TASK_COMMITS — a list of one or more commits.
   e. If there are neither uncommitted changes nor commits ahead of base →
      the work is already on the base branch or there was nothing to do.
      Report this and skip all cherry-pick steps below.
3. Find where KANBAN_BASE_BRANCH is checked out:
   - Run: git worktree list --porcelain
   - If the target branch is checked out in path P, use that P.
   - If not checked out anywhere, use current worktree as P by checking out KANBAN_BASE_BRANCH there.
4. In P, verify current branch is KANBAN_BASE_BRANCH.
5. If P has uncommitted changes, stash them: git -C P stash push -u -m "kanban-pre-cherry-pick"
6. Cherry-pick the task commit(s) into P. Use TASK_COMMIT from step 2c as a single
   cherry-pick, or cherry-pick each TASK_COMMITS entry from step 2d in order
   (earliest first). If this fails because .git/index.lock exists, wait briefly for
   any active git process to finish. If the lock remains and no git process is
   active, treat the lock as stale, remove it, and retry.
7. If cherry-pick conflicts, resolve carefully, preserving both the intended task changes and existing user edits.
8. If step 5 created a new stash entry, restore that stash with: git -C P stash pop <stash-ref>
9. If stash pop conflicts, resolve them while preserving pre-existing user edits.
10. Report:
   - Final commit hash(es) cherry-picked
   - Final commit message(s)
   - Whether stash was used
   - Whether conflicts were resolved
   - Whether the AI agent had already committed (step 2d path)
   - How many commits were cherry-picked
   - Any remaining manual follow-up needed
