---
name: bugfix-with-tests
description: Fix a bug using a failing-test-first workflow. The test proves the bug exists before the fix lands, and proves it's gone after. Use when the user reports a runtime error, crash, or incorrect behavior and wants a verified fix — not just a patch.
---

# Bugfix with Tests

## Philosophy

A fix without a test is a promise. A fix with a failing-then-passing test is proof.

The goal is not just to make the bug go away — it is to create a permanent record that the specific failure mode is covered. Future regressions will be caught automatically instead of surfacing as user-reported crashes.

**The mandatory sequence is:**

```
1. UNDERSTAND  — reproduce the failure in your head from logs/traces
2. RED         — write a test that fails for exactly the right reason
3. GREEN       — apply the minimal fix; test passes
4. CONFIRM     — run the full suite; no regressions
```

Skipping RED means you cannot be sure the test actually exercises the bug. A test written after the fix may pass for the wrong reason (the fix happened to also mask an unrelated issue, or the test never actually triggered the original code path).

## Step 1 — Understand the Bug

Before writing any test, identify:

- **The exact failure site**: stack frame, file, line number.
- **The trigger condition**: what specific sequence of events causes it? In the FTUE example: `startHelenArrival()` fires a fire-and-forget microtask, the screen gets disposed before it resolves, and `notifyListeners()` fires on a disposed `ChangeNotifier`.
- **Why the last commit introduced it**: diff the relevant files. Look for a changed assumption — a swapped guard, a new call order, a removed try-catch, a direct reference replacing an indirect one.

Do not write the test until you can describe the trigger condition in one sentence.

## Step 2 — Write the Failing Test (RED)

Write the narrowest test that fails for exactly the reason the bug fails in production.

**Principles:**

- Target the unit closest to the failure site. Prefer a unit test in the relevant `*_test.dart` file over a widget test unless the bug is inherently a widget lifecycle issue.
- The test failure message must name the bug. If the crash is `"A StationController was used after being disposed"`, the test should fail with that exact message — not a generic assertion error.
- One test per bug. Don't add multiple tests speculatively.
- The test should pass after the fix and continue passing through future refactors.

**Run the test before fixing.** Confirm it fails with the right error:

```bash
flutter test test/path/to/relevant_test.dart --name 'your test name'
```

If the test passes before the fix, it is not testing the bug. Revise it.

## Step 3 — Apply the Fix (GREEN)

Fix only what the failing test requires. Do not clean up surrounding code, add unrelated error handling, or refactor while RED.

After the fix, run the test again:

```bash
flutter test test/path/to/relevant_test.dart --name 'your test name'
```

It must pass. If it doesn't, the fix is wrong or incomplete.

## Step 4 — Confirm No Regressions

Run the full file (or relevant suite) to verify nothing broke:

```bash
flutter test test/path/to/relevant_test.dart
```

If the broader suite is affected by the change, run it too.

## What Makes a Good Regression Test

A good regression test for a bug is one that:

1. **Reproduces the trigger condition** — not just the symptom. Test the sequence of events, not just the end state.
2. **Fails with the original error** — the failure message should match what was reported in the crash log.
3. **Passes only after the correct fix** — if it can be made to pass by a no-op or unrelated change, it is not testing the bug.
4. **Is stable under refactors** — it tests behavior through public interfaces, not internal implementation.

## Common Patterns

### Async race (disposed object)

```dart
test('dispose during async op does not crash', () async {
  final ctrl = makeController();

  // Fire the async operation that will call notifyListeners after it resolves.
  await ctrl.startSomething(); // awaits internal async work, fires microtask

  // Dispose before the microtask's continuation runs.
  ctrl.dispose();

  // Drain all pending async work.
  // Without the fix: throws "X was used after being disposed."
  await pumpEventQueue();
});
```

### notifyListeners during locked widget tree

This is a widget test — the locked-tree assertion only fires inside a real widget binding.

```dart
testWidgets('dispose does not call notifyListeners while tree is locked',
    (tester) async {
  // Pump the widget with an active session.
  await tester.pumpWidget(buildSubject(game: gameWithActiveSoul));

  // Navigate away — triggers dispose() on the screen widget.
  await tester.tap(find.byKey(const Key('back_button')));
  await tester.pumpAndSettle();

  // If endInterview called notifyListeners during unmount, Flutter would have
  // thrown: "setState() or markNeedsBuild() called when widget tree was locked."
  // Reaching here means it did not.
});
```

### Guard pattern for async continuations

When a fire-and-forget `Future.microtask` calls `notifyListeners()` at the end, add a disposed guard:

```dart
bool _disposed = false;

@override
void dispose() {
  _disposed = true;
  super.dispose();
}

// Inside the microtask:
if (!_disposed) notifyListeners();
```

### Defer notifyListeners out of dispose()

When `dispose()` needs to trigger a side effect that calls `notifyListeners()` on a provider, defer it:

```dart
@override
void dispose() {
  final game = _game;
  WidgetsBinding.instance.addPostFrameCallback((_) {
    game.endInterview(); // safe: tree is unlocked by next frame
  });
  super.dispose();
}
```

## Checklist

```
[ ] Trigger condition identified from stack trace / logs
[ ] Test written and confirmed FAILING before fix
[ ] Test failure message matches the original crash
[ ] Fix applied — minimal, no scope creep
[ ] Test confirmed PASSING after fix
[ ] Full suite passes — no regressions
[ ] Commit includes both fix and test in the same commit
```
