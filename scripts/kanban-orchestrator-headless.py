#!/usr/bin/env python3
"""Headless kanban orchestrator. Spawns tasks in parallel without cmux,
streams status to a live-updating CLI dashboard."""
import sys, os, json, subprocess, time, threading, signal, shutil
from datetime import datetime

try:
    from rich.live import Live
    from rich.table import Table
    from rich.console import Console
    RICH = True
except ImportError:
    RICH = False

issues_dir  = sys.argv[1]
project_dir = sys.argv[2]
status_dir  = sys.argv[3]

deps  = json.load(open(os.path.join(status_dir, 'deps.json')))
tasks = deps['tasks']

start_time = time.time()
state_lock = threading.Lock()
shutdown   = threading.Event()

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


def has_failed_blocker(tid):
    for b in task_state[tid]['blockers']:
        if task_state[b]['status'] in ('FAILED', 'SKIPPED'):
            return True
        if has_failed_blocker(b):
            return True
    return False


def is_unblocked(tid):
    return all(task_state[b]['status'] == 'DONE' for b in task_state[tid]['blockers'])


def get_base_branch():
    return subprocess.run(
        ['git', '-C', project_dir, 'rev-parse', '--abbrev-ref', 'HEAD'],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def cleanup_worktree(tid):
    wt = task_state[tid]['worktree']
    if not wt:
        return
    branch = os.path.basename(wt)
    subprocess.run(['git', '-C', project_dir, 'worktree', 'remove', '--force', wt],
                   check=False, capture_output=True)
    subprocess.run(['git', '-C', project_dir, 'branch', '-D', branch],
                   check=False, capture_output=True)
    task_state[tid]['worktree'] = None


def spawn_task(tid):
    st         = task_state[tid]
    slug       = st['slug']
    issue_path = os.path.join(issues_dir, slug + '.md')
    worktree   = os.path.join(
        os.path.dirname(project_dir),
        f"{os.path.basename(project_dir)}-{slug}",
    )

    base_branch = get_base_branch()
    subprocess.run(['git', '-C', project_dir, 'worktree', 'add', worktree],
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


def render_table():
    c       = counts()
    elapsed = fmt_elapsed(time.time() - start_time)
    width   = shutil.get_terminal_size((120, 30)).columns
    last_w  = max(20, width - 60)

    title = (f"kanban (headless)  elapsed {elapsed}  "
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


def render_plain():
    c       = counts()
    elapsed = fmt_elapsed(time.time() - start_time)
    width   = shutil.get_terminal_size((120, 30)).columns
    out = [
        "\033[2J\033[H",
        f"kanban (headless)  elapsed={elapsed}  "
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


def run_loop():
    try_spawn_unblocked()
    if RICH:
        console = Console()
        with Live(render_table(), console=console,
                  refresh_per_second=4, screen=False) as live:
            while not all_settled() and not shutdown.is_set():
                time.sleep(0.25)
                check_completions()
                try_spawn_unblocked()
                live.update(render_table())
            live.update(render_table())
    else:
        while not all_settled() and not shutdown.is_set():
            check_completions()
            try_spawn_unblocked()
            sys.stdout.write(render_plain() + "\n")
            sys.stdout.flush()
            time.sleep(0.5)
        sys.stdout.write(render_plain() + "\n")


if __name__ == '__main__':
    run_loop()
    c = counts()
    elapsed = fmt_elapsed(time.time() - start_time)
    print(
        f"\n[kanban] settled in {elapsed}  "
        f"done={c['DONE']} failed={c['FAILED']} skipped={c['SKIPPED']}",
        flush=True,
    )
    print(f"[kanban] logs: {status_dir}", flush=True)
    sys.exit(0 if c['FAILED'] == 0 and c['SKIPPED'] == 0 else 1)
