#!/usr/bin/env python3
"""Parse an issues directory into a deps.json for the kanban orchestrator.
Reads all <ID>-<slug>.<state>.md files from given directory.

State suffix: .backlog.md (not started), .active.md (in progress), .done.md (done).
Orchestrator picks up .active.md and optionally .backlog.md for scheduling.
"""
import sys, os, re, json

issues_dir = sys.argv[1]
tasks = {}

for fname in sorted(os.listdir(issues_dir)):
    if not fname.endswith('.md'):
        continue
    # Match: <id>-<slug>.<state>.md or <id>-<slug>.md (legacy)
    m = re.match(r'^([^/]+)\.(backlog|active|done)\.md$', fname)
    legacy = re.match(r'^([^/]+)\.md$', fname)
    if m:
        task_id = m.group(1)        # e.g. "000042-add-login"
        state = m.group(2)
        slug = task_id
    elif legacy:
        task_id = legacy.group(1)
        state = 'unknown'
        slug = task_id
    else:
        continue

    # Only schedule non-done items
    if state == 'done':
        continue

    content = open(os.path.join(issues_dir, fname)).read()

    blockers = []
    in_blocked = False
    for line in content.splitlines():
        if line.strip() == '## Blocked by':
            in_blocked = True
            continue
        if in_blocked:
            if line.startswith('##'):
                break
            # Match any [blah.md] markdown link — extracts the full stem as blocker id
            bm = re.search(r'\[([^\]]+)\.md\]', line)
            if bm:
                blockers.append(bm.group(1))
            # Also match bare ID references like "000042" or "000042-add-login"
            bare = re.search(r'\b(\d{6})(?:\b|-)', line)
            if bare and not any(b.startswith(bare.group(1)) for b in blockers):
                blockers.append(bare.group(1))

    tasks[task_id] = {'slug': slug, 'blockers': blockers, 'state': state}

print(json.dumps({'tasks': tasks}, indent=2))
