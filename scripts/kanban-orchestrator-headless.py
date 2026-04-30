#!/usr/bin/env python3
"""Headless kanban orchestrator. Spawns tasks in parallel without cmux,
streams status to a live-updating CLI dashboard.

Usage:
  kanban-orchestrator-headless.py <issues_dir> <project_dir> <status_dir>
  kanban-orchestrator-headless.py --watch <issues_dir> <project_dir> <status_dir>
  kanban-orchestrator-headless.py --watch --poll-seconds 10 <...>

Flags:
  --watch            Keep alive after initial batch settles; watch for new
                     .backlog.md issues and auto-start them.
  --poll-seconds N   Watch loop poll interval in seconds (default: 5).
"""
import sys, os, json, subprocess, time, threading, signal, shutil
from datetime import datetime

try:
    from rich.live import Live
    from rich.table import Table
    from rich.console import Console
    RICH = True
except ImportError:
    RICH = False

# --- Argument parsing ---
watch_mode = False
poll_seconds = 5
positional = []
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == '--watch':
        watch_mode = True
        i += 1
    elif a == '--poll-seconds' and i + 1 < len(sys.argv):
        try:
            poll_seconds = int(sys.argv[i + 1])
        except ValueError:
            pass
        i += 2
    elif a.startswith('--'):
        i += 1  # skip unknown flags
    else:
        positional.append(a)
        i += 1

issues_dir  = positional[0]
project_dir = positional[1]
status_dir  = positional[2]

deps  = json.load(open(os.path.join(status_dir, 'deps.json')))
tasks = deps['tasks']

start_time = time.time()
state_lock = threading.Lock()
shutdown   = threading.Event()

# Track all known issue IDs (for watch mode dedup)
known_ids = set(tasks.keys())

# Per-task state
task_state = {}
for tid, info in tasks.items():
    task_state[tid] = {
        'slug':       info['slug'],
        'blockers':   info['blockers'],
        'status':     'PENDING',
        'started_at': None,
        'ended_at':   None,
        'log_path':   os.path.join(status_dir, f"{tid}.log"),
        'last_line':  '',
        'proc':       None,
        'worktree':   None,
    }

PARSER_SCRIPT = os.path.expanduser(
    '~/projects/renan/agent-tools/scripts/kanban-parse-deps.py'
)


# --- Helpers ---

def find_issue_file(tid):
    """Return the path of the issue file for given task ID, or None."""
    for suffix in ('.backlog.md', '.active.md'):
        path = os.path.join(issues_dir, tid + suffix)
        if os.path.exists(path):
            return path
    return None


def promote_to_active(tid):
    """Rename <tid>.backlog.md → <tid>.active.md. Returns active path or None."""
    backlog_path = os.path.join(issues_dir, tid + '.backlog.md')
    active_path  = os.path.join(issues_dir, tid + '.active.md')
    if os.path.exists(backlog_path):
        os.rename(backlog_path, active_path)
        return active_path
    return None


def has_failed_blocker(tid):
    for b in task_state[tid]['blockers']:
        if b not in task_state:
            continue  # blocker not created yet — cannot be failed
        if task_state[b]['status'] in ('FAILED', 'SKIPPED'):
            return True
        if has_failed_blocker(b):
            return True
    return False


def is_unblocked(tid):
    for b in task_state[tid]['blockers']:
        if b not in task_state:
            return False  # blocker doesn't exist yet
        if task_state[b]['status'] != 'DONE':
            return False
    return True


def get_repo_for_tid(tid):
    """Return the repo path for a task (from issue frontmatter `repo:`), falling back to project_dir."""
    repo = tasks.get(tid, {}).get('repo', '')
    if repo:
        return os.path.expanduser(repo)
    return project_dir


