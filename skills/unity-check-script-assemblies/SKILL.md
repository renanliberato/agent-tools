---
name: unity-check-script-assemblies
description: Check whether a Unity project's C# scripts currently compile by rerunning the cached Bee `ScriptAssemblies` target from the latest Unity Editor DAG. Use when an agent needs a fast build verdict for Unity scripts, wants compiler errors without launching a full editor-driven build, or needs to confirm whether recent code changes introduced C# compilation failures in a Unity project.
---

# Unity Check Script Assemblies

## Workflow

1. Confirm the project is a Unity project.
   Run this skill from a project root that contains `ProjectSettings/ProjectVersion.txt`.

2. Ensure Unity has produced a recent DAG for this project.
   This workflow depends on the latest `ScriptAssemblies` DAG entry in `~/Library/Logs/Unity/Editor.log`.
   If the script reports that no DAG was found, open the project in Unity or trigger a compile once, then rerun the skill.

3. Run the helper script from the Unity project root.

```bash
/Users/renan.liberato/.codex/skills/unity-check-script-assemblies/scripts/check_script_assemblies.sh
```

   To target a different project root explicitly:

```bash
/Users/renan.liberato/.codex/skills/unity-check-script-assemblies/scripts/check_script_assemblies.sh /path/to/unity-project
```

4. Interpret the result directly from the command output.
   A successful compile ends with `*** Tundra build success ...`.
   A failed compile ends with `*** Tundra build failed ...` and includes Roslyn or Bee error details such as file paths, line numbers, and compiler error codes.

5. Report the result succinctly.
   State whether `ScriptAssemblies` built successfully.
   If the build failed, include the first actionable compiler error with its file and line number.

## Practical Notes

- Prefer this skill when the user wants a quick compile verdict instead of a full Unity test run or editor launch workflow.
- Treat missing `ProjectVersion.txt`, a missing Unity installation for that version, or a missing DAG entry as setup/precondition failures, not compile failures.
- Do not hide the raw compiler output. Summarize it, but preserve the important failing path, line, and error code in your response.
- If multiple Unity projects have been opened recently and the DAG looks stale or unrelated, tell the user the Editor log may need to be refreshed by opening the target project in Unity and compiling once.
