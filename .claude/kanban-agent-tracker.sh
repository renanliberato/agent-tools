#!/usr/bin/env bash
input=$(cat)

tool_name=$(echo "$input" | jq -r '.tool_name // empty')
if [ "$tool_name" != "Agent" ]; then
  exit 0
fi

agent_name=$(echo "$input" | jq -r '.tool_input.subagent_type // empty')
if [ -z "$agent_name" ]; then
  prompt=$(echo "$input" | jq -r '.tool_input.prompt // empty' | head -c 200)
  for slug in kanban-plan kanban-code-reviewer kanban-docs-optimizer kanban-commit; do
    if echo "$prompt" | grep -q "$slug"; then
      agent_name="$slug"
      break
    fi
  done
fi

case "$agent_name" in
  kanban-plan|kanban-code-reviewer|kanban-docs-optimizer|kanban-commit) ;;
  *) exit 0 ;;
esac

session_id=$(echo "$input" | jq -r '.session_id // empty')
[ -z "$session_id" ] && exit 0

state_file="/tmp/claude-kanban-state-${session_id}.txt"
touch "$state_file"
grep -qxF "$agent_name" "$state_file" 2>/dev/null || echo "$agent_name" >> "$state_file"
