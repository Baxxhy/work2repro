#!/usr/bin/env bash
set -euo pipefail
source /root/Baxxhy/work2/reproductions/testupdater/deployment/runtime.sh
exec python -u "$TU_ROOT/deployment/run_testupdater.py" "$@"
