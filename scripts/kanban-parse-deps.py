#!/usr/bin/env python3
"""Parse an issues directory into a deps.json for the kanban orchestrator."""
import sys, os, re, json

issues_dir = sys.argv[1]
tasks = {}

for fname in sorted(os.listdir(issues_dir)):
    if not fname.endswith('.md'):
        continue
    m = re.match(r'^(\d+)-(.+)\.md$', fname)
    if not m:
        continue
    task_id = m.group(1)
    slug = fname[:-3]

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
            bm = re.search(r'\[(\d+)-[^\]]+\.md\]', line)
            if bm:
                blockers.append(bm.group(1))

    tasks[task_id] = {'slug': slug, 'blockers': blockers}

print(json.dumps({'tasks': tasks}, indent=2))
