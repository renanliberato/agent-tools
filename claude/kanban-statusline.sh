#!/usr/bin/env bash
input=$(cat)

git_worktree=$(echo "$input" | jq -r '.workspace.git_worktree // empty')
if [ -z "$git_worktree" ]; then
  exit 0
fi

session_id=$(echo "$input" | jq -r '.session_id // empty')
state_file="/tmp/claude-kanban-state-${session_id}.txt"

plan=0; reviewer=0; docs=0; commit=0

if [ -f "$state_file" ]; then
  while IFS= read -r line; do
    case "$line" in
      kanban-plan)           plan=1 ;;
      kanban-code-reviewer)  reviewer=1 ;;
      kanban-docs-optimizer) docs=1 ;;
      kanban-commit)         commit=1 ;;
    esac
  done < "$state_file"
fi

box_plan=$([ "$plan" -eq 1 ]     && echo "☑" || echo "☐")
box_rev=$([ "$reviewer" -eq 1 ]  && echo "☑" || echo "☐")
box_docs=$([ "$docs" -eq 1 ]     && echo "☑" || echo "☐")
box_commit=$([ "$commit" -eq 1 ] && echo "☑" || echo "☐")

printf "%s plan  %s review  %s docs  %s commit" \
  "$box_plan" "$box_rev" "$box_docs" "$box_commit"
