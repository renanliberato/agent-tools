#!/bin/zsh
set -euo pipefail

project_root="${1:-$PWD}"
editor_log="${UNITY_EDITOR_LOG:-$HOME/Library/Logs/Unity/Editor.log}"

if [[ ! -d "$project_root" ]]; then
  echo "Project root does not exist: $project_root" >&2
  exit 2
fi

cd "$project_root"

if [[ ! -f "ProjectSettings/ProjectVersion.txt" ]]; then
  echo "ProjectSettings/ProjectVersion.txt not found in: $project_root" >&2
  exit 2
fi

if [[ ! -f "$editor_log" ]]; then
  echo "Unity Editor log not found: $editor_log" >&2
  exit 2
fi

editor_version="$(
  awk '/^m_EditorVersion: /{print $2; exit}' ProjectSettings/ProjectVersion.txt
)"

if [[ -z "$editor_version" ]]; then
  echo "Could not read m_EditorVersion from ProjectSettings/ProjectVersion.txt" >&2
  exit 2
fi

unity_bee_backend="/Applications/Unity/Hub/Editor/$editor_version/Unity.app/Contents/bee_backend"

if [[ ! -x "$unity_bee_backend" ]]; then
  echo "Unity bee_backend not found or not executable: $unity_bee_backend" >&2
  exit 2
fi

dag_file="$(
  sed -nE 's#.*--dagfile="([^"]+)".* ScriptAssemblies$#\1#p' "$editor_log" | tail -n1
)"

if [[ -z "$dag_file" ]]; then
  echo "No ScriptAssemblies dagfile was found in $editor_log" >&2
  echo "Open the Unity project and let it compile once, then rerun this script." >&2
  exit 2
fi

if [[ ! -f "$dag_file" ]]; then
  echo "Resolved dagfile does not exist: $dag_file" >&2
  echo "Open the Unity project and let it compile again to refresh the DAG." >&2
  exit 2
fi

"$unity_bee_backend" --dagfile="$dag_file" --continue-on-failure ScriptAssemblies
