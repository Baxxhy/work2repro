#!/usr/bin/env bash
set -euo pipefail
source /root/Baxxhy/work2/reproductions/testupdater/deployment/runtime.sh
exec python -u /root/Baxxhy/work2/reproductions/testsyncer/deployment/run_testsyncer.py "$@"
