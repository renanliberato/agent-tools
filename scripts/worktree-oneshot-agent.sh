#!/usr/bin/env bash

orig_dir="$(pwd)"

git worktree add "../$1"
cd "../$1" || return

$2

cd "$orig_dir" || return
git worktree remove "../$1" -f

git branch -D "$1"