def get_branch_for_tid(tid):
    """Return the branch for a task (from issue frontmatter `branch:`),
    or the repo's current HEAD branch."""
    branch = tasks.get(tid, {}).get('branch', '')
    if branch:
        return branch
    repo = get_repo_for_tid(tid)
    return subprocess.run(
        ['git', '-C', repo, 'rev-parse', '--abbrev-ref', 'HEAD'],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def cleanup_worktree(tid):
    wt = task_state[tid]['worktree']
    if not wt:
        return
    repo = get_repo_for_tid(tid)
    branch = os.path.basename(wt)
    subprocess.run(['git', '-C', repo, 'worktree', 'remove', '--force', wt],
                   check=False, capture_output=True)
    subprocess.run(['git', '-C', repo, 'branch', '-D', branch],
                   check=False, capture_output=True)
    task_state[tid]['worktree'] = None


def spawn_task(tid):
    st         = task_state[tid]
    slug       = st['slug']

    # Resolve issue file — promote from backlog if needed
    issue_path = find_issue_file(tid)
    if issue_path is None:
        issue_path = promote_to_active(tid)
    elif issue_path.endswith('.backlog.md'):
        issue_path = promote_to_active(tid)

    if issue_path is None:
        with state_lock:
            st['status'] = 'FAILED'
            st['last_line'] = 'no issue file found'
        return

    repo_path = get_repo_for_tid(tid)
    base_branch = get_branch_for_tid(tid)

    worktree = os.path.join(
        os.path.dirname(project_dir),
        f"{os.path.basename(project_dir)}-{slug}",
    )

    subprocess.run(['git', '-C', repo_path, 'worktree', 'add', worktree],
                   check=True, capture_output=True)

    env = os.environ.copy()
    env['KANBAN_MODEL']    = env.get('KANBAN_MODEL', 'sonnet')
    env['KANBAN_HEADLESS'] = '1'

    log_f = open(st['log_path'], 'w')
    cmd = [
        os.path.expanduser('~/projects/renan/agent-tools/scripts/kanban-run-task.sh'),
        tid, slug, issue_path, status_dir, base_branch,
    ]
    proc = subprocess.Popen(
        cmd, cwd=worktree, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
        start_new_session=True,
    )

    with state_lock:
        st['status']     = 'RUNNING'
        st['started_at'] = time.time()
        st['proc']       = proc
        st['worktree']   = worktree

    def tail():
        try:
            for line in proc.stdout:
                if shutdown.is_set():
                    break
                log_f.write(line)
                log_f.flush()
                clean = line.rstrip()
                if clean:
                    with state_lock:
                        st['last_line'] = clean[:200]
        finally:
            log_f.close()

    threading.Thread(target=tail, daemon=True).start()


def check_completions():
    for tid, st in task_state.items():
        if st['status'] != 'RUNNING':
            continue
        proc = st['proc']
        if proc.poll() is None:
            continue

        done_marker   = os.path.join(status_dir, f"{tid}.done")
        failed_marker = os.path.join(status_dir, f"{tid}.failed")

        if os.path.exists(done_marker):
            new_status = 'DONE'
        else:
            new_status = 'FAILED'
            if not os.path.exists(failed_marker):
                open(failed_marker, 'w').close()

        with state_lock:
            st['status']   = new_status
            st['ended_at'] = time.time()
            st['proc']     = None
        cleanup_worktree(tid)


def try_spawn_unblocked():
    for tid in sorted(tasks.keys()):
        st = task_state[tid]
        if st['status'] != 'PENDING':
            continue
        if has_failed_blocker(tid):
            with state_lock:
                st['status'] = 'SKIPPED'
            continue
        if is_unblocked(tid):
            spawn_task(tid)


def all_settled():
    return all(
        st['status'] in ('DONE', 'FAILED', 'SKIPPED')
        for st in task_state.values()
    )


def reparse_deps():
    """Re-run kanban-parse-deps.py and return new tasks not yet tracked."""
    try:
        result = subprocess.run(
            [sys.executable, PARSER_SCRIPT, issues_dir],
            capture_output=True, text=True, check=True, timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"[kanban] deps re-parse error: {e}", flush=True)
        return {}

    new_deps = json.loads(result.stdout)
    new_tasks = {}
    for tid, info in new_deps['tasks'].items():
        if tid in known_ids:
            continue
        # Double-check not already .done.md (edge case)
        done_path = os.path.join(issues_dir, tid + '.done.md')
        if os.path.exists(done_path):
            known_ids.add(tid)
            continue
        new_tasks[tid] = info
    return new_tasks


def add_new_tasks(new_tasks):
    """Add newly discovered tasks to task_state and global tasks dict."""
    for tid, info in new_tasks.items():
        task_state[tid] = {
            'slug':       info['slug'],
            'blockers':   info['blockers'],
            'status':     'PENDING',
            'started_at': None,
            'ended_at':   None,
            'log_path':   os.path.join(status_dir, f"{tid}.log"),
            'last_line':  '',
            'proc':       None,
            'worktree':   None,
        }
        tasks[tid] = info
        known_ids.add(tid)


def fmt_elapsed(seconds):
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}h{m:02d}m"
    return f"{m:d}m{s:02d}s"


