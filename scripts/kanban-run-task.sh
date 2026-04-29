#!/usr/bin/env zsh
source ~/.zshrc 2>/dev/null

task_id="$1"
task_slug="$2"
abs_issue_path="$3"
status_dir="$4"

sonnet "Work on @${abs_issue_path} and git commit after finishing."

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[kanban] Task: ${task_slug}"
echo "Did it succeed? (y/n):"
read -r answer

if [[ "$answer" == "y" ]]; then
  touch "${status_dir}/${task_id}.done"
  echo "[kanban] ✓ Marked as done."
else
  touch "${status_dir}/${task_id}.failed"
  echo "[kanban] ✗ Marked as failed. Downstream tasks blocked."
fi
