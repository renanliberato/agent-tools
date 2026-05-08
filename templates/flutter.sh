# Flutter test template for broken-test-trace.sh
#
# Dart's test runner output format (compact reporter):
#   MM:SS +PASSED -FAILED: path/test.dart: description
#
# Failure signals:
#   - The -FAILED counter goes above 0 in the prefix
#   - Final line: "Some tests failed."
#
# Pass signal:
#   - Final line: "All tests passed!"

TEST_CMD="flutter test"

# Line-anchored: only matches the MM:SS +N -M prefix, never test descriptions
FAIL_PATTERN='^[0-9]{2}:[0-9]{2} \+[0-9]+ -[1-9]|^Some tests failed'

# Only matches the final summary line
PASS_PATTERN='^All tests passed!'

# Generous timeouts — flutter compilation can be slow
TIMEOUT_SEC=300
STALE_SEC=45
