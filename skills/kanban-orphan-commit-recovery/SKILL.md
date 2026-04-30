---
name: kanban-orphan-commit-recovery
description: Recover orphaned/dangling commits from kanban headless runs where the AI agent committed in the worktree but the kanban-commit agent failed to cherry-pick to the target branch (commit exists as a dangling object unreachable from any ref). Use when a ai-task-start-kanban-headless run completed/finished but the commit is missing from the target branch, or when investigating "nothing to commit — working tree is clean" in kanban-commit agent output.
---

# Kanban Orphan Commit Recovery

## Quick start

A task completed (`.done` marker exists, issue promoted to `.done.md`) but no commit appeared on the target branch? The AI agent likely committed its work before the commit agent ran, and the commit was orphaned during worktree cleanup.

```sh
# 1. Find candidate runs in temp status dirs
ls -d /tmp/kanban-*/*.log | grep <task-id>

# 2. Read the log — look for "Done. Commit <hash>" from the AI agent
cat /tmp/kanban-<project>-<pid>/<task-id>.log

# 3. Verify the commit still exists as a dangling object
git cat-file -t <hash>

# 4. Cherry-pick it onto the target branch
git cherry-pick <hash>
```

## Diagnosis workflow

### Step 1 — Find the run logs

The orchestrator stores per-task logs in `/tmp/kanban-<project_name>-<pid>/<task-id>.log`.

The project name is derived from the **parent dir of the kanban repo**, so for `deedsplease-h36-kanban` the logs land in `/tmp/kanban-projects-<pid>/`. Find them:

```sh
# search by task ID
ls -d /tmp/kanban-*/*.log | grep 000085
```

If the run used `--watch`, there may be multiple `kanban-<project>-<pid>` directories. Sort by mtime (`ls -lt`) to find the right one.

### Step 2 — Read the log for the commit hash

Scan the log for a line matching:

```
Done. Commit `<hash>` on branch `<worktree-branch>`.
```

This is printed by the AI agent (pi/sonnet) when it commits its work. The hash is your target.

If the log shows:

```
Nothing to commit — working tree is clean, no staged or untracked changes.
Cherry-pick | Skipped — no commit was created.
```

This confirms the kanban-commit agent hit the gap: the AI already committed, but the commit agent didn't know to cherry-pick it.

### Step 3 — Verify the commit object

Check if the commit still exists as a git object (it should, since git keeps dangling objects for ~30 days):

```sh
cd <project-repo>
git cat-file -t <hash>
# → "commit"
```

If it returns `fatal: Not a valid object name`, the commit was garbage-collected — you'll need to recover from the worktree's reflog (unlikely to survive cleanup) or redo the work manually.

### Step 4 — Cherry-pick onto the target branch

```sh
git switch <target-branch>

# Stash any local changes first
git stash push -u -m "pre-cherry-pick-<task-id>"

# Cherry-pick
git cherry-pick <hash>

# Restore local changes
git stash pop
```

If there are conflicts, resolve them carefully, preserving both the task work and any pre-existing edits.

### Step 5 — Verify

```sh
git log --oneline <target-branch> -3
# confirm the cherry-picked commit is at HEAD
```

## Why this happens

The root cause is a gap in `kanban-commit.md`:

1. The AI agent (task runner, `$model -p "$prompt"`) commits its work in the worktree during execution.
2. The kanban-commit agent runs next. Old step 2 said "stage and create a commit" — since the worktree is clean, nothing happens.
3. Old step 6 says "cherry-pick the task commit" but no new commit was created, so the agent skips cherry-picking entirely.
4. Worktree cleanup (`git worktree remove --force` + `git branch -D`) deletes the branch, leaving the commit dangling.

The fix (as of `21ccb26`) adds a discovery phase in step 2 that detects pre-existing commits via `git log HEAD --not $base_branch`.

## Known indicators

| Symptom | Cause |
|---|---|
| `.done` marker exists, no commit on target branch | Commit orphaned — follow recovery steps above |
| `.failed` marker exists, but log shows the task completed | Different failure mode (non-zero exit in task agent) |
| Task log shows "Done. Commit X" but `git cat-file -t X` fails | Commit was garbage-collected — redo task manually |
| Multiple `/tmp/kanban-*` dirs for same project | `--watch` mode spawns a new orchestrator each session |