STATUS_STYLE = {
    'PENDING': ('grey50', '·'),
    'RUNNING': ('yellow', '⚙'),
    'DONE':    ('green',  '✓'),
    'FAILED':  ('red',    '✗'),
    'SKIPPED': ('grey50', '⊘'),
}


def task_time(st):
    if st['status'] == 'RUNNING' and st['started_at']:
        return fmt_elapsed(time.time() - st['started_at'])
    if st['ended_at'] and st['started_at']:
        return fmt_elapsed(st['ended_at'] - st['started_at'])
    return '-'


def counts():
    c = {k: 0 for k in STATUS_STYLE}
    for st in task_state.values():
        c[st['status']] += 1
    return c


def render_table(watching=False):
    c       = counts()
    elapsed = fmt_elapsed(time.time() - start_time)
    width   = shutil.get_terminal_size((120, 30)).columns
    last_w  = max(20, width - 60)

    mode_tag = "watching" if watching else "headless"
    title = (f"kanban ({mode_tag})  elapsed {elapsed}  "
             f"[green]✓ {c['DONE']}[/]  "
             f"[yellow]⚙ {c['RUNNING']}[/]  "
             f"· {c['PENDING']}  "
             f"[red]✗ {c['FAILED']}[/]  "
             f"⊘ {c['SKIPPED']}")

    t = Table(title=title, expand=True, show_lines=False, pad_edge=False)
    t.add_column("", width=2)
    t.add_column("ID", width=4)
    t.add_column("Task", overflow="ellipsis", no_wrap=True)
    t.add_column("Status", width=8)
    t.add_column("Time", width=8, justify="right")
    t.add_column("Latest", overflow="ellipsis", no_wrap=True, max_width=last_w)

    with state_lock:
        for tid in sorted(tasks.keys()):
            st = task_state[tid]
            style, icon = STATUS_STYLE[st['status']]
            t.add_row(
                f"[{style}]{icon}[/]",
                tid,
                st['slug'],
                f"[{style}]{st['status']}[/]",
                task_time(st),
                st['last_line'],
            )
    return t


def render_plain(watching=False):
    c       = counts()
    elapsed = fmt_elapsed(time.time() - start_time)
    width   = shutil.get_terminal_size((120, 30)).columns
    mode_tag = "watching" if watching else "headless"
    out = [
        "\033[2J\033[H",
        f"kanban ({mode_tag})  elapsed={elapsed}  "
        f"done={c['DONE']} run={c['RUNNING']} pend={c['PENDING']} "
        f"fail={c['FAILED']} skip={c['SKIPPED']}",
        "-" * min(width, 120),
    ]
    last_w = max(20, width - 70)
    with state_lock:
        for tid in sorted(tasks.keys()):
            st = task_state[tid]
            _, icon = STATUS_STYLE[st['status']]
            out.append(
                f"{icon} {tid} {st['slug'][:40]:<40} "
                f"{st['status']:<8} {task_time(st):>7}  "
                f"{st['last_line'][:last_w]}"
            )
    return "\n".join(out)


