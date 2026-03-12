#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 /path/to/unity-project-root" >&2
  exit 1
fi

TARGET_ROOT="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)/UnityAssets"

if [ ! -d "$TARGET_ROOT" ]; then
  echo "Target project root does not exist: $TARGET_ROOT" >&2
  exit 1
fi

if [ ! -f "$TARGET_ROOT/ProjectSettings/ProjectVersion.txt" ]; then
  echo "Target is not a Unity project root: $TARGET_ROOT" >&2
  exit 1
fi

mkdir -p "$TARGET_ROOT/Assets" "$TARGET_ROOT/Scripts"

cp -R "$SOURCE_ROOT/Assets/." "$TARGET_ROOT/Assets/"
cp -R "$SOURCE_ROOT/Scripts/." "$TARGET_ROOT/Scripts/"
cp "$SOURCE_ROOT/unity-test" "$TARGET_ROOT/unity-test"
chmod +x "$TARGET_ROOT/unity-test"

echo "Installed unity-edit-mode-tests assets into $TARGET_ROOT"
