# Debug Session Replication Guide

This document describes how to replicate an evidence-based debug session like the one used to fix a **MissingReferenceException** caused by an out-of-order UI animation callback in a Unity modal flow. It is intended for creating skills or runbooks for coding agents in other apps and bug scenarios.

---

## 1. System prompt / debug mode workflow

The agent operates in **DEBUG MODE** with these rules:

- **Never fix without runtime evidence first.** Do not guess from code alone.
- **Always rely on runtime information + code** (never code alone).
- **Do not remove instrumentation** before post-fix verification logs prove success or the user explicitly confirms.

### Systematic workflow

1. **Generate 3–5 precise hypotheses** about why the bug occurs (detailed, aim for more rather than fewer).
2. **Instrument code** with logs to test all hypotheses in parallel.
3. **Ask user to reproduce** the bug; provide reproduction steps in a `<reproduction_steps>...</reproduction_steps>` block.
4. **Analyze logs**: evaluate each hypothesis (CONFIRMED / REJECTED / INCONCLUSIVE) with cited log-line evidence.
5. **Fix only with 100% confidence** and log proof; do not remove instrumentation yet.
6. **Verify with logs**: ask user to run again; compare before/after with cited entries.
7. **If logs prove success and user confirms:** remove logs and explain. **If failed:** remove code changes from rejected hypotheses only; generate new hypotheses and add more instrumentation.
8. **After confirmed success:** explain the problem and give a 1–2 line summary of the fix.

### Critical constraints

- NEVER fix without runtime evidence first.
- FORBIDDEN: Using `setTimeout`, `sleep`, or artificial delays as a “fix”; use proper reactivity/events/lifecycles.
- FORBIDDEN: Removing instrumentation before analyzing post-fix verification logs or receiving explicit user confirmation.
- Verification requires before/after log comparison with cited log lines; do not claim success without log proof.
- When all hypotheses are rejected, generate new ones and add more instrumentation.
- **Remove code changes from rejected hypotheses:** when logs prove a hypothesis wrong, revert the code changes for that hypothesis. Do not accumulate defensive guards or speculative fixes. Only keep changes supported by runtime evidence.

---

## 2. Logging configuration (provisioned per session)

The system provisions runtime logging for the session. The agent must capture and use:

- **Server endpoint:** e.g. `http://127.0.0.1:7489/ingest/<uuid>` — HTTP POST endpoint for logs (used for JavaScript/TypeScript).
- **Log path:** e.g. `/path/to/workspace/<session-log-dir>/debug-<session_id>.log` — NDJSON logs are written here. Exact path is provided in the workspace context.
- **Session ID:** e.g. `761119` — unique identifier for the debug session. If empty, do not use `X-Debug-Session-Id` or `sessionId` in payloads.

Rules:

- Do not proceed with instrumentation without valid logging configuration.
- Do not pre-create the log file; it is created when first written to.
- **Clear the log file before each run:** use the `delete_file` tool only (no `rm`/`touch`). Clear only the log file for this session; never delete or modify other sessions’ log files.
- Clearing the log file is not the same as removing instrumentation.

### Log format (NDJSON)

One JSON object per line. Example with sessionId:

```json
{"sessionId":"761119","id":"log_1733456789_abc","timestamp":1733456789000,"location":"RewardPopupController.cs:214","message":"afterCloseAnimation","data":{"popupDestroyed":true},"runId":"run1","hypothesisId":"H1"}
```

Without sessionId (when Session ID is empty):

```json
{"id":"log_1733456789_abc","timestamp":1733456789000,"location":"RewardPopupController.cs:214","message":"afterCloseAnimation","data":{"popupDestroyed":true},"runId":"run1","hypothesisId":"H1"}
```

Payload structure: `sessionId` (if provided), `runId`, `hypothesisId`, `location`, `message`, `data`, `timestamp`.

---

## 3. Instrumentation guidelines

- **Minimum:** at least 1 log; never skip instrumentation.
- **Maximum:** do not exceed 10 logs; if more seem needed, narrow hypotheses first. Typical range: 2–6 logs.
- Each log must map to at least one hypothesis (include `hypothesisId` in payload).
- **Wrap each debug log in a collapsible region** (e.g. `// #region agent log` … `// #endregion`) to keep the editor clean.
- **FORBIDDEN:** logging secrets (tokens, passwords, API keys, PII).

