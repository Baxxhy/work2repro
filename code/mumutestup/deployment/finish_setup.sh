#!/usr/bin/env bash
set -euo pipefail
source /root/Baxxhy/work2/reproductions/mumutestup/deployment/runtime.sh
exec 9>"$MUMU_ROOT/.setup.lock"
flock -n 9 || exit 1
# Wait for the already-running clone/install. Never start duplicate downloads.
while kill -0 2576542 2>/dev/null; do sleep 5; done
test -f "$MUMU_ROOT/upstream/requirements.txt"
python3 "$MUMU_ROOT/deployment/patch_upstream.py" "$MUMU_ROOT/upstream"
python3 "$MUMU_ROOT/deployment/prepare_repos.py" > "$MUMU_ROOT/logs/repository-preparation.log" 2>&1 &
repo_pid=$!
echo REPOSITORY_PREPARATION_PID=$repo_pid
while kill -0 2577524 2>/dev/null; do sleep 5; done
"$MUMU_ROOT/.venv/bin/python" -m pip check
nohup "$MUMU_ROOT/.venv/bin/python" "$MUMU_ROOT/deployment/embedding_server.py" > "$MUMU_ROOT/logs/embedding-server.log" 2>&1 < /dev/null &
echo $! > "$MUMU_ROOT/embedding.pid"
echo EMBEDDING_PID=$(cat "$MUMU_ROOT/embedding.pid")
wait "$repo_pid"
echo SETUP_COMPLETE
