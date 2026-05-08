#!/usr/bin/env bash
# broken-test-trace.sh — git bisect to find the commit that broke tests
#
# Runs a test command at each bisect step with a watchdog that monitors output
# in real-time. Kills the test process immediately when:
#   1. A failure pattern is spotted in output
#   2. Output goes stale (no new lines for STALE_SEC seconds)
#   3. Overall TIMEOUT_SEC is exceeded
#
# Usage:
#   ./broken-test-trace.sh [template] [from-hash]
#
#   template   — Built-in name (e.g. "flutter") or path to a .sh template file
#   from-hash  — Last known-good commit hash
#
# Templates define:
#   TEST_CMD       — Command to run (required)
#   FAIL_PATTERN   — grep -E pattern that signals test failure
#   PASS_PATTERN   — grep -E pattern that signals all tests passed (optional)
#   TIMEOUT_SEC    — Max seconds per test run (default: 300)
#   STALE_SEC      — Max seconds with no new output before treating as hang (default: 45)
#
# Example:
#   ./broken-test-trace.sh flutter abc123def

set -euo pipefail

# ── helpers ────────────────────────────────────────────────────────────────

die() { echo "[broken-test-trace] ERROR: $*" >&2; exit 1; }
info() { echo "[broken-test-trace] $*" >&2; }

# ── args ───────────────────────────────────────────────────────────────────

if [[ $# -lt 2 ]]; then
    echo "Usage: broken-test-trace.sh [template] [from-hash]" >&2
    echo "" >&2
    echo "  template   — Built-in name or path to .sh template file" >&2
    echo "  from-hash  — Last known-good commit hash" >&2
    echo "" >&2
    echo "Built-in templates: flutter" >&2
    echo "Custom templates: put a .sh file in $(dirname "$0")/../templates/" >&2
    exit 1
fi

template="$1"
from_hash="$2"

# ── template loading ───────────────────────────────────────────────────────

TEMPLATE_DIR="$(cd "$(dirname "$0")/../templates" 2>/dev/null && pwd)"

if [[ -f "$template" ]]; then
    # User passed a file path directly
    template_file="$template"
elif [[ -f "${TEMPLATE_DIR}/${template}.sh" ]]; then
    template_file="${TEMPLATE_DIR}/${template}.sh"
else
    # Built-in templates
    case "$template" in
        flutter)
            # Flutter test: kill on first -N (failure counter > 0) or "Some tests failed"
            TEST_CMD="flutter test"
            FAIL_PATTERN='^[0-9]{2}:[0-9]{2} \+[0-9]+ -[1-9]|^Some tests failed'
            PASS_PATTERN='^All tests passed!'
            TIMEOUT_SEC=300
            STALE_SEC=45
            ;;
        *)
            die "Unknown template '$template'. Available built-ins: flutter"
            ;;
    esac
fi

# Source template file if one was found (overrides built-in defaults)
if [[ -n "${template_file:-}" ]] && [[ -f "${template_file:-}" ]]; then
    info "Loading template: $template_file"
    # shellcheck disable=SC1090
    source "$template_file"
fi

# Apply defaults
TIMEOUT_SEC="${TIMEOUT_SEC:-300}"
STALE_SEC="${STALE_SEC:-45}"
FAIL_PATTERN="${FAIL_PATTERN:-}"
PASS_PATTERN="${PASS_PATTERN:-}"

if [[ -z "${TEST_CMD:-}" ]]; then
    die "Template must define TEST_CMD"
fi

info "TEST_CMD     = $TEST_CMD"
info "FAIL_PATTERN = ${FAIL_PATTERN:-<none>}"
info "PASS_PATTERN = ${PASS_PATTERN:-<none>}"
info "TIMEOUT_SEC  = $TIMEOUT_SEC"
info "STALE_SEC    = $STALE_SEC"

# ── validation ─────────────────────────────────────────────────────────────

# Check from-hash exists
if ! git cat-file -e "$from_hash^{commit}" 2>/dev/null; then
    die "Commit '$from_hash' not found in this repo"
fi

# Check HEAD is different from from-hash
if [[ "$(git rev-parse HEAD)" == "$(git rev-parse "$from_hash")" ]]; then
    die "HEAD is the same as from-hash — nothing to bisect"
fi

# Check clean working tree (bisect requires it)
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    die "Working tree is dirty. Please commit or stash changes before bisecting."
fi

# ── generate bisect-run helper script ──────────────────────────────────────

bisect_script="$(mktemp -t bisect-run.XXXXXX)"
chmod +x "$bisect_script"

# Write the helper script. Variables from this scope are expanded into it.
# The child script uses \$ for its own variables.
cat > "$bisect_script" << BISECT_END
#!/usr/bin/env bash
# Auto-generated bisect-run helper — called by git bisect run at each step
set -o pipefail

COMMIT=\$(git rev-parse --short HEAD)
echo "[bisect] testing commit \${COMMIT} ..." >&2

tmpout="\$(mktemp -t bt-output.XXXXXX)"
cleanup() { rm -f "\$tmpout"; }
trap cleanup EXIT

# Run test command in background, capturing all output
${TEST_CMD} > "\$tmpout" 2>&1 &
test_pid=\$!
start_time=\$SECONDS

