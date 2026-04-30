---
name: to-issues
description: ELIMINATED — Issues are created directly via backlog-add or manually. PRDs reference issues by ID in their frontmatter. This file is kept for reference.
---

# ELIMINATED

**to-issues is no longer needed.**

Issues are created directly as `<project>-kanban/issues/<id>-<slug>.<state>.md`.

- Use `backlog-add` for fast capture (with optional grilling).
- Write files manually if you need something specific.
- PRDs reference their associated issues in the `issues` frontmatter field.

The old sequential numbering (01, 02...) has been replaced by a single global sequential counter (000001, 000042...) shared across all issues regardless of state.
