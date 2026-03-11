---
name: tiger-style
description: Code review and design critique using TigerBeetle's TigerStyle principles (safety, performance, developer experience, zero technical debt). Use when the user asks for a "tiger style" review of unstaged changes, a commit, or a branch comparison, or explicitly requests TigerStyle guidance. Apply across languages and adapt Zig-specific rules to the project's conventions.
---

# Tiger Style

## Overview
Apply TigerStyle principles during code review: prioritize safety, then performance, then developer experience, and avoid technical debt. Use the full reference in `references/tigerstyle.md` for exact wording and deeper rationale.

## Workflow
1. Determine scope. Ask for repo context, diff/commit/branches if not provided. Use `git diff`, `git show`, or `git log` as needed.
2. Read `references/tigerstyle.md` to refresh key principles for the review.
3. Review with priority order: safety > performance > developer experience > style.
4. Flag issues as `Blocker`, `Should fix`, or `Suggestion`.
5. For each finding, provide:
   - Location (file/line or diff hunk)
   - What is wrong or risky
   - Why it matters (tie back to TigerStyle goals)
   - Concrete fix or alternative
6. Call out missing tests and propose assertions, bounds checks, or negative-space tests.

## Language Adaptation
- Do not enforce Zig-only rules (e.g., `zig fmt`, 4-space indentation, Zig naming) unless the project uses them.
- Translate principles to the project language:
  - Use explicitly-sized numeric types where the language supports them; otherwise be explicit about ranges and units.
  - Prefer bounded loops, explicit limits, and fail-fast checks.
  - Avoid recursion for unbounded workflows; favor iterative or bounded approaches.
  - Minimize dynamic allocation in hot paths; pre-allocate or pool where practical.
  - Avoid implicit defaults in library calls; pass options explicitly when meaningful.
  - Keep functions small and focused; split control flow from computation.

## Safety Checklist
- Assert inputs, outputs, invariants, and bounds.
- Handle error returns explicitly.
- Limit loops, queues, retries, and sizes.
- Split compound conditions to make cases explicit.
- State invariants positively; avoid negated logic where clarity suffers.

## Performance Checklist
- Do back-of-the-envelope resource sketches (CPU, memory, disk, network).
- Optimize for the slowest bottleneck first.
- Batch work and amortize costs.
- Extract hot loops; avoid hidden copies; avoid unnecessary allocations.

## Developer Experience Checklist
- Choose precise names; avoid ambiguous abbreviations.
- Explain rationale with brief comments when non-obvious.
- Keep ordering and grouping of code intentional.

## References
- `references/tigerstyle.md` contains the full TigerStyle source text.
