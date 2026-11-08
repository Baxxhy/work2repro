#!/usr/bin/env bash
set -euo pipefail
export MUMU_LUNA_OUTPUT=/root/Baxxhy/work2/reproductions/comparison/metrics-20261108
source /root/Baxxhy/work2/reproductions/mumutestup/deployment/runtime-luna.sh
export PYTHONPATH=/root/Baxxhy/work2/reproductions/mumutestup/deployment/updates4j_environment
export MUMU_LOGS_DIR="$MUMU_LUNA_OUTPUT/logs"
export MUMU_REPORTS_DIR="$MUMU_LUNA_OUTPUT/reports"
exec python -u /root/Baxxhy/work2/reproductions/comparison/evaluate_metrics.py "$@"
