#!/usr/bin/env zsh
source ~/.zshrc 2>/dev/null

task_id="$1"
task_slug="$2"
abs_issue_path="$3"
status_dir="$4"
base_branch="${5:-main}"

model="${KANBAN_MODEL:-sonnet}"
prompt="This is the task worktree at ${PWD}/. The project code is here — edit files in-place, commit from this directory. Issue spec at @${abs_issue_path}. Target branch is '${base_branch}'. Do all file edits and the git commit from the current directory; do not switch to other repos or worktrees."

if [[ "${KANBAN_HEADLESS:-0}" == "1" ]]; then
  "$model" -p "$prompt"
  task_exit=$?
else
  "$model" "$prompt"
  task_exit=0
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[kanban] Task: ${task_slug}"

if [[ "${KANBAN_HEADLESS:-0}" == "1" ]]; then
  if [[ $task_exit -eq 0 ]]; then
    answer="y"
    echo "[kanban] Headless run completed (exit 0) — auto-marking succeeded."
  else
    answer="n"
    echo "[kanban] Headless run failed (exit ${task_exit}) — auto-marking failed."
  fi
else
  echo "Did it succeed? (y/n):"
  read -r answer
fi

if [[ "$answer" == "y" ]]; then
  commit_lock="${status_dir}/commit.lock"
  while ! mkdir "${commit_lock}" 2>/dev/null; do
    echo "[kanban] Waiting for commit lock (another task is committing)..."
    sleep 5
  done
  echo "[kanban] Running commit agent..."
  # Ensure .claude/agents/ exists in the worktree (not tracked in git)
  mkdir -p "${PWD}/.claude/agents"
  agent_src="$(dirname "$0")/../.claude/agents"
  cp -r "${agent_src}/." "${PWD}/.claude/agents/"
  KANBAN_BASE_BRANCH="${base_branch}" pi -p "EXECUTE the following agent instructions now. Do NOT describe or discuss them. Do NOT ask what to do. Just run every step in order. KANBAN_BASE_BRANCH=${base_branch}.

@.claude/agents/kanban-commit.md"
  rmdir "${commit_lock}"
  touch "${status_dir}/${task_id}.done"

  # State transition: rename issue file to .done.md
  issues_dir="$(dirname "${abs_issue_path}")"
  fname="$(basename "${abs_issue_path}")"
  # Remove .backlog.md or .active.md suffix, add .done.md
  done_fname="${fname%.backlog.md}"
  done_fname="${done_fname%.active.md}"
  if [[ -z "$done_fname" ]]; then
    done_fname="${fname%.md}"
  fi
  done_fname="${done_fname}.done.md"

  # Update the issue file with completion metadata before renaming
  {
    echo ""
    echo "---"
    echo "completed: $(date +%Y-%m-%d)"
    echo "state: done"
    echo "---"
  } >> "${abs_issue_path}"

  mv "${abs_issue_path}" "${issues_dir}/${done_fname}"
  echo "[kanban] ✓ Issue transitioned: $(basename "${abs_issue_path}") → ${done_fname}"

  # Commit state transition to kanban repo
  kanban_dir="$(dirname "${issues_dir}")"
  git -C "${kanban_dir}" add -A
  git -C "${kanban_dir}" commit -m "done: ${task_id}-${task_slug}"
  echo "[kanban] ✓ Committed to kanban repo."
  echo "[kanban] ✓ Marked as done."
else
  touch "${status_dir}/${task_id}.failed"
  echo "[kanban] ✗ Marked as failed. Downstream tasks blocked."
fi
