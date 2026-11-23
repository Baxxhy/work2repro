#!/bin/bash
set -eu
: "${1:?diagnostic directory required}"
work=$1
h=/root/lby-docker/req2test/user
run="$h/benchmark/runs/r2t-di-20261123-102902-fixed-coreshop"
while [ ! -s "$run/coreshop/th/instances.jsonl" ]; do sleep 8; done
exec nsenter -t "$(systemctl show user@1001.service -p MainPID --value)" -m -- runuser -u r2tbench -- env HOME="$h" REQ2TEST_HOME="$h/benchmark" XDG_RUNTIME_DIR=/run/user/1001 PATH="/root/lby-docker/req2test/tools:$h/venv/bin:/usr/bin:/bin" "$h/venv/bin/python" "$work/replay_diagnostic.py" typed coreshop