def shutdown_handler(signum, frame):
    if shutdown.is_set():
        return
    shutdown.set()
    print("\n[kanban] interrupted — terminating running tasks…", flush=True)
    for tid, st in task_state.items():
        if st['proc'] and st['proc'].poll() is None:
            try:
                os.killpg(os.getpgid(st['proc'].pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.time() + 10
    for st in task_state.values():
        if st['proc']:
            remaining = max(0, deadline - time.time())
            try:
                st['proc'].wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(st['proc'].pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
    for tid in list(task_state):
        cleanup_worktree(tid)
    sys.exit(130)


signal.signal(signal.SIGINT,  shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)


def scheduling_loop(live=None, plain_mode=False):
    """Run scheduling loop until all tasks settle or shutdown."""
    if live:
        while not all_settled() and not shutdown.is_set():
            time.sleep(0.25)
            check_completions()
            try_spawn_unblocked()
            live.update(render_table(watching=False))
        live.update(render_table(watching=False))
    else:
        while not all_settled() and not shutdown.is_set():
            check_completions()
            try_spawn_unblocked()
            sys.stdout.write(render_plain(watching=False) + "\n")
            sys.stdout.flush()
            time.sleep(0.5)
        sys.stdout.write(render_plain(watching=False) + "\n")


def watch_loop(live=None, plain_mode=False):
    """After initial batch settles, watch for new .backlog.md files."""
    while not shutdown.is_set():
        # Before sleeping, check if any RUNNING tasks completed
        check_completions()

        # Re-parse for new issues
        new_tasks = reparse_deps()
        if new_tasks:
            add_new_tasks(new_tasks)
            print(f"[kanban] ✦ {len(new_tasks)} new issue(s) detected", flush=True)

        # Try to spawn any newly unblocked tasks
        try_spawn_unblocked()

        # Re-check all .backlog.md tasks — their blockers may now be met
        # even without new tasks (e.g. a just-completed task unblocked something)
        recheck_pending_backlog()

        # Update dashboard
        if live:
            live.update(render_table(watching=True))
        elif plain_mode:
            sys.stdout.write(render_plain(watching=True) + "\n")
            sys.stdout.flush()

        if shutdown.is_set():
            break

        time.sleep(poll_seconds)


def recheck_pending_backlog():
    """Check if any PENDING tasks became unblocked (without new issues arriving).

    This is needed when a task completes and its completion unblocks an existing
    .backlog.md issue that was already in the task graph.
    """
    for tid in sorted(tasks.keys()):
        st = task_state[tid]
        if st['status'] != 'PENDING':
            continue
        if has_failed_blocker(tid):
            with state_lock:
                st['status'] = 'SKIPPED'
            continue
        if is_unblocked(tid):
            # Task is unblocked but not yet spawned — spawn it
            spawn_task(tid)


def run_loop():
    # Phase 1: schedule and run all existing issues
    try_spawn_unblocked()

    if RICH:
        console = Console()
        with Live(render_table(watching=False), console=console,
                  refresh_per_second=4, screen=False) as live:
            scheduling_loop(live=live)

            if watch_mode and not shutdown.is_set():
                print(f"\n[kanban] initial batch settled — entering watch mode (poll every {poll_seconds}s)", flush=True)
                watch_loop(live=live)
    else:
        scheduling_loop(plain_mode=True)

        if watch_mode and not shutdown.is_set():
            print(f"\n[kanban] initial batch settled — entering watch mode (poll every {poll_seconds}s)", flush=True)
            watch_loop(plain_mode=True)

    if not watch_mode:
        c = counts()
        elapsed = fmt_elapsed(time.time() - start_time)
        print(
            f"\n[kanban] settled in {elapsed}  "
            f"done={c['DONE']} failed={c['FAILED']} skipped={c['SKIPPED']}",
            flush=True,
        )
        print(f"[kanban] logs: {status_dir}", flush=True)
        sys.exit(0 if c['FAILED'] == 0 and c['SKIPPED'] == 0 else 1)
    else:
        # In watch mode, we never exit normally
        c = counts()
        print(
            f"\n[kanban] settled in {fmt_elapsed(time.time() - start_time)} — "
            f"done={c['DONE']} failed={c['FAILED']} skipped={c['SKIPPED']} — "
            f"watching for new issues… (Ctrl+C to exit)",
            flush=True,
        )


if __name__ == '__main__':
    run_loop()
