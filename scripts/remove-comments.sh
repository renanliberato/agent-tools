#!/bin/bash

# Remove comments from changed C# files in a git range, touching only the
# lines that were added/modified in the range (pre-existing comments are kept).
# Usage: ./remove-comments.sh <git-range>
# Example: ./remove-comments.sh main..HEAD
#          ./remove-comments.sh HEAD~3..HEAD

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <git-range>"
    echo "Example: $0 main..HEAD"
    echo "         $0 HEAD~3..HEAD"
    exit 1
fi

RANGE=$1

# Get changed C# files in the range
changed_files=$(git diff --name-only "$RANGE" -- '*.cs' 2>/dev/null || echo "")

if [ -z "$changed_files" ]; then
    echo "No C# files found in range: $RANGE"
    exit 0
fi

echo "Processing the following files:"
echo "$changed_files"
echo ""

for file in $changed_files; do
    [ -f "$file" ] || continue

    # Collect the new-file line numbers of lines added in the range.
    # git diff -U0 emits hunks with no context; in "@@ -a,b +c,d @@" the +c,d
    # side is the new-file start line and each "+" line advances it.
    added_list=$(mktemp)
    git diff -U0 "$RANGE" -- "$file" | awk '
        /^@@ / {
            split($3, a, ",")
            newline = a[1] + 0
            next
        }
        /^\+\+\+/ { next }
        /^\+/ {
            print newline
            newline++
        }
    ' > "$added_list"

    if [ ! -s "$added_list" ]; then
        rm "$added_list"
        continue
    fi

    echo "Cleaning: $file"

    tmpfile=$(mktemp)
    awk '
        NR == FNR {
            added[$1] = 1
            next
        }
        {
            lines[FNR] = $0
        }
        END {
            n = FNR

            # Pass 1: find multi-line /* ... */ blocks. A block is removed
            # only when every one of its lines is part of the diff; otherwise
            # it is left untouched (even the added lines inside it).
            for (i = 1; i <= n; i++) {
                if (i in block || i in keep) continue
                t = lines[i]
                sub(/^[ \t]+/, "", t)
                if (t !~ /^\/\*/ || t ~ /\*\//) continue
                end = i
                while (end <= n && lines[end] !~ /\*\//) end++
                if (end > n) end = n
                alladded = 1
                for (j = i; j <= end; j++) {
                    if (!(j in added)) { alladded = 0; break }
                }
                if (alladded) {
                    for (j = i; j <= end; j++) block[j] = 1
                } else {
                    for (j = i; j <= end; j++) keep[j] = 1
                }
            }

            # Pass 2: emit, touching only lines that were added in the range
            for (i = 1; i <= n; i++) {
                line = lines[i]

                if (i in added && !(i in keep)) {
                    t = line
                    sub(/^[ \t]+/, "", t)

                    if (t ~ /^\/\//) {                       # // or /// line
                        continue
                    }
                    if (i in block) {                        # fully-added block
                        continue
                    }

                    if (t ~ /^\/\*/ && t ~ /\*\//) {         # single-line /* */ line
                        rest = t
                        sub(/\/\*.*\*\//, "", rest)
                        sub(/^[ \t]+/, "", rest)
                        if (rest == "") {
                            continue
                        }
                        line = rest
                        t = rest
                    }

                    # Strip a trailing // comment, but only when the // is not
                    # inside a string literal (even number of quotes before it)
                    if (line ~ /\/\//) {
                        pos = index(line, "//")
                        pre = substr(line, 1, pos - 1)
                        q = pre
                        gsub(/"/, "", q)
                        if (length(q) % 2 == 0) {
                            line = pre
                            sub(/[ \t]+$/, "", line)
                        }
                    }
                }
                print line
            }
        }
    ' "$added_list" "$file" > "$tmpfile"
    rm "$added_list"

    # Check if file actually changed
    if ! diff -q "$file" "$tmpfile" > /dev/null 2>&1; then
        mv "$tmpfile" "$file"
        echo "  ✓ Cleaned"
    else
        rm "$tmpfile"
        echo "  - No changes needed"
    fi
done

echo ""
echo "Done! Review changes with: git diff"
