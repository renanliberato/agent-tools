#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

cp -f -r "$repo_root/skills/." "$HOME/.agents/skills"
cp -f -r "$repo_root/skills/." "$HOME/.cursor/skills"