last_size=0
stale_start=0
fail_timeout=${TIMEOUT_SEC}
stale_timeout=${STALE_SEC}

echo "[bisect] \${COMMIT} — pid=\$test_pid, timeout=\${fail_timeout}s, stale=\${stale_timeout}s" >&2

while kill -0 \$test_pid 2>/dev/null; do
    elapsed=\$(( SECONDS - start_time ))
    now=\$SECONDS

    # ── check for failure patterns ────────────────────────────────────
    if [[ -n "${FAIL_PATTERN}" ]]; then
        if grep -qE '${FAIL_PATTERN}' "\$tmpout" 2>/dev/null; then
            printf '[bisect] \033[31mFAIL\033[0m \${COMMIT} — failure pattern matched at %ds\n' "\$elapsed" >&2
            kill -9 \$test_pid 2>/dev/null
            wait \$test_pid 2>/dev/null || true
            exit 1
        fi
    fi

    # ── check for pass patterns (early exit on all-pass) ─────────────
    if [[ -n "${PASS_PATTERN}" ]]; then
        if grep -qE '${PASS_PATTERN}' "\$tmpout" 2>/dev/null; then
            # Wait for test to finish naturally — the pass line appears at the end
            wait \$test_pid 2>/dev/null
            test_rc=\$?
            printf '[bisect] \033[32mPASS\033[0m \${COMMIT} — completed in %ds (exit %d)\n' "\$elapsed" "\$test_rc" >&2
            exit 0
        fi
    fi

    # ── check for stale output (hung test) ───────────────────────────
    cur_size=\$(wc -c < "\$tmpout" 2>/dev/null || echo 0)
    if [[ "\$cur_size" -eq "\$last_size" ]]; then
        if [[ \$stale_start -eq 0 ]]; then
            stale_start=\$now
        elif [[ \$(( now - stale_start )) -ge \$stale_timeout ]]; then
            stale_dur=\$(( now - stale_start ))
            printf '[bisect] \033[33mSTALE\033[0m \${COMMIT} — no output for %ds, treating as hang\n' "\$stale_dur" >&2
            kill -9 \$test_pid 2>/dev/null
            wait \$test_pid 2>/dev/null || true
            exit 1
        fi
    else
        stale_start=0
        last_size=\$cur_size
    fi

    # ── overall timeout ──────────────────────────────────────────────
    if [[ \$elapsed -ge \$fail_timeout ]]; then
        printf '[bisect] \033[33mTIMEOUT\033[0m \${COMMIT} — %ds elapsed, killing\n' "\$elapsed" >&2
        kill -9 \$test_pid 2>/dev/null
        wait \$test_pid 2>/dev/null || true
        exit 1
    fi

    sleep 0.5
done

# Test process exited naturally — use its exit code
wait \$test_pid 2>/dev/null
test_rc=\$?
elapsed=\$(( SECONDS - start_time ))

if [[ \$test_rc -eq 0 ]]; then
    printf '[bisect] \033[32mPASS\033[0m \${COMMIT} — exit 0 in %ds\n' "\$elapsed" >&2
else
    printf '[bisect] \033[31mFAIL\033[0m \${COMMIT} — exit %d in %ds\n' "\$test_rc" "\$elapsed" >&2
fi
exit \$test_rc
BISECT_END

# ── snapshot HEAD before bisect (so we can report after reset) ─────────────

orig_head="$(git rev-parse --short HEAD)"

# ── run bisect ─────────────────────────────────────────────────────────────

info "Starting bisect: HEAD (bad) ← ... → $from_hash (good)"
info "Bisect helper: $bisect_script"

git bisect start HEAD "$from_hash" --
git bisect run "$bisect_script"
bisect_rc=$?

# ── capture the bad commit BEFORE resetting bisect state ───────────────────

bad_commit=""
if [[ $bisect_rc -eq 0 ]]; then
    # git bisect run exits 0 when it found the first bad commit.
    # The bad commit is the one currently checked out (detached HEAD).
    bad_commit="$(git rev-parse --short HEAD 2>/dev/null || echo "")"
    if [[ -z "$bad_commit" ]]; then
        # Fallback: check the bisect log for the first bad commit
        bad_commit="$(git bisect log 2>/dev/null | head -1 | awk '{print $NF}' || echo "")"
    fi
fi

# ── reset bisect state ─────────────────────────────────────────────────────

git bisect reset 2>/dev/null || true
rm -f "$bisect_script"

# ── report ─────────────────────────────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [[ -n "$bad_commit" ]]; then
    info "✓ First bad commit: $bad_commit"
    echo ""
    git log --oneline -1 "$bad_commit" 2>/dev/null || true
    echo ""
    # Show the range of commits tested
    info "Range: $from_hash (good) → $bad_commit (first bad) → $orig_head (bad HEAD)"
else
    info "Bisect did not identify a single bad commit (exit $bisect_rc)"
    info "This can happen if:"
    info "  - from-hash is not actually good (tests fail there too)"
    info "  - Skipped commits prevented bisect from completing"
    info "  - Bisect was interrupted"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

exit $bisect_rc
