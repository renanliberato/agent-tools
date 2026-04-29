#!/usr/bin/env zsh
source ~/.zshrc 2>/dev/null

task_id="$1"
task_slug="$2"
abs_issue_path="$3"
status_dir="$4"

${KANBAN_MODEL:-sonnet} "Read the issue spec at @${abs_issue_path}, then implement it in the current worktree (${PWD}/). Do all file edits and the git commit from the current directory; do not switch to the parent worktree for git operations."

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
