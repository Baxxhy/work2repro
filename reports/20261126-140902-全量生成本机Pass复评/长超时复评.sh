#!/bin/bash
set -eu
umask 077
base="$HOME/reeval/medium-th-2051-20261126-140902"
. "$HOME/venv/bin/activate"
export DOCKER_HOST="unix://$XDG_RUNTIME_DIR/docker.sock"
export TMPDIR="$XDG_RUNTIME_DIR/req2test-temp"
mkdir -p "$TMPDIR"
export R2T_EXTENDED_TIMEOUTS=20261117-v1
export PYTHONPATH="$base/timeouts:$HOME/repo/benchmark"
evaluate_project() (
    p=$1
    workers=$2
    run="medium-local-exec-20261126-140902-$p"
    exec 9>"$base/logs/$p.long.lock"
    flock 9
    results="$HOME/.req2test/runs/$run"
    if test -s "$results/summary.json" && test -s "$results/$p/th/instances.jsonl"; then
        echo 0 > "$base/logs/$p.exit"
        exit 0
    fi
    for attempt in 1 2 3; do
        log="$base/logs/$p-long-$(date +%s).log"
        echo "$log" > "$base/logs/$p.current"
        if req2test evaluate --predictions "$base/input/$p.jsonl" --split eval --view th --project "$p" --run-id "$run" --metrics exec --workers "$workers" --docker-host "$DOCKER_HOST" >"$log" 2>&1; then
            echo 0 > "$base/logs/$p.exit"
            exit 0
        else
            rc=$?
        fi
        nonce=$(sed -n "s/^retire it with: req2test env down --project $p --nonce \([a-zA-Z0-9]*\)$/\1/p" "$log" | tail -1)
        if [[ -n "$nonce" ]]; then req2test env down --project "$p" --nonce "$nonce" >>"$log" 2>&1 || break; fi
        workers=$(( (workers + 1) / 2 ))
        sleep 5
    done
    echo "$rc" > "$base/logs/$p.exit"
    exit "$rc"
)
status=0
while (( $# )); do
    evaluate_project "$1" "$2" || status=1
    shift 2
done
exit "$status"
