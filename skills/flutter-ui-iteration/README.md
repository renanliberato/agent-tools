# codex-skill-flutter-ui-iteration

This repo hosts a Codex skill focused on iterating Flutter UI.

## Using skills

Save your skills where Codex expects them (see the official guide: https://developers.openai.com/codex/skills/#where-to-save-skills), then point Codex at this repo or copy the `SKILL.md` into your skills directory.

## Why close the loop

Closing the loop here means a single Codex session can make a code change, hot reload, take a screenshot, reason about the result, and repeat. That tight feedback cycle speeds up UI iteration, reduces guesswork, and keeps changes aligned with the visual outcome.

```
+--------------+     +--------------+     +--------------+     +--------------+     +--------------+
| code change  | --> |  hot reload  | --> |  screenshot  | --> |    reason    | --> |    repeat    |
+--------------+     +--------------+     +--------------+     +--------------+     +--------------+
       ^                                                                                           v
       |                                                                                           |
       <-------------------------------------------------------------------------------------------+
```
