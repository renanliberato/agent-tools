#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

destination_dir="$repo_root/skills"
source_dirs=(
  "$HOME/.agents/skills"
  "$HOME/.codex/skills"
)

mkdir -p "$destination_dir"

copied_any=false
for source_dir in "${source_dirs[@]}"; do
  if [[ ! -d "$source_dir" ]]; then
    continue
  fi

  cp -f -r "$source_dir/." "$destination_dir/"
  copied_any=true
done

if [[ "$copied_any" == false ]]; then
  echo "No upstream skill directories found." >&2
  exit 1
fi
