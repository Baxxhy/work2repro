#!/usr/bin/env bash
set -euo pipefail
export MUMU_LUNA_OUTPUT="${MUMU_LUNA_OUTPUT:-/root/Baxxhy/work2/reproductions/mumutestup/runs/luna571-20261104}"
source /root/Baxxhy/work2/reproductions/mumutestup/deployment/runtime-luna.sh
if [[ -e "$MUMU_LUNA_OUTPUT/status.json" ]]; then
    echo 'Existing run found; refusing to overwrite.' >&2
    exit 2
fi
mkdir -p "$MUMU_LUNA_OUTPUT/runtime-sources"
cp "$MUMU_ROOT/deployment/"{run_mumu.py,run_mumu_luna.py,codex_luna_bridge.py,runtime-luna.sh,start_luna_full.sh} "$MUMU_LUNA_OUTPUT/runtime-sources/"
python "$MUMU_ROOT/deployment/warm_luna_bridge.py"
python "$MUMU_ROOT/deployment/run_mumu_luna.py" --upstream "$MUMU_LUNA_UPSTREAM" --output "$MUMU_LUNA_OUTPUT" --workers 10 --preflight-only
exec python -u "$MUMU_ROOT/deployment/run_mumu_luna.py" --upstream "$MUMU_LUNA_UPSTREAM" --output "$MUMU_LUNA_OUTPUT" --workers 10
