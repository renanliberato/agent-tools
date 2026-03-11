---
name: evidence-debugger
description: Run evidence-first debug investigations that require runtime logs before code fixes. Use when a user reports a bug, exception, stale-reference issue, lifecycle race, or other behavior that cannot be fixed safely from static code inspection alone, especially when the workflow should generate hypotheses, add targeted instrumentation, collect reproduction logs, evaluate hypotheses with cited log evidence, verify the fix with before/after logs, and keep instrumentation until success is proven.
---

# Evidence Debugger

## Workflow

1. Confirm the logging configuration before editing.
   Resolve a logging destination before instrumenting.
   If the user already gave a session log path, use it.
   Otherwise, create one yourself with a deterministic unique name such as `/tmp/evidence-debugger-<timestamp>-<shortid>.ndjson` and tell the user the exact path so later turns can refer to it.
   When relevant, also resolve the server endpoint and session ID.
   Do not instrument anything until the logging destination is known.

2. Reconstruct the failure from runtime context.
   Read the bug report, stack trace, and relevant code paths.
   Identify the user flow, the failing method, and the likely lifecycle boundaries involved.

3. Generate 3 to 5 precise hypotheses.
   Make each hypothesis falsifiable.
   Prefer mechanism-level statements such as stale references, destroyed objects, unexpected branch selection, out-of-order callbacks, or invalid state transitions.

4. Add the minimum instrumentation needed to test the hypotheses in parallel.
   Add at least 1 log and usually 2 to 6 total.
   Never exceed 10 logs without narrowing the hypotheses first.
   Wrap every debug log in a collapsible region.
   Include `hypothesisId`, `location`, `message`, `timestamp`, and useful state in every payload.
   Never log secrets, tokens, passwords, API keys, or PII.

5. Clear only the current session log before the user runs again.
   Delete only the current session log file.
   Do not treat log clearing as instrumentation removal.
   If you generated the log path yourself, keep using that same path for the current investigation until verification is complete.

6. Ask the user to reproduce with a `<reproduction_steps>` block.
   End with a short, numbered, interface-agnostic instruction block.
   Tell the user to reply in natural language when the reproduction attempt is done.
   If services must restart, say so.

7. Read the logs and evaluate every hypothesis.
   Mark each one as `CONFIRMED`, `REJECTED`, or `INCONCLUSIVE`.
   Cite exact log lines when explaining the verdict.
   Identify the single root-cause mechanism that best explains the failure.

8. Apply only the evidence-backed fix.
   Keep the change small and architecture-consistent.
   Do not keep speculative guards or unrelated cleanup.
   If a hypothesis was rejected, remove the code changes that were only supporting that hypothesis.

9. Verify with logs before claiming success.
   Keep instrumentation active for the verification run.
   Compare before and after behavior with cited log evidence.
   Remove instrumentation only after the logs prove success or the user explicitly confirms the issue is fixed.

10. Close with a short explanation.
    Summarize the actual failure mechanism and the precise fix in 1 to 2 lines.

## Required Constraints

- Never fix from code inspection alone when runtime evidence is expected to be obtainable.
- Never use `setTimeout`, `sleep`, or artificial delays as the fix for a race or lifecycle bug.
- Never remove instrumentation before post-fix verification succeeds or the user explicitly confirms success.
- Never claim the issue is fixed without log proof or explicit user confirmation.
- When all current hypotheses are rejected, generate new ones and instrument again.

## Instrumentation Rules

- Map each log to at least one hypothesis.
- Log function entry, function exit, branch choice, state mutation, and pre/post critical values as needed.
- For JavaScript or TypeScript, send the payload to the provisioned HTTP endpoint and include the session ID when present.
- For C#, Unity, or other non-JavaScript environments, append one NDJSON object per log line directly to the session log path.
- When no path was provided by the user, prefer a self-generated log file in `/tmp` over blocking on missing session-log setup.
- Keep instrumentation snippets minimal and local to the suspected mechanism.

## Reproduction Block

Use this exact structure at the end of the investigation request:

```xml
<reproduction_steps>
1. Reproduce the issue in the target environment.
2. Follow the bug path until the failing action occurs.
3. Reply here when the reproduction attempt is done.
</reproduction_steps>
```

Only keep numbered steps inside the tag.

## Analysis Standard

- Cite the log lines that support each hypothesis verdict.
- Distinguish root cause from downstream consequences.
- Prefer one concrete mechanism over a vague multi-cause explanation.
- If verification fails, remove the rejected hypothesis changes only, then repeat the hypothesis and instrumentation loop.

## Reference

Read [debug-session-replication-guide.md](./references/debug-session-replication-guide.md) when you need:

- The full checklist for a debug session
- Detailed NDJSON payload examples
- Unity and non-JavaScript logging guidance
- The worked Unity lifecycle MissingReferenceException example used to illustrate this skill
