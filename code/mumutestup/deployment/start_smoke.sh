#!/usr/bin/env bash
set -euo pipefail
source /root/Baxxhy/work2/reproductions/mumutestup/deployment/runtime.sh
for attempt in $(seq 1 240); do
  if curl --noproxy '*' -fsS --max-time 3 http://127.0.0.1:8000/health >/dev/null && curl --noproxy '*' -fsS --max-time 3 http://127.0.0.1:8001/health >/dev/null; then
    exec python "$MUMU_ROOT/deployment/run_mumu.py" --upstream "$MUMU_ROOT/upstream" --output "$MUMU_ROOT/runs/smoke-ormlite-20261030" --project j256/ormlite-core --sample-index 0 --workers 1
  fi
  sleep 5
done
echo 'Model services did not become healthy within 20 minutes' >&2
exit 1
