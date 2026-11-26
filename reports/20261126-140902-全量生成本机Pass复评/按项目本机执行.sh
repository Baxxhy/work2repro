#!/bin/bash
set -u
umask 077
base="$HOME/reeval/medium-th-2051-20261126-140902"
while (( $# )); do
  p=$1
  workers=$2
  shift 2
  run="medium-local-exec-20261126-140902-$p"
  "$HOME/req2test-local" evaluate --predictions "$base/input/$p.jsonl" --split eval --view th --project "$p" --run-id "$run" --metrics exec --workers "$workers" >> "$base/logs/$p.log" 2>&1
  rc=$?
  printf '%s\n' "$rc" > "$base/logs/$p.exit"
done
