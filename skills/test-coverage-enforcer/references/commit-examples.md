# Test Coverage Patterns (Project-Agnostic)

These patterns illustrate what strong coverage looks like when introducing new behavior.

## Config/Filter Logic

Coverage patterns:
- Validate config parsing for nil, empty, and populated inputs.
- Exercise filter behavior with concrete inputs and verify side effects (order, omitted IDs, counts).
- Ensure no-op behavior when inputs are empty.
- Add retrocompat tests to ensure defaults remain unchanged and new behavior only activates when gated.

## Localization/Fallback Behavior

Coverage patterns:
- Use in-memory databases for integration-style repository/handler tests.
- Seed fixtures for both localized and base data.
- Verify localized behavior and fallback behavior.
- Test handler responses end-to-end (status + decoded payload).
- Add retrocompat tests that prove base behavior remains default unless a locale or flag is provided.
