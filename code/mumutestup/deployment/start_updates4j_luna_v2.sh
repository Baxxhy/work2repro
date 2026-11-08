#!/usr/bin/env bash
set -euo pipefail
export MUMU_LUNA_OUTPUT=/root/Baxxhy/work2/reproductions/mumutestup/runs/updates4j-luna-v2-20261106
export MUMU_LUNA_BRIDGE_URL=http://127.0.0.1:8013/v1
source /root/Baxxhy/work2/reproductions/mumutestup/deployment/runtime-luna.sh
export MUMU_REPOS_DIR=/root/Baxxhy/work2/reproductions/testupdater/repos
exec python -u "$MUMU_ROOT/deployment/run_mumu_luna.py" --upstream "$MUMU_LUNA_UPSTREAM" --dataset-root "$MUMU_ROOT/datasets/updates4j" --output "$MUMU_LUNA_OUTPUT" --workers 7 --resume
