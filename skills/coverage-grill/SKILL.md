---
name: coverage-grill
description: Run or read Flutter/Dart coverage, scan for user-facing test gaps, grill the user one question at a time to confirm expected behavior (surfacing real bugs in the process), then file kanban issues for confirmed bugs and behavioral gaps. Use when the user wants to increase test confidence on a specific area of the app, or says "what should we test", "find coverage gaps", or "grill me on behavior".
---

# Coverage Grill

Four phases executed in sequence: **collect → scan → grill → file**.

---

## Phase 1 — Collect coverage

Check whether `coverage/lcov.info` exists and is fresh (modified within the last 2 hours).

- **Fresh**: use it directly. Tell the user you're reading existing coverage.
- **Stale or missing**: run `flutter test --coverage > /tmp/test_output.txt 2>&1` (no `--no-test-assets`). Check the exit code. If tests fail, surface the failures and stop — do not proceed to scan on a broken suite.

Parse `coverage/lcov.info` to build a per-file table:

```
pct   hit  total  path
 0.0%   0/  107   lib/modes/levels/screens/soul_lost_screen.dart
 0.9%   1/  117   lib/modes/levels/screens/level_completion_screen.dart
...
```

Report: total lines, total covered, overall %, number of source files.

---

## Phase 2 — Scan for user-facing gaps

Ask the user which **area or mode** to focus on (e.g. "levels mode", "IAP flow", "onboarding"). Use the answer to filter the file list.

**Exclude by default** (never file issues for these):
- `lib/debug/`
- `lib/debug/gallery/`
- Any file whose path fragment matches `_test_seam`, `test_seam`, `gallery_entry`
- Pure model/config files with no branching logic (data classes, enums, constants)

**Rank remaining files** by: `uncovered_lines DESC`, then `pct ASC`. Weight large low-coverage files highest.

For each file, read the source and categorise the uncovered lines into:

| Category | Examples | Worth filing? |
|---|---|---|
| Branching logic | `if/else`, `switch`, callbacks, async guards | Yes |
| Animation/visual only | `AnimationController`, `Tween`, `build` body with no logic | No |
| Dead code | unreachable catch, `langSuffix = ''` | File as bug, not test gap |
| CTA callbacks | `onTap`, `onRetry`, `onClose`, `onConfirm` | Yes |
| Service/provider methods | fetch, submit, cache, state transitions | Yes |

Stop scanning when you have 4–8 candidate gaps. Quality over quantity — each candidate must have a concrete runtime risk you can articulate.

---

## Phase 3 — Grill

For each candidate, form **one behavioral question** before asking it:

- Cross-reference the code against the question. If the code already answers it definitively (no ambiguity), skip and move on.
- Frame questions as runtime scenarios, not test suggestions. ✗ "Should we test `_onConfirm`?" ✓ "If the widget unmounts mid-stamp animation, should `onJudgment` still fire?"
- Provide your recommended answer based on what the code implies.
- Ask **one question at a time** and wait for the answer before continuing.

### When an answer reveals a bug

If the stated behavior differs from the code:
- Say so explicitly: "The code does X but you said Y — that's a confirmed bug."
- Stop and file it immediately (Phase 4) before moving to the next question.
- Do NOT continue grilling until the issue is filed.

### When an answer confirms expected behavior

Note it as "confirmed — test should assert this" and move to the next candidate.

### When an answer reveals dead code or dropped features

File a cleanup issue (not a test issue), note it as "dead code confirmed", and move on.

### Stopping criteria

Stop grilling when:
- All candidates have been resolved (confirmed, bugged, or skipped), OR
- The user says "that's enough" or "move to filing"

---

## Phase 4 — File issues

Use the kanban issue tracker (see `issue-tracker` skill for ID reservation and commit format).

### For confirmed bugs

```yaml
type: bug
severity: minor   # wrong output, display error, dead code
           # major only for: crash, data loss, silent wrong callback, broken core flow
```

Title: one sentence describing what's wrong at runtime. No "missing test" language.

Body sections:
1. **Bug** — what the code does vs. what it should do, with a code snippet
2. **Fix** — concrete fix (algorithm, rename, remove block, etc.)
3. **Test cases** — 3–6 concrete assertions that prove the fix

### For behavioral gaps (no confirmed bug, just no test coverage)

```yaml
type: test
severity: minor
```

Title: `<ComponentName> <behavior> has no tests`.

Body sections:
1. **What's uncovered** — specific methods/paths with their runtime risk
2. **What to test** — numbered list of concrete test cases

### Always append to every new issue

```markdown
## Implementation notes

Do not run `flutter test --coverage` or generate coverage reports as part of this task. Coverage will be addressed in a separate pass.
```

### Before filing — check the trash

Read `<kanban-repo>/issues/*.trash.md` titles. Do not re-file anything similar to a trashed issue.

---

## Constraints

- **Never file issues for**: animation tests, overlay presence/snapshot assertions, shell scripts, kanban infrastructure, style/readability refactors, duplicate code with no divergence risk, `docs/` or `CHANGELOG.md` gaps.
- **Severity discipline**: `major` only for confirmed runtime impact a user directly encounters. Missing tests are never `major`.
- **One question at a time** in the grill — do not batch questions.
- **Do not run coverage** during Phase 4 or in any filed issue's implementation notes.
