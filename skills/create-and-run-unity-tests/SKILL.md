---
name: create-and-run-unity-tests
description: Add a simple Unity Edit Mode unit test to an existing project, run it through the repository's `./unity-test` daemon workflow, inspect `status`, `results`, and `events`, and report whether the new test definitely ran and passed. Use when a user asks Codex to create Unity tests and verify them through `./unity-test` instead of only editing files.
---

# Create And Run Unity Tests

## Workflow

1. Inspect the project before editing.
   Find existing Unity test files and `.asmdef` files, then add the new test inside an existing Edit Mode test assembly when possible.
   Prefer a small deterministic NUnit test that avoids scene setup, assets, or long-running editor state.

2. Pick the lightest valid target.
   Favor pure C# helpers, static utilities, or existing code already covered by the current test assembly references.
   Avoid introducing a brand new test assembly unless the project has no suitable test location.

3. Add one simple test.
   Use a clear fixture and method name.
   Record the exact fully qualified test name because you will need it when checking `./unity-test events`.

4. Run the Unity daemon workflow from the project root.

```bash
./unity-test run
./unity-test status
./unity-test results
./unity-test events
```

   If the user explicitly asks for this exact sequence, follow it exactly.
   If the user only wants to validate the new test quickly and does not require a full suite run, you may pass a filter to `./unity-test run`.

5. Poll `./unity-test status` until the run is no longer active.
   Treat `refreshing`, `compiling`, and `running` as active states.
   `finished` may exist only briefly.
   In practice, the daemon can advance from `running` back to `idle` quickly, so `idle` after an observed active state usually means the run already completed and you must confirm completion with `results` and `events`.
   Do not assume there will be a literal `pending` status from `./unity-test status`; the request queue is represented by `Library/TestDaemon/run-tests.pending`.

6. Read `./unity-test results` for the run overview.
   Use it to report total, passed, failed, skipped, duration, and timestamps.
   If `results` is missing or stale, report that the editor may not have consumed the request.

7. Read `./unity-test events` for per-test proof.
   Search for the exact fully qualified name of the new test.
   Confirm that at least one `testFinished` event exists for that test.
   Treat duplicated `testStarted` or `testFinished` entries as daemon noise if they agree on the outcome.
   The new test counts as definitely run only if it appears in `events` for the triggered run.

8. Report the verdict clearly.
   State the test file you created, whether the new test was run, and whether it passed.
   Also include the run summary from `results`.
   If the suite passed overall but the new test name never appeared in `events`, say that you cannot prove the new test ran.

## Practical Checks

- Use `rg --files -g '*Tests*.cs' -g '*Test*.cs' -g '*.asmdef'` to find the existing test layout quickly.
- Prefer modifying a project-owned test folder over package tests unless the user asked for package work.
- Avoid touching unrelated untracked files while adding the test.
- If the user asked you to show command output, summarize the important lines from `status`, `results`, and `events` in your answer.
- If the test run fails, report the failure directly and include the relevant failing test names or failure messages from `results` and `events`.
