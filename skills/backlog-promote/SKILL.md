---
name: backlog-promote
description: DEPRECATED — The backlog/issue distinction no longer exists. All work items are issues (<project>-kanban/issues/<id>-<slug>.<state>.md) from creation. Use backlog-add to capture an issue, to-prd to create a PRD. This skill is kept for reference only.
---

# DEPRECATED

**backlog-promote is no longer needed.**

The old pipeline was: `backlog-add → backlog-promote → to-prd → to-issues`.

The new pipeline is:
- `backlog-add` — creates an issue directly in `<project>-kanban/issues/<id>-<slug>.backlog.md`
- `to-prd` — creates a numbered, versioned PRD in `<project>-kanban/prds/<id>-<slug>.md`
- State transitions are `git mv` operations: `.backlog.md → .active.md → .done.md`

There is no "promotion" step because there is no distinction between a backlog entry and an issue. They are the same file from creation.
