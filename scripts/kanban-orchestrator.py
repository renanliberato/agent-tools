#!/usr/bin/env python3
"""Watches a status dir and spawns cmux tabs for unblocked kanban tasks."""
import sys, os, json, subprocess, time

issues_dir    = sys.argv[1]
project_dir   = sys.argv[2]
status_dir    = sys.argv[3]
workspace_ref = sys.argv[4]

deps         = json.load(open(os.path.join(status_dir, 'deps.json')))
tasks        = deps['tasks']
failures_log = os.path.join(status_dir, 'failures.log')

# Capture orchestrator's own pane so we can refocus it after spawning task tabs
_orch_pane = os.environ.get('CMUX_SURFACE_ID', '')

spawned   = set()
done      = set()
failed    = set()
retryable = set()   # failed tasks still eligible for r/s
surfaces  = {}      # task_id → surface_ref
worktrees = {}      # task_id → worktree path


def has_failed_blocker(task_id):
    for b in tasks[task_id]['blockers']:
        if b in failed or has_failed_blocker(b):
            return True
    return False


def is_unblocked(task_id):
    return all(b in done for b in tasks[task_id]['blockers'])


def cleanup_task(task_id):
    if task_id in surfaces:
        subprocess.run(['cmux', 'close-surface', '--surface', surfaces.pop(task_id)], check=False)
    if task_id in worktrees:
        wt = worktrees.pop(task_id)
        branch = os.path.basename(wt)
        subprocess.run(['git', '-C', project_dir, 'worktree', 'remove', '--force', wt], check=False)
        subprocess.run(['git', '-C', project_dir, 'branch', '-D', branch], check=False)


def spawn_task(task_id):
    slug       = tasks[task_id]['slug']
    issue_path = os.path.join(issues_dir, slug + '.md')
    worktree   = os.path.join(os.path.dirname(project_dir),
                              f"{os.path.basename(project_dir)}-{slug}")

    base_branch = subprocess.run(
        ['git', '-C', project_dir, 'rev-parse', '--abbrev-ref', 'HEAD'],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    subprocess.run(['git', '-C', project_dir, 'worktree', 'add', worktree], check=True)

    result = subprocess.run(
        ['cmux', 'new-surface', '--type', 'terminal', '--workspace', workspace_ref],
        capture_output=True, text=True, check=True,
    )
    surface_ref = result.stdout.strip().split()[1]

    subprocess.run(['cmux', 'rename-tab', '--surface', surface_ref, slug], check=True)

    model    = os.environ.get('KANBAN_MODEL', 'sonnet')
    headless = os.environ.get('KANBAN_HEADLESS', '0')
    cmd = (
        f"cd '{worktree}' && "
        f"KANBAN_MODEL='{model}' KANBAN_HEADLESS='{headless}' "
        f"~/projects/renan/agent-tools/scripts/kanban-run-task.sh "
        f"'{task_id}' '{slug}' '{issue_path}' '{status_dir}' '{base_branch}'\n"
    )
    subprocess.run(['cmux', 'send', '--surface', surface_ref, cmd], check=True)

    spawned.add(task_id)
    surfaces[task_id]  = surface_ref
    worktrees[task_id] = worktree
    print(f"[kanban] → spawned {slug}", flush=True)
    if _orch_pane:
        subprocess.run(['cmux', 'focus-pane', '--pane', _orch_pane], check=False)


def try_spawn_unblocked():
    for task_id in sorted(tasks.keys()):
        if task_id in spawned:
            continue
        if has_failed_blocker(task_id):
            continue
        if is_unblocked(task_id):
            spawn_task(task_id)


def handle_failure(task_id):
    """Pause the loop and ask the user to retry or skip."""
    slug = tasks[task_id]['slug']
    retryable.add(task_id)
    cleanup_task(task_id)
    with open(failures_log, 'a') as f:
        f.write(f"[kanban] ✗ {slug} FAILED\n")

    if os.environ.get('KANBAN_HEADLESS', '0') == '1':
        retryable.discard(task_id)
        print(f"[kanban] ✗ {slug} FAILED — auto-skipped (headless)", flush=True)
        return

    while task_id in retryable:
        print(f"\n[kanban] ✗ {slug} FAILED", flush=True)
        print(f"  r {task_id} — retry (fresh worktree)", flush=True)
        print(f"  s {task_id} — skip permanently", flush=True)
        try:
            line = input("> ").strip()
        except EOFError:
            break

        parts = line.split()
        if len(parts) != 2:
            print("[kanban] expected: r <id> or s <id>", flush=True)
            continue
        cmd, tid = parts
        if tid != task_id:
            print(f"[kanban] unknown id {tid!r}", flush=True)
            continue

        if cmd == 'r':
            # Remove old status file so the watch loop won't re-trigger
            try:
                os.remove(os.path.join(status_dir, f"{task_id}.failed"))
            except FileNotFoundError:
                pass
            failed.discard(task_id)
            retryable.discard(task_id)
            spawned.discard(task_id)
            spawn_task(task_id)
            print(f"[kanban] retrying {slug} …", flush=True)

        elif cmd == 's':
            retryable.discard(task_id)
            print(f"[kanban] skipped {slug} — downstream tasks blocked", flush=True)

        else:
            print("[kanban] expected: r <id> or s <id>", flush=True)


def all_settled():
    if retryable:
        return False
    for task_id in tasks:
        if task_id in done or task_id in failed:
            continue
        if has_failed_blocker(task_id):
            continue
        return False
    return True


# Initial pass
try_spawn_unblocked()
print(f"[kanban] Watching {status_dir} …", flush=True)

while not all_settled():
    time.sleep(2)
    for fname in os.listdir(status_dir):
        if fname.endswith('.done'):
            task_id = fname[:-5]
            if task_id not in done and task_id not in retryable:
                done.add(task_id)
                print(f"[kanban] ✓ {tasks[task_id]['slug']}", flush=True)
                cleanup_task(task_id)
                try_spawn_unblocked()

        elif fname.endswith('.failed'):
            task_id = fname[:-7]
            if task_id not in failed and task_id not in retryable:
                failed.add(task_id)
                handle_failure(task_id)

print("[kanban] All tasks settled.", flush=True)
