---
name: test-coverage-enforcer
description: Ensure implementation plans and code changes include automated tests (unit/integration) for every new scenario or use case; use when asked to guarantee tests, enforce coverage, or create plans that must include tests.
---

# Test Coverage Enforcer

## Objectives
- Guarantee that every code change and new scenario/use case is covered by automated tests (unit or integration).
- Refuse to finalize without tests unless the user explicitly waives the requirement.

## Non-negotiables
1. Identify new or changed behaviors and map each to tests.
2. Require retrocompatibility by default: existing behavior must remain the default path, and new behavior must be gated (param/config/envvar/etc).
3. Add tests for each new scenario/use case **and** for retrocompatibility (existing behavior still works by default). If impossible, stop and ask for missing info or an explicit waiver.
4. Always run the full test suite whenever modifying code or tests. If blocked, stop and request approval or an explicit waiver.
5. Do not claim tests ran unless actually run; if not run, state so and provide commands.
6. If changes are documentation-only with no behavior change, mark tests as not applicable.

## Workflow
1. Enumerate changes and scenarios.
2. Build a Test Coverage Matrix.
3. Plan or implement code and tests together.
4. Verify via tests (run all tests when code/tests change).
5. Report coverage and commands.

### Test Coverage Matrix (required)
Use this table in plans and final summaries:

Change/Scenario | Test Type | Test Location | Status
---|---|---|---
Example: new filter behavior | unit | `backend/internal/stylesranking/filters_test.go` | new

### Plan requirements
- Include tasks for creating/updating tests and running them.
- Do not end a plan without explicit test steps.

### Implementation rules
- Prefer unit tests for pure logic, integration tests for API/IO flows.
- For bug fixes, add regression tests first.
- Update or add fixtures, mocks, or fakes as needed.
- Keep tests close to existing conventions (file naming, helper patterns).
- Ensure retrocompatibility tests cover default behavior and new behavior only when gated.

### Exception handling
- If a user requests skipping tests or retrocompatibility, confirm explicitly and record the waiver in the response.
- If the environment blocks test writing (missing frameworks, ambiguous behavior), ask for clarification instead of proceeding.

## Output format
- Always include a `Tests` section listing added/updated tests and whether they ran.
- Include a `Coverage Gaps` section only if a user waived tests or missing info prevented coverage.
- If tests were not run, include the exact commands to run them.

## Pattern examples
- Consult `references/commit-examples.md` for concrete test-coverage patterns.
