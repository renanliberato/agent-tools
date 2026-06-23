---
name: mirage-task-mr
description: Use to run an isolated coding task end-to-end on a fresh mirage COW clone — create the clone, work on a new branch making checkpoint commits after each logical step, then push with GitLab push options to open a draft Merge Request targeting main. Trigger when the user says "do this on a mirage branch", "work in a mirage clone and open a draft MR", "isolate this and open an MR", "checkpoint-commit and push a draft MR", or asks for isolated branch work that ends in a merge request. Especially for large/Unity repos where a git worktree is too expensive.
---

# mirage-task-mr

Run a coding task in an isolated mirage clone, commit progress in safe checkpoints, and finish
by pushing a branch that auto-opens a **draft** Merge Request against `main`.

The point is safety and reviewability: the source repo is never touched, your progress is never
lost (each logical step is committed), and the work lands as a draft MR a human can review before
it merges. This skill orchestrates three things you already have — the `mirage` skill for the
clone, ordinary git for checkpoints, and GitLab push options for the MR — into one disciplined flow.

## When to use vs. not

Use it when a task deserves isolation *and* should end as a reviewable MR: risky refactors,
agent-driven changes, anything on a large/Unity repo where a `git worktree` forces a multi-GB
reimport.

Don't reach for it for a tiny in-place edit on a small repo (a plain branch is cheaper), or when
the user explicitly wants to work directly in their current checkout. If the user only wants the
clone (no MR) use the `mirage` skill alone; if they only want an MR on work already done, skip
straight to the push step.

## Workflow

Create a todo per step so nothing is skipped.

### 1. Create the isolated clone

Invoke the **`mirage` skill** to make the clone. Pick the variant by task:

- Unity work that runs the editor → `mirage new <src> --name <task-slug>` (Unity-ready, reuses `Library/`).
- Code-only changes → `mirage new <src> --no-library` (lighter).

Then `cd` into the clone path it reports. **All remaining work happens inside the clone**, never
the source. Confirm with `git -C <clone> remote -v` that `origin` points at the same GitLab repo —
the clone inherits it, which is what lets the final push open the MR upstream.

### 2. Start a fresh branch

Branch off the current base (usually `main`) with a descriptive, kebab-case name reflecting the task:

```bash
git switch -c feature/<task-slug>
```

Use `fix/`, `feature/`, or `chore/` prefixes to match the repo's convention. Never commit straight
to `main`.

### 3. Work in checkpoint commits

Do the task, and **commit after each logical step** — a coherent unit like one file converted, one
function fixed, one subsystem wired. Don't batch the whole task into a single end commit, and don't
commit broken-on-purpose WIP either; each checkpoint should be a sensible point to roll back to.

```bash
git add -A && git commit -m "feat: <what this step accomplished>"
```

Why checkpoints: if a later step goes wrong you reset to the last good commit instead of losing
everything, and the MR history reads as a clear sequence of decisions. Write real messages
(imperative, conventional-commit style) — they become the MR's story.

For Unity repos, remember you can't run the editor from here as the user does — verify compilation
via the `unity-compile-check` skill or Unity MCP, and tell the user to check the editor for
compile errors after script changes (per project conventions). Don't claim it builds without
evidence.

### 4. Finish: push and open a draft MR

When the task is complete and verified, push the branch with **GitLab push options** so the MR is
created automatically as a draft targeting `main`:

```bash
git push -u origin feature/<task-slug> \
  -o merge_request.create \
  -o merge_request.target=main \
  -o merge_request.title="Draft: <concise MR title>" \
  -o merge_request.description="<one-paragraph summary of what changed and why>" \
  -o merge_request.remove_source_branch
```

Notes that keep this robust:

- The `Draft:` title prefix is what marks the MR as draft and works across GitLab versions; the
  newer `-o merge_request.draft` option does the same on recent GitLab if you prefer it.
- If the branch was already pushed, `merge_request.create` is ignored on later pushes — open the MR
  with the GitLab MCP `create_merge_request` (set `draft: true`, `target_branch: main`) instead.
- GitLab prints the MR URL in the push output. **Report that URL to the user** so they can review.

### 5. Report back

Give the user: the clone path, the branch name, a short list of the checkpoint commits, and the
draft MR URL. Mention the clone still exists (cleanable later via `mirage rm <name>`) so they know
where the work lives.

## Quick reference

| Step | Command |
|------|---------|
| Clone (Unity) | `mirage new <src> --name <slug>` |
| Clone (code-only) | `mirage new <src> --no-library` |
| Branch | `git switch -c feature/<slug>` |
| Checkpoint | `git add -A && git commit -m "<step>"` |
| Push + draft MR | `git push -u origin <branch> -o merge_request.create -o merge_request.target=main -o merge_request.title="Draft: <title>"` |
| Cleanup later | `mirage rm <slug>` |
