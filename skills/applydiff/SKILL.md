---
name: applydiff
description: Apply the current Git working-tree diff (including untracked files) into the main repository directory resolved from git-common-dir. Use when the user asks to mirror, sync, or apply local changes from the current nested repository/worktree into the parent repository with a generated patch.
---

# Apply Diff

Always resolve and run the script from the skill directory, not from the project repository.

Use the skill directory that contains this `SKILL.md` file, then run:

```bash
bash <skill-dir>/scripts/applydiff.sh
```

Example (if already inside `<skill-dir>`):

```bash
bash scripts/applydiff.sh
```

Follow this workflow:

1. Resolve `<skill-dir>` as the directory containing this `SKILL.md`.
2. Verify the script exists at `<skill-dir>/scripts/applydiff.sh`.
3. Run `bash <skill-dir>/scripts/applydiff.sh` (or run from `<skill-dir>` and use `bash scripts/applydiff.sh`).
4. Report the final output line to the user.
5. If it fails, include:
- the first error line,
- the final output line,
- and, when available, the patch file path printed by the script.

Guardrails:

- Do not run `bash scripts/applydiff.sh` from the repository root unless that root is the skill directory.
- Do not re-implement patch logic inline.
- If `/tmp/gitdiff.XXXXXX.patch` already exists and the script fails with `mktemp ... File exists`, remove that file and retry once.

Use this skill script as the single source of truth instead of rewriting patch logic in-line.
