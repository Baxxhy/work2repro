#!/usr/bin/env bash
set -euo pipefail
# Run in the normal SSH login environment. Do not source runtime-luna.sh here:
# the model service uses the working Codex login/network configuration, while
# MuMu's Python clients have a local API URL pointing back at this service.
mumu_root=/root/Baxxhy/work2/reproductions/mumutestup
luna_output="${MUMU_LUNA_OUTPUT:-$mumu_root/runs/luna20-20261104}"
mkdir -p "$luna_output"
if [[ -e "$luna_output/bridge.pid" || -e "$luna_output/bridge-fatal.json" ]]; then
    echo "Inspect the existing bridge before restarting: $luna_output" >&2
    exit 2
fi
nohup "$mumu_root/.venv/bin/python" -u "$mumu_root/deployment/codex_luna_bridge.py" \
    --port 8012 --work-dir /tmp/mumutestup-luna-text-workspace \
    --audit-file "$luna_output/bridge-audit.jsonl" \
    --fatal-file "$luna_output/bridge-fatal.json" \
    --concurrency "${MUMU_LUNA_CONCURRENCY:-2}" --timeout 600 \
    > "$luna_output/bridge.log" 2>&1 < /dev/null &
bridge_pid=$!
printf '%s\n' "$bridge_pid" > "$luna_output/bridge.pid"
printf 'bridge_pid=%s\n' "$bridge_pid"