### Placement

- Function entry with parameters.
- Function exit with return values.
- Values before/after critical operations.
- Branch execution paths (which if/else ran).
- Suspected error/edge-case values.
- State mutations and intermediate values.

### Non-JavaScript (e.g. C#, Unity)

- Write directly to the **log path** in append mode using standard library file I/O.
- Write a single NDJSON line per log, then close (or flush).
- Keep snippets minimal (ideally one line or a few).

Example (C#):

```csharp
const string logPath = "/path/to/workspace/<session-log-dir>/debug-761119.log";
try
{
    string line = "{\"sessionId\":\"761119\",\"hypothesisId\":\"H1\",\"location\":\"RewardPopupController.HandleClaim\",\"message\":\"entry\",\"data\":{\"popupDestroyed\":" + (this == null).ToString().ToLowerInvariant() + "},\"timestamp\":" + System.DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() + "}\n";
    File.AppendAllText(logPath, line);
}
catch (System.Exception) { }
```

### JavaScript/TypeScript

- Use the one-line fetch template to POST to the server endpoint, with `Content-Type: application/json` and, if provided, `X-Debug-Session-Id`. Include `sessionId` in the body when Session ID is present.

---

## 4. Reproduction steps (mandatory)

- Conclude with a `<reproduction_steps>...</reproduction_steps>` block so the interface can show steps and a proceed/mark-as-fixed action.
- Use one short, interface-agnostic instruction: e.g. “Press Proceed/Mark as fixed when done.” Do not say “click” or “press or click”; do not ask the user to reply “done.”
- Remind the user if apps/services need to be restarted.
- Inside the tag: only a numbered list, no extra header.

Example:

```xml
<reproduction_steps>
1. Open the project in Unity and enter Play mode.
2. Progress until a reward popup appears after completing the target action.
3. Tap Claim, then dismiss the popup as soon as the close animation starts.
4. Wait for the previous crash point during the animation completion path.
5. Press Proceed/Mark as fixed when done.
</reproduction_steps>
```

---

## 5. Log analysis and hypothesis evaluation

After the user runs and confirms:

- Read the log file at the provided **log path**.
- Evaluate each hypothesis: **CONFIRMED**, **REJECTED**, or **INCONCLUSIVE**, citing specific log lines (e.g. “Line 254: HandleClaim entry with popupDestroyed: false”).
- Root cause: identify the single mechanism that explains the crash (e.g. “Popup teardown completed before the close animation callback fired; the callback still called RefreshRewardVisuals on a destroyed popup → MissingReferenceException on RewardIconView.SetVisible”).

---

## 6. Fix and verification

- Implement the fix using only evidence-backed changes. Do not remove instrumentation yet.
- Optionally tag verification logs with `runId: "post-fix"`.
- Keep logs active until verification succeeds or the user explicitly confirms.
- Compare before/after logs with cited entries; do not claim success without log proof.
- Only remove instrumentation after successful post-fix verification or explicit user request. If the user confirms “the issue was fixed” (even if the log file was deleted), treat as success and remove all debug logs.

---

## 7. Code hygiene when hypotheses are rejected

- When logs prove a hypothesis wrong, **revert the code changes** made for that hypothesis.
- Do not keep defensive guards, speculative fixes, or unproven changes.
- Only keep modifications supported by runtime evidence.
- Prefer reusing existing architecture and patterns; keep fixes small and precise.

---

## 8. Example: MissingReferenceException (worked example)

### Bug report (summary)

- **Exception:** `MissingReferenceException: The object of type 'UnityEngine.UI.Image' has been destroyed but you are still trying to access it.`
- **Stack:** `RewardIconView.SetVisible` ← `RewardPopupController.RefreshRewardVisuals` ← `RewardPopupController.OnCloseAnimationComplete` ← animation completion callback ← `UIManager.ClosePopup`.
- **Scenario:** A reward popup opens after a mission completes; the user taps Claim and dismisses the popup quickly while the close animation is still running; exception occurs when the animation callback fires.

### Hypotheses used

- **H1:** `UIManager.ClosePopup` destroys the popup before the close animation completion callback runs, but `OnCloseAnimationComplete()` still calls `RefreshRewardVisuals()` on the destroyed popup hierarchy.
- **H2:** `HandleClaim()` runs twice, causing the second invocation to trigger close logic after the popup has already been torn down.
- **H3:** `RewardIconView.activeImage` is cleared during teardown while `RefreshRewardVisuals()` still assumes it is valid.

### Instrumentation added

- `RewardPopupController.HandleClaim`: log on entry with `popupDestroyed`, `alreadyClaimed` (H2).
- `UIManager.ClosePopup`: log `beginClose` with popup instance id and active animation count (H1).
- `RewardPopupController.OnCloseAnimationComplete`: log on entry with `popupDestroyed`, `iconViewNull` (H1/H3).
- `RewardPopupController.RefreshRewardVisuals`: log on entry with `popupDestroyed`, `rewardState`, `iconViewNull` (H1/H3).
- `RewardIconView.SetVisible`: log on entry with `activeImageNull`, `selfDestroyed` (H3).

### Log evidence (summary)

- `HandleClaim` runs once with `alreadyClaimed: false`, so H2 is rejected.
- `UIManager.ClosePopup` logs `beginClose`, then `OnCloseAnimationComplete` logs `popupDestroyed: true`.
- `RefreshRewardVisuals` logs `popupDestroyed: true`, `iconViewNull: false`; `RewardIconView.SetVisible` logs `activeImageNull: true`, `selfDestroyed: true` immediately before the exception.
- **H1 CONFIRMED;** H3 is a downstream consequence of H1 (destroyed UI during callback), not an independent cause.

### Fixes applied (evidence-based)

1. **RewardPopupController:** Unregister the close animation completion callback during teardown so it cannot fire after the popup is destroyed.
2. **RewardPopupController.OnCloseAnimationComplete:** Return immediately when `this == null || gameObject == null` before calling `RefreshRewardVisuals()`.
3. **RewardPopupController.HandleClaim:** Set `isClosing = true` before starting the close sequence so duplicate claim inputs cannot schedule extra callbacks.
4. **RewardIconView:** Guard `SetVisible` with `if (activeImage != null)` before accessing `.gameObject`.

### One-line summary

The popup close animation completed after the popup had already been torn down, but its callback still invoked `RefreshRewardVisuals`, which reached a destroyed `RewardIconView` and caused `MissingReferenceException`. Fix: unregister the callback during teardown, bail out if the popup is already destroyed, and guard the icon view access.

---

## 9. Internal context available to the agent

- **Workspace path** and **session log path** (exact `debug-<session_id>.log` location for the current session).
- **Session ID** for the debug session.
- **Server endpoint** for HTTP-based logging (when applicable).
- **Git status** and open/recent files (for context on what was changed).
- **Always-applied workspace rules** (e.g. CLAUDE.md, Unity patterns, no [Inject], Clean Architecture).
- **User rules** (e.g. Unity: no CLI tests, compilation may fail for new classes, add debug logs when investigating without a clear fix, MacOS/zsh).
- **Agent skills** listed (e.g. debug-investigation, create-rule); use when relevant.
- **MCP instructions** (e.g. GitLab) for browsing/searching code in other repos.

---

## 10. Checklist for a new debug session

1. Confirm logging configuration (log path, server endpoint, session ID).
2. Reproduce and understand the stack trace and user scenario.
3. Write 3–5 hypotheses with clear, testable conditions.
4. Add 2–6 instrumentation points; each log must include hypothesisId and go to the session log path (or server).
5. Wrap logs in collapsible regions; no secrets in logs.
6. Delete only this session’s log file before asking the user to run.
7. Provide `<reproduction_steps>` and ask user to run.
8. Read logs; evaluate each hypothesis with cited lines; identify root cause.
9. Implement only evidence-based fix; keep instrumentation.
10. Ask user to verify; compare before/after logs if available.
11. On success (or explicit user confirmation): remove all instrumentation and document the fix in 1–2 lines.
12. If a hypothesis is rejected: remove only the code changes for that hypothesis; add new hypotheses and instrumentation if needed.
